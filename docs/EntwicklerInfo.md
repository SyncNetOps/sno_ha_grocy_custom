# Entwicklerdokumentation: SNO-HA_Grocy-custom (v1.0.3)

Willkommen in der Entwicklerdokumentation für die `sno_ha_grocy_custom` Integration für Home Assistant. Diese Dokumentation dient als Leitfaden für die Weiterentwicklung, Fehlerbehebung und Architekturverständnis der Codebase.

## 1. Architektur-Überblick

Die Integration fungiert als Brücke zwischen der **Grocy API** und **Home Assistant**. Sie ist nach dem modernen Home Assistant Integrationsstandard aufgebaut und nutzt asynchrone Programmierung (`asyncio`, `aiohttp`).

**Der grundlegende Datenfluss:**
1. **API-Schicht (`api.py`)**: Kommuniziert direkt mit dem Grocy-Server über HTTP-REST.
2. **Daten-Koordinator (`__init__.py`)**: Nutzt den `DataUpdateCoordinator` von Home Assistant, um die API zyklisch (Polling) abzufragen und die Daten im RAM von Home Assistant zwischenzuspeichern.
3. **Plattformen (`sensor.py`, `todo.py`)**: Greifen auf die zwischengespeicherten Daten des Koordinators zu und erstellen daraus Home Assistant Entitäten.
4. **Services (`__init__.py` & `services.yaml`)**: Leiten Benutzeraktionen (z.B. Produkt verbrauchen) direkt über die API-Schicht an Grocy weiter und fordern danach ein asynchrones Refresh des Koordinators an.

---

## 2. Dateistruktur und Zusammenhänge

Jede Datei in dieser Integration hat einen strikt abgegrenzten Zuständigkeitsbereich (Separation of Concerns). Im Folgenden werden alle Dateien detailliert aufgeschlüsselt.

### 2.1 `manifest.json`
* **Zweck:** Definiert die Metadaten der Integration für Home Assistant.
* **Inhalt:** Name, Domäne (`sno_ha_grocy_custom`), Version (`v1.0.3`), Issue-Tracker und externe Abhängigkeiten (z.B. `aiohttp`).
* **Wichtig:** Wenn neue externe Python-Bibliotheken benötigt werden, müssen diese im Array `"requirements"` hinzugefügt werden.

### 2.2 `const.py`
* **Zweck:** Zentrale Ablage für alle projektweiten Konstanten.
* **Inhalt:** * `DOMAIN` (der interne Name der Integration).
  * Setup-Keys (z.B. `CONF_URL`, `CONF_API_KEY`).
  * `UPDATE_INTERVAL`: Das Standard-Polling-Intervall (aktuell 60 Sekunden).
  * Konstanten für die Options-Modi (`MODE_NONE`, `MODE_SENSOR`, `MODE_TODO`, `MODE_BOTH`).
* **Wichtig:** Keine hartcodierten Strings in der Logik verwenden. Alles gehört in diese Datei, um Fehler bei Umbenennungen zu vermeiden.

### 2.3 `api.py`
* **Zweck:** Der Grocy REST-API Client. Dies ist die **einzige** Datei, die direkte Netzwerkanfragen an den Grocy Server sendet.
* **Funktionsweise:** * Die Klasse `GrocyApiClient` kapselt `aiohttp.ClientSession`.
  * `test_connection()`: Wird vom Config-Flow genutzt, um beim Setup die Credentials zu validieren.
  * `_async_get()` und `_async_post()`: Private Basis-Methoden mit integrierter Fehlerbehandlung und Timeouts (via `asyncio.timeout`).
  * **Datenabruf-Methoden:** z.B. `async_get_stock()`, `async_get_chores()`.
  * **Aktions-Methoden:** z.B. `async_add_product()`, `async_execute_chore()`.
* **Weiterentwicklung:** Wenn Grocy ein neues Feature bekommt, muss hier die entsprechende Endpunkt-Funktion implementiert werden, bevor sie in HA genutzt werden kann.

### 2.4 `__init__.py`
* **Zweck:** Der Einstiegspunkt (Entry Point) der Integration.
* **Hauptfunktionen:**
  1. `async_setup_entry`: Wird beim Starten der Integration aufgerufen.
  2. Initialisiert den `GrocyApiClient` und den `DataUpdateCoordinator`. Der Koordinator holt in einem Rutsch alle relevanten Daten (Stock, Chores, Tasks, Batteries, etc.) in ein großes Dictionary. Dies verhindert ein "Zuspammen" der Grocy-API mit hunderten Einzelanfragen.
  3. Startet die Plattformen via `hass.config_entries.async_forward_entry_setups` (`sensor` und `todo`).
  4. Registriert die Custom Services (z.B. `consume_product`, `transfer_product`).
  5. **`GrocyPictureView`**: Ein intelligenter lokaler Webserver-Proxy innerhalb von HA. Da Grocy-Bilder per API-Key geschützt sind und HA Dashboards diesen Key nicht injizieren können, routet diese View das Bild durch HA und hängt den Key serverseitig an.
  6. Ruft `async_install_assets()` aus der `autoinstall.py` auf.

### 2.5 `config_flow.py`
* **Zweck:** Handhabt das User-Interface beim Hinzufügen der Integration und bei nachträglichen Einstellungsänderungen.
* **Inhalt:**
  * `GrocyConfigFlow`: Verarbeitet die Initialeingabe (URL und API-Key) und prüft die Verbindung via `api.test_connection()`.
  * `GrocyOptionsFlowHandler`: Erlaubt dem User nachträglich zu definieren, wie Aufgaben, Hausarbeiten und Einkaufslisten in HA dargestellt werden sollen (Nur Sensoren, Nur To-Do Liste, Beides oder Deaktiviert).
* **Weiterentwicklung:** Bei neuen Einstellungsoptionen müssen diese sowohl in den `Schema`-Definitionen als auch im `OptionsFlow` hinterlegt werden.

### 2.6 `sensor.py`
* **Zweck:** Bereitstellung von Status-Sensoren (Inventory, ablaufende Produkte, fällige Hausarbeiten etc.).
* **Architektur:**
  * Nutzt das Konzept der `CoordinatorEntity`. Die Sensoren rufen keine eigenen Daten ab, sondern greifen asynchron auf `self.coordinator.data` zu.
  * `GrocyBaseSensor`: Basisklasse, die Boilerplate-Code für Namensgebung, Unique-IDs und Attribut-Zuweisungen spart.
  * Spezifische Klassen wie `GrocyMasterInventorySensor` oder `GrocyStockExpiringSensor`.
* **Wichtig:** Die `async_setup_entry` Logik prüft vor der Sensor-Instanziierung die in `config_flow` gesetzten Options (z.B. `options.get(CONF_MODE_TASKS)`), um zu verhindern, dass unerwünschte Sensoren registriert werden.

### 2.7 `todo.py`
* **Zweck:** Native Unterstützung für die Home Assistant To-Do Plattform.
* **Architektur:**
  * Beinhaltet Listen-Klassen (`GrocyTasksTodoList`, `GrocyChoresTodoList`, `GrocyShoppingTodoList`), die von `TodoListEntity` erben.
  * Übersetzt die Grocy JSON-Antworten in HA native `TodoItem` Objekte.
  * Handhabt Statusänderungen (Abhaken in HA -> Senden an `api.py` -> Refresh des Coordinators).

### 2.8 `services.yaml`
* **Zweck:** UI-Deklaration für die Home Assistant Entwicklerwerkzeuge und Automatisierungen.
* **Inhalt:** Erklärt HA, welche Services verfügbar sind (z.B. `sno_ha_grocy_custom.consume_product`), welche Felder sie akzeptieren (inklusive Beschreibungen, Typen und Maximalwerten) und welche Selektoren genutzt werden sollen.
* **Weiterentwicklung:** Jeder neue Service in `__init__.py` **muss** hier dokumentiert werden, sonst ist er im HA-Frontend unsichtbar.

### 2.9 `autoinstall.py`
* **Zweck:** User-Experience / QoL (Quality of Life) Feature.
* **Funktion:** Bei jedem Start der Integration prüft dieses Skript, ob die mitgelieferten Blueprints (z.B. für NFC-Scans oder Benachrichtigungen) und Custom Frontend Cards (JS Dateien) physisch auf dem Home Assistant Host existieren. Ist dies nicht der Fall, werden sie automatisch in `/config/blueprints/` und `/config/www/sno_ha_grocy_custom/` erzeugt.
* **Vorteil:** Erspart dem Endanwender komplexe manuelle Kopiervorgänge.
* **Weiterentwicklung:** Wenn du neue Dashboards, Karten oder Blueprints entwickelst, pflege den String-Inhalt als Konstante in diese Datei ein.

---

## 3. Workflow für Erweiterungen (How-To)

Wenn du ein **neues Feature** hinzufügen möchtest (Beispiel: *Eine neue Funktion, um ein Rezept hinzuzufügen*), gehe wie folgt vor:

1. **`api.py` erweitern:**
   Implementiere die Methode, die den HTTP POST/GET an den Grocy Endpunkt sendet.
   ```python
   async def async_add_recipe(self, name: str) -> bool:
       return await self._async_post("/api/recipes", {"name": name})

 * Dienst registrieren (__init__.py):
   Füge in async_setup_entry unter dem Abschnitt "Services" den Handler hinzu:
   async def handle_add_recipe(call):
    name = call.data.get("name")
    if name:
        await call_and_refresh(client.async_add_recipe(name))
hass.services.async_register(DOMAIN, "add_recipe", handle_add_recipe)

 * Benutzeroberfläche definieren (services.yaml):
   Mache den Dienst für den Endanwender in HA sichtbar:
   add_recipe:
  name: "Rezept hinzufügen"
  description: "Fügt ein neues Rezept in Grocy hinzu."
  fields:
    name:
      name: "Rezeptname"
      required: true
      selector: { text: {} }

4. Best Practices für dieses Repository
 * Fehlerbehandlung: Verlasse dich in api.py nicht darauf, dass der Grocy Server antwortet. Benutze asyncio.timeout. Wenn Grocy nicht erreichbar ist, werfe eine Exception, die vom DataUpdateCoordinator als UpdateFailed gefangen wird.
 * Performance: Home Assistant blockiert bei synchronen Requests. Nutze immer await und aiohttp.
 * State Updates: Wenn ein Service ausgeführt wird (z.B. Chore erledigt), ändere nicht den Sensor-Wert manuell. Setze den API-Call ab und nutze await coordinator.async_request_refresh(), damit die frischen Daten sauber von Grocy in alle Entitäten propagiert werden.
 * Lokalisierung: Halte Rückmeldungen für den Anwender benutzerfreundlich.
5. Troubleshooting (Fehlersuche)
 * Sensoren aktualisieren sich nicht: Überprüfe den DataUpdateCoordinator im __init__.py. Wahrscheinlich schlägt ein API Call fehl und bricht das gesammelte Polling ab. Prüfe das HA Fehler-Log auf UpdateFailed.
 * Bilder laden im Dashboard nicht: Die GrocyPictureView in __init__.py könnte Probleme haben, wenn die URL-Struktur in der Grocy-Antwort von Grocy-Version zu Grocy-Version variiert. Prüfe, ob der Regex/Base64 Encoder saubere Dateinamen extrahiert.
Dokumentation erstellt für v1.0.3 der sno_ha_grocy_custom Integration.

