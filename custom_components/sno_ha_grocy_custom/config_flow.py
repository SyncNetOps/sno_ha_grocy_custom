"""Config Flow & Options Flow für Grocy (V2.0 Multi-Step Fix)."""
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
)

from .api import GrocyApiClient
from .const import (
    DOMAIN, CONF_URL, CONF_API_KEY, LOGGER,
    CONF_MODE_TASKS, CONF_MODE_CHORES, CONF_MODE_SHOPPING,
    CONF_ADVANCED_STATS, MODE_NONE, MODE_SENSOR, MODE_TODO, MODE_BOTH,
    CONF_ENABLE_AI, CONF_GEMINI_API_KEY, CONF_AI_AUTO_CREATE, CONF_AI_SYNC_SHOPPING, CONF_AI_PRODUCT_GROUP, CONF_AI_DEFAULT_QU,
    CONF_ENABLE_COOKIDOO, CONF_COOKIDOO_EMAIL, CONF_COOKIDOO_PASSWORD, CONF_COOKIDOO_LOCALE, COOKIDOO_LOCALES
)

def get_select_schema():
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(value=MODE_NONE, label="Deaktiviert"),
                SelectOptionDict(value=MODE_SENSOR, label="Nur Sensoren"),
                SelectOptionDict(value=MODE_TODO, label="Nur Interaktive Todo-Liste"),
                SelectOptionDict(value=MODE_BOTH, label="Beides (Sensoren & Todo-Liste)"),
            ],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )

class GrocyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self):
        self._setup_data = {}
        self._client = None
        self._groups = [{"value": "0", "label": "Keine (Root)"}]
        self._units = [{"value": "1", "label": "Stück"}]

    async def async_step_user(self, user_input=None):
        """Schritt 1: Grocy Basis & URL"""
        errors = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            self._client = GrocyApiClient(user_input[CONF_URL], user_input[CONF_API_KEY], session)
            try:
                await self._client.test_connection()
                self._setup_data.update(user_input)
                return await self.async_step_ai_setup()
            except Exception:
                errors["base"] = "cannot_connect"

        schema = vol.Schema({
            vol.Required(CONF_URL, default="http://DEINE-GROCY-IP"): str,
            vol.Required(CONF_API_KEY): str,
            vol.Required(CONF_MODE_TASKS, default=MODE_BOTH): get_select_schema(),
            vol.Required(CONF_MODE_CHORES, default=MODE_BOTH): get_select_schema(),
            vol.Required(CONF_MODE_SHOPPING, default=MODE_BOTH): get_select_schema(),
            vol.Required(CONF_ADVANCED_STATS, default=False): bool
        })
        # last_step=False zwingt den "Weiter" Button zu erscheinen!
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors, last_step=False)

    async def async_step_ai_setup(self, user_input=None):
        """Schritt 2: KI Setup"""
        if user_input is not None:
            self._setup_data.update(user_input)
            return await self.async_step_cookidoo_setup()

        # Versuche dynamisch Gruppen und Einheiten von Grocy zu laden
        if self._client:
            try:
                grps = await self._client.async_get_product_groups()
                if grps and isinstance(grps, list): 
                    self._groups = [{"value": str(g["id"]), "label": g.get("name", "Unbekannt")} for g in grps]
                unts = await self._client.async_get_quantity_units()
                if unts and isinstance(unts, list): 
                    self._units = [{"value": str(u["id"]), "label": u.get("name", "Unbekannt")} for u in unts]
            except Exception as e:
                LOGGER.error(f"Fehler beim Laden von Grocy Dropdowns: {e}")

        # Normale bool-Typen für sauberes Mapping in der de.json
        schema = vol.Schema({
            vol.Required(CONF_ENABLE_AI, default=False): bool,
            vol.Optional(CONF_GEMINI_API_KEY, default=""): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Required(CONF_AI_AUTO_CREATE, default=False): bool,
            vol.Required(CONF_AI_SYNC_SHOPPING, default=False): bool,
            vol.Optional(CONF_AI_PRODUCT_GROUP, default="0"): SelectSelector(SelectSelectorConfig(options=self._groups, mode=SelectSelectorMode.DROPDOWN)),
            vol.Optional(CONF_AI_DEFAULT_QU, default="1"): SelectSelector(SelectSelectorConfig(options=self._units, mode=SelectSelectorMode.DROPDOWN))
        })
        return self.async_show_form(step_id="ai_setup", data_schema=schema, last_step=False)

    async def async_step_cookidoo_setup(self, user_input=None):
        """Schritt 3: Cookidoo Setup"""
        errors = {}
        if user_input is not None:
            if user_input.get(CONF_ENABLE_COOKIDOO):
                email = user_input.get(CONF_COOKIDOO_EMAIL)
                pwd = user_input.get(CONF_COOKIDOO_PASSWORD)
                loc = user_input.get(CONF_COOKIDOO_LOCALE, "de-DE")
                if email and pwd:
                    try:
                        from cookidoo_api import Cookidoo 
                        cookidoo = Cookidoo(email, pwd, loc)
                        await cookidoo.login()
                    except Exception as e:
                        LOGGER.error(f"Cookidoo Login Test fehlgeschlagen: {e}")
                        errors["base"] = "cookidoo_auth_failed"
            
            if not errors:
                self._setup_data.update(user_input)
                return self.async_create_entry(title="SNO-HA Grocy", data=self._setup_data)

        locales = [SelectOptionDict(value=l, label=l) for l in COOKIDOO_LOCALES]
        schema = vol.Schema({
            vol.Required(CONF_ENABLE_COOKIDOO, default=False): bool,
            vol.Optional(CONF_COOKIDOO_EMAIL, default=""): str,
            vol.Optional(CONF_COOKIDOO_PASSWORD, default=""): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Optional(CONF_COOKIDOO_LOCALE, default="de-DE"): SelectSelector(SelectSelectorConfig(options=locales, mode=SelectSelectorMode.DROPDOWN))
        })
        return self.async_show_form(step_id="cookidoo_setup", data_schema=schema, errors=errors, last_step=True)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return GrocyOptionsFlow(config_entry)


class GrocyOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry
        self._options = dict(config_entry.options)
        if not self._options:
            self._options = dict(config_entry.data)
        self._client = None
        self._groups = [{"value": "0", "label": "Keine (Root)"}]
        self._units = [{"value": "1", "label": "Stück"}]

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            self._options.update(user_input)
            session = async_get_clientsession(self.hass)
            self._client = GrocyApiClient(self.config_entry.data[CONF_URL], self.config_entry.data[CONF_API_KEY], session)
            return await self.async_step_ai_setup()

        schema = vol.Schema({
            vol.Required(CONF_MODE_TASKS, default=self._options.get(CONF_MODE_TASKS, MODE_BOTH)): get_select_schema(),
            vol.Required(CONF_MODE_CHORES, default=self._options.get(CONF_MODE_CHORES, MODE_BOTH)): get_select_schema(),
            vol.Required(CONF_MODE_SHOPPING, default=self._options.get(CONF_MODE_SHOPPING, MODE_BOTH)): get_select_schema(),
            vol.Required(CONF_ADVANCED_STATS, default=self._options.get(CONF_ADVANCED_STATS, False)): bool
        })
        return self.async_show_form(step_id="init", data_schema=schema, last_step=False)

    async def async_step_ai_setup(self, user_input=None):
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_cookidoo_setup()

        if self._client:
            try:
                grps = await self._client.async_get_product_groups()
                if grps and isinstance(grps, list): 
                    self._groups = [{"value": str(g["id"]), "label": g.get("name", "Unbekannt")} for g in grps]
                unts = await self._client.async_get_quantity_units()
                if unts and isinstance(unts, list): 
                    self._units = [{"value": str(u["id"]), "label": u.get("name", "Unbekannt")} for u in unts]
            except Exception as e:
                LOGGER.error(f"Fehler beim Laden von Grocy Dropdowns in Options: {e}")

        schema = vol.Schema({
            vol.Required(CONF_ENABLE_AI, default=self._options.get(CONF_ENABLE_AI, False)): bool,
            vol.Optional(CONF_GEMINI_API_KEY, default=self._options.get(CONF_GEMINI_API_KEY, "")): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Required(CONF_AI_AUTO_CREATE, default=self._options.get(CONF_AI_AUTO_CREATE, False)): bool,
            vol.Required(CONF_AI_SYNC_SHOPPING, default=self._options.get(CONF_AI_SYNC_SHOPPING, False)): bool,
            vol.Optional(CONF_AI_PRODUCT_GROUP, default=self._options.get(CONF_AI_PRODUCT_GROUP, "0")): SelectSelector(SelectSelectorConfig(options=self._groups, mode=SelectSelectorMode.DROPDOWN)),
            vol.Optional(CONF_AI_DEFAULT_QU, default=self._options.get(CONF_AI_DEFAULT_QU, "1")): SelectSelector(SelectSelectorConfig(options=self._units, mode=SelectSelectorMode.DROPDOWN))
        })
        return self.async_show_form(step_id="ai_setup", data_schema=schema, last_step=False)

    async def async_step_cookidoo_setup(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input.get(CONF_ENABLE_COOKIDOO):
                email = user_input.get(CONF_COOKIDOO_EMAIL)
                pwd = user_input.get(CONF_COOKIDOO_PASSWORD)
                loc = user_input.get(CONF_COOKIDOO_LOCALE, "de-DE")
                if email and pwd:
                    try:
                        from cookidoo_api import Cookidoo 
                        cookidoo = Cookidoo(email, pwd, loc)
                        await cookidoo.login()
                    except Exception as e:
                        LOGGER.error(f"Cookidoo Login Test fehlgeschlagen: {e}")
                        errors["base"] = "cookidoo_auth_failed"
            
            if not errors:
                self._options.update(user_input)
                return self.async_create_entry(title="", data=self._options)

        locales = [SelectOptionDict(value=l, label=l) for l in COOKIDOO_LOCALES]
        schema = vol.Schema({
            vol.Required(CONF_ENABLE_COOKIDOO, default=self._options.get(CONF_ENABLE_COOKIDOO, False)): bool,
            vol.Optional(CONF_COOKIDOO_EMAIL, default=self._options.get(CONF_COOKIDOO_EMAIL, "")): str,
            vol.Optional(CONF_COOKIDOO_PASSWORD, default=self._options.get(CONF_COOKIDOO_PASSWORD, "")): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Optional(CONF_COOKIDOO_LOCALE, default=self._options.get(CONF_COOKIDOO_LOCALE, "de-DE")): SelectSelector(SelectSelectorConfig(options=locales, mode=SelectSelectorMode.DROPDOWN))
        })
        return self.async_show_form(step_id="cookidoo_setup", data_schema=schema, errors=errors, last_step=True)