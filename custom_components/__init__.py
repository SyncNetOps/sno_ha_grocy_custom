"""Initialisierung der SNO-HA_Grocy-custom Integration V4.3."""
from datetime import timedelta
import voluptuous as vol
import re
import base64

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.helpers.config_validation as cv
from homeassistant.components.http import HomeAssistantView
from aiohttp import web

from .api import GrocyApiClient
from .const import DOMAIN, CONF_URL, CONF_API_KEY, UPDATE_INTERVAL, LOGGER
from .autoinstall import async_install_assets

PLATFORMS = ["sensor", "todo"]

# V4.3 NEU: Web-Server für Grocy Produktbilder
class GrocyPictureView(HomeAssistantView):
    """Proxy, um Grocy-Bilder in HA Dashboards anzuzeigen."""
    url = "/api/sno_grocy/picture/{filename}"
    name = "api:sno_grocy:picture"
    requires_auth = False # Erlaubt die Anzeige in Dashboard-Karten ohne Login-Token Probleme

    def __init__(self, client: GrocyApiClient):
        self.client = client

    async def get(self, request, filename):
        if not filename:
            return web.Response(status=404)
        
        # Grocy verlangt den Dateinamen als Base64-String in der URL
        encoded_fn = base64.b64encode(filename.encode('utf-8')).decode('utf-8')
        endpoint = f"/api/files/productpictures/{encoded_fn}"
        
        picture_bytes = await self.client.async_get_raw(endpoint)
        if picture_bytes:
            # Sende das Bild direkt an das Dashboard zurück
            return web.Response(body=picture_bytes, content_type="image/jpeg")
        return web.Response(status=404)


def _extract_id(value) -> int:
    if not value: return None
    match = re.search(r"^(\d+)", str(value))
    return int(match.group(1)) if match else None

def _get_entity_attr(hass, entity_id, attr_name):
    if not entity_id: return None
    state = hass.states.get(entity_id)
    if state and attr_name in state.attributes:
        return int(state.attributes[attr_name])
    return None

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.async_create_task(async_install_assets(hass))

    session = async_get_clientsession(hass)
    client = GrocyApiClient(entry.data[CONF_URL], entry.data[CONF_API_KEY], session)

    # Bild-Server registrieren
    hass.http.register_view(GrocyPictureView(client))

    async def async_update_data():
        try:
            return await client.async_get_all_data()
        except Exception as err:
            raise UpdateFailed(f"Fehler bei der Kommunikation mit Grocy: {err}")

    coordinator = DataUpdateCoordinator(
        hass, LOGGER, name="sno_ha_grocy_custom_update",
        update_method=async_update_data, update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator, "client": client}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    async def call_and_refresh(coro):
        if await coro: await coordinator.async_request_refresh()

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
        if prod_id: await call_and_refresh(client.async_transfer_product(prod_id, call.data.get("amount", 1), None, _extract_id(call.data.get("location_id_to")), _extract_id(call.data.get("qu_id"))))
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

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)