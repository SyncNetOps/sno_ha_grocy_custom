# **🛒 SNO-HA_Grocy-custom (V1.0.x)**

Willkommen zur ultimativen [Grocy](https://grocy.info/) ERP-Integration für Home Assistant\!

Diese Integration  **SNO-HA_Grocy-custom** wurde von Grund auf neu entwickelt. Sie nutzt modernste Home Assistant Konzepte (DataUpdateCoordinator, native Entity-Selektoren, To-Do Listen Two-Way-Sync) und schont dabei die Ressourcen deines Servers.

## **🔥 Features & Highlights**

### **🪄 Der magische Auto-Installer (Zero-Setup)**

Schluss mit dem manuellen Herunterladen von dutzenden JavaScript-Dateien oder YAML-Vorlagen\! Beim Start von Home Assistant prüft das System automatisch, ob die Custom-Dashboard-Karten und Blueprints vorhanden sind. Fehlen diese, werden sie **vollautomatisch generiert** und in die korrekten Ordner geschrieben (/config/www/ und /config/blueprints/).

### **📦 Smart Device Splitting**

Verabschiede dich von endlosen, unübersichtlichen Entitäten-Listen. Deine Grocy-Daten werden intelligent in übersichtliche, virtuelle Geräte gruppiert:

* **Lager:** Produkte, Vorräte, Fehlbestände.  
* **Aufgaben & Hausarbeiten:** Sauber getrennte To-Dos.  
* **Batterien:** Ladezyklen und Fälligkeiten.  
* **Rezepte:** Heutiger Speiseplan (Meal Plan).  
* **Statistiken:** Finanzielle Auswertungen (Lagerwert, Ausgaben letzte 30 Tage).

### **📋 Native To-Do Listen (Two-Way-Sync)**

Nutze die offiziellen Home Assistant To-Do Listen, um Grocy direkt im HA-Frontend oder in der Companion App zu steuern:

* **Einkaufszettel:** Hake Artikel beim Einkaufen in der HA-App ab – sie verschwinden in Echtzeit aus Grocy.  
* **Aufgaben (Tasks) & Hausarbeiten (Chores):** Klicke in der Liste auf "Erledigt". Grocy berechnet im Hintergrund automatisch das Datum für die nächste Fälligkeit.

### **🎯 Keine IDs mehr abtippen (Entity Selectors)**

Das Erstellen von Automatisierungen war noch nie so einfach. Alle Services unterstützen **native Home Assistant Dropdowns**. Du suchst in der Benutzeroberfläche einfach nach "Milch", wählst den Sensor aus, und die Integration extrahiert im Hintergrund vollautomatisch die korrekte product_id.

## **🖼️ Inkludierte Dashboard-Karten (Glassmorphism UI)**

Dank des Auto-Installers steht dir sofort ein hochperformantes JavaScript-Bundle (sno-grocy-cards.js) mit 5 maßgeschneiderten Lovelace-Karten zur Verfügung. Alle Karten unterstützen ein modernes **Glassmorphism-Design**:

1. **Grocy Inventory Explorer:** Ein interaktiver Baukasten für dein Lager (Kachel-Grid, Virtuelles Regal oder Tabelle). Inklusive nativem Popup zum schnellen Verbrauchen/Kaufen.  
2. **Grocy Multi-Action Card:** Erstelle "Quick Pantry" Buttons für den Schnellzugriff (Verbrauchen, Kaufen, Umbuchen).  
3. **Grocy Household Hub:** Eine Übersicht aller überfälligen Hausarbeiten und Aufgaben inkl. "Erledigen"-Button direkt in der Karte.  
4. **Grocy Meal Plan:** Zeigt den heutigen Essensplan. Koche ein Rezept per Knopfdruck ab.  
5. **Grocy Shopping Card:** Dein Supermarkt-Begleiter mit interaktiven Checkboxen.

*(Zusätzlich werden automatisch Automatisierungs-Blueprints für "NFC-Verbrauch" und "Hausarbeit-Erinnerungen" installiert\!)*

## **🛠️ Installation**

### **Methode 1: Über HACS (Empfohlen)**

Da diese Integration brandneu ist, fügst du sie am besten als benutzerdefiniertes Repository zu HACS hinzu:

1. Öffne **HACS** in Home Assistant.  
2. Klicke oben rechts auf das Drei-Punkte-Menü \-\> **Benutzerdefinierte Repositories**.  
3. Füge die URL dieses Repositories ein: https://github.com/SyncNetOps/sno_ha_grocy_custom  
4. Kategorie: **Integration**.  
5. Herunterladen und Home Assistant **komplett neu starten**.

### **Methode 2: Manuell**

1. Lade dir dieses Repository als ZIP-Datei herunter.  
2. Entpacke das Archiv und kopiere den Ordner custom_components/sno_ha_grocy_custom in das Verzeichnis /config/custom_components/ deines Home Assistants.  
3. Home Assistant **neu starten** und Browser-Cache leeren (STRG+F5).

## **🚀 Einrichtung in Home Assistant**

1. Generiere in Grocy einen API-Key *(Schraubenschlüssel oben rechts \-\> Manage API keys \-\> Hinzufügen)*.  
2. Gehe in Home Assistant zu **Einstellungen \-\> Geräte & Dienste**.  
3. Klicke auf **Integration hinzufügen** und suche nach SNO-HA_Grocy-custom.  
4. Gib deine exakte Grocy URL (inkl. http:// / https:// und Port) sowie den API-Key ein.

### **⚙️ Der Options-Flow (Dynamische Anpassung)**

Nach der Installation kannst du bei der Integration auf **Konfigurieren** klicken. Hier entscheidest du flexibel, wie du Module (Aufgaben, Hausarbeiten, Shopping) nutzen willst:

* Nur als Sensoren (für eigene Dashboards)  
* Nur als To-Do Liste (für die HA Sidebar)  
* Beides kombiniert oder komplett deaktiviert.

*(Änderungen werden sofort ohne Neustart übernommen\!)*

## **🤖 Automatisierungen & Services (Beispiele)**

Hier sind einige Beispiele, wie du die nativen Services in deinen YAML-Routinen oder Dashboards nutzen kannst:

### **1\. Smart Mülleimer: Produkt via NFC verbrauchen**

*Scanne einen NFC Tag am Mülleimer, um "Milch" aus Grocy abzubuchen.*

alias: "Milch verbraucht per NFC"  
trigger:  
  \- platform: tag  
    tag_id: "deine-nfc-tag-id"  
action:  
  \- action: sno_ha_grocy_custom.consume_product  
    data:  
      entity_id: sensor.sno_ha_grocy_custom_product_5 \# Oder den Namen im UI-Dropdown wählen  
      amount: 1

### **2\. Smart Home Cleaning: Hausarbeit automatisch erledigen**

*Wenn der Saugroboter fertig ist, wird die Hausarbeit in Grocy abgehakt.*

alias: "Hausarbeit: Saugen erledigt"  
trigger:  
  \- platform: state  
    entity_id: vacuum.roborock  
    to: "docked"  
    from: "cleaning"  
action:  
  \- action: sno_ha_grocy_custom.execute_chore  
    data:  
      entity_id: sensor.sno_ha_grocy_custom_chore_3

### **3\. Rezept kochen (Dashboard Button)**

*Zieht alle Zutaten für ein Rezept aus dem Lagerbestand ab.*

type: button  
name: "Spaghetti Bolognese gekocht"  
icon: mdi:chef-hat  
tap_action:  
  action: perform-action  
  perform_action: sno_ha_grocy_custom.consume_recipe  
  data:  
    recipe_id: 8

### **Alle verfügbaren Services:**

* sno_ha_grocy_custom.consume_product (Produkt verbrauchen)  
* sno_ha_grocy_custom.add_product (Produkt kaufen/hinzufügen)  
* sno_ha_grocy_custom.transfer_product (Produkt in ein anderes Lager umbuchen)  
* sno_ha_grocy_custom.execute_chore (Hausarbeit abschließen)  
* sno_ha_grocy_custom.complete_task (Aufgabe abschließen)  
* sno_ha_grocy_custom.charge_battery (Batterie-Ladezyklus zurücksetzen)

*Entwickelt mit ❤️ für das Home Assistant & Grocy Ökosystem.*