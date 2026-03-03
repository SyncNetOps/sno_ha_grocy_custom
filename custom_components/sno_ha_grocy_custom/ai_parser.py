"""
SNO-HA_Grocy-custom V1.3.0: KI-Parser (Powered by Gemini).
Smart Unit Mapping & Ignore-Filter für Gewürze/Kleinigkeiten.
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
        "qu_name": "Gramm",
        "product_id": 14,
        "raw_ingredient_name": "Mehl",
        "ignore_for_stock": false
      }}
    ]
  }}
]

2. UNMESSBARE KLEINIGKEITEN IGNORIEREN (WICHTIG!):
Wenn eine Zutat im Text eine physikalisch ungenaue oder unwesentliche Menge hat, die man in einem Warenwirtschaftssystem nicht per ID tracken will (z.B. '1 Prise Salz', 'etwas Pfeffer', 'Schuss Öl', 'nach Geschmack', '1 Lorbeerblatt', 'Salz und Pfeffer'), MUSS `ignore_for_stock` auf true gesetzt werden! In diesem Fall ist die `product_id` irrelevant. Fülle "amount", "qu_name" und "raw_ingredient_name" aber trotzdem aus (z.B. amount: 1, qu_name: "Prise", raw_ingredient_name: "Salz").

3. EINHEITEN ZUWEISEN (Für alle anderen Zutaten): 
Ordne der Rezeptmenge die logischste Sub-Einheit oder Basis-Einheit aus folgendem Grocy-Wörterbuch (Format "ID": "Name") zu:
{json.dumps(unit_dict, ensure_ascii=False)}
Übersetze auch Abkürzungen! ('EL' oder 'tbsp' -> Esslöffel, 'ml' -> Milliliter, 'g' -> Gramm).
Setze `qu_id` auf die Zahl aus dem Wörterbuch und `qu_name` auf den Namen der Einheit.

4. PRODUKT MAPPING: 
Hier ist mein existierendes Grocy-Produkt-Wörterbuch:
{json.dumps(product_dict, ensure_ascii=False)}
Für jede trackbare Zutat MUSST du die passendste `product_id` finden. Gibt es absolut keinen logischen Treffer, setze `product_id` auf -1.

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