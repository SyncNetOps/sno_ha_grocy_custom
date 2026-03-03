"""
SNO-HA_Grocy-custom V1.2.0: KI-Parser (Powered by Gemini).
Berücksichtigt nun Portionen, Einheitenumrechnung und filtert Gewürze (Ignore for Stock).
"""
import json
import logging
import aiohttp
import asyncio

LOGGER = logging.getLogger(__package__)
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

async def async_parse_recipe_with_ai(api_key: str, text_input: str, grocy_products: list, grocy_units: list, session: aiohttp.ClientSession) -> list:
    if not api_key:
        return []

    product_dict = {str(p.get('id')): p.get('name') for p in grocy_products if isinstance(p, dict)}
    unit_dict = {str(u.get('id')): u.get('name') for u in grocy_units if isinstance(u, dict)}
    
    prompt = f"""Du bist ein Daten-Konverter für eine Grocy Home Assistant Integration.
Generiere aus dem folgenden Text ein exaktes JSON-Array.

REGELN:
1. Das Array muss EXAKT diese Struktur haben:
[
  {{
    "name": "Name des Gerichts",
    "description": "Erstelle eine detailreiche Schritt-für-Schritt Zubereitungsanleitung. WICHTIG: Formatiere diese mit HTML-Tags (<p>, <b>, <br>).",
    "base_servings": 4, 
    "ingredients": [
      {{
        "amount": 500.0,
        "qu_id": 2,
        "product_id": 14,
        "raw_ingredient_name": "Mehl",
        "ignore_for_stock": false
      }}
    ]
  }}
]

2. PORTIONEN & UMRECHNUNG: 
Rechne die Rezeptmengen in die logischste Basis-Einheit aus folgendem Grocy-Einheiten-Wörterbuch (Format "ID": "Name") um:
{json.dumps(unit_dict, ensure_ascii=False)}
Beispiel: Im Rezept steht "1 kg Mehl", in meinem Wörterbuch gibt es "2: Gramm". Dann setze "amount": 1000 und "qu_id": 2.
Setze "qu_id" zwingend auf eine Zahl aus diesem Wörterbuch!

3. GEWÜRZE & KLEINIGKEITEN IGNORIEREN:
Wenn eine Zutat eine ungenaue oder unwesentliche Kleinigkeit ist, die man nicht klassisch im Lager erfasst (z.B. '1 Prise Salz', 'etwas Pfeffer', 'Schuss Öl', '1 Lorbeerblatt', '1 TL Zucker'), dann setze `ignore_for_stock` zwingend auf true!

4. SMART DEDUPLICATION: 
Hier ist mein existierendes Grocy-Produkt-Wörterbuch:
{json.dumps(product_dict, ensure_ascii=False)}
Für jede Zutat MUSST du die logisch passendste `product_id` aus dem Wörterbuch finden.
Gibt es absolut keinen Treffer, setze `product_id` zwingend auf -1.

TEXT-INPUT:
{text_input}

GIB NUR DAS JSON ZURÜCK! Keine Markdown Codeblöcke.
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