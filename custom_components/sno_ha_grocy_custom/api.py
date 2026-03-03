"""API Client für SNO-HA_Grocy-custom V1.5.2 (Restored Endpoints)."""
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
                return []
        except Exception as e:
            LOGGER.error(f"Fehler bei GET {endpoint}: {e}")
            return []

    async def _async_post(self, endpoint: str, payload: dict) -> bool:
        try:
            async with asyncio.timeout(30):
                response = await self._session.post(f"{self._url}{endpoint}", json=payload, headers=self._headers)
                return response.status in [200, 204]
        except Exception as e:
            LOGGER.error(f"Fehler bei POST {endpoint}: {e}")
            return False

    async def _async_post_return_id(self, endpoint: str, payload: dict) -> int | None:
        try:
            async with asyncio.timeout(30):
                response = await self._session.post(f"{self._url}{endpoint}", json=payload, headers=self._headers)
                if response.status == 200:
                    data = await response.json()
                    return data.get("created_object_id")
                else:
                    resp_text = await response.text()
                    LOGGER.error(f"POST {endpoint} fehlgeschlagen (HTTP {response.status}): {resp_text}")
                    return None
        except Exception as e:
            LOGGER.error(f"Fehler bei POST_RETURN_ID {endpoint}: {e}")
            return None

    # --- DATEN ABRUFEN ---
    async def async_get_stock(self) -> list: return await self._async_get("/api/stock")
    async def async_get_chores(self) -> list: return await self._async_get("/api/chores")
    async def async_get_tasks(self) -> list: return await self._async_get("/api/tasks")
    async def async_get_shopping_list(self) -> list: return await self._async_get("/api/objects/shopping_list")
    async def async_get_meal_plan(self) -> list:
        now = datetime.now()
        start = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        end = (now + timedelta(days=7)).strftime("%Y-%m-%d")
        return await self._async_get(f"/api/objects/meal_plan?query[]=day>={start}&query[]=day<={end}")
    async def async_get_recipes(self) -> list: return await self._async_get("/api/recipes")
    async def async_get_batteries(self) -> list: return await self._async_get("/api/batteries")
    async def async_get_equipment(self) -> list: return await self._async_get("/api/objects/equipment")
    async def async_get_products(self) -> list: return await self._async_get("/api/objects/products")
    
    # --- WIEDERHERGESTELLTE ENDPUNKTE (Fehlten und verursachten den UI Fehler) ---
    async def async_get_locations(self) -> list: return await self._async_get("/api/objects/locations")
    async def async_get_product_groups(self) -> list: return await self._async_get("/api/objects/product_groups")
    async def async_get_quantity_units(self) -> list: return await self._async_get("/api/objects/quantity_units")
    async def async_get_quantity_unit_conversions(self) -> list: return await self._async_get("/api/objects/quantity_unit_conversions")

    # --- AKTIONEN AUSFÜHREN ---
    async def async_consume_product(self, product_id: int, amount: float, qu_id: int = None) -> bool:
        payload = {"amount": float(amount), "transaction_type": "consume", "spoiled": False}
        if qu_id is not None: payload["qu_id"] = int(qu_id)
        return await self._async_post(f"/api/stock/products/{int(product_id)}/consume", payload)

    async def async_add_product(self, product_id: int, amount: float, price: float = None, qu_id: int = None) -> bool:
        payload = {"amount": float(amount), "transaction_type": "purchase"}
        if price is not None: payload["price"] = float(price)
        if qu_id is not None: payload["qu_id"] = int(qu_id)
        return await self._async_post(f"/api/stock/products/{int(product_id)}/add", payload)

    async def async_transfer_product(self, product_id: int, amount: float, location_id_from: int = None, location_id_to: int = None, qu_id: int = None) -> bool:
        payload = {"amount": float(amount)}
        if location_id_from is not None: payload["location_id_from"] = int(location_id_from)
        if location_id_to is not None: payload["location_id_to"] = int(location_id_to)
        if qu_id is not None: payload["qu_id"] = int(qu_id)
        return await self._async_post(f"/api/stock/products/{int(product_id)}/transfer", payload)

    async def async_consume_recipe(self, recipe_id: int) -> bool:
        return await self._async_post(f"/api/recipes/{int(recipe_id)}/consume", {})

    async def async_execute_chore(self, chore_id: int) -> bool:
        return await self._async_post(f"/api/chores/{int(chore_id)}/execute", {})

    async def async_complete_task(self, task_id: int) -> bool:
        return await self._async_post(f"/api/tasks/{int(task_id)}/complete", {})

    async def async_charge_battery(self, battery_id: int) -> bool:
        return await self._async_post(f"/api/batteries/{int(battery_id)}/charge", {})

    async def async_add_shopping_list_item(self, note: str, amount: float = 1, product_id: int = None) -> bool:
        payload = {"note": note, "amount": float(amount), "shopping_list_id": 1}
        if product_id: payload["product_id"] = int(product_id)
        return await self._async_post("/api/objects/shopping_list", payload)

    async def async_delete_shopping_list_item(self, item_id: int) -> bool:
        try:
            async with asyncio.timeout(10):
                response = await self._session.delete(f"{self._url}/api/objects/shopping_list/{int(item_id)}", headers=self._headers)
                return response.status in [200, 204]
        except Exception as e:
            LOGGER.error(f"Fehler beim Löschen des Items {item_id}: {e}")
            return False

    # --- REZEPT- & KI-ENGINE AKTIONEN ---
    async def async_create_product(self, name: str, location_id: int, qu_id: int, product_group_id: int = None) -> int | None:
        payload = {
            "name": name,
            "location_id": int(location_id),
            "qu_id_purchase": int(qu_id),
            "qu_id_stock": int(qu_id),
            "min_stock_amount": 0,
            "description": "Automatisch importiert via SNO-HA KI-Bridge"
        }
        if product_group_id:
            payload["product_group_id"] = int(product_group_id)
        return await self._async_post_return_id("/api/objects/products", payload)

    async def async_add_recipe(self, name: str, description: str = "", base_servings: int = 1) -> int | None:
        payload = {
            "name": name,
            "description": description,
            "base_servings": int(base_servings),
            "desired_servings": int(base_servings),
            "type": "normal"
        }
        return await self._async_post_return_id("/api/objects/recipes", payload)

    async def async_add_recipe_ingredient(self, recipe_id: int, product_id: int, amount: float, qu_id: int = None) -> bool:
        payload = {
            "recipe_id": int(recipe_id),
            "product_id": int(product_id),
            "amount": float(amount)
        }
        if qu_id is not None:
            payload["qu_id"] = int(qu_id)
        result = await self._async_post_return_id("/api/objects/recipes_pos", payload)
        return result is not None

    async def async_add_meal_plan(self, day: str, recipe_id: int, type: str = "recipe") -> bool:
        payload = {
            "day": day,
            "type": type,
            "recipe_id": int(recipe_id),
            "recipe_servings": 1
        }
        result = await self._async_post_return_id("/api/objects/meal_plan", payload)
        return result is not None

    # --- Setup Helfer ---
    async def async_create_quantity_unit(self, name: str, name_plural: str, description: str) -> int | None:
        payload = {"name": name, "name_plural": name_plural, "description": description}
        return await self._async_post_return_id("/api/objects/quantity_units", payload)

    async def async_create_quantity_unit_conversion(self, from_qu_id: int, to_qu_id: int, factor: float) -> bool:
        payload = {"from_qu_id": int(from_qu_id), "to_qu_id": int(to_qu_id), "factor": float(factor)}
        result = await self._async_post_return_id("/api/objects/quantity_unit_conversions", payload)
        return result is not None