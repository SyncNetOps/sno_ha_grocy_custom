"""Automatischer Installer für Frontend-Karten und Blueprints (V1.4.2 Ultimate)."""
import os
import logging
from homeassistant.core import HomeAssistant

LOGGER = logging.getLogger(__package__)

# --- BLUEPRINTS ---
BP_NFC = """blueprint:
  name: Grocy NFC-Verbrauch
  description: Verbraucht ein Produkt via NFC Tag.
  domain: automation
  input:
    nfc_tag: { name: NFC Tag ID, selector: { text: {} } }
    product_sensor: { name: Produkt Sensor, selector: { entity: { domain: sensor } } }
    amount: { name: Verbrauchsmenge, default: 1.0, selector: { number: { min: 0.1, max: 100.0, step: 0.1 } } }
trigger:
  - platform: event
    event_type: tag_scanned
    event_data: { tag_id: !input nfc_tag }
action:
  - action: sno_ha_grocy_custom.consume_product
    data: { entity_id: !input product_sensor, amount: !input amount }
"""

BP_CHORE = """blueprint:
  name: Grocy Hausarbeit-Erinnerung
  description: Tägliche Push-Erinnerung für überfällige Hausarbeiten inkl. Erledigen-Button.
  domain: automation
  input:
    chore_sensor: { name: Hausarbeit Sensor, selector: { entity: { domain: sensor } } }
    notify_device: { name: Smartphone, selector: { device: { integration: mobile_app } } }
    check_time: { name: Prüf-Uhrzeit, default: "18:00:00", selector: { time: {} } }
trigger:
  - platform: time
    at: !input check_time
condition:
  - condition: template
    value_template: >
      {% set due = states(chore_sensor) %}
      {{ due != 'Nicht geplant' and due != 'Unbekannt' and as_timestamp(due) < as_timestamp(now()) }}
action:
  - action: notify.mobile_app_{{ device_attr(notify_device, 'name') | slugify }}
    data:
      message: "Eine Hausarbeit ist überfällig: {{ state_attr(chore_sensor, 'friendly_name') }}"
      title: "Grocy Erinnerung"
      data: { actions: [ { action: "MARK_CHORE_DONE", title: "Als erledigt markieren" } ] }
  - wait_for_trigger:
      - platform: event
        event_type: mobile_app_notification_action
        event_data: { action: "MARK_CHORE_DONE" }
    timeout: "06:00:00"
    continue_on_timeout: false
  - action: sno_ha_grocy_custom.execute_chore
    data: { entity_id: !input chore_sensor }
"""

BP_AI_IMPORT = """blueprint:
  name: SNO-HA Grocy - Auto-Sync AI Import
  description: "Überwacht einen Text-Sensor oder eine To-Do Liste (z.B. von Cookidoo) und sendet neue Texte automatisch an den Grocy KI-Import."
  domain: automation
  input:
    trigger_entity:
      name: Auslöser Entität (Sensor / Todo)
      description: "Entität, die den Rezepttext erhält (z.B. sensor.cookidoo_heute)"
      selector:
        entity: {}
trigger:
  - platform: state
    entity_id: !input trigger_entity
condition:
  - condition: template
    value_template: "{{ trigger.to_state.state not in ['unknown', 'unavailable', ''] }}"
action:
  - service: sno_ha_grocy_custom.import_recipe_via_ai
    data:
      text_input: "{{ trigger.to_state.state }}"
"""

# --- JAVASCRIPT KARTEN BUNDLE (V1.4.2 Ultimate + AI Hub) ---
JS_BUNDLE = r"""
// ----------------------------------------------------
// 1. GLOBALE HILFSFUNKTIONEN & DESIGN ENGINE
// ----------------------------------------------------
function getGrocyDomain(hass) {
    if (!hass) return 'sno_ha_grocy_custom';
    return Object.keys(hass.services).find(d => hass.services[d] && hass.services[d].consume_product) || 'sno_ha_grocy_custom';
}

function getMasterSensor(hass) {
    if (!hass || !hass.states) return null;
    let key = Object.keys(hass.states).find(k => k.startsWith('sensor.') && k.includes('inventory_master'));
    if (key) return hass.states[key];
    key = Object.keys(hass.states).find(k => k.startsWith('sensor.') && hass.states[k].attributes && hass.states[k].attributes.inventory !== undefined);
    return key ? hass.states[key] : null;
}

function fireConfigChange(element, newConfig) {
    const event = new CustomEvent("config-changed", {
        detail: { config: JSON.parse(JSON.stringify(newConfig)) },
        bubbles: true,
        composed: true
    });
    element.dispatchEvent(event);
}

const GLASS_CSS = `
    .glass-mode { background: transparent !important; border: 1px solid rgba(128,128,128,0.2) !important; box-shadow: 0 12px 40px rgba(0,0,0,0.15) !important; }
    .glass-bg { position: absolute; top:0; left:0; right:0; bottom:0; background: var(--card-background-color, #fff); opacity: 0.65; backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); z-index: 0; }
    .content-wrapper { position: relative; z-index: 1; }
    .glass-inner { background: rgba(128,128,128,0.1) !important; backdrop-filter: blur(8px); border: 1px solid rgba(128,128,128,0.15) !important; box-shadow: 0 4px 15px rgba(0,0,0,0.05) !important; }
    .glass-inner:hover { background: rgba(128,128,128,0.2) !important; box-shadow: 0 6px 20px rgba(0,0,0,0.1) !important; transform: translateY(-2px); }
`;


// ==========================================
// 2. GROCY INVENTORY EXPLORER
// ==========================================
class GrocyInventoryExplorerCard extends HTMLElement {
    constructor() { super(); this.attachShadow({ mode: 'open' }); this._selectedItem = null; }
    setConfig(config) { this.config = { title: "Lagerbestand", display_mode: "grid", use_glass: false, disable_popup: false, allowed_users: "", scroll_height: 500, ...config }; this.render(); }
    set hass(hass) { 
        const oldHass = this._hass;
        this._hass = hass; 
        if (!this._initialized) { 
            this._initialized = true; 
            this.render(); 
        } else {
            const mk = Object.keys(hass.states).find(k => k.includes('inventory_master') || (hass.states[k].attributes && hass.states[k].attributes.inventory));
            if (mk && oldHass && oldHass.states[mk] !== hass.states[mk]) { this.render(); }
        }
    }
    
    closeModal() { 
        const dialog = this.shadowRoot.getElementById('modal-dialog');
        if(dialog) dialog.close();
        this._selectedItem = null; 
        this.render(); 
    }
    
    openModal(item) { 
        this._selectedItem = item; 
        this.render(); 
    }

    handleAction(action, amount) {
        if (!this._hass || !this._selectedItem) return;
        if (navigator.vibrate) navigator.vibrate(50);
        this._hass.callService(getGrocyDomain(this._hass), action, { product_id: parseInt(this._selectedItem.product_id), amount: amount });
        this.closeModal();
    }

    render() {
        if (!this.config || !this._hass) return;
        
        const isGlass = this.config.use_glass;
        const glassClass = isGlass ? 'glass-mode' : '';
        const glassInner = isGlass ? 'glass-inner' : '';
        const scrollHeight = this.config.scroll_height || 500;

        // BERECHTIGUNGSSYSTEM PRÜFEN
        let canClick = !this.config.disable_popup;
        let currentUser = (this._hass.user && this._hass.user.name) ? this._hass.user.name.toLowerCase() : "";
        if (canClick && this.config.allowed_users && this.config.allowed_users.trim() !== '') {
            const allowedList = this.config.allowed_users.split(',').map(u => u.trim().toLowerCase());
            if (!allowedList.includes(currentUser)) {
                canClick = false; // Benutzer nicht berechtigt
            }
        }
        const cursorStyle = canClick ? 'pointer' : 'default';
        
        try {
            const masterSensor = getMasterSensor(this._hass);
            let inventory = masterSensor?.attributes?.inventory || [];

            if (this.config.filter_location) inventory = inventory.filter(i => i.location === this.config.filter_location);
            if (this.config.filter_group) inventory = inventory.filter(i => i.group === this.config.filter_group);
            if (this.config.hide_empty) inventory = inventory.filter(i => parseFloat(i.amount || 0) > 0);

            inventory.sort((a, b) => (a.name || '').localeCompare(b.name || ''));

            let contentHtml = '';
            const mode = this.config.display_mode || 'grid';

            if (inventory.length === 0) {
                contentHtml = `<div class="empty-state" style="text-align:center; padding:24px; color:var(--secondary-text-color); font-style:italic;">Keine Produkte gefunden.</div>`;
            } else if (mode === 'shelf') {
                let shelfHtml = inventory.map((item, index) => {
                    const visual = item.image_url ? `<img src="${item.image_url}" style="width:50px; height:50px; object-fit:contain; filter:drop-shadow(0px 4px 2px rgba(0,0,0,0.3));" onerror="this.style.display='none'">` : `<ha-icon icon="mdi:food" style="--mdc-icon-size:40px; color:#795548;"></ha-icon>`;
                    const badge = `<div style="position:absolute; top:-5px; right:0; background:${parseFloat(item.amount)<=0?'var(--error-color,red)':'var(--primary-color)'}; color:white; border-radius:12px; padding:2px 6px; font-size:10px; font-weight:bold; box-shadow:0 2px 4px rgba(0,0,0,0.2);">${item.amount}</div>`;
                    return `<div class="shelf-item click-item" data-index="${index}" style="width:70px; display:flex; flex-direction:column; align-items:center; cursor:${cursorStyle}; position:relative; padding-bottom:8px; border-bottom:8px solid #a67c52; transition:transform 0.2s;">${visual}${badge}<div style="font-size:10px; text-align:center; margin-top:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:100%; color:var(--primary-text-color);">${item.name}</div></div>`;
                }).join('');
                contentHtml = `<div class="${glassInner}" style="display:flex; flex-wrap:wrap; gap:16px; padding:10px; justify-content:center; background:rgba(0,0,0,0.02); border-radius:12px;">${shelfHtml}</div>`;
            } else if (mode === 'table') {
                let rows = inventory.map((item, index) => `
                    <tr class="t-row click-item" data-index="${index}" style="cursor:${cursorStyle}; border-bottom:1px solid var(--divider-color); transition:background 0.2s;">
                        <td style="padding:8px;">${item.image_url ? `<img src="${item.image_url}" style="width:30px; height:30px; object-fit:contain; border-radius:4px;" onerror="this.style.display='none'">` : `<ha-icon icon="mdi:food"></ha-icon>`}</td>
                        <td style="padding:8px; font-weight:bold; color:var(--primary-text-color);">${item.name}</td>
                        <td style="padding:8px; color:var(--primary-text-color);">${item.amount} ${item.qu}</td>
                        <td style="padding:8px; color:var(--secondary-text-color); font-size:12px;">${item.location}</td>
                    </tr>`).join('');
                contentHtml = `<div class="${glassInner}" style="border-radius:12px; overflow:hidden;"><table style="width:100%; border-collapse:collapse; font-size:14px;"><tr style="text-align:left; border-bottom:2px solid var(--divider-color); color:var(--secondary-text-color); background:rgba(0,0,0,0.02);"><th></th><th>Produkt</th><th>Bestand</th><th>Lager</th></tr>${rows}</table></div>`;
            } else {
                let gridHtml = inventory.map((item, index) => {
                    const visual = item.image_url ? `<img src="${item.image_url}" style="width:50px; height:50px; object-fit:contain; margin-bottom:8px;" onerror="this.style.display='none'">` : `<ha-icon icon="mdi:food" style="--mdc-icon-size:40px; color:var(--primary-color); margin-bottom:8px;"></ha-icon>`;
                    const emptyStyle = parseFloat(item.amount) <= 0 ? 'border-color:rgba(255,0,0,0.3); opacity:0.7;' : '';
                    return `<div class="grid-item click-item ${glassInner}" data-index="${index}" style="background:var(--secondary-background-color); border-radius:12px; padding:12px; text-align:center; cursor:${cursorStyle}; border:2px solid transparent; display:flex; flex-direction:column; align-items:center; transition:all 0.2s; ${emptyStyle}">${visual}<div style="font-weight:bold; font-size:13px; margin-bottom:4px; line-height:1.2; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; color:var(--primary-text-color);">${item.name}</div><div style="font-size:12px; color:var(--secondary-text-color); background:rgba(0,0,0,0.05); padding:2px 8px; border-radius:10px;">${item.amount} ${item.qu}</div></div>`;
                }).join('');
                contentHtml = `<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(100px, 1fr)); gap:12px;">${gridHtml}</div>`;
            }

            // NATIVE DIALOG POPUP
            let modalHtml = '';
            if (this._selectedItem && canClick) {
                const item = this._selectedItem;
                const visual = item.image_url ? `<img src="${item.image_url}" style="width:100px; height:100px; object-fit:contain; margin-bottom:10px; drop-shadow:0 4px 6px rgba(0,0,0,0.2);" onerror="this.style.display='none'">` : `<ha-icon icon="mdi:food" style="--mdc-icon-size:80px; color:var(--primary-color);"></ha-icon>`;
                modalHtml = `
                <dialog id="modal-dialog" style="padding:0; border:none; background:transparent; outline:none; max-width:95vw; margin:auto; overflow:visible;">
                    <div class="${glassInner}" style="background:var(--card-background-color); padding:20px; box-sizing:border-box; border-radius:16px; width:100%; min-width:250px; max-width:320px; text-align:center; box-shadow:0 10px 40px rgba(0,0,0,0.4); position:relative;">
                        <button id="modal-close" style="position:absolute; top:10px; right:10px; background:none; border:none; color:var(--secondary-text-color); cursor:pointer; padding:4px; margin:0;"><ha-icon icon="mdi:close"></ha-icon></button>
                        ${visual}
                        <h3 style="margin:0 0 5px 0; color:var(--primary-text-color); word-wrap:break-word;">${item.name}</h3>
                        <p style="margin:0 0 20px 0; color:var(--secondary-text-color); font-size:14px;">Bestand: <b>${item.amount} ${item.qu}</b><br><small style="opacity:0.8;">${item.location} | ${item.group}</small></p>
                        <div style="display:flex; gap:10px; justify-content:center; margin-bottom:0; flex-wrap:wrap;">
                            <button class="a-btn m-minus" data-action="consume_product" style="flex:1 1 100px; padding:12px; box-sizing:border-box; border:none; border-radius:10px; font-weight:bold; cursor:pointer; color:white; background:var(--error-color, #f44336); box-shadow: 0 4px 10px rgba(244,67,54,0.3); transition:0.2s;">-1 Verbrauchen</button>
                            <button class="a-btn m-plus" data-action="add_product" style="flex:1 1 100px; padding:12px; box-sizing:border-box; border:none; border-radius:10px; font-weight:bold; cursor:pointer; color:white; background:var(--success-color, #4caf50); box-shadow: 0 4px 10px rgba(76,175,80,0.3); transition:0.2s;">+1 Kaufen</button>
                        </div>
                    </div>
                </dialog>`;
            }

            this.shadowRoot.innerHTML = `
                <style>
                    ${GLASS_CSS}
                    .a-btn:active { transform: scale(0.95); }
                    .t-row:hover { background: rgba(128,128,128,0.1); }
                    dialog::backdrop { background: rgba(0,0,0,0.6); backdrop-filter: blur(5px); -webkit-backdrop-filter: blur(5px); }
                    /* Scrollbereich hinzufügen */
                    .scroll-container {
                        max-height: ${scrollHeight}px;
                        overflow-y: auto;
                        padding-right: 4px; /* Platz für den Scrollbalken */
                    }
                    /* Styling für den Scrollbalken (Webkit) */
                    .scroll-container::-webkit-scrollbar { width: 6px; }
                    .scroll-container::-webkit-scrollbar-track { background: transparent; }
                    .scroll-container::-webkit-scrollbar-thumb { background-color: var(--divider-color, rgba(150, 150, 150, 0.3)); border-radius: 10px; }
                </style>
                <ha-card class="${glassClass}" style="position:relative; padding:16px; border-radius:16px; background:var(--ha-card-background, var(--card-background-color, white)); overflow:hidden;">
                    ${isGlass ? '<div class="glass-bg"></div>' : ''}
                    <div class="content-wrapper">
                        <div style="font-size:20px; font-weight:500; margin-bottom:16px; display:flex; align-items:center; color:var(--primary-text-color);"><ha-icon icon="mdi:box-search-outline" style="margin-right:8px; color:var(--primary-color);"></ha-icon> ${this.config.title || 'Lagerbestand'}</div>
                        <div class="scroll-container">
                            ${contentHtml}
                        </div>
                    </div>
                    ${modalHtml}
                </ha-card>
            `;

            // Clicks nur binden, wenn erlaubt
            if (canClick) {
                this.shadowRoot.querySelectorAll('.click-item').forEach(el => {
                    el.addEventListener('click', () => this.openModal(inventory[el.getAttribute('data-index')]));
                });
            }

            if (this._selectedItem && canClick) {
                const dialog = this.shadowRoot.getElementById('modal-dialog');
                if (dialog && typeof dialog.showModal === 'function') {
                    dialog.showModal(); // Öffnet das native Popup!
                }
                
                this.shadowRoot.getElementById('modal-close').addEventListener('click', () => this.closeModal());
                
                // Schließen bei Klick auf den Hintergrund
                dialog.addEventListener('click', (e) => {
                    if (e.target === dialog) this.closeModal(); 
                });

                this.shadowRoot.querySelectorAll('.a-btn').forEach(btn => {
                    btn.addEventListener('click', () => this.handleAction(btn.getAttribute('data-action'), 1));
                });
            }
        } catch (error) {
            console.error("Grocy Card Render Error:", error);
            this.shadowRoot.innerHTML = `<ha-card style="padding:16px; color:var(--error-color, red);">Fehler beim Darstellen der Karte: ${error.message}</ha-card>`;
        }
    }
    static getStubConfig() { return { type: "custom:grocy-inventory-explorer-card", title: "Lagerbestand", display_mode: "grid", use_glass: false, scroll_height: 500 }; }
    static getConfigElement() { return document.createElement("grocy-inventory-explorer-editor"); }
}
customElements.define('grocy-inventory-explorer-card', GrocyInventoryExplorerCard);

class GrocyInventoryExplorerEditor extends HTMLElement {
    setConfig(config) { 
        this._config = config ? JSON.parse(JSON.stringify(config)) : {}; 
        if (!this.innerHTML || this.innerHTML.trim() === '') { this.render(); } 
    }
    set hass(hass) { 
        const oldHass = this._hass;
        this._hass = hass; 
        if (!this._initialized) { 
            this._initialized = true; 
            this.render(); 
        } else {
            const mk = Object.keys(hass.states).find(k => k.includes('inventory_master') || (hass.states[k].attributes && hass.states[k].attributes.inventory));
            if (mk && oldHass && oldHass.states[mk] !== hass.states[mk]) { this.updateDropdowns(); }
        }
    }

    updateDropdowns() {
        if (!this._hass) return;
        const master = getMasterSensor(this._hass);
        if (!master || !master.attributes) return;

        const locEl = this.querySelector('#cfg-loc');
        const grpEl = this.querySelector('#cfg-grp');

        if (locEl && master.attributes.locations) {
            let locs = '<option value="">-- Alle --</option>';
            Object.values(master.attributes.locations).sort().forEach(l => locs += `<option value="${l}" ${this._config.filter_location === l ? 'selected' : ''}>${l}</option>`);
            if (locEl.innerHTML !== locs) locEl.innerHTML = locs;
        }

        if (grpEl && master.attributes.groups) {
            let grps = '<option value="">-- Alle --</option>';
            Object.values(master.attributes.groups).sort().forEach(g => grps += `<option value="${g}" ${this._config.filter_group === g ? 'selected' : ''}>${g}</option>`);
            if (grpEl.innerHTML !== grps) grpEl.innerHTML = grps;
        }
    }
    
    render() {
        if (!this._config) return;

        this.innerHTML = `
            <div style="display:flex; flex-direction:column; gap:12px;">
                <label style="font-weight:bold;">Titel</label>
                <input type="text" id="cfg-title" value="${this._config.title || 'Lagerbestand'}" style="padding:8px; border:1px solid var(--divider-color); border-radius:4px; background:var(--card-background-color); color:var(--primary-text-color);">
                
                <label style="font-weight:bold;">Ansicht (Design)</label>
                <select id="cfg-mode" style="padding:8px; border:1px solid var(--divider-color); border-radius:4px; background:var(--card-background-color); color:var(--primary-text-color);">
                    <option value="grid" ${this._config.display_mode === 'grid' ? 'selected' : ''}>Kachel Raster (Grid)</option>
                    <option value="shelf" ${this._config.display_mode === 'shelf' ? 'selected' : ''}>Virtuelles Regal</option>
                    <option value="table" ${this._config.display_mode === 'table' ? 'selected' : ''}>Liste / Tabelle</option>
                </select>
                
                <label style="font-weight:bold;">Max. Höhe (Scrollbereich in px)</label>
                <input type="number" id="cfg-scroll" value="${this._config.scroll_height || 500}" style="padding:8px; border:1px solid var(--divider-color); border-radius:4px; background:var(--card-background-color); color:var(--primary-text-color);">

                <div style="border-top:1px solid var(--divider-color); margin-top:8px; padding-top:12px; font-weight:bold; color:var(--primary-color);">Filter</div>
                <label>Lagerort:</label><select id="cfg-loc" style="padding:6px; background:var(--card-background-color); color:var(--primary-text-color);"><option value="">Wird geladen...</option></select>
                <label>Gruppe:</label><select id="cfg-grp" style="padding:6px; background:var(--card-background-color); color:var(--primary-text-color);"><option value="">Wird geladen...</option></select>
                <label style="display:flex; align-items:center; gap:8px;"><input type="checkbox" id="cfg-hide" ${this._config.hide_empty ? 'checked' : ''}> Leere Produkte ausblenden</label>
                
                <div style="border-top:1px solid var(--divider-color); margin-top:8px; padding-top:12px; font-weight:bold; color:var(--primary-color);">Sicherheit & Berechtigungen</div>
                <label style="display:flex; align-items:center; gap:8px; color:var(--error-color, red);">
                    <input type="checkbox" id="cfg-nopop" ${this._config.disable_popup ? 'checked' : ''}> 
                    <span>Klick-Popup komplett deaktivieren</span>
                </label>
                <label style="display:block; font-size:12px; margin-top:4px;">Nur für diese Benutzer erlauben (Kommagetrennt):</label>
                <input type="text" id="cfg-users" value="${this._config.allowed_users || ''}" placeholder="Leer = Alle Benutzer dürfen klicken" style="padding:8px; border:1px solid var(--divider-color); border-radius:4px; background:var(--card-background-color); color:var(--primary-text-color);">
                
                <div style="border-top:1px solid var(--divider-color); margin-top:8px; padding-top:12px; font-weight:bold; color:var(--primary-color);">Erweitertes Design</div>
                <label style="display:flex; align-items:center; gap:8px; background:rgba(var(--rgb-primary-color), 0.1); padding:10px; border-radius:8px;">
                    <input type="checkbox" id="cfg-glass" ${this._config.use_glass ? 'checked' : ''}> 
                    <span style="font-weight:bold;">✨ Modern UI (Glassmorphism) aktivieren</span>
                </label>
            </div>
        `;

        this.updateDropdowns();

        this.querySelectorAll('select, input[type="checkbox"]').forEach(el => el.addEventListener('change', () => {
            const newConfig = {
                ...this._config,
                display_mode: this.querySelector('#cfg-mode').value,
                filter_location: this.querySelector('#cfg-loc').value || undefined,
                filter_group: this.querySelector('#cfg-grp').value || undefined,
                hide_empty: this.querySelector('#cfg-hide').checked,
                use_glass: this.querySelector('#cfg-glass').checked,
                disable_popup: this.querySelector('#cfg-nopop').checked
            };
            this._config = newConfig;
            fireConfigChange(this, newConfig);
        }));

        this.querySelectorAll('input[type="text"], input[type="number"]').forEach(input => input.addEventListener('input', (e) => {
            const newConfig = { ...this._config };
            if (e.target.id === 'cfg-title') newConfig.title = e.target.value;
            if (e.target.id === 'cfg-users') newConfig.allowed_users = e.target.value;
            if (e.target.id === 'cfg-scroll') newConfig.scroll_height = parseInt(e.target.value) || 500;
            this._config = newConfig;
            fireConfigChange(this, newConfig);
        }));
    }
}
customElements.define('grocy-inventory-explorer-editor', GrocyInventoryExplorerEditor);


// ==========================================
// 3. GROCY MULTI-ACTION CARD
// ==========================================
class GrocyMultiActionCard extends HTMLElement {
    constructor() { super(); this.attachShadow({ mode: 'open' }); }
    setConfig(config) { this.config = config; this.render(); }
    set hass(hass) { this._hass = hass; if (!this._initialized) { this._initialized = true; this.render(); } }
    
    _extId(val) { if (!val) return null; const m = String(val).match(/^(\d+)/); return m ? parseInt(m[1], 10) : null; }
    
    render() {
        if (!this.config) return;
        const items = this.config.items || [];
        const isGlass = this.config.use_glass;
        const glassClass = isGlass ? 'glass-mode' : '';
        const glassInner = isGlass ? 'glass-inner' : '';
        
        let buttonsHtml = items.map((i, idx) => {
            let actionName = i.action === 'add_product' ? 'Kaufen' : (i.action === 'transfer_product' ? 'Umbuchen' : 'Verbrauchen');
            return `<div class="m-btn ${glassInner}" data-idx="${idx}" style="background:var(--secondary-background-color); border-radius:12px; padding:12px; text-align:center; cursor:pointer; transition:transform 0.2s;">
                <ha-icon icon="${i.icon || 'mdi:food'}" style="color:${i.color || 'var(--primary-color)'}; --mdc-icon-size:32px; margin-bottom:8px;"></ha-icon>
                <div style="font-weight:bold; font-size:14px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:var(--primary-text-color);">${i.name || 'Unbekannt'}</div>
                <div style="font-size:12px; color:var(--secondary-text-color);">${i.amount || 1}x ${actionName}</div>
            </div>`;
        }).join('');

        this.shadowRoot.innerHTML = `
            <style>${GLASS_CSS} .m-btn:active { transform: scale(0.95); }</style>
            <ha-card class="${glassClass}" style="position:relative; padding:16px; border-radius:16px; background:var(--ha-card-background, var(--card-background-color, white)); overflow:hidden;">
                ${isGlass ? '<div class="glass-bg"></div>' : ''}
                <div class="content-wrapper">
                    ${this.config.title ? `<div style="font-size:20px; font-weight:500; margin-bottom:16px; color:var(--primary-text-color);">${this.config.title}</div>` : ''}
                    <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(100px, 1fr)); gap:12px;">${buttonsHtml}</div>
                </div>
            </ha-card>
        `;

        this.shadowRoot.querySelectorAll('.m-btn').forEach(btn => btn.addEventListener('click', () => {
            if (!this._hass) return;
            const i = items[btn.dataset.idx];
            const data = { product_id: this._extId(i.product_id), amount: parseFloat(i.amount || 1) };
            if (i.action === 'transfer_product' && i.location_id_to) data.location_id_to = this._extId(i.location_id_to);
            if (i.qu_id) data.qu_id = this._extId(i.qu_id);
            
            if (navigator.vibrate) navigator.vibrate(50);
            this._hass.callService(getGrocyDomain(this._hass), i.action || 'consume_product', data);
            
            btn.style.opacity = '0.5'; setTimeout(() => btn.style.opacity = '1', 200);
        }));
    }
    static getStubConfig() { return { type: "custom:grocy-multi-action-card", title: "Quick Pantry", use_glass: false, items: [{ name: "Beispiel", action: "consume_product", amount: 1 }] }; }
    static getConfigElement() { return document.createElement("grocy-multi-action-editor"); }
}
customElements.define('grocy-multi-action-card', GrocyMultiActionCard);

class GrocyMultiActionEditor extends HTMLElement {
    setConfig(config) { 
        this._config = config ? JSON.parse(JSON.stringify(config)) : {};
        if (!this.innerHTML || this.innerHTML.trim() === '') { this.render(); } 
    }
    set hass(hass) { 
        const oldHass = this._hass;
        this._hass = hass; 
        if (!this._initialized) { 
            this._initialized = true; 
            this.render(); 
        } else {
            const mk = Object.keys(hass.states).find(k => k.includes('inventory_master') || (hass.states[k].attributes && hass.states[k].attributes.inventory));
            if (mk && oldHass && oldHass.states[mk] !== hass.states[mk]) { this.updateDatalists(); }
        }
    }

    updateDatalists() {
        if (!this._hass) return;
        const products = Object.values(this._hass.states).filter(s => s.attributes && s.attributes.product_id).map(s => ({ id: s.attributes.product_id, name: s.attributes.friendly_name || s.entity_id })).sort((a,b) => a.name.localeCompare(b.name));
        const dlP = this.querySelector('#dl-p');
        if (dlP) dlP.innerHTML = products.map(p => `<option value="${p.id} - ${p.name}"></option>`).join('');

        const master = getMasterSensor(this._hass);
        if (master && master.attributes) {
            if (master.attributes.locations) {
                const dlL = this.querySelector('#dl-l');
                if (dlL) dlL.innerHTML = Object.keys(master.attributes.locations).map(id => `<option value="${id} - ${master.attributes.locations[id]}"></option>`).join('');
            }
            if (master.attributes.quantity_units) {
                const dlQ = this.querySelector('#dl-q');
                if (dlQ) dlQ.innerHTML = Object.keys(master.attributes.quantity_units).map(id => `<option value="${id} - ${master.attributes.quantity_units[id]}"></option>`).join('');
            }
        }
    }

    render() {
        if (!this._config) return;

        const items = this._config.items || [];
        const itemsHtml = items.map((item, index) => {
            const pText = item.product_id ? `${item.product_id}` : '';
            const lText = item.location_id_to ? `${item.location_id_to}` : '';
            const qText = item.qu_id ? `${item.qu_id}` : '';
            
            return `
            <div style="border:1px solid var(--divider-color); padding:12px; margin-bottom:12px; border-radius:8px; background:rgba(0,0,0,0.02);">
                <div style="display:flex; justify-content:space-between; margin-bottom:12px;">
                    <strong>Button ${index + 1}</strong>
                    <button class="d-btn" data-idx="${index}" style="color:var(--error-color,red); background:none; border:none; cursor:pointer;">✖ Löschen</button>
                </div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
                    <div><label style="font-size:12px;">Anzeigename</label><input type="text" class="cfg-in" data-idx="${index}" data-f="name" value="${item.name || ''}" style="width:100%; padding:6px; box-sizing:border-box; background:var(--card-background-color); color:var(--primary-text-color);"></div>
                    <div><label style="font-size:12px;">🔍 Produkt (ID/Name tippen)</label><input type="text" list="dl-p" class="cfg-in" data-idx="${index}" data-f="product_id" value="${pText}" style="width:100%; padding:6px; box-sizing:border-box; background:var(--card-background-color); color:var(--primary-text-color);"></div>
                    <div><label style="font-size:12px;">Aktion</label>
                        <select class="cfg-in" data-idx="${index}" data-f="action" style="width:100%; padding:6px; box-sizing:border-box; background:var(--card-background-color); color:var(--primary-text-color);">
                            <option value="consume_product" ${item.action === 'consume_product' ? 'selected' : ''}>Verbrauchen (-)</option>
                            <option value="add_product" ${item.action === 'add_product' ? 'selected' : ''}>Kaufen (+)</option>
                            <option value="transfer_product" ${item.action === 'transfer_product' ? 'selected' : ''}>Umbuchen</option>
                        </select>
                    </div>
                    <div><label style="font-size:12px;">Menge</label><input type="number" step="0.1" class="cfg-in" data-idx="${index}" data-f="amount" value="${item.amount !== undefined ? item.amount : 1}" style="width:100%; padding:6px; box-sizing:border-box; background:var(--card-background-color); color:var(--primary-text-color);"></div>
                    <div><label style="font-size:12px;">🔍 Ziel-Lager</label><input type="text" list="dl-l" class="cfg-in" data-idx="${index}" data-f="location_id_to" value="${lText}" style="width:100%; padding:6px; box-sizing:border-box; background:var(--card-background-color); color:var(--primary-text-color);"></div>
                    <div><label style="font-size:12px;">🔍 Einheit</label><input type="text" list="dl-q" class="cfg-in" data-idx="${index}" data-f="qu_id" value="${qText}" style="width:100%; padding:6px; box-sizing:border-box; background:var(--card-background-color); color:var(--primary-text-color);"></div>
                    <div><label style="font-size:12px;">Icon</label><ha-icon-picker class="cfg-icon" data-idx="${index}" data-f="icon" value="${item.icon || 'mdi:food'}" style="width:100%;"></ha-icon-picker></div>
                    <div><label style="font-size:12px;">Farbe</label><input type="color" class="cfg-in" data-idx="${index}" data-f="color" value="${item.color || '#2196F3'}" style="width:100%; height:36px; box-sizing:border-box;"></div>
                </div>
            </div>`;
        }).join('');

        this.innerHTML = `
            <datalist id="dl-p"></datalist>
            <datalist id="dl-l"></datalist>
            <datalist id="dl-q"></datalist>
            <div style="margin-bottom:16px;">
                <label style="font-weight:bold; display:block; margin-bottom:4px;">Karten-Titel</label>
                <input type="text" id="cfg-title" value="${this._config.title || ''}" style="width:100%; padding:8px; box-sizing:border-box; border:1px solid var(--divider-color); border-radius:4px; background:var(--card-background-color); color:var(--primary-text-color);">
            </div>
            ${itemsHtml}
            <button id="add-btn" style="width:100%; padding:10px; background:var(--primary-color); color:white; border:none; border-radius:4px; cursor:pointer; margin-bottom:16px;">+ Neuer Button</button>
            <div style="border-top:1px solid var(--divider-color); padding-top:12px;">
                <label style="display:flex; align-items:center; gap:8px; background:rgba(var(--rgb-primary-color), 0.1); padding:10px; border-radius:8px;">
                    <input type="checkbox" id="cfg-glass" ${this._config.use_glass ? 'checked' : ''}> 
                    <span style="font-weight:bold;">✨ Modern UI (Glassmorphism) aktivieren</span>
                </label>
            </div>
        `;
        
        this.updateDatalists();

        this.querySelector('#cfg-glass').addEventListener('change', () => {
            this._config.use_glass = this.querySelector('#cfg-glass').checked;
            fireConfigChange(this, this._config);
        });

        this.querySelector('#cfg-title').addEventListener('input', e => {
            const newConfig = { ...this._config, title: e.target.value };
            this._config = newConfig;
            fireConfigChange(this, newConfig);
        });

        this.querySelector('#add-btn').addEventListener('click', () => {
            const newItems = [...(this._config.items || []), { name: "Neu", action: "consume_product", amount: 1 }];
            const newConfig = { ...this._config, items: newItems };
            this._config = newConfig; 
            fireConfigChange(this, newConfig);
            this.render(); 
        });

        this.querySelectorAll('.d-btn').forEach(btn => btn.addEventListener('click', e => {
            const newItems = [...this._config.items];
            newItems.splice(parseInt(e.target.dataset.idx), 1);
            const newConfig = { ...this._config, items: newItems };
            this._config = newConfig; 
            fireConfigChange(this, newConfig);
            this.render(); 
        }));

        this.querySelectorAll('select.cfg-in, input[type="number"].cfg-in, input[type="color"].cfg-in').forEach(input => input.addEventListener('change', e => {
            const idx = parseInt(e.target.dataset.idx);
            const field = e.target.dataset.f;
            let val = e.target.value;
            
            if (['product_id', 'location_id_to', 'qu_id'].includes(field)) val = val ? parseInt(val, 10) : undefined;
            else if (field === 'amount') val = val ? parseFloat(val) : undefined;
            
            const newItems = [...this._config.items];
            newItems[idx] = { ...newItems[idx], [field]: val };
            this._config = { ...this._config, items: newItems };
            fireConfigChange(this, this._config);
        }));

        this.querySelectorAll('input[type="text"].cfg-in').forEach(input => input.addEventListener('input', e => {
            const idx = parseInt(e.target.dataset.idx);
            const newItems = [...this._config.items];
            newItems[idx] = { ...newItems[idx], [e.target.dataset.f]: e.target.value };
            this._config = { ...this._config, items: newItems };
            fireConfigChange(this, this._config);
        }));

        this.querySelectorAll('.cfg-icon').forEach(picker => picker.addEventListener('value-changed', e => {
            const idx = parseInt(e.target.dataset.idx);
            const newItems = [...this._config.items];
            newItems[idx] = { ...newItems[idx], icon: e.detail.value };
            this._config = { ...this._config, items: newItems };
            fireConfigChange(this, this._config);
        }));
    }
}
customElements.define('grocy-multi-action-editor', GrocyMultiActionEditor);


// ==========================================
// 4. GROCY HOUSEHOLD HUB CARD
// ==========================================
class GrocyHouseholdHubCard extends HTMLElement {
    constructor() { super(); this.attachShadow({ mode: 'open' }); }
    setConfig(config) { this.config = config; this.render(); }
    set hass(hass) { 
        const oldHass = this._hass;
        this._hass = hass; 
        if (!this._initialized) { 
            this._initialized = true; 
            this.render(); 
        } else {
            let changed = false;
            for (let key in hass.states) {
                if (key.includes('_chore_') || key.includes('_task_')) {
                    if (!oldHass || oldHass.states[key] !== hass.states[key]) { changed = true; break; }
                }
            }
            if (changed) this.render();
        }
    }
    render() {
        if (!this.config || !this._hass) return;
        let items = [];
        try {
            Object.values(this._hass.states).forEach(state => {
                const isChore = state.entity_id.includes('_chore_') && this.config.show_chores !== false;
                const isTask = state.entity_id.includes('_task_') && this.config.show_tasks !== false;
                if (isChore || isTask) {
                    const val = state.state;
                    if (this.config.hide_unscheduled && (val === 'Nicht geplant' || val === 'Unbekannt')) return;
                    if (isTask && val === 'Erledigt') return;
                    let isOverdue = false, dateObj = null;
                    if (isChore && val !== 'Nicht geplant' && val !== 'Unbekannt') { dateObj = new Date(val); isOverdue = dateObj < new Date(); }
                    let cleanName = (state.attributes.friendly_name || "Unbekannt").replace('Hausarbeit: ', '').replace('Aufgabe: ', '');
                    items.push({ id: isChore ? state.attributes.chore_id : state.attributes.task_id, name: cleanName, type: isChore ? 'chore' : 'task', status: val, isOverdue, dateObj, icon: isChore ? 'mdi:spray-bottle' : 'mdi:clipboard-check-outline' });
                }
            });
            items.sort((a, b) => { if (a.isOverdue && !b.isOverdue) return -1; if (!a.isOverdue && b.isOverdue) return 1; if (a.dateObj && b.dateObj) return a.dateObj - b.dateObj; return 0; });
            
            const isGlass = this.config.use_glass;
            const glassClass = isGlass ? 'glass-mode' : '';
            const glassInner = isGlass ? 'glass-inner' : '';

            let listHtml = items.length === 0 ? `<div style="text-align:center; padding:24px; color:var(--secondary-text-color); font-style:italic;">Alles erledigt! 🎉</div>` : items.map(item => {
                let dStatus = item.dateObj ? item.dateObj.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' }) : item.status;
                return `<div class="${glassInner}" style="display:flex; align-items:center; padding:12px; border-radius:8px; background:${item.isOverdue ? 'rgba(255,0,0,0.05)' : 'var(--secondary-background-color)'}; margin-bottom:8px; border-left:${item.isOverdue ? '4px solid var(--error-color,red)' : 'none'};">
                    <ha-icon icon="${item.icon}" style="margin-right:16px; color:var(--primary-color);"></ha-icon>
                    <div style="flex:1; overflow:hidden;"><div style="font-weight:bold; font-size:15px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:var(--primary-text-color);">${item.name}</div><div style="font-size:12px; color:${item.isOverdue ? 'var(--error-color,red);font-weight:bold;' : 'var(--secondary-text-color);'}">${item.isOverdue ? '⚠️ Überfällig (' + dStatus + ')' : dStatus}</div></div>
                    <button class="hh-btn" data-type="${item.type}" data-id="${item.id}" style="background:var(--primary-color); color:white; border:none; border-radius:50%; width:40px; height:40px; cursor:pointer;"><ha-icon icon="mdi:check"></ha-icon></button>
                </div>`;
            }).join('');
            
            this.shadowRoot.innerHTML = `
                <style>${GLASS_CSS} .hh-btn:active{transform:scale(0.9);}</style>
                <ha-card class="${glassClass}" style="position:relative; padding:16px; border-radius:16px; background:var(--ha-card-background, var(--card-background-color, white)); overflow:hidden;">
                    ${isGlass ? '<div class="glass-bg"></div>' : ''}
                    <div class="content-wrapper">
                        <div style="font-size:20px; font-weight:500; margin-bottom:16px; color:var(--primary-text-color);"><ha-icon icon="mdi:clipboard-check-outline" style="margin-right:8px; color:var(--primary-color);"></ha-icon> ${this.config.title || "Hausarbeiten & Aufgaben"}</div>
                        ${listHtml}
                    </div>
                </ha-card>
            `;
            this.shadowRoot.querySelectorAll('.hh-btn').forEach(btn => btn.addEventListener('click', () => {
                if (navigator.vibrate) navigator.vibrate(50);
                this._hass.callService(getGrocyDomain(this._hass), btn.dataset.type === 'chore' ? 'execute_chore' : 'complete_task', { [btn.dataset.type === 'chore' ? 'chore_id' : 'task_id']: parseInt(btn.dataset.id) });
                btn.parentElement.style.opacity = '0.5';
            }));
        } catch (err) {
            console.error("Hub Error:", err);
            this.shadowRoot.innerHTML = `<ha-card style="padding:16px; color:red;">Fehler: ${err.message}</ha-card>`;
        }
    }
    static getStubConfig() { return { type: "custom:grocy-household-hub-card", title: "Household Hub", use_glass: false }; }
    static getConfigElement() { return document.createElement("grocy-household-hub-editor"); }
}
customElements.define('grocy-household-hub-card', GrocyHouseholdHubCard);

class GrocyHouseholdHubEditor extends HTMLElement {
    setConfig(config) { 
        this._config = config ? JSON.parse(JSON.stringify(config)) : {}; 
        if (!this.innerHTML || this.innerHTML.trim() === '') { this.render(); }
    }
    render() {
        if (!this._config) return;
        this.innerHTML = `
            <div style="display:flex; flex-direction:column; gap:10px;">
                <label style="font-weight:bold;">Titel</label>
                <input type="text" id="cfg-title" value="${this._config.title || 'Hausarbeiten & Aufgaben'}" style="padding:8px; border-radius:4px; border:1px solid var(--divider-color); box-sizing:border-box; background:var(--card-background-color); color:var(--primary-text-color);">
                <label><input type="checkbox" id="cfg-c" ${this._config.show_chores !== false ? 'checked' : ''}> Hausarbeiten anzeigen</label>
                <label><input type="checkbox" id="cfg-t" ${this._config.show_tasks !== false ? 'checked' : ''}> Aufgaben anzeigen</label>
                <label><input type="checkbox" id="cfg-h" ${this._config.hide_unscheduled ? 'checked' : ''}> 'Nicht geplante' ausblenden</label>
                <div style="border-top:1px solid var(--divider-color); padding-top:12px; margin-top:8px;">
                    <label style="display:flex; align-items:center; gap:8px; background:rgba(var(--rgb-primary-color), 0.1); padding:10px; border-radius:8px;">
                        <input type="checkbox" id="cfg-glass" ${this._config.use_glass ? 'checked' : ''}> 
                        <span style="font-weight:bold;">✨ Modern UI (Glassmorphism) aktivieren</span>
                    </label>
                </div>
            </div>`;
            
        this.querySelector('#cfg-title').addEventListener('input', e => {
            const newConfig = { ...this._config, title: e.target.value };
            this._config = newConfig;
            fireConfigChange(this, newConfig);
        });
        this.querySelectorAll('input[type="checkbox"]').forEach(i => i.addEventListener('change', () => {
            const newConfig = {
                ...this._config,
                show_chores: this.querySelector('#cfg-c').checked,
                show_tasks: this.querySelector('#cfg-t').checked,
                hide_unscheduled: this.querySelector('#cfg-h').checked,
                use_glass: this.querySelector('#cfg-glass').checked
            };
            this._config = newConfig;
            fireConfigChange(this, newConfig);
        }));
    }
}
customElements.define('grocy-household-hub-editor', GrocyHouseholdHubEditor);


// ==========================================
// 5. GROCY MEAL PLAN CARD
// ==========================================
class GrocyMealPlanCard extends HTMLElement {
    constructor() { super(); this.attachShadow({ mode: 'open' }); }
    setConfig(config) { this.config = config; this.render(); }
    set hass(hass) { 
        const oldHass = this._hass;
        this._hass = hass; 
        if (!this._initialized) { 
            this._initialized = true; 
            this.render(); 
        } else {
            const mpKey = Object.keys(hass.states).find(k => k.endsWith('_meal_plan_today'));
            if (mpKey && oldHass && oldHass.states[mpKey] !== hass.states[mpKey]) {
                this.render();
            }
        }
    }
    render() {
        if (!this.config || !this._hass) return;
        try {
            const mpKey = Object.keys(this._hass.states).find(k => k.endsWith('_meal_plan_today'));
            const p = (mpKey && this._hass.states[mpKey].attributes) ? this._hass.states[mpKey].attributes.heute_geplant : [];
            
            const isGlass = this.config.use_glass;
            const glassClass = isGlass ? 'glass-mode' : '';
            const glassInner = isGlass ? 'glass-inner' : '';

            let h = (!p || p.length === 0) ? `<div style="text-align:center; padding:32px 16px; color:var(--secondary-text-color);"><ha-icon icon="mdi:silverware-clean" style="--mdc-icon-size:48px; color:var(--divider-color); margin-bottom:16px;"></ha-icon><div>Heute steht nichts auf dem Speiseplan!</div></div>` : p.map(x => `
                <div class="${glassInner}" style="background:var(--secondary-background-color); border-radius:8px; padding:16px; margin-bottom:12px;">
                    <div style="display:flex; align-items:center; margin-bottom:12px;"><div style="background:rgba(var(--rgb-primary-color),0.1); color:var(--primary-color); width:40px; height:40px; border-radius:50%; display:flex; align-items:center; justify-content:center; margin-right:12px;"><ha-icon icon="mdi:chef-hat"></ha-icon></div><div style="font-size:18px; font-weight:bold; color:var(--primary-text-color);">${x.name}</div></div>
                    <div style="display:flex; flex-direction:column; gap:8px; color:var(--secondary-text-color); font-size:14px; margin-bottom:16px;"><span><ha-icon icon="mdi:account-group" style="--mdc-icon-size:18px;"></ha-icon> ${x.servings} Portionen</span>${x.note ? `<span><ha-icon icon="mdi:note-text-outline" style="--mdc-icon-size:18px;"></ha-icon> ${x.note}</span>` : ''}</div>
                    <button class="mp-btn" data-id="${x.recipe_id}" style="width:100%; background:var(--primary-color); color:white; border:none; padding:12px; border-radius:8px; font-weight:bold; cursor:pointer; font-size:15px; box-shadow:0 4px 10px rgba(var(--rgb-primary-color), 0.3);"><ha-icon icon="mdi:pot-steam"></ha-icon> Rezept kochen</button>
                </div>`).join('');
            
            this.shadowRoot.innerHTML = `
                <style>${GLASS_CSS} .mp-btn:active{transform:scale(0.95);}</style>
                <ha-card class="${glassClass}" style="padding:0; border-radius:16px; overflow:hidden; background:var(--ha-card-background, var(--card-background-color, white)); position:relative;">
                    ${isGlass ? '<div class="glass-bg"></div>' : ''}
                    <div class="content-wrapper">
                        <div style="background:${isGlass ? 'rgba(var(--rgb-primary-color), 0.8)' : 'var(--primary-color)'}; color:white; padding:16px; font-size:20px; font-weight:bold; display:flex; align-items:center; backdrop-filter:blur(5px);"><ha-icon icon="mdi:calendar-star" style="margin-right:12px;"></ha-icon> ${this.config.title || 'Heutiger Speiseplan'}</div>
                        <div style="padding:16px;">${h}</div>
                    </div>
                </ha-card>
            `;
            this.shadowRoot.querySelectorAll('.mp-btn').forEach(b => b.addEventListener('click', () => {
                if (navigator.vibrate) navigator.vibrate(50);
                this._hass.callService(getGrocyDomain(this._hass), 'consume_recipe', { recipe_id: parseInt(b.dataset.id) });
                b.innerHTML = '<ha-icon icon="mdi:check"></ha-icon> Wird gekocht...'; b.style.opacity = '0.5';
            }));
        } catch(err) {
            console.error("MealPlan Error:", err);
        }
    }
    static getStubConfig() { return { type: "custom:grocy-meal-plan-card", title: "Heutiger Speiseplan", use_glass: false }; }
    static getConfigElement() { return document.createElement("grocy-meal-plan-editor"); }
}
customElements.define('grocy-meal-plan-card', GrocyMealPlanCard);

class GrocyMealPlanEditor extends HTMLElement {
    setConfig(config) { 
        this._config = config ? JSON.parse(JSON.stringify(config)) : {}; 
        if (!this.innerHTML || this.innerHTML.trim() === '') { this.render(); }
    }
    render() {
        if (!this._config) return;
        this.innerHTML = `
            <div style="display:flex; flex-direction:column; gap:10px;">
                <label style="display:block; margin-bottom:6px; font-weight:bold;">Karten-Titel</label>
                <input type="text" id="cfg-title" value="${this._config.title || 'Heutiger Speiseplan'}" style="width:100%; padding:8px; border-radius:4px; border:1px solid var(--divider-color); box-sizing:border-box; background:var(--card-background-color); color:var(--primary-text-color);">
                <div style="border-top:1px solid var(--divider-color); padding-top:12px; margin-top:8px;">
                    <label style="display:flex; align-items:center; gap:8px; background:rgba(var(--rgb-primary-color), 0.1); padding:10px; border-radius:8px;">
                        <input type="checkbox" id="cfg-glass" ${this._config.use_glass ? 'checked' : ''}> 
                        <span style="font-weight:bold;">✨ Modern UI (Glassmorphism) aktivieren</span>
                    </label>
                </div>
            </div>`;
            
        this.querySelector('#cfg-title').addEventListener('input', e => { 
            const newConfig = { ...this._config, title: e.target.value };
            this._config = newConfig;
            fireConfigChange(this, newConfig); 
        });
        
        this.querySelector('#cfg-glass').addEventListener('change', () => {
            const newConfig = { ...this._config, use_glass: this.querySelector('#cfg-glass').checked };
            this._config = newConfig;
            fireConfigChange(this, newConfig);
        });
    }
}
customElements.define('grocy-meal-plan-editor', GrocyMealPlanEditor);


// ==========================================
// 6. GROCY SHOPPING CARD
// ==========================================
class GrocyShoppingCard extends HTMLElement {
    constructor() { super(); this.attachShadow({ mode: 'open' }); }
    setConfig(config) { this.config = config; this.render(); }
    set hass(hass) { 
        const oldHass = this._hass;
        this._hass = hass; 
        if (!this._initialized) { 
            this._initialized = true; 
            this.render(); 
        } else {
            const listKey = Object.keys(hass.states).find(k => k.endsWith('_shopping_list'));
            if (listKey && oldHass && oldHass.states[listKey] !== hass.states[listKey]) {
                this.render();
            }
        }
    }
    render() {
        if (!this.config || !this._hass) return;
        try {
            const sListKey = Object.keys(this._hass.states).find(k => k.endsWith('_shopping_list'));
            const items = (sListKey && this._hass.states[sListKey].attributes) ? this._hass.states[sListKey].attributes.items : [];
            
            const isGlass = this.config.use_glass;
            const glassClass = isGlass ? 'glass-mode' : '';
            const glassInner = isGlass ? 'glass-inner' : '';
            
            const groups = {}; (items||[]).forEach(i => { if (!groups[i.group]) groups[i.group] = []; groups[i.group].push(i); });
            let contentHtml = (!items || items.length === 0) ? `<div style="text-align:center; padding:24px; color:var(--secondary-text-color); font-style:italic;">Der Einkaufszettel ist leer!</div>` : Object.keys(groups).sort().map(g => `<div style="font-weight:bold; color:var(--primary-color); margin-top:16px; margin-bottom:8px; border-bottom:1px solid var(--divider-color); padding-bottom:4px;">${g}</div>` + groups[g].map(item => `
                <div class="s-row" style="display:flex; align-items:center; padding:8px 0; transition:0.2s;">
                    <label style="display:block; position:relative; padding-left:24px; cursor:pointer; user-select:none;"><input type="checkbox" class="s-chk" data-id="${item.id}" style="position:absolute; opacity:0; cursor:pointer;"><span class="s-cm ${glassInner}" style="position:absolute; top:0; left:0; height:24px; width:24px; background-color:var(--secondary-background-color); border:2px solid var(--divider-color); border-radius:6px; transition:0.2s;"></span></label>
                    <div style="display:flex; justify-content:space-between; flex:1; margin-left:12px; font-size:15px; color:var(--primary-text-color);"><span>${item.name}</span><span style="color:var(--secondary-text-color); font-weight:bold; background:var(--secondary-background-color); padding:2px 8px; border-radius:12px; font-size:12px;">${item.amount}x</span></div>
                </div>`).join('')).join('');

            this.shadowRoot.innerHTML = `
                <style>
                    ${GLASS_CSS}
                    .s-chk:checked ~ .s-cm { background-color:var(--primary-color) !important; border-color:var(--primary-color) !important; } 
                    .s-cm:after { content:""; position:absolute; display:none; left:8px; top:4px; width:5px; height:10px; border:solid white; border-width:0 2px 2px 0; transform:rotate(45deg); } 
                    .s-chk:checked ~ .s-cm:after { display:block; }
                </style>
                <ha-card class="${glassClass}" style="position:relative; padding:16px; border-radius:16px; background:var(--ha-card-background, var(--card-background-color, white)); overflow:hidden;">
                    ${isGlass ? '<div class="glass-bg"></div>' : ''}
                    <div class="content-wrapper">
                        <div style="font-size:20px; font-weight:500; margin-bottom:16px; display:flex; align-items:center; color:var(--primary-text-color);"><ha-icon icon="mdi:cart-outline" style="margin-right:8px; color:var(--primary-color);"></ha-icon>${this.config.title || 'Supermarkt Begleiter'}</div>
                        ${contentHtml}
                    </div>
                </ha-card>`;
                
            this.shadowRoot.querySelectorAll('.s-chk').forEach(box => box.addEventListener('change', e => {
                if (!e.target.checked) return;
                if (navigator.vibrate) navigator.vibrate(50);
                const todoEntity = Object.keys(this._hass.states).find(id => id.startsWith('todo.') && (id.includes('shopping') || id.includes('einkauf'))) || 'todo.sno_ha_grocy_custom_einkaufszettel';
                this._hass.callService('todo', 'update_item', { entity_id: todoEntity, item: e.target.dataset.id, status: 'completed' });
                e.target.closest('.s-row').style.opacity = '0.3';
            }));
        } catch(err) { console.error("Shopping Error", err); }
    }
    static getStubConfig() { return { type: "custom:grocy-shopping-card", title: "Supermarkt Begleiter", use_glass: false }; }
    static getConfigElement() { return document.createElement("grocy-shopping-editor"); }
}
customElements.define('grocy-shopping-card', GrocyShoppingCard);

class GrocyShoppingEditor extends HTMLElement {
    setConfig(config) { 
        this._config = config ? JSON.parse(JSON.stringify(config)) : {}; 
        if (!this.innerHTML || this.innerHTML.trim() === '') { this.render(); }
    }
    render() {
        if (!this._config) return;
        this.innerHTML = `
            <div style="display:flex; flex-direction:column; gap:10px;">
                <label style="display:block; margin-bottom:6px; font-weight:bold;">Karten-Titel</label>
                <input type="text" id="cfg-title" value="${this._config.title || 'Supermarkt Begleiter'}" style="width:100%; padding:8px; border-radius:4px; border:1px solid var(--divider-color); box-sizing:border-box; background:var(--card-background-color); color:var(--primary-text-color);">
                <div style="border-top:1px solid var(--divider-color); padding-top:12px; margin-top:8px;">
                    <label style="display:flex; align-items:center; gap:8px; background:rgba(var(--rgb-primary-color), 0.1); padding:10px; border-radius:8px;">
                        <input type="checkbox" id="cfg-glass" ${this._config.use_glass ? 'checked' : ''}> 
                        <span style="font-weight:bold;">✨ Modern UI (Glassmorphism) aktivieren</span>
                    </label>
                </div>
            </div>
        `;
        
        this.querySelector('#cfg-title').addEventListener('input', e => { 
            const newConfig = { ...this._config, title: e.target.value };
            this._config = newConfig;
            fireConfigChange(this, newConfig); 
        });
        
        this.querySelector('#cfg-glass').addEventListener('change', () => {
            const newConfig = { ...this._config, use_glass: this.querySelector('#cfg-glass').checked };
            this._config = newConfig;
            fireConfigChange(this, newConfig);
        });
    }
}
customElements.define('grocy-shopping-editor', GrocyShoppingEditor);


// ==========================================
// 7. GROCY SMART RECIPE HUB (AI IMPORT)
// ==========================================
class GrocySmartRecipeHub extends HTMLElement {
    set hass(hass) {
        this._hass = hass;
        if (!this.content) {
            this.innerHTML = `
                <ha-card header="🤖 Smart Recipe Hub">
                    <div class="card-content">
                        <p style="color: var(--secondary-text-color); margin-top: 0;">Füge hier dein Rezept oder einen Wochenplan ein. Die KI parst die Zutaten, gleicht sie mit deinem Bestand ab und füllt den Essensplan.</p>
                        <textarea id="recipe-input" rows="8" style="width: 100%; border-radius: 8px; padding: 10px; border: 1px solid var(--divider-color, #ccc); background-color: var(--card-background-color); color: var(--primary-text-color); font-family: inherit; margin-bottom: 15px; resize: vertical; box-sizing: border-box;" placeholder="Beispiel:\\nAm Montag gibt es Chili con Carne.\\nZutaten:\\n- 500g Hackfleisch\\n- 1 Dose Tomaten\\n- 1 Prise Salz..."></textarea>
                        <div id="status-area" style="margin-bottom: 15px; font-size: 14px;"></div>
                        <mwc-button raised id="import-btn" style="width: 100%; --mdc-theme-primary: var(--primary-color);">
                            <ha-icon icon="mdi:auto-fix" style="margin-right: 8px;"></ha-icon>
                            In Grocy analysieren & anlegen
                        </mwc-button>
                    </div>
                </ha-card>
            `;
            this.content = this.querySelector('.card-content');
            this.btn = this.querySelector('#import-btn');
            this.input = this.querySelector('#recipe-input');
            this.status = this.querySelector('#status-area');

            this.btn.addEventListener('click', () => this.importRecipe());
        }
    }

    async importRecipe() {
        const text = this.input.value.trim();
        if (!text) {
            this.status.innerHTML = "<span style='color: var(--error-color, #db4437); font-weight: bold;'>⚠️ Bitte gib einen Text ein!</span>";
            return;
        }

        this.btn.disabled = true;
        this.input.disabled = true;
        this.status.innerHTML = `<span style="display: flex; align-items: center; gap: 8px; color: var(--primary-color); font-weight: bold;"><ha-circular-progress active size="small"></ha-circular-progress> KI analysiert und synchronisiert...</span>`;

        try {
            await this._hass.callService('sno_ha_grocy_custom', 'import_recipe_via_ai', {
                text_input: text
            });
            this.status.innerHTML = "<span style='color: var(--success-color, #0f9d58); font-weight: bold;'>✅ Import abgeschlossen!</span><br><span style='color: var(--secondary-text-color);'>Rezepte und Essenspläne wurden angelegt. Fehlende Zutaten findest du auf der Einkaufsliste.</span>";
            this.input.value = ""; // Textfeld leeren
        } catch (err) {
            this.status.innerHTML = `<span style='color: var(--error-color, #db4437); font-weight: bold;'>❌ Fehler: ${err.message}</span>`;
        } finally {
            this.btn.disabled = false;
            this.input.disabled = false;
        }
    }
}
customElements.define('grocy-smart-recipe-hub', GrocySmartRecipeHub);

// --- REGISTRIERUNG IN HOME ASSISTANT ---
window.customCards = window.customCards || [];
window.customCards.push({ type: "grocy-inventory-explorer-card", name: "Grocy Inventory Explorer", description: "Baukasten für dein Lager (Regal, Grid, Tabelle)", preview: true });
window.customCards.push({ type: "grocy-multi-action-card", name: "Grocy Multi-Action", description: "Schnellzugriff Buttons", preview: true });
window.customCards.push({ type: "grocy-household-hub-card", name: "Grocy Household Hub", description: "Hausarbeiten & Aufgaben", preview: true });
window.customCards.push({ type: "grocy-meal-plan-card", name: "Grocy Meal Plan", description: "Heutiger Essensplan", preview: true });
window.customCards.push({ type: "grocy-shopping-card", name: "Grocy Supermarkt Begleiter", description: "Einkaufsliste sortiert", preview: true });
window.customCards.push({ type: "grocy-smart-recipe-hub", name: "Grocy Smart Recipe Hub", description: "KI Rezept-Import & Wochenplaner", preview: true });

console.info("SNO-HA_Grocy-custom: Karten V1.4.2 Ultimate geladen.");
"""

def _install_sync(hass_config_path):
    """Schreibt alle Dateien physisch auf die Festplatte."""
    www_dir = os.path.join(hass_config_path, "www", "sno_ha_grocy_custom")
    bp_dir = os.path.join(hass_config_path, "blueprints", "automation", "sno_ha_grocy_custom")
    
    os.makedirs(www_dir, exist_ok=True)
    os.makedirs(bp_dir, exist_ok=True)

    with open(os.path.join(bp_dir, "nfc_consume.yaml"), "w", encoding="utf-8") as f: f.write(BP_NFC)
    with open(os.path.join(bp_dir, "chore_reminder.yaml"), "w", encoding="utf-8") as f: f.write(BP_CHORE)
    with open(os.path.join(bp_dir, "auto_ai_import.yaml"), "w", encoding="utf-8") as f: f.write(BP_AI_IMPORT)
    with open(os.path.join(www_dir, "sno-grocy-cards.js"), "w", encoding="utf-8") as f: f.write(JS_BUNDLE)
    
    LOGGER.info("SNO-HA_Grocy-custom: Auto-Installer hat Blueprints und Frontend-Karten erfolgreich generiert!")

async def async_install_assets(hass: HomeAssistant):
    """Startet den Installer asynchron im Hintergrund."""
    await hass.async_add_executor_job(_install_sync, hass.config.path())