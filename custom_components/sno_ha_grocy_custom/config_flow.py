"""Config Flow & Options Flow für Grocy."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SelectOptionDict,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    BooleanSelector,
)

from .api import GrocyApiClient
from .const import (
    DOMAIN, CONF_URL, CONF_API_KEY, LOGGER,
    CONF_MODE_TASKS, CONF_MODE_CHORES, CONF_MODE_SHOPPING,
    CONF_ADVANCED_STATS, MODE_NONE, MODE_SENSOR, MODE_TODO, MODE_BOTH,
    CONF_ENABLE_AI, CONF_GEMINI_API_KEY, CONF_AI_AUTO_CREATE, CONF_AI_SYNC_SHOPPING, CONF_AI_PRODUCT_GROUP, CONF_AI_DEFAULT_QU,
    CONF_COOKIDOO_ENABLE, CONF_COOKIDOO_EMAIL, CONF_COOKIDOO_PASSWORD, CONF_COOKIDOO_LOCALE, COOKIDOO_LOCALES
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
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Startet den mehrstufigen Options Flow."""
        return await self.async_step_main()

    async def async_step_main(self, user_input=None):
        """Schritt 1: Grocy & KI Assistent Setup."""
        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_cookidoo()

        select_ui = get_select_schema()

        # Init Client für dynamische API-Abfragen
        session = async_get_clientsession(self.hass)
        client = GrocyApiClient(self._cfg_entry.data[CONF_URL], self._cfg_entry.data[CONF_API_KEY], session)
        
        # Dynamische Dropdowns füllen (Produktgruppen)
        try:
            product_groups = await client.async_get_product_groups()
            group_options = [SelectOptionDict(value="0", label="Keine Gruppe zuweisen")]
            for g in product_groups:
                group_options.append(SelectOptionDict(value=str(g.get("id")), label=g.get("name")))
        except Exception:
            group_options = [SelectOptionDict(value="0", label="Fehler beim Laden")]

        # Dynamische Dropdowns füllen (Einheiten)
        try:
            quantity_units = await client.async_get_quantity_units()
            qu_options = []
            for qu in quantity_units:
                qu_options.append(SelectOptionDict(value=str(qu.get("id")), label=qu.get("name")))
            if not qu_options:
                qu_options = [SelectOptionDict(value="1", label="1 (Keine Einheiten in Grocy gefunden)")]
        except Exception:
            qu_options = [SelectOptionDict(value="1", label="1 (Fehler beim Laden)")]

        schema = vol.Schema({
            vol.Required(CONF_MODE_TASKS, default=self.options.get(CONF_MODE_TASKS, MODE_BOTH)): select_ui,
            vol.Required(CONF_MODE_CHORES, default=self.options.get(CONF_MODE_CHORES, MODE_BOTH)): select_ui,
            vol.Required(CONF_MODE_SHOPPING, default=self.options.get(CONF_MODE_SHOPPING, MODE_BOTH)): select_ui,
            vol.Required(CONF_ADVANCED_STATS, default=self.options.get(CONF_ADVANCED_STATS, False)): BooleanSelector(),
            
            # KI Assistent Bereich
            vol.Required(CONF_ENABLE_AI, default=self.options.get(CONF_ENABLE_AI, False)): BooleanSelector(),
            vol.Optional(CONF_GEMINI_API_KEY, default=self.options.get(CONF_GEMINI_API_KEY, "")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_AI_AUTO_CREATE, default=self.options.get(CONF_AI_AUTO_CREATE, False)): BooleanSelector(),
            vol.Optional(CONF_AI_PRODUCT_GROUP, default=self.options.get(CONF_AI_PRODUCT_GROUP, "0")): SelectSelector(
                SelectSelectorConfig(options=group_options, mode=SelectSelectorMode.DROPDOWN)
            ),
            vol.Optional(CONF_AI_DEFAULT_QU, default=self.options.get(CONF_AI_DEFAULT_QU, qu_options[0]["value"])): SelectSelector(
                SelectSelectorConfig(options=qu_options, mode=SelectSelectorMode.DROPDOWN)
            ),
            vol.Required(CONF_AI_SYNC_SHOPPING, default=self.options.get(CONF_AI_SYNC_SHOPPING, False)): BooleanSelector(),
        })

        return self.async_show_form(step_id="main", data_schema=schema, last_step=False)

    async def async_step_cookidoo(self, user_input=None):
        """Schritt 2: Cookidoo Bridge Setup."""
        errors = {}
        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        schema = vol.Schema({
            vol.Required(CONF_COOKIDOO_ENABLE, default=self.options.get(CONF_COOKIDOO_ENABLE, False)): BooleanSelector(),
            vol.Optional(CONF_COOKIDOO_EMAIL, default=self.options.get(CONF_COOKIDOO_EMAIL, "")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.EMAIL)
            ),
            vol.Optional(CONF_COOKIDOO_PASSWORD, default=self.options.get(CONF_COOKIDOO_PASSWORD, "")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Optional(CONF_COOKIDOO_LOCALE, default=self.options.get(CONF_COOKIDOO_LOCALE, "de-DE")): SelectSelector(
                SelectSelectorConfig(options=COOKIDOO_LOCALES, mode=SelectSelectorMode.DROPDOWN)
            ),
        })

        return self.async_show_form(
            step_id="cookidoo",
            data_schema=schema,
            errors=errors,
            last_step=True
        )