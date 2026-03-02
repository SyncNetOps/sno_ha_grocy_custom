"""API Client für SNO-HA_Grocy-custom V4.3."""
import aiohttp
import asyncio
from datetime import datetime, timedelta
from .const import LOGGER

class GrocyApiClient:
    def __init__(self, url: str, api_key: str, session: aiohttp.ClientSession) -> None:
        self._url = url.rstrip("/")
        self._api_key = api_key
        self._session = session
        self._headers = {
            "GROCY-API-KEY": self._api_key,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    async def test_connection(self) -> bool:
        try:
            async with asyncio.timeout(10):
                response = await self._session.get(f"{self._url}/api/system/info", headers=self._headers)
                if response.status != 200:
                    raise Exception(f"Verbindung fehlgeschlagen: HTTP {response.status}")
                return True
        except Exception as e:
            LOGGER.error("Verbindungstest fehlgeschlagen: %s", e)
            raise

    async def _async_get(self, endpoint: str):
        try:
            async with asyncio.timeout(30):
                response = await self._session.get(f"{self._url}{endpoint}", headers=self._headers)
                if response.status == 200:
                    return await response.json()
                return {} if response.status == 400 else None
        except Exception as e:
            LOGGER.error("Fehler bei GET %s: %s", endpoint, e)
            return None

    # V4.3 NEU: Raw-Downloader für Bilder (ohne JSON Parsing)
    async def async_get_raw(self, endpoint: str):
        try:
            async with asyncio.timeout(15):
                # Bilder brauchen einen speziellen Accept-Header
                headers = {"GROCY-API-KEY": self._api_key, "Accept": "*/*"}
                response = await self._session.get(f"{self._url}{endpoint}", headers=headers)
                if response.status == 200:
                    return await response.read()
                return None
        except Exception as e:
            LOGGER.error("Fehler bei RAW GET (Bild Download) %s: %s", endpoint, e)
            return None

    async def _async_post(self, endpoint: str, payload: dict = None) -> bool:
        payload = payload or {}
        try:
            async with asyncio.timeout(15):
                response = await self._session.post(f"{self._url}{endpoint}", headers=self._headers, json=payload)
                if response.status in [200, 204]:
                    return True
                error_text = await response.text()
                LOGGER.error("Grocy API Fehler! HTTP %s bei %s. Antwort: %s. Gesendet: %s", response.status, endpoint, error_text, payload)
                return False
        except Exception as e:
            LOGGER.error("POST Exception %s: %s", endpoint, e)
            return False

    async def _async_delete(self, endpoint: str) -> bool:
        try:
            async with asyncio.timeout(15):
                response = await self._session.delete(f"{self._url}{endpoint}", headers=self._headers)
                return response.status in [200, 204]
        except Exception as e:
            LOGGER.error("DELETE Exception %s: %s", endpoint, e)
            return False

    async def async_get_all_data(self) -> dict:
        data = {}
        data["stock"] = await self._async_get("/api/stock")
        data["stock_volatile"] = await self._async_get("/api/stock/volatile")
        data["products"] = await self._async_get("/api/objects/products")
        data["product_groups"] = await self._async_get("/api/objects/product_groups")
        data["locations"] = await self._async_get("/api/objects/locations")
        data["quantity_units"] = await self._async_get("/api/objects/quantity_units")
        data["chores"] = await self._async_get("/api/chores")
        data["chores_objects"] = await self._async_get("/api/objects/chores")
        data["tasks"] = await self._async_get("/api/tasks")
        data["batteries"] = await self._async_get("/api/batteries")
        data["shopping_list"] = await self._async_get("/api/objects/shopping_list")
        data["equipment"] = await self._async_get("/api/objects/equipment")
        data["meal_plan"] = await self._async_get("/api/objects/meal_plan")
        data["recipes"] = await self._async_get("/api/recipes")
        
        date_30_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        data["stock_log"] = await self._async_get(f"/api/objects/stock_log?query[]=row_created_timestamp>={date_30_days_ago}")
        return data

    async def async_consume_product(self, product_id: int, amount: float, qu_id: int = None) -> bool:
        payload = {"amount": amount, "transaction_type": "consume", "spoiled": False}
        if qu_id is not None: payload["qu_id"] = qu_id
        return await self._async_post(f"/api/stock/products/{product_id}/consume", payload)

    async def async_add_product(self, product_id: int, amount: float, price: float = None, qu_id: int = None) -> bool:
        payload = {"amount": amount, "transaction_type": "purchase"}
        if price is not None: payload["price"] = price
        if qu_id is not None: payload["qu_id"] = qu_id
        return await self._async_post(f"/api/stock/products/{product_id}/add", payload)

    async def async_transfer_product(self, product_id: int, amount: float, location_id_from: int = None, location_id_to: int = None, qu_id: int = None) -> bool:
        payload = {"amount": amount}
        if location_id_from is not None: payload["location_id_from"] = location_id_from
        if location_id_to is not None: payload["location_id_to"] = location_id_to
        if qu_id is not None: payload["qu_id"] = qu_id
        return await self._async_post(f"/api/stock/products/{product_id}/transfer", payload)

    async def async_consume_recipe(self, recipe_id: int) -> bool:
        return await self._async_post(f"/api/recipes/{recipe_id}/consume", {})

    async def async_execute_chore(self, chore_id: int) -> bool:
        return await self._async_post(f"/api/chores/{chore_id}/execute", {})

    async def async_complete_task(self, task_id: int) -> bool:
        return await self._async_post(f"/api/tasks/{task_id}/complete", {"done_time": ""})

    async def async_charge_battery(self, battery_id: int) -> bool:
        return await self._async_post(f"/api/batteries/{battery_id}/charge", {})