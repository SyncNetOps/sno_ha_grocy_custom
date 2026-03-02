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




# Entwicklerdokumentation: Frontend, Blueprints & Sensoren

Diese Dokumentation beschreibt das exakte Zusammenspiel der UI-Elemente, Automatisierungen und der Sensoren der `sno_ha_grocy_custom` Integration. Sie richtet sich an Entwickler, die Dashboards, Automatisierungen oder die Datenaufbereitung erweitern möchten.

---

## 1. Das Architektur-Muster (Zusammenspiel & Abhängigkeiten)

Die Integration nutzt ein strikt **unidirektionales Datenfluss-Muster (One-Way Data Binding)** für das Frontend, um die Performance in Home Assistant hoch zu halten und die Grocy API zu schonen.

**Der Lese-Zyklus (Daten-Anzeige):**
1. **Backend:** Der `DataUpdateCoordinator` holt alle Grocy-Daten als großes JSON-Objekt.
2. **Sensoren:** Die Klassen in `sensor.py` greifen sich ihre spezifischen Listen (z.B. `meal_plan`) aus dem Coordinator. Der native Zustand (`native_value`) des Sensors ist meist nur ein Zähler (z.B. "3"), aber die **kompletten Rohdaten** werden in die `extra_state_attributes` geschrieben.
3. **Frontend (Karten):** Die Custom JS-Cards aus `autoinstall.py` fragen **niemals** selbst die Grocy-API ab. Sie lauschen via Home Assistant Websocket auf Statusänderungen der Sensoren und rendern ihre HTML-Oberfläche ausschließlich anhand der JSON-Objekte aus den `extra_state_attributes`.

**Der Schreib-Zyklus (Benutzer-Interaktion):**
1. Ein User klickt in einer Karte auf einen Button oder nutzt einen Blueprint (NFC).
2. Es wird ein nativer HA-Service aufgerufen (z.B. `sno_ha_grocy_custom.consume_product`).
3. Der Service (`__init__.py`) sendet den API-Call an Grocy.
4. Nach Erfolg löst der Service **sofort** ein `coordinator.async_request_refresh()` aus. 
5. Die Sensoren aktualisieren ihre Attribute -> Die Karten rendern sich in Echtzeit neu.

---

## 2. Sensoren und ihre Attribute (`sensor.py`)

Die Sensoren sind das Herzstück der Datenbereitstellung. Jeder Entwickler muss wissen, welche Daten in den Attributen (Payload) versteckt sind.

### 2.1 Der "Baukasten-Motor": `GrocyMasterInventorySensor`
* **Zustand (`native_value`):** Letzter Aktualisierungszeitpunkt oder Gesamt-Bestands-Count.
* **Attribute:** Beinhaltet das komplette, unmodifizierte Array des Lagerbestands (Stock) inklusive verschachtelter Produkt-Details, Standort-IDs und Barcodes.
* **Abhängigkeit:** Dies ist der primäre Datenlieferant für die *Inventory Explorer-Karte*.

### 2.2 Bestands-Sensoren (Stock)
Alle folgenden Sensoren filtern den Master-Stock basierend auf Grocy-Logik. Sie liefern als State eine Zahl und als Attribut die gefilterte Liste (`items`).
* **`GrocyStockTotalSensor`:** Alle Produkte im Bestand.
* **`GrocyStockMissingSensor`:** Produkte, die unterhalb des in Grocy definierten Mindestbestands (min_stock_amount) liegen.
* **`GrocyStockExpiringSensor`:** Produkte, deren Ablaufdatum in den nächsten X Tagen (meist 5) erreicht wird.
* **`GrocyStockExpiredSensor`:** Produkte, deren Haltbarkeitsdatum in der Vergangenheit liegt.
* **`GrocyStockValueSensor`:** (Gesteuert durch Options-Flow `CONF_ADVANCED_STATS`) Berechnet den monetären Gesamtwert des Lagers anhand von Menge x Preis.

### 2.3 Mahlzeiten & Rezepte
* **`GrocyRecipesTotalSensor`:** * **State:** Anzahl aller angelegten Rezepte.
* **`GrocyMealPlanTodaySensor`:** * **State:** Anzahl der für den heutigen Tag (`dt_util.now().date()`) geplanten Mahlzeiten.
  * **Attribute:** Enthält ein Array `plans` mit den kompletten Rezept-Details für den heutigen Tag.
  * **Abhängigkeit:** Datenlieferant für die *Grocy Meal Plan Card*.

### 2.4 Batterien & Equipment
* **`GrocyEquipmentSensor`:** Liefert Geräte-Handbücher und Garantie-Daten (Attribut `items`).
* **`GrocyBatteriesTotalSensor`:** Gesamtzahl der in Grocy verwalteten Batterien.
* **`GrocyBatteriesDueSensor`:**
  * **State:** Anzahl der entladenen / fälligen Batterien.
  * **Attribute:** Beinhaltet `battery_id` der fälligen Batterien, um per Service direkt das Aufladen tracken zu können.

---

## 3. Die Custom Dashboard-Karten (`autoinstall.py`)

Die JS-Dateien dieser Karten werden von der Integration automatisch in `/config/www/sno_ha_grocy_custom/` erzeugt und im HA-Frontend registriert.

* **`grocy-inventory-explorer-card`** (Virtuelle Speisekammer / Inventory Explorer)
  * **Funktion:** Visualisiert den Lagerbestand interaktiv (Suchen, Filtern, Sortieren).
  * **Zusammenspiel:** Nutzt den `GrocyMasterInventorySensor`. Verwendet die Grocy-Picture Proxy-View (`/api/sno_grocy/picture/`), um Bilder datenschutzkonform im Dashboard anzuzeigen.
* **`grocy-household-hub-card`** (Hausarbeiten & Aufgaben)
  * **Funktion:** Zeigt fällige Chores und Tasks in einem modernen UI an und bietet Buttons zum "Erledigen".
  * **Zusammenspiel:** Feuert bei Knopfdruck die Services `execute_chore` und `complete_task`.
* **`grocy-meal-plan-card`** (Heutiger Essensplan)
  * **Funktion:** Zeigt Bild, Name und (falls vorhanden) Zutaten für das heutige Rezept an.
  * **Zusammenspiel:** Parst die `plans` Attribute des `GrocyMealPlanTodaySensor`. Bei Klick auf "Verbrauchen" wird der Service `consume_recipe` abgefeuert.
* **`grocy-shopping-card`** (Einkaufsliste sortiert)
  * **Funktion:** Native Ansicht des Einkaufszettels.
  * **Zusammenspiel:** Zieht Daten aus der Shopping-List Instanz. Bietet "In den Einkaufswagen" (Hinzufügen) Logik, die in Grocy als Kauf (`transaction_type: purchase`) verarbeitet wird (`add_product` Service).

---

## 4. Blueprints / Automatisierungen (`autoinstall.py`)

Blueprints sind standardisierte Automatisierungsvorlagen für den Endnutzer. Sie werden automatisch im Ordner `/config/blueprints/automation/sno_ha_grocy_custom/` erstellt.

### 4.1 Grocy NFC-Verbrauch (`nfc_consume.yaml` / `BP_NFC`)
* **Zweck:** Barrierefreier Vorratsabbau in der Küche per Smartphone und NFC-Sticker.
* **Funktionsweise (Ablauf):**
  1. **Trigger:** Lauscht auf das Home Assistant Event `tag_scanned`.
  2. **Bedingung (Input):** Die `tag_id` muss mit dem vom User im Blueprint gewählten NFC-Tag übereinstimmen.
  3. **Aktion:** Ruft den Service `sno_ha_grocy_custom.consume_product` auf.
  4. **Datenübergabe:** Übergibt die in den Blueprint-Inputs definierte `entity_id` (den Produkt-Sensor) und die fest definierte `amount` (Menge, Standard 1.0).
* **Entwickler-Fokus:** Wenn sich in `services.yaml` die Parameter für `consume_product` ändern, **muss** dieser Blueprint zwingend angepasst werden.

### 4.2 Grocy Hausarbeit-Erinnerung (`chore_reminder.yaml` / `BP_CHORE`)
* **Zweck:** Proaktives Task-Management per Smartphone-Pushnachricht (Actionable Notification).
* **Funktionsweise (Ablauf):**
  1. **Trigger:** Zeitgesteuert (z.B. täglich um 18:00 Uhr).
  2. **Bedingung:** Prüft, ob der im Blueprint hinterlegte Sensor für überfällige Hausarbeiten (z.B. `GrocyChoresOverdueSensor`) einen Wert `> 0` hat.
  3. **Aktion 1 (Benachrichtigung):** Sendet eine Benachrichtigung an das Mobile Device (`notify.mobile_app_...`).
  4. **Aktion 2 (Interaktion):** Die Nachricht enthält spezifische `actions` (Buttons) im Payload – z.B. "action: ERLEDIGT".
  5. **Aktion 3 (Event-Handling):** Der Blueprint lauscht auf das Event `mobile_app_notification_action`. Wird "ERLEDIGT" geklickt, ruft der Blueprint `sno_ha_grocy_custom.execute_chore` auf.
* **Entwickler-Fokus:** Dieser Blueprint ist ein Paradebeispiel für den UX-Mehrwert. Bei Erweiterungen (z.B. "Aufgabe verschieben") müssen neue Services in `__init__.py` geschrieben und hier als weitere `actions` in den Push-Payload eingebettet werden.

---

### Checkliste für Code-Änderungen an diesen Komponenten:
- [ ] Wird eine neue Eigenschaft eines Produkts im Dashboard gebraucht? -> In `sensor.py` (Master Sensor) sicherstellen, dass die Eigenschaft aus dem API-JSON nicht verworfen wird.
- [ ] Wird ein neuer Service in `__init__.py` registriert? -> Muss zwingend in `services.yaml` dokumentiert werden, sonst können Custom Cards und Blueprints ihn nicht via HA aufrufen.
- [ ] Wurde das Design einer Karte geändert? -> Den JS-Code als Einzeiler (minified/escaped) im Python-String in `autoinstall.py` aktualisieren!
- [ ] 
