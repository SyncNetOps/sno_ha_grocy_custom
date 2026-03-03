# **Entwicklerdokumentation: SNO-HA\_Grocy-custom (V1.3.0 Ultimate)**

Willkommen in der offiziellen Entwicklerdokumentation der SNO-HA\_Grocy-custom Integration für Home Assistant. Diese Integration ist weit mehr als ein einfacher API-Wrapper: Sie ist ein intelligentes, proaktives Haushalts- und Küchenmanagementsystem mit nativer KI-Unterstützung.

Diese Dokumentation richtet sich an Entwickler, Contributoren und fortgeschrittene Anwender, die die Architektur verstehen, Fehler beheben oder das System erweitern möchten.

## **1\. Systemarchitektur & Datenfluss**

Die Integration folgt dem modernen Home Assistant (HA) Architektur-Standard für asynchrone Polling-APIs, erweitert um eine Event-getriebene Aktionsschicht und eine autonome KI-Schnittstelle.

### **1.1 Der Lese-Zyklus (One-Way Data Binding)**

1. **Polling:** Der DataUpdateCoordinator (\_\_init\_\_.py) fragt alle UPDATE\_INTERVAL (60s) die Grocy-REST-API ab.  
2. **Bündelung:** Anstatt zig Einzel-Requests zu senden, holt das System alle relevanten Endpunkte (Stock, Chores, Tasks, Recipes, etc.) in einem einzigen, großen asynchronen Durchlauf in ein lokales State-Dictionary.  
3. **Sensoren:** Die Plattformen (sensor.py, todo.py) halten keinen eigenen Zustand. Sie greifen lediglich auf das Dictionary des Coordinators zu und projizieren die Daten als Attribute in das HA-Frontend.

### **1.2 Der Schreib-Zyklus (User Actions)**

1. **Trigger:** Ein User klickt im Frontend, nutzt einen NFC-Tag oder feuert eine Automatisierung.  
2. **Service Call:** Ein in services.yaml definierter und in \_\_init\_\_.py registrierter Service (z.B. consume\_product) wird aufgerufen.  
3. **API Post:** Die api.py sendet die Anforderung an Grocy.  
4. **State-Refresh:** Bei Erfolg triggert die Integration sofort coordinator.async\_request\_refresh(). Die UI aktualisiert sich in Echtzeit.

## **2\. Dateistruktur & Module**

Jede Datei hat eine strikte Trennung der Zuständigkeiten (Separation of Concerns).

### **⚙️ Kern-Logik (Backend)**

* **manifest.json**: Metadaten der Integration. Definiert externe Abhängigkeiten (z.B. aiohttp).  
* **const.py**: Das Gehirn für statische Daten. Enthält alle Options-Keys, Basis-Konfigurationen und – besonders wichtig in V1.3.0 – die Wörterbücher für DEFAULT\_QUANTITY\_UNITS (Standard-Einheiten) und UNIT\_CONVERSIONS (Umrechnungsfaktoren).  
* **api.py**: Der reine REST-Client. Hier findet die **einzige** Netzwerkkommunikation mit dem Grocy-Server statt. Zeichnet sich durch strikte Typisierung (Type Casting in int und float) und Timeouts aus, um HA nicht zu blockieren.  
* **ai\_parser.py**: Das unabhängige KI-Modul. Baut den Prompt zusammen, injiziert das lokale Grocy-Wörterbuch, sendet die Anfrage an Google Gemini und erzwingt einen strikten JSON-Output zur Weiterverarbeitung.  
* **\_\_init\_\_.py**: Der Entry-Point.  
  * Initialisiert den Coordinator.  
  * Führt beim Start den \_async\_setup\_grocy\_environment Check aus (legt fehlende Einheiten an).  
  * Beinhaltet die GrocyPictureView (Ein lokaler Base64-Proxy, der Grocy-Bilder durch das HA-Authentifizierungssystem schleust, damit sie in Dashboards sichtbar werden).  
  * Registriert alle Service-Handler.

### **📊 Entitäten (HA-Plattformen)**

* **sensor.py**: Definiert alle Sensoren. Der wichtigste ist der GrocyMasterInventorySensor, der das komplette Inventar-JSON als Attribut für das Frontend bereithält.  
* **todo.py**: Mappt die Grocy-Einkaufsliste, Hausarbeiten und Aufgaben nativ auf die Home Assistant To-Do Listen Funktion (todo. Domäne).

### **🖥️ User Experience & Frontend**

* **config\_flow.py**: Steuert das Setup- und Options-Menü. Holt dynamisch (live) Produktgruppen und Mengeneinheiten aus Grocy, um dem Nutzer echte Dropdown-Menüs für die Konfiguration anzubieten.  
* **translations/de.json**: Übersetzungen für das Konfigurationsmenü.  
* **services.yaml**: UI-Deklaration aller Services für den HA Automatisierungs-Editor. Erklärt Datentypen, Min/Max-Werte und Beschreibungen.  
* **autoinstall.py**: Das Deployment-Modul. Eine Besonderheit dieser Integration: Beim Start prüft dieses Skript, ob Custom-JavaScript-Karten und YAML-Blueprints auf dem Host-System in /www/ und /blueprints/ existieren und erstellt diese bei Bedarf automatisch aus Hardcoded-Strings.

## **3\. Die KI-Rezept-Engine (Deep Dive V1.3.0)**

Das Killer-Feature der Integration ist die Fähigkeit, unstrukturierten Text in relationale Datenbankeinträge zu verwandeln.

### **3.1 Smart Deduplication (Verhinderung von Duplikaten)**

Um die Datenbank sauber zu halten, übergibt die Integration der KI vorab ein Wörterbuch aller **existierenden** Produkte und Einheiten.

* **Flow:** KI liest "1 kg Mehl" \-\> Sucht im Wörterbuch \-\> Findet ID 14 ("Mehl") und ID 2 ("Gramm") \-\> Gibt im JSON {product\_id: 14, amount: 1000, qu\_id: 2} zurück.

### **3.2 Die "Ignore-for-Stock" Logik**

Nicht alles, was in einem Rezept steht, gehört ins Warenwirtschaftssystem. Die KI hat den strikten Prompt, Dinge wie *Prise, Messerspitze, Schuss, etwas, nach Geschmack* zu erkennen. Sie setzt den Flag ignore\_for\_stock: true. Die \_\_init\_\_.py fängt diesen Flag ab. Das Produkt wird nicht in Grocy angelegt, sondern in eine HTML-formatierte Liste als Notiz unten an die Rezept-Zubereitung (description) gehängt.

### **3.3 Auto-Create & Fallbacks**

Hat der Nutzer "Auto-Create" aktiviert, und die KI meldet ein unbekanntes Produkt (product\_id: \-1), legt die api.py das Produkt automatisch in Grocy an. Um Fehler (HTTP 400\) der strengen Grocy-API zu vermeiden, nutzt die Integration dafür die Standard-Standorte und die in den Optionen gewählte Standard-Produktgruppe und Einheit.

## **4\. Verfügbare Aktionen (Services)**

Alle Aktionen können über HA-Skripte, Automatisierungen oder Dashboard-Buttons aufgerufen werden (sno\_ha\_grocy\_custom.xyz):

* **consume\_product**: Produkt verbrauchen (Optional mit spezifischer Verpackungsgröße).  
* **add\_product**: Produkt einkaufen (Lagermenge erhöhen).  
* **transfer\_product**: Produkt zwischen Lagerorten umbuchen.  
* **execute\_chore**: Hausarbeit als erledigt markieren.  
* **complete\_task**: Aufgabe abschließen.  
* **charge\_battery**: Batterie-Zyklus tracken.  
* **import\_recipe\_via\_ai**: Nimmt einen Rezept-Text (oder Wochenplan) als Parameter text\_input an und durchläuft den gesamten KI-Generierungs-Zyklus.

## **5\. Frontend: Dashboards & Blueprints (via autoinstall.py)**

Die Integration bringt ihr eigenes UI/UX Ökosystem mit, das beim Start automatisch entpackt wird.

### **5.1 Custom Dashboard Karten (JavaScript)**

Nutzer müssen nur /local/sno\_ha\_grocy\_custom/sno-grocy-cards.js als Ressource in HA eintragen.

* **grocy-inventory-explorer-card**: Die virtuelle Speisekammer. Visuelle Darstellung des GrocyMasterInventorySensor inklusive Bild-Proxy.  
* **grocy-household-hub-card**: Kanban-Board für offene Chores und Tasks inkl. Erledigen-Buttons.  
* **grocy-meal-plan-card**: Zeigt das heutige Gericht (inklusive Rezept-Zutaten) an und bietet einen Button zum sofortigen Abbuchen der Zutaten.  
* **grocy-shopping-card**: Interaktiver Einkaufszettel.  
* *(In Planung)* **grocy-smart-recipe-hub**: UI für Copy\&Paste Rezept-Import und KI-Freitext-Kochen.

### **5.2 Blueprints (Automatisierungsvorlagen)**

Nutzer finden diese im HA Automatisierungs-Menü unter Vorlagen.

* **NFC-Verbrauch (nfc\_consume.yaml)**: Erlaubt es, NFC-Sticker mit HA zu scannen und direkt eine festgelegte Menge eines Grocy-Produkts zu verbrauchen.  
* **Hausarbeit-Erinnerung (chore\_reminder.yaml)**: Sendet Push-Nachrichten bei überfälligen Hausarbeiten. Die Benachrichtigung hat "Actionable Buttons", mit denen die Hausarbeit direkt aus der Notification heraus als erledigt markiert werden kann.

## **6\. Einstellungsmöglichkeiten (Options Flow)**

Die Integration lässt sich nach der Installation komplett individualisieren:

* **Modus-Schalter (Tasks, Chores, Shopping)**: Soll das Modul als Sensor, als interaktive Todo-Liste, beides oder gar nicht in HA geladen werden?  
* **Erweiterte Statistiken**: Aktiviert rechenintensive Sensoren (z.B. aktueller monetärer Lagerwert).  
* **KI-Setup**:  
  * **KI Aktivieren**: Hauptschalter.  
  * **API-Key**: Geschütztes Feld für den Gemini Key.  
  * **Auto-Create**: Dürfen unbekannte Rezeptzutaten selbstständig im Grocy-Stamm angelegt werden?  
  * **Standard-Produktgruppe**: Dynamisches Dropdown. Ordnet neue Artikel einer bestimmten Gruppe (z.B. "KI Import") zu.  
  * **Standard-Mengeneinheit**: Dynamisches Dropdown. Fallback für das Erstellen neuer Artikel.  
  * **Auto-Sync Einkaufsliste**: Werden fehlende Zutaten aus KI-Rezepten direkt auf den Einkaufszettel gesetzt?

## **7\. Hinweise für die Weiterentwicklung (Best Practices)**

1. **Async is King:** Nutze ausschließlich await und aiohttp für Netzwerk-Anfragen. Home Assistant reagiert extrem empfindlich auf blockierenden Code.  
2. **Error Handling:** Da APIs (Grocy und Google Gemini) ausfallen können, ist asyncio.timeout Pflicht. Fange Fehler sauber ab und logge sie per LOGGER.error, ohne die Schleife (den Event-Loop) crashen zu lassen.  
3. **Grocy Schema-Änderungen:** Grocy (PHP) ändert gelegentlich Datenbank-Schemata (z.B. der Wegfall von qu\_factor\_purchase\_to\_stock in der Produkttabelle in neueren Versionen). Prüfe bei Payload-Fehlern (HTTP 400\) immer zuerst die aktuelle Grocy Swagger/OpenAPI Spezifikation.  
4. **Strikte Typisierung:** Bei api.py POST-Requests müssen Zahlen zwingend als int() oder float() gecastet werden. Die Grocy REST-API lehnt Strings (