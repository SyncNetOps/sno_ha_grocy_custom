"""Initialisierung der SNO-HA_Grocy-custom Integration V1.3.0 Ultimate."""
from datetime import timedelta
import voluptuous as vol
import base64

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.components.http import HomeAssistantView
from aiohttp import web

from .api import GrocyApiClient
from .const import (
    DOMAIN, CONF_URL, CONF_API_KEY, UPDATE_INTERVAL, LOGGER,
    CONF_ENABLE_AI, CONF_GEMINI_API_KEY, CONF_AI_AUTO_CREATE, CONF_AI_SYNC_SHOPPING, CONF_AI_PRODUCT_GROUP, CONF_AI_DEFAULT_QU,
    DEFAULT_QUANTITY_UNITS, UNIT_CONVERSIONS
)
from .autoinstall import async_install_assets
from .ai_parser import async_parse_recipe_with_ai

PLATFORMS = ["sensor", "todo"]

class GrocyPictureView(HomeAssistantView):
    url = "/api/sno_grocy/picture/{filename}"
    name = "api:sno_grocy:picture"
    requires_auth = False

    def __init__(self, client: GrocyApiClient):
        self.client = client

    async def get(self, request, filename):
        if not filename: return web.Response(status=404)
        encoded_fn = base64.b64encode(filename.encode('utf-8')).decode('utf-8')
        try:
            async with self.client._session.get(f"{self.client._url}/api/files/productpictures/{encoded_fn}", headers=self.client._headers) as response:
                if response.status == 200:
                    return web.Response(body=await response.read(), content_type=response.headers.get("Content-Type", "image/jpeg"))
        except Exception as e:
            LOGGER.error("Fehler beim Laden des Grocy Bildes: %s", e)
        return web.Response(status=404)

async def _async_setup_grocy_environment(client: GrocyApiClient):
    """Prüft und erstellt fehlende Standard-Einheiten und Umrechnungen in Grocy."""
    LOGGER.info("SNO-HA Grocy: Prüfe System-Umgebung (Maßeinheiten)...")
    existing_units = await client.async_get_quantity_units()
    unit_map = {u.get("name").lower(): u.get("id") for u in existing_units if isinstance(u, dict)}
    
    # 1. Fehlende Einheiten anlegen
    for unit in DEFAULT_QUANTITY_UNITS:
        u_name_low = unit["name"].lower()
        if u_name_low not in unit_map:
            new_id = await client.async_create_quantity_unit(unit["name"], unit["name_plural"], unit["description"])
            if new_id:
                unit_map[u_name_low] = new_id
                LOGGER.info(f"Maßeinheit angelegt: {unit['name']}")

    # 2. Globale Umrechnungen prüfen und anlegen
    existing_conversions = await client.async_get_quantity_unit_conversions()
    
    for base_name, conv_name, factor in UNIT_CONVERSIONS:
        base_id = unit_map.get(base_name.lower())
        conv_id = unit_map.get(conv_name.lower())
        
        if base_id and conv_id:
            # Prüfen ob diese Umrechnung (von -> zu) schon existiert
            exists = False
            for ec in existing_conversions:
                if int(ec.get("from_qu_id", 0)) == int(conv_id) and int(ec.get("to_qu_id", 0)) == int(base_id):
                    exists = True
                    break
            
            if not exists:
                await client.async_create_quantity_unit_conversion(conv_id, base_id, factor)
                LOGGER.info(f"Umrechnung angelegt: 1 {conv_name} = {factor} {base_name}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    session = async_get_clientsession(hass)
    client = GrocyApiClient(entry.data[CONF_URL], entry.data[CONF_API_KEY], session)
    
    # Führe Auto-Setup der Einheiten im Hintergrund aus
    hass.async_create_task(_async_setup_grocy_environment(client))

    async def async_update_data():
        try:
            return {
                "stock": await client.async_get_stock(),
                "chores": await client.async_get_chores(),
                "tasks": await client.async_get_tasks(),
                "shopping_list": await client.async_get_shopping_list(),
                "meal_plan": await client.async_get_meal_plan(),
                "recipes": await client.async_get_recipes(),
                "batteries": await client.async_get_batteries(),
                "equipment": await client.async_get_equipment(),
                "products": await client.async_get_products()
            }
        except Exception as e:
            raise UpdateFailed(f"Fehler bei Grocy: {e}")

    coordinator = DataUpdateCoordinator(hass, LOGGER, name=DOMAIN, update_method=async_update_data, update_interval=timedelta(seconds=UPDATE_INTERVAL))
    await coordinator.async_config_entry_first_refresh()

    enable_ai = entry.options.get(CONF_ENABLE_AI, False)
    gemini_api_key = entry.options.get(CONF_GEMINI_API_KEY, "")
    auto_create = entry.options.get(CONF_AI_AUTO_CREATE, False)
    sync_shopping = entry.options.get(CONF_AI_SYNC_SHOPPING, False)
    
    selected_pg = entry.options.get(CONF_AI_PRODUCT_GROUP, "0")
    product_group_id = int(selected_pg) if str(selected_pg) != "0" else None
    selected_qu = entry.options.get(CONF_AI_DEFAULT_QU, "1")
    default_qu_id = int(selected_qu) if str(selected_qu) != "0" else 1

    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator, "client": client}
    await async_install_assets(hass)
    hass.http.register_view(GrocyPictureView(client))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def call_and_refresh(coro):
        try:
            await coro
            await coordinator.async_request_refresh()
        except Exception as e: LOGGER.error("Service Fehler: %s", e)

    def _get_entity_attr(hass, entity_id, attr_name):
        if not entity_id: return None
        state = hass.states.get(entity_id)
        return state.attributes.get(attr_name) if state else None

    def _extract_id(val):
        try: return int(val) if val else None
        except: return None

    async def handle_consume(call):
        prod_id = _get_entity_attr(hass, call.data.get("entity_id"), "product_id") or _extract_id(call.data.get("product_id"))
        if prod_id: await call_and_refresh(client.async_consume_product(prod_id, call.data.get("amount", 1), _extract_id(call.data.get("qu_id"))))
    hass.services.async_register(DOMAIN, "consume_product", handle_consume)

    async def handle_add(call):
        prod_id = _get_entity_attr(hass, call.data.get("entity_id"), "product_id") or _extract_id(call.data.get("product_id"))
        if prod_id: await call_and_refresh(client.async_add_product(prod_id, call.data.get("amount", 1), call.data.get("price"), _extract_id(call.data.get("qu_id"))))
    hass.services.async_register(DOMAIN, "add_product", handle_add)

    async def handle_transfer(call):
        prod_id = _get_entity_attr(hass, call.data.get("entity_id"), "product_id") or _extract_id(call.data.get("product_id"))
        if prod_id: await call_and_refresh(client.async_transfer_product(prod_id, call.data.get("amount", 1), _extract_id(call.data.get("location_id_from")), _extract_id(call.data.get("location_id_to")), _extract_id(call.data.get("qu_id"))))
    hass.services.async_register(DOMAIN, "transfer_product", handle_transfer)

    async def handle_chore(call):
        chore_id = _get_entity_attr(hass, call.data.get("entity_id"), "chore_id") or _extract_id(call.data.get("chore_id"))
        if chore_id: await call_and_refresh(client.async_execute_chore(chore_id))
    hass.services.async_register(DOMAIN, "execute_chore", handle_chore)

    async def handle_task(call):
        task_id = _get_entity_attr(hass, call.data.get("entity_id"), "task_id") or _extract_id(call.data.get("task_id"))
        if task_id: await call_and_refresh(client.async_complete_task(task_id))
    hass.services.async_register(DOMAIN, "complete_task", handle_task)

    async def handle_battery(call):
        bat_id = _get_entity_attr(hass, call.data.get("entity_id"), "battery_id") or _extract_id(call.data.get("battery_id"))
        if bat_id: await call_and_refresh(client.async_charge_battery(bat_id))
    hass.services.async_register(DOMAIN, "charge_battery", handle_battery)

    # --- KI REZEPT IMPORT SERVICE (V1.3.0) ---
    if enable_ai:
        async def handle_ai_import(call):
            text_input = call.data.get("text_input")
            if not text_input or not gemini_api_key: return

            LOGGER.info("Starte KI-Rezept-Analyse. Bitte warten...")
            products = await client.async_get_products()
            units = await client.async_get_quantity_units()
            
            recipes = await async_parse_recipe_with_ai(gemini_api_key, text_input, products, units, session)
            
            if not recipes:
                LOGGER.warning("KI konnte keine Rezepte extrahieren.")
                return
            
            locs = await client._async_get("/api/objects/locations")
            default_location_id = int(locs[0].get("id", 1)) if locs else 1

            for recipe in recipes:
                recipe_name = recipe.get("name", "KI Importiertes Rezept")
                base_servings = recipe.get("base_servings", 1) 
                
                raw_desc = recipe.get("description", "")
                if not raw_desc.startswith("<"): raw_desc = raw_desc.replace("\n", "<br>")
                
                ingredients = recipe.get("ingredients", [])
                valid_ingredients = []
                ignored_notes = []
                
                for ing in ingredients:
                    if ing.get("ignore_for_stock", False):
                        amt = ing.get("amount", "")
                        qu_name = ing.get("qu_name", "")
                        name = ing.get("raw_ingredient_name", "Zutat")
                        ignored_notes.append(f"• {amt} {qu_name} {name}".replace("  ", " ").strip())
                    else:
                        valid_ingredients.append(ing)
                        
                if ignored_notes:
                    raw_desc += "<br><br><b>💡 Ungetrackte Kleinigkeiten (Gewürze & Co.):</b><br>" + "<br>".join(ignored_notes)
                
                recipe_desc = f"<p>{raw_desc}</p>" if not raw_desc.startswith("<") else raw_desc

                recipe_id = await client.async_add_recipe(recipe_name, recipe_desc, base_servings)
                if not recipe_id: continue
                
                LOGGER.info(f"Rezept '{recipe_name}' angelegt. Verknüpfe {len(valid_ingredients)} trackbare Zutaten...")
                
                for ing in valid_ingredients:
                    prod_id = ing.get("product_id")
                    amount = ing.get("amount", 1)
                    raw_name = ing.get("raw_ingredient_name", "Unbekannt")
                    
                    # KI hat im besten Fall die exakte qu_id aus unserem Wörterbuch zurückgegeben
                    qu_id = ing.get("qu_id", default_qu_id)
                    
                    # Fall 1: Auto-Create
                    if str(prod_id) == "-1" and auto_create:
                        new_id = await client.async_create_product(raw_name, default_location_id, qu_id, product_group_id)
                        if new_id:
                            prod_id = new_id
                            LOGGER.info(f"Neues Produkt automatisch angelegt: {raw_name}")
                    
                    # Fall 2: Zutat anbinden
                    if prod_id and str(prod_id) != "-1":
                        success = await client.async_add_recipe_ingredient(recipe_id, prod_id, amount, qu_id)
                        if not success:
                            LOGGER.error(f"Fehler: Zutat '{raw_name}' (ID: {prod_id}, QU: {qu_id}) wurde abgelehnt.")
                    else:
                        # Fall 3: Einkaufszettel
                        if sync_shopping:
                            await client.async_add_shopping_list_item(f"[REZEPT: {recipe_name}] Fehlende Zutat: {amount}x {raw_name}")
            
            await coordinator.async_request_refresh()

        hass.services.async_register(DOMAIN, "import_recipe_via_ai", handle_ai_import)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)