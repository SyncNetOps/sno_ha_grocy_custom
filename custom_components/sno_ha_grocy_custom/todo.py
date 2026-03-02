"""Native To-Do Listen Unterstützung für Grocy (V4)."""
from homeassistant.components.todo import TodoListEntity, TodoItem, TodoItemStatus, TodoListEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER, MODE_TODO, MODE_BOTH, CONF_MODE_TASKS, CONF_MODE_CHORES, CONF_MODE_SHOPPING

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    client = data["client"]
    options = entry.options

    lists = []

    if options.get(CONF_MODE_TASKS, MODE_BOTH) in [MODE_TODO, MODE_BOTH]:
        lists.append(GrocyTasksTodoList(coordinator, client, entry.entry_id))
    
    if options.get(CONF_MODE_CHORES, MODE_BOTH) in [MODE_TODO, MODE_BOTH]:
        lists.append(GrocyChoresTodoList(coordinator, client, entry.entry_id))

    if options.get(CONF_MODE_SHOPPING, MODE_BOTH) in [MODE_TODO, MODE_BOTH]:
        lists.append(GrocyShoppingTodoList(coordinator, client, entry.entry_id))

    async_add_entities(lists)


class GrocyTasksTodoList(CoordinatorEntity, TodoListEntity):
    _attr_supported_features = (TodoListEntityFeature.CREATE_TODO_ITEM | TodoListEntityFeature.UPDATE_TODO_ITEM | TodoListEntityFeature.DELETE_TODO_ITEM)

    def __init__(self, coordinator, client, entry_id):
        super().__init__(coordinator)
        self.client = client
        self._attr_unique_id = f"{entry_id}_todo_tasks"
        self._attr_name = "Grocy Aufgaben"

    @property
    def todo_items(self) -> list[TodoItem] | None:
        tasks = self.coordinator.data.get("tasks", [])
        items = []
        for t in tasks:
            if isinstance(t, dict):
                status = TodoItemStatus.COMPLETED if str(t.get("done")) == "1" else TodoItemStatus.NEEDS_ACTION
                
                # FIX: Namen-Auslesung
                if "task" in t and isinstance(t["task"], dict):
                    name = t["task"].get("name", "Aufgabe")
                    uid = str(t["task"].get("id", t.get("id")))
                else:
                    name = t.get("name", "Aufgabe")
                    uid = str(t.get("id"))
                    
                items.append(TodoItem(uid=uid, summary=name, status=status))
        return items

    async def async_create_todo_item(self, item: TodoItem) -> None:
        await self.client.async_add_task(item.summary)
        await self.coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        if item.status == TodoItemStatus.COMPLETED:
            await self.client.async_complete_task(int(item.uid))
            await self.coordinator.async_request_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        for uid in uids:
            await self.client.async_delete_task(int(uid))
        await self.coordinator.async_request_refresh()


class GrocyChoresTodoList(CoordinatorEntity, TodoListEntity):
    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM

    def __init__(self, coordinator, client, entry_id):
        super().__init__(coordinator)
        self.client = client
        self._attr_unique_id = f"{entry_id}_todo_chores"
        self._attr_name = "Grocy Hausarbeiten"

    @property
    def todo_items(self) -> list[TodoItem] | None:
        chores = self.coordinator.data.get("chores", [])
        chores_objects = self.coordinator.data.get("chores_objects", [])
        items = []
        for c in chores:
            if isinstance(c, dict):
                chore_id = str(c.get("chore_id", c.get("id")))
                name = "Hausarbeit"
                
                if "chore" in c and isinstance(c["chore"], dict):
                    name = c["chore"].get("name", name)
                elif "name" in c:
                    name = c.get("name")
                else:
                    # Fallback auf das Master-Lexikon
                    for obj in chores_objects:
                        if str(obj.get("id")) == chore_id:
                            name = obj.get("name", name)
                            break
                            
                items.append(TodoItem(uid=chore_id, summary=name, status=TodoItemStatus.NEEDS_ACTION))
        return items

    async def async_update_todo_item(self, item: TodoItem) -> None:
        if item.status == TodoItemStatus.COMPLETED:
            await self.client.async_execute_chore(int(item.uid))
            await self.coordinator.async_request_refresh()


class GrocyShoppingTodoList(CoordinatorEntity, TodoListEntity):
    _attr_supported_features = (TodoListEntityFeature.CREATE_TODO_ITEM | TodoListEntityFeature.UPDATE_TODO_ITEM | TodoListEntityFeature.DELETE_TODO_ITEM)

    def __init__(self, coordinator, client, entry_id):
        super().__init__(coordinator)
        self.client = client
        self._attr_unique_id = f"{entry_id}_todo_shopping"
        self._attr_name = "Grocy Einkaufszettel"

    @property
    def todo_items(self) -> list[TodoItem] | None:
        shopping_list = self.coordinator.data.get("shopping_list", [])
        items = []
        for item in shopping_list:
            if isinstance(item, dict):
                note = item.get("note")
                amount = item.get("amount", "1")
                product_id = item.get('product_id')
                
                if note:
                    summary = note
                elif product_id:
                    summary = f"Produkt-ID {product_id} ({amount}x)"
                else:
                    summary = "Unbekannter Artikel"
                    
                items.append(TodoItem(uid=str(item.get("id")), summary=summary, status=TodoItemStatus.NEEDS_ACTION))
        return items

    async def async_create_todo_item(self, item: TodoItem) -> None:
        await self.client.async_add_shopping_list_item(item.summary)
        await self.coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        if item.status == TodoItemStatus.COMPLETED:
            await self.client.async_delete_shopping_list_item(int(item.uid))
            await self.coordinator.async_request_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        for uid in uids:
            await self.client.async_delete_shopping_list_item(int(uid))
        await self.coordinator.async_request_refresh()