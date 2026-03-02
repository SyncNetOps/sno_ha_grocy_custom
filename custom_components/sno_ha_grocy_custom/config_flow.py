"""Config Flow & Options Flow für Grocy V4.1."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SelectOptionDict,
)

from .api import GrocyApiClient
from .const import (
    DOMAIN, CONF_URL, CONF_API_KEY, LOGGER,
    CONF_MODE_TASKS, CONF_MODE_CHORES, CONF_MODE_SHOPPING,
    CONF_ADVANCED_STATS, MODE_NONE, MODE_SENSOR, MODE_TODO, MODE_BOTH
)

async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    session = async_get_clientsession(hass)
    client = GrocyApiClient(data[CONF_URL], data[CONF_API_KEY], session)
    await client.test_connection()
    return {"title": "SNO-HA_Grocy-custom"}

def get_select_schema():
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(value=MODE_NONE, label="Deaktiviert"),
                SelectOptionDict(value=MODE_SENSOR, label="Nur Sensoren"),
                SelectOptionDict(value=MODE_TODO, label="Nur To-Do Liste"),
                SelectOptionDict(value=MODE_BOTH, label="Beides (Sensoren & Liste)"),
            ],
            mode=SelectSelectorMode.DROPDOWN
        )
    )

class GrocyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except Exception as e:
                LOGGER.error("Verbindungstest fehlgeschlagen: %s", e)
                errors["base"] = "cannot_connect"

        schema = vol.Schema({
            vol.Required(CONF_URL, default="http://"): str,
            vol.Required(CONF_API_KEY): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return GrocyOptionsFlowHandler(config_entry)

class GrocyOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._cfg_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        entry = getattr(self, "config_entry", self._cfg_entry)
        options = entry.options
        select_ui = get_select_schema()

        schema = vol.Schema({
            vol.Required(CONF_MODE_TASKS, default=options.get(CONF_MODE_TASKS, MODE_BOTH)): select_ui,
            vol.Required(CONF_MODE_CHORES, default=options.get(CONF_MODE_CHORES, MODE_BOTH)): select_ui,
            vol.Required(CONF_MODE_SHOPPING, default=options.get(CONF_MODE_SHOPPING, MODE_BOTH)): select_ui,
            vol.Optional(CONF_ADVANCED_STATS, default=options.get(CONF_ADVANCED_STATS, False)): bool,
        })
        return self.async_show_form(step_id="init", data_schema=schema)