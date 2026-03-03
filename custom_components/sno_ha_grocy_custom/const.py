"""Konstanten für die SNO-HA_Grocy-custom Integration."""
import logging

DOMAIN = "sno_ha_grocy_custom"
LOGGER = logging.getLogger(__package__)

CONF_URL = "url"
CONF_API_KEY = "api_key"

UPDATE_INTERVAL = 60 # Polling-Intervall in Sekunden

# Options-Keys für Plattformen
CONF_MODE_TASKS = "mode_tasks"
CONF_MODE_CHORES = "mode_chores"
CONF_MODE_SHOPPING = "mode_shopping"
CONF_ADVANCED_STATS = "advanced_stats" 

# --- KI & Rezept-Engine Optionen ---
CONF_ENABLE_AI = "enable_ai"
CONF_GEMINI_API_KEY = "gemini_api_key"
CONF_AI_AUTO_CREATE = "ai_auto_create"
CONF_AI_SYNC_SHOPPING = "ai_sync_shopping"
CONF_AI_PRODUCT_GROUP = "ai_product_group" 
CONF_AI_DEFAULT_QU = "ai_default_qu" # NEU: Standard Mengeneinheit Dropdown

MODE_NONE = "none"
MODE_SENSOR = "sensor"
MODE_TODO = "todo"
MODE_BOTH = "both"

MODE_OPTIONS = {
    MODE_NONE: "Deaktiviert",
    MODE_SENSOR: "Nur Sensoren",
    MODE_TODO: "Nur To-Do Liste",
    MODE_BOTH: "Beides (Sensoren & Liste)"
}