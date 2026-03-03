"""
SNO-HA_Grocy-custom V1.4.0: KI-Parser (Powered by Gemini).
Inklusive Meal-Plan Datums-Extraktion und strikter Basis-Einheiten Umrechnung.
"""
import json
import logging
import aiohttp
import asyncio
from datetime import datetime

LOGGER = logging.getLogger(__package__)
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

async def async_parse_recipe_with_ai(api_key: str, text_input: str, grocy_products: list, grocy_units: list, session: aiohttp.ClientSession) -> list:
    if not api_key:
        return []

    product_dict = {str(p.get('id')): p.get('name') for p in grocy_products if isinstance(p, dict)}
    unit_dict = {str(u.get('id')): u.get('name') for u in grocy_units if isinstance(u, dict)}
    
    # Heutiges Datum als Anker für relative Wochenpläne (Montag, Morgen, etc.)
    today_str = datetime.now().strftime("%Y-%m-%d")
    weekday_str = datetime.now().strftime("%A")
    
    prompt = f"""Du bist ein intelligenter Daten-Konverter für die Grocy Home Assistant Integration.
Heute ist der {today_str} (Wochentag: {weekday_str}). Generiere aus dem Text ein exaktes JSON-Array.

REGELN:
1. Das Array muss EXAKT diese Struktur haben:
[
  {{
    "name": "Name des Gerichts",
    "description": "Schritt-für-Schritt Anleitung. Formatiere diese mit HTML-Tags (<p>, <b>, <br>).",
    "base_servings": 4, 
    "meal_plan_day": "2023-10-30", 
    "ingredients": [
      {{
        "amount": 500.0,
        "qu_id": 2,
        "qu_name": "Gramm",
        "product_id": 14,
        "raw_ingredient_name": "Mehl",
        "ignore_for_stock": false
      }}
    ]
  }}
]

2. ESSENSPLANUNG (MEAL PLAN):
Analysiere den Text auf Wochentage oder Daten (z.B. "Montag", "Morgen", "fürs Wochenende"). Berechne ausgehend vom heutigen Datum ({today_str}) das Zieldatum im Format YYYY-MM-DD. Gibt es keinen Hinweis, setze `meal_plan_day` auf null.

3. UNMESSBARE KLEINIGKEITEN IGNORIEREN:
Setze `ignore_for_stock` auf true für Dinge wie 'Prise', 'etwas', 'Schuss', 'nach Geschmack', 'Lorbeerblatt'. Die `product_id` ist dann egal.

4. UMRECHNUNG IN BASIS-EINHEITEN (EXTREM WICHTIG FÜR DAS LAGER): 
Rechne alle Mengen zwingend in die kleinstmögliche Basis-Einheit aus dem folgenden Grocy-Wörterbuch um:
{json.dumps(unit_dict, ensure_ascii=False)}
Wenn im Rezept "1 kg Mehl" steht, das Wörterbuch aber "Gramm" kennt, MUSST du amount=1000 und die ID für Gramm ausgeben. "1 Liter" wird zu amount=1000 und ID für Milliliter!

5. PRODUKT MAPPING: 
Hier ist mein existierendes Grocy-Produkt-Wörterbuch:
{json.dumps(product_dict, ensure_ascii=False)}
Finde die passendste `product_id` (Zahl). Gibt es keinen Treffer, setze `product_id` auf -1.

TEXT-INPUT:
{text_input}

GIB NUR DAS REINE JSON ZURÜCK!
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }

    try:
        async with asyncio.timeout(20):
            response = await session.post(f"{GEMINI_API_URL}?key={api_key}", json=payload)
            response.raise_for_status()
            data = await response.json()
            
            raw_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "[]")
            
            if raw_text.startswith("```json"):
                raw_text = raw_text.split("```json")[1].rsplit("```")[0].strip()
            elif raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1].rsplit("```")[0].strip()
                
            return json.loads(raw_text)

    except Exception as e:
        LOGGER.error(f"KI-Import fehlgeschlagen: {e}")
    
    return []