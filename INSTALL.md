# **🛠️ Installation & Einrichtung (SNO-HA\_Grocy-custom)**

Die Einrichtung der Integration ist in wenigen Minuten erledigt. Folge dieser Schritt-für-Schritt-Anleitung, um dein Grocy-System erfolgreich mit Home Assistant zu verbinden.

## **🔑 Vorbereitung: Grocy API-Key generieren**

Bevor wir in Home Assistant starten, benötigst du einen API-Schlüssel aus deinem Grocy-System:

1. Logge dich in die Weboberfläche deiner Grocy-Instanz ein.  
2. Klicke oben rechts auf das **Schraubenschlüssel-Symbol** (Einstellungen).  
3. Wähle **Manage API keys** (API Keys verwalten).  
4. Klicke auf **Hinzufügen**, um einen neuen Schlüssel zu erstellen.  
5. **Kopiere den angezeigten Schlüssel** (Du wirst ihn in Schritt 3 benötigen).

## **📦 Schritt 1: Integration installieren**

Du hast zwei Möglichkeiten, die Integrationdateien in Home Assistant einzuspielen. **Methode A wird dringend empfohlen**, da du so zukünftig automatische Updates erhältst.

### **Methode A: Installation über HACS (Empfohlen)**

Da diese Integration neu ist, muss sie als benutzerdefiniertes Repository (Custom Repository) hinzugefügt werden:

1. Öffne **HACS** in der linken Seitenleiste von Home Assistant.  
2. Klicke oben rechts auf das Drei-Punkte-Menü (...) und wähle **Benutzerdefinierte Repositories**.  
3. Trage folgendes ein:  
   * **URL:** https://github.com/SyncNetOps/sno\_ha\_grocy\_custom  
   * **Kategorie:** Integration  
4. Klicke auf **Hinzufügen**.  
5. Suche in HACS nach SNO-HA\_Grocy-custom, klicke darauf und wähle **Herunterladen**.  
6. **Wichtig:** Starte Home Assistant im Anschluss komplett neu\!

### **Methode B: Manuelle Installation**

1. Lade dir dieses Repository über den grünen Code-Button als ZIP-Datei herunter.  
2. Navigiere in deinem Home Assistant Dateisystem (z.B. per *Studio Code Server* oder *Samba Share*) in den Ordner /config/custom\_components/.  
3. Erstelle dort einen Ordner mit dem exakten Namen sno\_ha\_grocy\_custom.  
4. Entpacke die ZIP-Datei und kopiere alle enthaltenen Dateien (inklusive aller Unterordner wie translations) in den soeben erstellten Ordner.  
5. **Wichtig:** Starte Home Assistant im Anschluss komplett neu\!

## **⚙️ Schritt 2: In Home Assistant einrichten (Config Flow)**

Nachdem Home Assistant neu gestartet ist und die Dateien geladen hat, verbinden wir nun dein Grocy.

1. Gehe in Home Assistant zu **Einstellungen** ➔ **Geräte & Dienste**.  
2. Klicke unten rechts auf den Button **\+ Integration hinzufügen**.  
3. Suche in der Liste nach SNO-HA\_Grocy-custom und klicke darauf.  
4. Es öffnet sich das Einrichtungsfenster. Trage hier deine Daten ein:  
   * **URL:** Die vollständige Adresse zu deinem Grocy (z. B. http://192.168.178.50:9283 oder https://grocy.deinedomain.de). Achte auf http/https und den korrekten Port\!  
   * **API Key:** Füge hier den in der Vorbereitung kopierten API-Schlüssel ein.  
5. Klicke auf Absenden. Home Assistant prüft nun die Verbindung. War diese erfolgreich, ist die Grundinstallation abgeschlossen\!

*(Hinweis: Leere an dieser Stelle am besten einmal deinen Browser-Cache mit STRG \+ F5 oder in der Companion App, damit alle neuen Icons korrekt geladen werden.)*

## **🎛️ Schritt 3: Module anpassen (Options Flow)**

Du hast die volle Kontrolle darüber, wie deine To-Dos und Listen in Home Assistant dargestellt werden.

1. Bleibe unter **Einstellungen** ➔ **Geräte & Dienste**.  
2. Klicke bei der neuen SNO-HA\_Grocy-custom Integration auf **Konfigurieren**.  
3. Hier kannst du per Dropdown-Menü für Aufgaben, Hausarbeiten und die Einkaufsliste separat wählen, wie diese in Home Assistant importiert werden sollen:  
   * **Deaktiviert:** Das Modul wird ignoriert.  
   * **Nur Sensoren:** Erstellt für jedes Element einen einzelnen Sensor (nützlich für eigene, hochgradig angepasste Dashboards).  
   * **Nur To-Do Liste:** Bindet die Daten in die nativen Home Assistant To-Do Listen (Seitenleiste) ein – ideal zum Abhaken\!  
   * **Beides:** Kombiniert Sensoren und To-Do Listen.  
4. Deine Änderungen werden beim Klick auf "Absenden" **sofort und ohne Neustart** angewendet.

## **🖼️ Schritt 4: Dashboard-Karten nutzen (Zero-Setup)**

Die Integration verfügt über eine **Auto-Installer Engine**.

Beim Start von Home Assistant wurden im Hintergrund bereits alle notwendigen JavaScript-Dateien für die 5 Dashboard-Karten (/config/www/sno\_ha\_grocy\_custom/) sowie nützliche Automatisierungs-Blueprints (/config/blueprints/) für dich generiert.

**So fügst du die Karten deinem Dashboard hinzu:**

1. Öffne ein beliebiges Dashboard in Home Assistant und klicke oben rechts auf das Stift-Symbol (Dashboard bearbeiten).  
2. Klicke auf **\+ Karte hinzufügen** und scrolle ganz nach unten zu **Manuell** (bzw. Custom).  
3. Du kannst nun einfach eine der folgenden Karten verwenden (die visuelle Konfiguration erfolgt dann direkt im Editor):  
   * type: custom:grocy-inventory-explorer-card (Der Lager-Baukasten)  
   * type: custom:grocy-multi-action-card (Schnellzugriff & Umbuchen)  
   * type: custom:grocy-household-hub-card (Aufgaben & Hausarbeiten)  
   * type: custom:grocy-meal-plan-card (Essensplan)  
   * type: custom:grocy-shopping-card (Einkaufszettel)

🎉 **Fertig\! Dein Grocy-System ist nun vollständig und nativ in Home Assistant integriert.**