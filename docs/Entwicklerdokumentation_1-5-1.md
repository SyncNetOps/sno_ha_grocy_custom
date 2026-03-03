# **Entwicklerdokumentation: SNO-HA\_Grocy-custom (V1.5.2 Final)**

Willkommen in der offiziellen Entwicklerdokumentation der sno\_ha\_grocy\_custom Integration für Home Assistant. Diese Integration ist ein intelligentes, proaktives Haushalts- und Küchenmanagementsystem mit nativer KI-Unterstützung (Google Gemini).

Diese Dokumentation richtet sich an Entwickler, Contributoren und fortgeschrittene Anwender, die die Architektur verstehen, Fehler beheben oder das System erweitern möchten.

## **1\. Systemarchitektur & Datenfluss**

Die Integration folgt dem modernen Home Assistant (HA) Architektur-Standard für asynchrone Polling-APIs, erweitert um eine Event-getriebene Aktionsschicht und eine autonome KI-Schnittstelle.

### **1.1 Der Lese-Zyklus (One-Way Data Binding)**

1. **Polling:** Der DataUpdateCoordinator (in \_\_init\_\_.py) fragt alle UPDATE\_INTERVAL (Standard: 60s) die Grocy-REST-API ab.  
2. **Bündelung:** Anstatt dutzende Einzel-Requests zu senden, holt das System alle relevanten Endpunkte (Stock, Locations, Groups, Units, Chores, Tasks, Recipes, etc.) in einem einzigen, großen asynchronen Durchlauf in ein lokales State-Dictionary.  
3. **Entitäten:** Die Plattformen (sensor.py, todo.py) halten keinen eigenen Zustand. Sie greifen lediglich auf das Dictionary des Coordinators zu und projizieren die Daten als Attribute in das HA-Frontend.

### **1.2 Der Schreib-Zyklus (User Actions)**

1. **Trigger:** Ein User interagiert im Frontend (z.B. Smart Recipe Hub Karte), nutzt einen NFC-Tag oder triggert eine Automatisierung.  
2. **Service Call:** Ein in services.yaml definierter Service wird aufgerufen.  
3. **API Call:** Die api.py sendet den entsprechenden POST/DELETE Request an Grocy.  
4. **State-Refresh:** Bei Erfolg triggert die Integration sofort coordinator.async\_request\_refresh(). Die Home Assistant UI aktualisiert sich dadurch in Echtzeit.

## **2\. Dateistruktur & Module**

Die Integration verwendet eine strikte Trennung der Zuständigkeiten (Separation of Concerns).

### **⚙️ Kern-Logik (Backend)**

* **manifest.json**: Metadaten der Integration. Definiert externe Abhängigkeiten (z.B. aiohttp) und die Version.  
* **const.py**: Zentrale Datei für statische Daten. Enthält alle Options-Keys und die System-Wörterbücher für DEFAULT\_QUANTITY\_UNITS (Standard-Einheiten) und UNIT\_CONVERSIONS (Umrechnungsfaktoren).  
* **api.py**: Der reine REST-Client. Hier findet die **einzige** Netzwerkkommunikation mit dem Grocy-Server statt. Alle Payloads werden hier strikt typisiert (int(), float()), um Fehler durch die Grocy PHP-Backend-Validierung (HTTP 400\) zu vermeiden.  
* **ai\_parser.py**: Das unabhängige KI-Modul. Baut den Prompt zusammen, injiziert lokale Grocy-Wörterbücher, sendet die Anfrage an Google Gemini und erzwingt einen strikten JSON-Output zur Weiterverarbeitung.  
* **\_\_init\_\_.py**: Der Entry-Point der Integration.  
  * Initialisiert den Coordinator und die API.  
  * Führt beim Start den \_async\_setup\_grocy\_environment Check aus (legt bei Bedarf fehlende Einheiten in Grocy an).  
  * Stellt die GrocyPictureView bereit (Ein lokaler Base64-Proxy, der Grocy-Bilder durch das HA-Authentifizierungssystem schleust).  
  * Registriert alle Service-Handler (inklusive der komplexen import\_recipe\_via\_ai Logik).

### **📊 Entitäten (HA-Plattformen)**

* **sensor.py**: Definiert alle Sensoren. Der wichtigste ist der GrocyMasterInventorySensor, der das komplette Inventar als JSON-Attribut für das Frontend bereithält.  
* **todo.py**: Mappt die Grocy-Einkaufsliste, Hausarbeiten und Aufgaben nativ auf die Home Assistant To-Do Listen (todo. Domäne).

### **🖥️ User Experience & Frontend**

* **config\_flow.py**: Steuert das Setup- und Options-Menü. Kommuniziert live mit Grocy, um dynamische Dropdowns (z.B. für Produktgruppen) zu generieren.  
* **translations/de.json**: Deutsche Übersetzungen für das Konfigurationsmenü.  
* **services.yaml**: UI-Deklaration aller Services für den HA Automatisierungs-Editor (Datentypen, Min/Max-Werte, Beschreibungen).  
* **autoinstall.py**: Automatisches Deployment-Modul. Prüft beim Start, ob Custom-JavaScript-Karten und YAML-Blueprints auf dem Host-System in /www/ und /blueprints/ existieren und erstellt diese bei Bedarf aus Hardcoded-Strings. *Besonderheit in V1.5.2:* Enthält hochentwickelte dynamische Fallbacks für die UI-Editoren, falls Backend-Daten fehlen.

## **3\. Die KI-Rezept-Engine (Deep Dive)**

Das Kernstück der Integration ist die Fähigkeit, unstrukturierten Text in relationale Datenbankeinträge zu verwandeln. Der Service import\_recipe\_via\_ai führt dabei folgende Schritte aus:

### **3.1 Smart Deduplication & Session Cache**

Um die Datenbank sauber zu halten, übergibt die Integration der KI vorab ein Wörterbuch aller existierenden Produkte.

* Die KI sucht für Text-Zutaten (z.B. "500g Tomaten") die passendste product\_id (z.B. ID 22: "Dosentomaten").  
* **Bulk-Collision Fix:** Wenn mehrere Rezepte auf einmal importiert werden und eine neue Zutat erfordern (z.B. "Hackfleisch"), speichert die \_\_init\_\_.py die neu erstellte ID in einem session\_created\_products Cache. Das verhindert UNIQUE Constraint SQL-Fehler beim zweiten Rezept.

### **3.2 Die "Ignore-for-Stock" Logik (Gewürze)**

Nicht alles gehört in ein Warenwirtschaftssystem. Die KI erkennt physikalisch ungenaue Mengen (Prise, Messerspitze, Schuss, Lorbeerblatt) und setzt das Flag ignore\_for\_stock: true. Die Integration legt dafür kein Produkt an, sondern schreibt diese Zutaten als formatierte Notiz ("💡 Ungetrackte Zutaten") in die Zubereitungs-Beschreibung des Rezepts.

### **3.3 Smart Unit Conversions (Einheiten)**

Beim Start legt die Integration globale Umrechnungsregeln (z.B. 1 EL \= 15 ml, 1 kg \= 1000 g) in Grocy an. Die KI mappt Rezept-Zutaten intelligent auf diese Einheiten. Beim späteren "Verbrauchen" des Rezepts kann Grocy so automatisch korrekte Lagermengen abbuchen.

### **3.4 Essensplanung & Aggregierter Vorrats-Check**

* **Meal Plan:** Die KI analysiert den Text auf Wochentage ("für Montag") und berechnet das absolute Datum. Die Integration trägt das Rezept automatisch in den Grocy Kalender ein.  
* **Aggregierter Sync:** Werden mehrere Rezepte importiert, berechnet die Logik in einem "virtuellen Lager" (virtual\_stock) den aggregierten Bedarf (z.B. 2x 400g Hackfleisch \= 800g). Es wird immer nur die tatsächliche Differenz zum Grocy-Lagerbestand auf die Einkaufsliste gesetzt.

## **4\. Frontend: Dashboards & Blueprints**

Die Dateien werden durch autoinstall.py beim Start von Home Assistant im System entpackt.

### **4.1 Custom Dashboard Karten (Lovelace JavaScript)**

Gebündelt in /local/sno\_ha\_grocy\_custom/sno-grocy-cards.js. Home Assistant erfordert für Custom Cards zwingend sogenannte "Editor-Klassen" (z.B. GrocySmartRecipeHubEditor), da sonst beim Hinzufügen der Karten der Fehler i.setConfig is not a function auftritt.

* **grocy-inventory-explorer-card**: Die virtuelle Speisekammer. Visualisiert Bestände und nutzt die GrocyPictureView für Bilder. *Entwickler-Hinweis:* Der Editor dieser Karte extrahiert Lagerorte und Gruppen dynamisch aus den Produktdaten (master.attributes.inventory), falls die direkten Listen-Attribute des Sensors einmal ausfallen sollten.  
* **grocy-household-hub-card**: Kanban-Board für Hausarbeiten und Aufgaben inkl. Quick-Actions.  
* **grocy-meal-plan-card**: Zeigt den heutigen Essensplan inkl. Rezept-Zutaten und "Jetzt kochen" (Verbrauchen) Button an.  
* **grocy-shopping-card**: Interaktive Einkaufsliste.  
* **grocy-smart-recipe-hub**: Interaktives Textfeld für den KI-Rezept-Import mit Lade-Feedback und Event-Handling für den Service-Call.

### **4.2 Blueprints (Automatisierungsvorlagen)**

Zu finden im Home Assistant Automatisierungs-Editor unter Vorlagen:

* **NFC-Verbrauch (nfc\_consume.yaml)**: Scannt man einen NFC-Tag, wird automatisch eine festgelegte Menge eines Produkts in Grocy verbraucht.  
* **Hausarbeit-Erinnerung (chore\_reminder.yaml)**: Push-Benachrichtigungen auf das Smartphone für überfällige Hausarbeiten. Enthält einen "Actionable Button", um die Aufgabe direkt aus der Benachrichtigung als erledigt zu markieren.  
* **Auto-Sync AI Import (auto\_ai\_import.yaml)**: Überwacht einen beliebigen Text-Sensor (z.B. von Cookidoo) und sendet neue Strings automatisch unsichtbar an den KI-Import.

## **5\. Konfiguration (Options Flow)**

Über Einstellungen \-\> Geräte & Dienste \-\> SNO-HA Grocy \-\> Konfigurieren können folgende Parameter justiert werden:

* **Modus-Schalter (Tasks, Chores, Shopping):** Definiert, ob die jeweiligen Module als Sensoren, interaktive Todo-Listen, beides oder gar nicht geladen werden.  
* **Erweiterte Statistiken:** Berechnet den aktuellen monetären Lagerwert in Euro (CPU-intensiver).  
* **KI-Setup:**  
  * **KI Aktivieren:** Hauptschalter.  
  * **API-Key:** Verstecktes Feld für den Gemini API-Schlüssel.  
  * **Auto-Create:** Erlaubt der Integration, völlig unbekannte Zutaten als neue Produkte in Grocy anzulegen.  
  * **Standard-Produktgruppe:** Dynamisches Dropdown. Ordnet neu erstellte Artikel dieser Gruppe zu.  
  * **Standard-Mengeneinheit:** Dynamisches Dropdown. Fallback-Lager-Einheit für neue Artikel.  
  * **Auto-Sync Einkaufsliste:** Setzt fehlende Zutaten aus KI-Rezepten direkt auf den Einkaufszettel.