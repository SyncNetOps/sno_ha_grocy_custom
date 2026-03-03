"""Konstanten für die SNO-HA_Grocy-custom Integration V1.3.0."""
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

# KI & Rezept-Engine Optionen
CONF_ENABLE_AI = "enable_ai"
CONF_GEMINI_API_KEY = "gemini_api_key"
CONF_AI_AUTO_CREATE = "ai_auto_create"
CONF_AI_SYNC_SHOPPING = "ai_sync_shopping"
CONF_AI_PRODUCT_GROUP = "ai_product_group" 
CONF_AI_DEFAULT_QU = "ai_default_qu"

# --- NEU V1.3.0: Standard-Maßeinheiten für Auto-Setup ---
# Diese Einheiten werden beim Start geprüft und ggf. in Grocy angelegt.
DEFAULT_QUANTITY_UNITS = [
    # Basis-Lager-Einheiten
    {"name": "Gramm", "name_plural": "Gramm", "description": "g"},
    {"name": "Milliliter", "name_plural": "Milliliter", "description": "ml"},
    {"name": "Stück", "name_plural": "Stücke", "description": "Stk"},
    {"name": "Dose", "name_plural": "Dosen", "description": "Dose"},
    {"name": "Packung", "name_plural": "Packungen", "description": "Pack"},
    
    # Sub-Einheiten (Rezept-Mengen)
    {"name": "Kilogramm", "name_plural": "Kilogramm", "description": "kg"},
    {"name": "Liter", "name_plural": "Liter", "description": "L"},
    {"name": "Deziliter", "name_plural": "Deziliter", "description": "dl"},
    {"name": "Zentiliter", "name_plural": "Zentiliter", "description": "cl"},
    {"name": "Esslöffel", "name_plural": "Esslöffel", "description": "EL"},
    {"name": "Teelöffel", "name_plural": "Teelöffel", "description": "TL"},
    {"name": "Tasse", "name_plural": "Tassen", "description": "Cup"},
    {"name": "Zehe", "name_plural": "Zehen", "description": "Zehe"},
    {"name": "Spritzer", "name_plural": "Spritzer", "description": "Spritzer"},
    {"name": "Tropfen", "name_plural": "Tropfen", "description": "Trpf"},
    {"name": "Päckchen", "name_plural": "Päckchen", "description": "Pck"}
]

# --- NEU V1.3.0: Globale Umrechnungsregeln ---
# Format: (Basis-Einheit, Umrechnungs-Einheit, Faktor)
# Bedeutet: 1 Umrechnungs-Einheit = Faktor x Basis-Einheit
UNIT_CONVERSIONS = [
    # Masse
    ("Gramm", "Kilogramm", 1000.0),
    # Volumen
    ("Milliliter", "Liter", 1000.0),
    ("Milliliter", "Deziliter", 100.0),
    ("Milliliter", "Zentiliter", 10.0),
    ("Milliliter", "Esslöffel", 15.0),
    ("Milliliter", "Teelöffel", 5.0),
    ("Milliliter", "Tasse", 250.0),
    ("Milliliter", "Spritzer", 2.0),
    ("Milliliter", "Tropfen", 0.05),
    # Mengen
    ("Stück", "Zehe", 1.0)
]

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