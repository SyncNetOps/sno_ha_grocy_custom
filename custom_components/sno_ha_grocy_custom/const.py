"""Konstanten für die SNO-HA_Grocy-custom Integration V4.1."""
import logging

DOMAIN = "sno_ha_grocy_custom"
LOGGER = logging.getLogger(__package__)

CONF_URL = "url"
CONF_API_KEY = "api_key"

UPDATE_INTERVAL = 60 # Polling-Intervall in Sekunden

# Options-Keys
CONF_MODE_TASKS = "mode_tasks"
CONF_MODE_CHORES = "mode_chores"
CONF_MODE_SHOPPING = "mode_shopping"
CONF_ADVANCED_STATS = "advanced_stats" # NEU in V4.1

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