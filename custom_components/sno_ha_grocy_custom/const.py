"""Konstanten für die SNO-HA_Grocy-custom Integration V1.6.0."""
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

MODE_NONE = "none"
MODE_SENSOR = "sensor"
MODE_TODO = "todo"
MODE_BOTH = "both"

# KI & Rezept-Engine Optionen
CONF_ENABLE_AI = "enable_ai"
CONF_GEMINI_API_KEY = "gemini_api_key"
CONF_AI_AUTO_CREATE = "ai_auto_create"
CONF_AI_SYNC_SHOPPING = "ai_sync_shopping"
CONF_AI_PRODUCT_GROUP = "ai_product_group" 
CONF_AI_DEFAULT_QU = "ai_default_qu"

# --- NEU V1.6.0: Cookidoo Bridge Optionen ---
CONF_COOKIDOO_ENABLE = "cookidoo_enable"
CONF_COOKIDOO_EMAIL = "cookidoo_email"
CONF_COOKIDOO_PASSWORD = "cookidoo_password"
CONF_COOKIDOO_LOCALE = "cookidoo_locale"

# Verfügbare Cookidoo Länder/Sprachen
COOKIDOO_LOCALES = [
    "de-DE", "en-GB", "en-US", "es-ES", "fr-FR", 
    "it-IT", "pt-PT", "pl-PL", "nl-NL", "cs-CZ"
]

# --- Standard-Maßeinheiten für Auto-Setup ---
# Diese Einheiten werden beim Start geprüft und ggf. in Grocy angelegt.
# Hinweis: Unmessbare Einheiten (Prise, Messerspitze, Schuss) fehlen hier absichtlich, 
# da die KI diese aussortiert und nur als Text im Rezept hinterlegt!
DEFAULT_QUANTITY_UNITS = [
    {"name": "Stück", "name_plural": "Stück", "description": "Stk."},
    {"name": "Gramm", "name_plural": "Gramm", "description": "g"},
    {"name": "Kilogramm", "name_plural": "Kilogramm", "description": "kg"},
    {"name": "Milliliter", "name_plural": "Milliliter", "description": "ml"},
    {"name": "Liter", "name_plural": "Liter", "description": "l"},
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

# --- Globale Umrechnungsregeln ---
# Format: (Basis-Einheit, Umrechnungs-Einheit, Faktor)
# Bedeutet: 1 Umrechnungs-Einheit = Faktor x Basis-Einheit
UNIT_CONVERSIONS = [
    # Masse
    ("Gramm", "Kilogramm", 1000.0),
    # Volumen
    ("Milliliter", "Liter", 1000.0),
    ("Milliliter", "Deziliter", 100.0),
    ("Milliliter", "Zentiliter", 10.0),
    ("Zentiliter", "Deziliter", 10.0),
    ("Deziliter", "Liter", 10.0)
]