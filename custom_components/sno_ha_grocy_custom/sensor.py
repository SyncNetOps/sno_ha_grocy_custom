"""Definition der Grocy Sensoren (V4.3) inkl. Master-Sensor und UX-Fixes."""
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN, LOGGER, MODE_SENSOR, MODE_BOTH,
    CONF_MODE_TASKS, CONF_MODE_CHORES, CONF_MODE_SHOPPING, CONF_ADVANCED_STATS
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    options = entry.options

    sensors = [
        GrocyMasterInventorySensor(coordinator), # V4.3 NEU: Der Baukasten-Motor
        GrocyStockTotalSensor(coordinator),
        GrocyStockMissingSensor(coordinator),
        GrocyStockExpiringSensor(coordinator),
        GrocyStockExpiredSensor(coordinator),
        GrocyEquipmentSensor(coordinator),
        GrocyRecipesTotalSensor(coordinator),
        GrocyMealPlanTodaySensor(coordinator),
        GrocyBatteriesTotalSensor(coordinator),
        GrocyBatteriesDueSensor(coordinator),
        GrocyStockValueSensor(coordinator, options),
        GrocyMonthlySpendSensor(coordinator, options),
        GrocyMonthlyConsumeSensor(coordinator, options)
    ]

    products = coordinator.data.get("products", [])
    if isinstance(products, list):
        for product in products:
            if isinstance(product, dict) and "id" in product:
                sensors.append(GrocyProductSensor(coordinator, product))
                
    batteries = coordinator.data.get("batteries", [])
    if isinstance(batteries, list):
        for bat in batteries:
            if isinstance(bat, dict) and "id" in bat:
                sensors.append(GrocySingleBatterySensor(coordinator, bat))

    if options.get(CONF_MODE_SHOPPING, MODE_BOTH) in [MODE_SENSOR, MODE_BOTH]:
        sensors.append(GrocyShoppingListSensor(coordinator))

    if options.get(CONF_MODE_CHORES, MODE_BOTH) in [MODE_SENSOR, MODE_BOTH]:
        sensors.extend([GrocyChoresTotalSensor(coordinator), GrocyChoresOverdueSensor(coordinator)])
        chores = coordinator.data.get("chores", [])
        if isinstance(chores, list):
            for chore in chores:
                if isinstance(chore, dict) and "id" in chore:
                    sensors.append(GrocySingleChoreSensor(coordinator, chore))

    if options.get(CONF_MODE_TASKS, MODE_BOTH) in [MODE_SENSOR, MODE_BOTH]:
        sensors.extend([GrocyTasksTotalSensor(coordinator), GrocyTasksOverdueSensor(coordinator)])
        tasks = coordinator.data.get("tasks", [])
        if isinstance(tasks, list):
            for task in tasks:
                if isinstance(task, dict) and "id" in task:
                    sensors.append(GrocySingleTaskSensor(coordinator, task))

    async_add_entities(sensors)

class GrocyBaseSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, device_id: str, device_name: str):
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self.entry_id = coordinator.config_entry.entry_id
        self._device_id = device_id
        self._device_name = device_name

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, f"{self.entry_id}_{self._device_id}")}, "name": f"Grocy {self._device_name}", "manufacturer": "Grocy"}

    def _get_list(self, key: str) -> list:
        data = self.coordinator.data.get(key)
        return data if isinstance(data, list) else []

    def _is_overdue(self, date_str: str) -> bool:
        if not date_str or not isinstance(date_str, str):
            return False
        return date_str < dt_util.now().isoformat()

    def _get_products_dict(self) -> dict:
        return {str(p.get("id")): p for p in self._get_list("products") if isinstance(p, dict)}
        
    def _get_groups_dict(self) -> dict:
        return {str(g.get("id")): g.get("name", "Unbekannt") for g in self._get_list("product_groups") if isinstance(g, dict)}


# ==========================================
# V4.3 NEU: Der Master-Sensor
# ==========================================
class GrocyMasterInventorySensor(GrocyBaseSensor):
    """Bündelt das komplette Inventar, Lagerorte und Bilder für den Dashboard Baukasten."""
    def __init__(self, coordinator):
        super().__init__(coordinator, "stock", "Lager")
        self._attr_unique_id = f"{self.entry_id}_inventory_master"
        self._attr_name = "Inventory Master (Datenbasis)"
        self._attr_icon = "mdi:database-search"

    @property
    def native_value(self):
        return len(self._get_list("stock"))

    @property
    def extra_state_attributes(self):
        p_dict = self._get_products_dict()
        groups = self._get_groups_dict()
        locs = {str(l.get("id")): l.get("name") for l in self._get_list("locations") if isinstance(l, dict)}
        qus = {str(q.get("id")): q.get("name") for q in self._get_list("quantity_units") if isinstance(q, dict)}
        
        inventory = []
        for item in self._get_list("stock"):
            pid = str(item.get("product_id"))
            prod = p_dict.get(pid, {})
            
            # Bild-URL generieren (Proxy über HA)
            pic_name = prod.get("picture_file_name")
            pic_url = f"/api/sno_grocy/picture/{pic_name}" if pic_name else None
            
            inventory.append({
                "stock_id": item.get("id"),
                "product_id": pid,
                "name": prod.get("name", "Unbekannt"),
                "amount": float(item.get("amount", 0)),
                "group": groups.get(str(prod.get("product_group_id")), "Keine Gruppe"),
                "location": locs.get(str(prod.get("location_id")), "Standard Lager"),
                "qu": qus.get(str(prod.get("qu_id_stock")), "Stück"),
                "best_before": item.get("best_before_date"),
                "image_url": pic_url
            })
            
        return {
            "inventory": inventory,
            "locations": locs,
            "quantity_units": qus,
            "groups": groups
        }


# --- Basis Sensoren ---
class GrocyStockTotalSensor(GrocyBaseSensor):
    def __init__(self, c):
        super().__init__(c, "stock", "Lager")
        self._attr_unique_id, self._attr_name, self._attr_icon = f"{self.entry_id}_stock_total", "Lagerbestand (Gesamt)", "mdi:package-variant-closed"
    @property
    def native_value(self): return len(self._get_list("stock"))

class GrocyStockMissingSensor(GrocyBaseSensor):
    def __init__(self, c):
        super().__init__(c, "stock", "Lager")
        self._attr_unique_id, self._attr_name, self._attr_icon = f"{self.entry_id}_stock_missing", "Fehlende Produkte", "mdi:cart-arrow-down"
    @property
    def native_value(self): return len(self.coordinator.data.get("stock_volatile", {}).get("missing_products", []))

class GrocyStockExpiringSensor(GrocyBaseSensor):
    def __init__(self, c):
        super().__init__(c, "stock", "Lager")
        self._attr_unique_id, self._attr_name, self._attr_icon = f"{self.entry_id}_stock_expiring", "Bald ablaufende Produkte", "mdi:clock-alert-outline"
    @property
    def native_value(self): return len(self.coordinator.data.get("stock_volatile", {}).get("expiring_products", []))

class GrocyStockExpiredSensor(GrocyBaseSensor):
    def __init__(self, c):
        super().__init__(c, "stock", "Lager")
        self._attr_unique_id, self._attr_name, self._attr_icon = f"{self.entry_id}_stock_expired", "Abgelaufene Produkte", "mdi:skull-crossbones"
    @property
    def native_value(self): return len(self.coordinator.data.get("stock_volatile", {}).get("expired_products", []))

class GrocyShoppingListSensor(GrocyBaseSensor):
    def __init__(self, c):
        super().__init__(c, "stock", "Lager")
        self._attr_unique_id, self._attr_name, self._attr_icon = f"{self.entry_id}_shopping_list", "Einkaufszettel (Artikel)", "mdi:format-list-checks"
    @property
    def native_value(self): return len(self._get_list("shopping_list"))
    @property
    def extra_state_attributes(self):
        p_dict, g_dict = self._get_products_dict(), self._get_groups_dict()
        detailed_items = []
        for item in self._get_list("shopping_list"):
            pid = str(item.get("product_id"))
            name = item.get("note", "") or p_dict.get(pid, {}).get("name", "Unbekannter Artikel")
            group_name = g_dict.get(str(p_dict.get(pid, {}).get("product_group_id", "none")), "Ohne Gruppe")
            detailed_items.append({"id": str(item.get("id")), "name": name, "amount": item.get("amount", 1), "group": group_name})
        return {"items": detailed_items}

class GrocyEquipmentSensor(GrocyBaseSensor):
    def __init__(self, c):
        super().__init__(c, "stock", "Lager")
        self._attr_unique_id, self._attr_name, self._attr_icon = f"{self.entry_id}_equipment", "Ausstattung", "mdi:toolbox-outline"
    @property
    def native_value(self): return len(self._get_list("equipment"))

class GrocyProductSensor(GrocyBaseSensor):
    def __init__(self, c, p: dict):
        super().__init__(c, "stock", "Lager")
        self._product_id = p.get("id")
        self._attr_unique_id = f"{self.entry_id}_product_{self._product_id}"
        self._attr_name = f"{p.get('name', 'Unbekanntes Produkt')}"
        self._attr_icon = "mdi:food"
    @property
    def native_value(self):
        for item in self._get_list("stock"):
            if str(item.get("product_id")) == str(self._product_id): return float(item.get("amount", 0))
        return 0.0
    @property
    def extra_state_attributes(self): return {"product_id": self._product_id}


# --- Statistiken ---
class GrocyStockValueSensor(GrocyBaseSensor):
    def __init__(self, coordinator, options):
        super().__init__(coordinator, "statistics", "Statistiken")
        self._options = options
        self._attr_unique_id, self._attr_name, self._attr_icon, self._attr_state_class = f"{self.entry_id}_stock_value", "Gesamter Lagerwert", "mdi:cash-multiple", SensorStateClass.TOTAL
    @property
    def native_value(self):
        p_dict = self._get_products_dict()
        total = 0.0
        for item in self._get_list("stock"):
            pid, amount, price = str(item.get("product_id")), float(item.get("amount", 0) or 0), float(item.get("price", 0) or 0)
            if price == 0 and pid in p_dict: price = float(p_dict[pid].get("default_price", 0) or 0)
            total += (price * amount)
        return round(total, 2)
    @property
    def native_unit_of_measurement(self): return "€"

class GrocyMonthlySpendSensor(GrocyBaseSensor):
    def __init__(self, coordinator, options):
        super().__init__(coordinator, "statistics", "Statistiken")
        self._options = options
        self._attr_unique_id, self._attr_name, self._attr_icon, self._attr_state_class = f"{self.entry_id}_monthly_spend", "Ausgaben (letzte 30 Tage)", "mdi:cart-arrow-right", SensorStateClass.MEASUREMENT
    @property
    def native_value(self):
        total = sum((float(l.get("amount", 0) or 0) * float(l.get("price", 0) or 0)) for l in self._get_list("stock_log") if l.get("transaction_type") == "purchase" and str(l.get("undone", "0")) == "0")
        return round(total, 2)
    @property
    def native_unit_of_measurement(self): return "€"

class GrocyMonthlyConsumeSensor(GrocyBaseSensor):
    def __init__(self, coordinator, options):
        super().__init__(coordinator, "statistics", "Statistiken")
        self._options = options
        self._attr_unique_id, self._attr_name, self._attr_icon, self._attr_state_class = f"{self.entry_id}_monthly_consume", "Verbrauch (letzte 30 Tage)", "mdi:cash-minus", SensorStateClass.MEASUREMENT
    @property
    def native_value(self):
        p_dict = self._get_products_dict()
        total = 0.0
        for log in self._get_list("stock_log"):
            if log.get("transaction_type") == "consume" and str(log.get("undone", "0")) == "0":
                pid, amount, price = str(log.get("product_id")), abs(float(log.get("amount", 0) or 0)), float(log.get("price", 0) or 0)
                if price == 0 and pid in p_dict: price = float(p_dict[pid].get("default_price", 0) or 0)
                total += (amount * price)
        return round(total, 2)
    @property
    def native_unit_of_measurement(self): return "€"


# --- Chores, Tasks & Batteries ---
class GrocyChoresTotalSensor(GrocyBaseSensor):
    def __init__(self, c):
        super().__init__(c, "chores", "Hausarbeiten")
        self._attr_unique_id, self._attr_name, self._attr_icon = f"{self.entry_id}_chores_total", "Hausarbeiten (Gesamt)", "mdi:broom"
    @property
    def native_value(self): return len(self._get_list("chores"))

class GrocyChoresOverdueSensor(GrocyBaseSensor):
    def __init__(self, c):
        super().__init__(c, "chores", "Hausarbeiten")
        self._attr_unique_id, self._attr_name, self._attr_icon = f"{self.entry_id}_chores_overdue", "Hausarbeiten (Überfällig)", "mdi:alert-decagram"
    @property
    def native_value(self): return len([c for c in self._get_list("chores") if isinstance(c, dict) and self._is_overdue(c.get("next_estimated_execution_time"))])

class GrocySingleChoreSensor(GrocyBaseSensor):
    def __init__(self, c, chore: dict):
        super().__init__(c, "chores", "Hausarbeiten")
        self._chore_id = str(chore.get("chore_id", chore.get("id")))
        
        # V4.3 FIX: Zuverlässige Namenssuche über das Master-Lexikon
        raw_name = "Hausarbeit"
        if "chore" in chore and isinstance(chore["chore"], dict):
            raw_name = chore["chore"].get("name", raw_name)
        elif "name" in chore:
            raw_name = chore.get("name")
        else:
            # Fallback, falls die API den Namen nicht direkt mitliefert
            chores_objects = c.data.get("chores_objects", [])
            for obj in chores_objects:
                if str(obj.get("id")) == self._chore_id:
                    raw_name = obj.get("name", raw_name)
                    break

        self._attr_unique_id = f"{self.entry_id}_chore_{self._chore_id}"
        self._attr_name = f"Hausarbeit: {raw_name}"
        self._attr_icon = "mdi:spray-bottle"
        
    @property
    def native_value(self):
        for c in self._get_list("chores"):
            cid = str(c.get("chore_id", c.get("id")))
            if cid == self._chore_id: return c.get("next_estimated_execution_time", c.get("next_execution_time")) or "Nicht geplant"
        return "Unbekannt"
    @property
    def extra_state_attributes(self): return {"chore_id": self._chore_id}

class GrocyTasksTotalSensor(GrocyBaseSensor):
    def __init__(self, c):
        super().__init__(c, "tasks", "Aufgaben")
        self._attr_unique_id, self._attr_name, self._attr_icon = f"{self.entry_id}_tasks_total", "Aufgaben (Offen)", "mdi:checkbox-marked-circle-outline"
    @property
    def native_value(self): return len([t for t in self._get_list("tasks") if isinstance(t, dict) and str(t.get("done")) == "0"])

class GrocyTasksOverdueSensor(GrocyBaseSensor):
    def __init__(self, c):
        super().__init__(c, "tasks", "Aufgaben")
        self._attr_unique_id, self._attr_name, self._attr_icon = f"{self.entry_id}_tasks_overdue", "Aufgaben (Überfällig)", "mdi:alert-circle-outline"
    @property
    def native_value(self): return len([t for t in self._get_list("tasks") if isinstance(t, dict) and str(t.get("done")) == "0" and self._is_overdue(t.get("due_date"))])

class GrocySingleTaskSensor(GrocyBaseSensor):
    def __init__(self, c, t: dict):
        super().__init__(c, "tasks", "Aufgaben")
        raw_task = t.get("task", t)
        self._task_id = str(raw_task.get("id", t.get("id")))
        
        # V4.3 FIX: Sichere Namensauslesung
        raw_name = raw_task.get("name", t.get("name", "Aufgabe"))
        self._attr_unique_id = f"{self.entry_id}_task_{self._task_id}"
        self._attr_name = f"Aufgabe: {raw_name}"
        self._attr_icon = "mdi:clipboard-check-outline"
    @property
    def native_value(self):
        for task in self._get_list("tasks"):
            tid = str(task.get("task", task).get("id", task.get("id")))
            if tid == self._task_id: return "Erledigt" if str(task.get("done")) == "1" else "Offen"
        return "Unbekannt"
    @property
    def extra_state_attributes(self): return {"task_id": self._task_id}

class GrocyBatteriesTotalSensor(GrocyBaseSensor):
    def __init__(self, c):
        super().__init__(c, "batteries", "Batterien")
        self._attr_unique_id, self._attr_name, self._attr_icon = f"{self.entry_id}_batteries_total", "Batterien (Gesamt)", "mdi:battery"
    @property
    def native_value(self): return len(self._get_list("batteries"))

class GrocyBatteriesDueSensor(GrocyBaseSensor):
    def __init__(self, c):
        super().__init__(c, "batteries", "Batterien")
        self._attr_unique_id, self._attr_name, self._attr_icon = f"{self.entry_id}_batteries_due", "Batterien (Zu laden)", "mdi:battery-alert"
    @property
    def native_value(self): return len([b for b in self._get_list("batteries") if isinstance(b, dict) and self._is_overdue(b.get("next_estimated_charge_time"))])

class GrocySingleBatterySensor(GrocyBaseSensor):
    def __init__(self, c, b: dict):
        super().__init__(c, "batteries", "Batterien")
        
        self._battery_id = str(b.get("battery_id", b.get("id")))
        
        # V4.3 FIX: Sichere Namensauslesung
        raw_name = "Batterie"
        if "battery" in b and isinstance(b["battery"], dict):
            raw_name = b["battery"].get("name", raw_name)
        elif "name" in b:
            raw_name = b.get("name")
            
        self._attr_unique_id = f"{self.entry_id}_battery_{self._battery_id}"
        self._attr_name = f"Batterie: {raw_name}"
        self._attr_icon = "mdi:battery-charging"
    @property
    def native_value(self):
        for bat in self._get_list("batteries"):
            bid = str(bat.get("battery_id", bat.get("id")))
            if bid == self._battery_id: return bat.get("next_estimated_charge_time") or "Nicht geplant"
        return "Unbekannt"
    @property
    def extra_state_attributes(self): return {"battery_id": self._battery_id}

class GrocyRecipesTotalSensor(GrocyBaseSensor):
    def __init__(self, c):
        super().__init__(c, "recipes", "Rezepte")
        self._attr_unique_id, self._attr_name, self._attr_icon = f"{self.entry_id}_recipes_total", "Rezepte (Gesamt)", "mdi:silverware-fork-knife"
    @property
    def native_value(self): return len(self._get_list("recipes"))

class GrocyMealPlanTodaySensor(GrocyBaseSensor):
    def __init__(self, c):
        super().__init__(c, "recipes", "Rezepte")
        self._attr_unique_id, self._attr_name, self._attr_icon = f"{self.entry_id}_meal_plan_today", "Essensplan (Heute)", "mdi:calendar-star"
    @property
    def native_value(self):
        today = dt_util.now().date().isoformat()
        return len([p for p in self._get_list("meal_plan") if isinstance(p, dict) and p.get("day") == today])
    @property
    def extra_state_attributes(self):
        today = dt_util.now().date().isoformat()
        plans = [p for p in self._get_list("meal_plan") if isinstance(p, dict) and p.get("day") == today]
        recipes = {str(r.get("id")): r.get("name") for r in self._get_list("recipes") if isinstance(r, dict)}
        return {"heute_geplant": [{"recipe_id": str(p.get("recipe_id")), "name": recipes.get(str(p.get("recipe_id")), f"Rezept ID {p.get('recipe_id')}"), "servings": p.get("recipe_servings", 1), "note": p.get("note", "")} for p in plans]}