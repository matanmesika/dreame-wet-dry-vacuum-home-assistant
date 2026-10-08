/* Work-in-progress presentation only. No cloud requests or raw property writes. */
const DREAME_DOMAIN = "dreame_wet_dry_vacuum";
const registryCache = new WeakMap();
const BAD_STATES = new Set(["unknown", "unavailable"]);
const MAINTENANCE_THRESHOLD = 10;
const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));

// Semantic role -> existing registry unique-ID suffix. Entity names may change.
const ROLES = {
  vacuum: ["vacuum", "vacuum"], warnings: ["sensor", "h15_property_4_1"], errors: ["sensor", "h15_property_4_2"],
  clean_empty: ["binary_sensor", "h15_warn_0_1"], clean_empty_error: ["binary_sensor", "h15_error_23_1"],
  dirty_missing: ["binary_sensor", "h15_error_11_1"], dirty_full: ["binary_sensor", "h15_error_12_1"],
  dirty_tank_status: ["sensor", "h15_property_4_6"],
  dirty_cleaning: ["binary_sensor", "h15_warn_8_1"], dirty_blocked: ["binary_sensor", "h15_error_28_1"],
  battery: ["sensor", "h15_property_3_1"], work: ["sensor", "h15_property_1_28"],
  online: ["binary_sensor", "online"], charging: ["binary_sensor", "charging"],
  clean_progress: ["sensor", "h15_property_1_29"], dry_progress: ["sensor", "h15_property_1_30"],
  clean_count: ["sensor", "h15_property_1_54"], runtime: ["sensor", "h15_property_1_53"],
  filter: ["sensor", "consumable_filter"], brush: ["sensor", "consumable_front_brush"],
  filter_worn: ["binary_sensor", "h15_warn_6_1"], brush_worn: ["binary_sensor", "h15_warn_4_1"],
  mode: ["select", "h15_setting_16_7"], suction: ["select", "h15_setting_16_1"],
  water: ["select", "h15_setting_16_2"], hot_water: ["select", "h15_setting_16_8"],
  wash_mode: ["select", "h15_setting_1_8"], dry_mode: ["select", "h15_setting_1_10"],
  traction: ["select", "h15_setting_23_1"], detergent: ["select", "h15_setting_1_67"],
  moisture: ["select", "h15_setting_26_3"], arm: ["select", "h15_setting_24_1"],
  arm_smart: ["switch", "h15_setting_24_1_bit_0"], arm_hot: ["switch", "h15_setting_24_1_bit_3"],
  arm_suction: ["switch", "h15_setting_24_1_bit_2"], arm_custom: ["switch", "h15_setting_24_1_bit_4"],
  language: ["select", "h15_setting_1_17"], temperature: ["select", "h15_setting_25_1"],
  return_wash: ["select", "h15_setting_1_81"], return_dry: ["select", "h15_setting_1_82"],
  scheduled_wash: ["select", "h15_setting_1_75"], scheduled_dry: ["select", "h15_setting_1_83"],
  repeat: ["select", "h15_setting_1_77"], schedule_time: ["number", "h15_setting_1_76"],
  volume: ["number", "h15_setting_1_14"], custom: ["switch", "h15_setting_16_6"],
  auto_wash: ["switch", "h15_setting_1_7"], auto_dry: ["switch", "h15_setting_1_9"],
  smart_dry: ["switch", "h15_setting_26_1"], protection: ["switch", "h15_setting_26_2"],
  timed_dry: ["switch", "h15_setting_1_11"],
  start_clean: ["button", "h15_command_start_self_clean"], resume_clean: ["button", "h15_command_resume_self_clean"],
  stop_clean: ["button", "h15_command_stop_self_clean"], start_dry: ["button", "h15_command_start_self_dry"],
  stop_dry: ["button", "h15_command_stop_self_dry"], reset_filter: ["button", "h15_command_reset_filter"],
  reset_brush: ["button", "h15_command_reset_front_brush"],
};
const TEXT = {
  he: {
    operation: "תפעול", status: "מצב המכשיר", maintenance: "תחזוקה", battery: "סוללה", work: "פעולה נוכחית",
    online: "חיבור לרשת", charging: "טעינה", connected: "מחובר", disconnected: "מנותק", yes: "כן", no: "לא",
    unknown: "לא ידוע", unavailable: "לא זמין", mode: "מצב ניקוי", suction: "עוצמת שאיבה", water: "כמות מים",
    hot_water: "חימום מים", wash_mode: "מצב ניקוי עצמי", dry_mode: "מצב ייבוש", volume: "עוצמת קול",
    silent: "שקט", low: "נמוך", high: "גבוה", custom: "ניקוי מותאם אישית", auto_wash: "ניקוי וייבוש בחזרה למעמד",
    auto_dry: "ייבוש מברשת אוטומטי", smart_dry: "ייבוש חכם", protection: "הגנה מפני לחות", timed_dry: "ייבוש מתוזמן",
    traction: "הנעה", detergent: "ערבוב חומר ניקוי", moisture: "רגישות לחות", arm: "מצבי הזרוע", language: "שפת קול",
    temperature: "טמפרטורת ברירת מחדל", return_wash: "ניקוי בחזרה למעמד", return_dry: "ייבוש בחזרה למעמד",
    scheduled_wash: "ניקוי מתוזמן", scheduled_dry: "ייבוש מתוזמן", repeat: "חזרה על תזמון", schedule_time: "שעת תזמון",
    start_clean: "ניקוי עצמי", resume_clean: "המשך ניקוי", stop_clean: "עצירת ניקוי", start_dry: "הפעלת ייבוש", stop_dry: "עצירת ייבוש",
    arm_smart: "זרוע — מצב חכם", arm_hot: "זרוע — מים חמים", arm_suction: "זרוע — שאיבה", arm_custom: "זרוע — מותאם אישית",
    device_type: "סוג מכשיר", device: "מכשיר", profile_note: "שינוי סוג המכשיר מאפס את בחירת הישויות הידנית. המיפוי נעשה לפי מזהי האינטגרציה.",
    filter: "פילטר", brush: "מברשת גליל", reset_filter: "איפוס פילטר", reset_brush: "איפוס מברשת",
    clean_progress: "התקדמות ניקוי עצמי", dry_progress: "התקדמות ייבוש", clean_count: "מספר ניקיונות", runtime: "זמן עבודה מצטבר",
    advanced: "הגדרות נוספות ותזמון", alerts: "התראות פעילות", no_alerts: "אין התראות פעילות מדווחות",
    alert_unknown: "חלק מחיוויי ההתראות אינם זמינים; אין להסיק שהמכשיר ללא תקלות.",
    remaining: "נותרו", reset_confirm: "לאפס את מונה התחזוקה במכשיר? יש לאשר רק אחרי החלפה או תחזוקה לפי הוראות היצרן.",
    cancel: "ביטול", confirm: "אישור איפוס", waiting: "הפקודה נשלחה; ממתינים לדיווח המכשיר.",
    wip: "מיפוי בפיתוח · חלק מהאפשרויות עדיין דורשות אימות במכשיר", empty: "אין נתונים זמינים להצגה בקבוצה זו.",
    setup: "לא נמצא מכשיר יחיד התואם לסוג שנבחר. יש להגדיר device_id או entity בכרטיס.",
    registry_error: "אין גישה לרשימת הישויות. אפשר להגדיר entities ידנית או לנסות שוב.", retry: "נסה שוב",
    offline: "המכשיר אינו מדווח כמחובר; פקדי התפעול מושבתים.", loading: "טוען את המכשיר…", error: "הפעולה נכשלה",
    schedule_note: "לפי אזור הזמן של המכשיר. לתזמון חדש: קבע שעה ואז חזרה.",
    cleaning_settings: "הגדרות ניקוי", wash_settings: "ניקוי וייבוש", device_settings: "הגדרות המכשיר",
    back: "חזרה", save: "אישור בחירה",
    tanks: "מיכלי מים", clean_tank: "מיכל מים נקיים", dirty_tank: "מיכל מים מלוכלכים",
    clean_empty: "התראת מים נקיים חסרים", clean_empty_error: "התראת מים נקיים חסרים",
    dirty_missing: "מיכל חסר", dirty_full: "מיכל מלא — יש לרוקן", dirty_cleaning: "נדרש ניקוי", dirty_blocked: "סתימה במיכל",
    tank_no_alert: "אין התראה מדווחת", tank_normal: "תקין", tank_note: "לא מדווח אחוז או מפלס רציף; המצב מבוסס על חיוויי המכשיר שאומתו.",
    tank_partial: "חלק מחיוויי המיכל אינם זמינים.", fault_reported: "המכשיר מדווח על תקלה", warning_reported: "המכשיר מדווח על אזהרה",
    show_maintenance: "פתיחת תחזוקה", native: "חלון המכשיר המובנה",
    warnings: "אזהרות", errors: "שגיאות", vacuum: "ישות השואב הראשית", editor_title: "כותרת", editor_language: "שפת הכרטיס",
    automatic: "אוטומטי", editor_entities: "בחירת ישויות ידנית",
    editor_note: "השאר אוטומטי לזיהוי מהמכשיר, או בחר לכל חיווי ישות מתאימה. ההגדרה משנה רק את הכרטיס.",
    filter_worn: "התראת שחיקת פילטר", brush_worn: "התראת שחיקת מברשת",
    maintenance_required: "נדרשת תחזוקה — ניקוי או החלפה", maintenance_counter_ok: "היתרה מעל סף התחזוקה",
    maintenance_percent_unknown: "אין אחוז יתרה מאומת", maintenance_hours_unknown: "האחוז לא זמין; מוצגת יתרת הזמן שהמכשיר מדווח", maintenance_due: "נדרשת תחזוקה",
  },
  en: {
    operation: "Operation", status: "Device status", maintenance: "Maintenance", battery: "Battery", work: "Current activity",
    online: "Connectivity", charging: "Charging", connected: "Connected", disconnected: "Disconnected", yes: "Yes", no: "No",
    unknown: "Unknown", unavailable: "Unavailable", mode: "Cleaning mode", suction: "Suction", water: "Water level",
    hot_water: "Hot water", wash_mode: "Self-cleaning mode", dry_mode: "Drying mode", volume: "Voice volume",
    silent: "Silent", low: "Low", high: "High", custom: "Personalized cleaning", auto_wash: "Wash & dry on return",
    auto_dry: "Auto roller drying", smart_dry: "Smart drying", protection: "Moisture protection", timed_dry: "Timed drying",
    traction: "Traction", detergent: "Detergent mixing", moisture: "Moisture sensitivity", arm: "Lifting arm modes", language: "Voice language",
    temperature: "Default temperature", return_wash: "Return wash mode", return_dry: "Return dry mode",
    scheduled_wash: "Scheduled wash mode", scheduled_dry: "Scheduled dry mode", repeat: "Schedule repeat", schedule_time: "Scheduled time",
    start_clean: "Self-clean", resume_clean: "Resume cleaning", stop_clean: "Stop cleaning", start_dry: "Start drying", stop_dry: "Stop drying",
    arm_smart: "Lifting arm — Smart", arm_hot: "Lifting arm — Hot Water", arm_suction: "Lifting arm — Suction", arm_custom: "Lifting arm — Custom",
    device_type: "Device type", device: "Device", profile_note: "Changing device type resets manual entity selections. Mapping uses integration registry IDs.",
    filter: "Filter", brush: "Roller brush", reset_filter: "Reset filter", reset_brush: "Reset brush",
    clean_progress: "Self-cleaning progress", dry_progress: "Drying progress", clean_count: "Clean count", runtime: "Total working time",
    advanced: "More settings & scheduling", alerts: "Active alerts", no_alerts: "No reported active alerts",
    alert_unknown: "Some alert states are unavailable; this does not prove the device is fault-free.",
    remaining: "remaining", reset_confirm: "Reset this maintenance counter on the device? Confirm only after replacement or manufacturer-recommended maintenance.",
    cancel: "Cancel", confirm: "Confirm reset", waiting: "Command sent; waiting for device telemetry.",
    wip: "Mapping in progress · some controls still need physical verification", empty: "No data available for this section.",
    setup: "No single H15 found. Set device_id or entity in this card.",
    registry_error: "Cannot access the entity registry. Configure entities manually or retry.", retry: "Retry",
    offline: "Device is not reporting online; operation controls are disabled.", loading: "Loading device…", error: "Action failed",
    schedule_note: "Uses the device timezone. For a new schedule: set time, then repeat.",
    cleaning_settings: "Cleaning settings", wash_settings: "Wash & dry", device_settings: "Device settings",
    back: "Back", save: "Confirm selection",
    tanks: "Water tanks", clean_tank: "Clean water tank", dirty_tank: "Used water tank",
    clean_empty: "Clean water shortage alert", clean_empty_error: "Clean water shortage alert",
    dirty_missing: "Tank missing", dirty_full: "Tank full — empty it", dirty_cleaning: "Cleaning required", dirty_blocked: "Tank blockage",
    tank_no_alert: "No reported alert", tank_normal: "Normal", tank_note: "No percentage or continuous water level is reported; status uses verified device indicators.",
    tank_partial: "Some tank indicators are unavailable.", fault_reported: "Device reports a fault", warning_reported: "Device reports a warning",
    show_maintenance: "Open maintenance", native: "Native device dialog",
    warnings: "Warnings", errors: "Errors", vacuum: "Primary vacuum entity", editor_title: "Title", editor_language: "Card language",
    automatic: "Automatic", editor_entities: "Manual entity selection",
    editor_note: "Leave Automatic to discover from the device, or choose an entity for each indicator. This only changes the card.",
    filter_worn: "Filter wear alert", brush_worn: "Brush wear alert",
    maintenance_required: "Maintenance required — clean or replace", maintenance_counter_ok: "Remaining life above maintenance threshold",
    maintenance_percent_unknown: "No verified remaining percentage", maintenance_hours_unknown: "Percentage unavailable; showing time reported by the device", maintenance_due: "Maintenance required",
  },
};

const H14_ROLES = {
  battery: ["sensor", "battery"], work: ["sensor", "status"],
  online: ["binary_sensor", "online"], charging: ["binary_sensor", "charging"],
  clean_progress: ["sensor", "level_washing"], dry_progress: ["sensor", "level_drying"],
  clean_count: ["sensor", "total_clean_count"], runtime: ["sensor", "total_time"],
  filter: ["sensor", "consumable_filter"], brush: ["sensor", "consumable_front_brush"],
  errors: ["sensor", "error"], warnings: ["sensor", "warn"],
  clean_empty: ["binary_sensor", "clean_water_empty"],
  dirty_full: ["binary_sensor", "dirty_tank_full"], dirty_missing: ["binary_sensor", "dirty_tank_missing"],
  dirty_cleaning: ["binary_sensor", "dirty_tank_not_clean"],
  suction: ["number", "clean_power"], water: ["number", "clean_water"], volume: ["number", "volume"],
  traction: ["select", "power_wheel"], custom: ["switch", "custom_switch"],
  auto_wash: ["switch", "auto_backwash"], auto_dry: ["switch", "auto_dry_switch"],
  timed_dry: ["switch", "time_dry_after_clean"],
  start_clean: ["button", "start_self_clean"], start_dry: ["button", "start_self_dry"],
};
function deviceProfile(device, entries = []) {
  if (!device) return undefined;
  const model = String(device.model || "").toLowerCase();
  if (model.includes("w2449e") || model === "h15 pro heat") return "H15";
  if (model.includes("w2306") || /^h14(?: pro)?$/.test(model)) return "H14";
  const ids = entries.filter((e) => e.device_id === device.id && e.platform === DREAME_DOMAIN).map((e) => e.unique_id || "");
  if (ids.some((id) => /_h15_(property|setting|command)_/.test(id))) return "H15";
  if (ids.some((id) => /_(battery|status|clean_power)$/.test(id))) return "H14";
  return undefined;
}
function profileRoles(profile) { return profile === "H14" ? H14_ROLES : ROLES; }

function validateConfig(config) {
  if (!config || typeof config !== "object") throw new Error("Invalid card configuration");
  if (config.model && !["H15", "H14", "auto"].includes(config.model)) throw new Error("model must be H15, H14 or auto");
  const roles = profileRoles(config.model);
  const entities = config.entities || {};
  for (const [role, id] of Object.entries(entities)) {
    if (!roles[role] || typeof id !== "string" || !id.startsWith(`${roles[role][0]}.`) && !(config.model === "auto" && H14_ROLES[role] && id.startsWith(`${H14_ROLES[role][0]}.`))) {
      throw new Error(`Invalid entity for role: ${role}`);
    }
  }
  if (config.image && !/^\/(?!\/)/.test(config.image)) throw new Error("image must be a local /local/ or /api/ URL");
  if (config.language && !["he", "en"].includes(config.language)) throw new Error("language must be he or en");
  return { ...config, entities: { ...entities } };
}

function resolveDevice(config, devices, entries) {
  const requested = config.model || "H15";
  const matches = (device) => device && (requested === "auto" ? !!deviceProfile(device, entries) : deviceProfile(device, entries) === requested) &&
    entries.some((e) => e.device_id === device.id && e.platform === DREAME_DOMAIN);
  if (config.device_id) return devices.find((d) => d.id === config.device_id && matches(d));
  if (config.entity) {
    const entry = entries.find((e) => e.entity_id === config.entity && e.platform === DREAME_DOMAIN);
    return devices.find((d) => d.id === entry?.device_id && matches(d));
  }
  const candidates = devices.filter(matches);
  return candidates.length === 1 ? candidates[0] : undefined;
}

function resolveRoles(device, entries, overrides = {}, profile = deviceProfile(device, entries)) {
  const result = {};
  const cloudID = device?.identifiers?.find(([domain]) => domain === DREAME_DOMAIN)?.[1];
  if (cloudID) {
    for (const [role, [domain, suffix]] of Object.entries(profileRoles(profile))) {
      const suffixes = ["filter", "brush"].includes(role) ? [`${suffix}_percent`, suffix] : [suffix];
      const entry = suffixes.map((candidate) => entries.find((e) => e.device_id === device.id && e.platform === DREAME_DOMAIN &&
        e.unique_id === `${cloudID}_${candidate}` && e.entity_id.startsWith(`${domain}.`) && !e.disabled_by && !e.hidden_by)).find(Boolean);
      if (entry) result[role] = entry.entity_id;
    }
  }
  return { ...result, ...overrides };
}

function isUsable(state, domain) {
  // Unpressed HA buttons legitimately have state 'unknown'.
  return !!state && state.state !== "unavailable" && (domain === "button" || state.state !== "unknown");
}

function serviceFor(role, state, value, roles = ROLES) {
  const domain = roles[role]?.[0];
  if (!domain || !isUsable(state, domain)) throw new Error("Entity unavailable");
  if (domain === "button") return [domain, "press", {}];
  if (domain === "select") {
    if (!state.attributes.options?.includes(value)) throw new Error("Unsupported option");
    return [domain, "select_option", { option: value }];
  }
  if (domain === "switch") {
    if (!["on", "off"].includes(state.state) || typeof value !== "boolean") throw new Error("Unknown switch state");
    return [domain, value ? "turn_on" : "turn_off", {}];
  }
  if (domain === "number") {
    const number = Number(value);
    const { min, max, step } = state.attributes;
    if (!Number.isFinite(number) || !Number.isFinite(min) || !Number.isFinite(max) || !(step > 0) ||
      number < min || number > max || Math.abs((number - min) / step - Math.round((number - min) / step)) > 1e-6 ||
      (role === "volume" && roles === ROLES && ![0, 1, 2].includes(number))) throw new Error("Unsupported number value");
    return [domain, "set_value", { value: number }];
  }
  throw new Error("Read-only entity");
}

const DEVICE_ART = `<svg viewBox="0 0 200 300" aria-hidden="true">
  <defs><linearGradient id="body"><stop stop-color="#24272c"/><stop offset=".5" stop-color="#525960"/><stop offset="1" stop-color="#202329"/></linearGradient></defs>
  <ellipse cx="100" cy="276" rx="74" ry="12" fill="currentColor" opacity=".08"/>
  <path d="M94 125V27c0-20 24-20 24-4v37" fill="none" stroke="#7b8389" stroke-width="11" stroke-linecap="round"/>
  <path d="M74 112q26-14 52 0v126H74Z" fill="url(#body)" stroke="#7b8389"/>
  <rect x="79" y="139" width="42" height="75" rx="13" fill="#191c22" opacity=".65"/>
  <ellipse cx="100" cy="112" rx="26" ry="9" fill="#434a50"/>
  <ellipse cx="100" cy="111" rx="12" ry="4" fill="none" stroke="var(--primary-color)" stroke-width="2"/>
  <path d="M79 221h42v25H79" fill="#383e44"/><rect x="43" y="240" width="114" height="32" rx="13" fill="url(#body)" stroke="#7b8389"/>
  <rect x="50" y="255" width="100" height="7" rx="3" fill="var(--primary-color)" opacity=".8"/>
</svg>`;

class DreameDeviceCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._tab = "operation";
    this._roles = {};
    this._entries = [];
    this._alerts = [];
    this._pending = false;
    this._message = "";
    this._generation = 0;
    this._scrollPositions = new Map();
    this._scrolling = false;
    this.shadowRoot.addEventListener("click", (event) => this._click(event));
    this.shadowRoot.addEventListener("change", (event) => this._change(event));
    this.shadowRoot.addEventListener("focusout", () => queueMicrotask(() => this._render()));
    this.shadowRoot.addEventListener("scroll", (event) => this._onScroll(event), { capture: true, passive: true });
  }
  disconnectedCallback() {
    for (const unsubscribe of this._registryUnsubscribers || []) unsubscribe();
    this._registryUnsubscribers = []; this._registryConnection = undefined; clearTimeout(this._scrollIdle); this._scrolling = false; }
  _viewKey() { return `${this._tab}/${this._settings || ""}/${this._choice || ""}`; }
  _onScroll(event) {
    if (event.target.id !== "device-panel") return;
    this._scrolling = true;
    this._scrollPositions.set(this._renderedView || this._viewKey(), event.target.scrollTop);
    clearTimeout(this._scrollIdle);
    this._scrollIdle = setTimeout(() => {
      this._scrolling = false;
      if (this._renderDeferred) { this._renderDeferred = false; this._render(); }
    }, 180);
  }
  setConfig(config) {
    this._config = validateConfig(config);
    this._generation++;
    this._roles = this._config.entities;
    this._detectedProfile = undefined;
    this._device = undefined;
    this._alerts = [];
    this._resolved = false;
    this._resolving = false;
    this._registryError = "";
    this._message = "";
    this._confirm = undefined;
    this._settings = undefined;
    this._choice = undefined;
    this._scrollPositions.clear();
    this._renderedView = undefined;
    this._renderedHTML = undefined;
    if (this._hass) this._discover(true);
    this._render();
  }
  set hass(hass) {
    this._hass = hass;
    this._watchRegistry();
    if (this._config && !this._resolved && !this._resolving) this._discover();
    this._render();
  }
  _watchRegistry() {
    const connection = this._hass?.connection;
    if (!connection?.subscribeEvents || connection === this._registryConnection) return;
    for (const unsubscribe of this._registryUnsubscribers || []) unsubscribe();
    this._registryUnsubscribers = [];
    this._registryConnection = connection;
    for (const type of ["entity_registry_updated", "device_registry_updated"]) {
      Promise.resolve(connection.subscribeEvents(() => {
        registryCache.delete(connection);
        if (!this._resolving) this._discover(true);
      }, type)).then((unsubscribe) => {
        if (this._registryConnection === connection) this._registryUnsubscribers.push(unsubscribe);
        else unsubscribe();
      }).catch(() => {});
    }
  }
  getCardSize() { return 8; }
  getGridOptions() { return { columns: 12, min_columns: 6 }; }
  static getStubConfig() { return { title: "Dreame H15 Pro Heat" }; }
  static getConfigElement() { return document.createElement("dreame-device-card-editor"); }
  _t(key) { return TEXT[this._language][key] || key; }
  get _language() { return this._config?.language || (this._hass?.language?.startsWith("he") ? "he" : "en"); }
  get _direction() { return this._language === "he" ? "rtl" : "ltr"; }
  _navIcon(back = false) {
    return `mdi:${back ? "arrow" : "chevron"}-${(this._direction === "rtl") === back ? "right" : "left"}`;
  }
  get _profile() { return this._config?.model === "H14" ? "H14" : this._detectedProfile || deviceProfile(this._device) || "H15"; }
  get _roleMap() { return profileRoles(this._profile); }
  _state(role) { return this._hass?.states?.[this._roles[role]]; }
  _online() { return this._state("online")?.state === "on"; }
  _activityTone() {
    if (!this._online()) return "offline";
    if (this._activeAlerts().length || this._reportedCode("errors") > 0 || this._reportedCode("warnings") > 0 || this._state("vacuum")?.state === "error") return "alert";
    const work = this._state("work");
    if (!work || BAD_STATES.has(work.state)) return "unknown";
    const raw = work.attributes.raw_value;
    if ([5, 26, 27, 28, 42].includes(raw)) return "cleaning";
    if ([6, 23, 24, 25, 32, 33, 34, 35].includes(raw)) return "drying";
    if ([11, 12, 30, 31, 37, 43].includes(raw)) return "paused";
    if (raw === 4 || (raw == null && this._state("charging")?.state === "on")) return "charging";
    return "idle";
  }
  _batteryTone() {
    const battery = this._state("battery");
    const value = Number(battery?.state);
    if (!battery || BAD_STATES.has(battery.state) || !Number.isFinite(value) || value < 0 || value > 100) return "unknown";
    return value <= 20 ? "low" : "normal";
  }
  _progressValue() {
    const tone = this._activityTone();
    const role = tone === "cleaning" ? "clean_progress" : tone === "drying" ? "dry_progress" : undefined;
    const state = role && this._state(role);
    if (!state || BAD_STATES.has(state.state)) return undefined;
    const value = Number(state.state);
    return Number.isFinite(value) && value >= 0 && value <= 100 ? value : undefined;
  }
  _contextReady(role) {
    if (this._profile !== "H15") return true;
    if (["mode", "suction", "water", "hot_water"].includes(role) && this._state("custom")?.state !== "on") return false;
    if (["suction", "water"].includes(role) && this._state("mode")?.attributes.raw_value !== 4 && this._state("mode")?.state !== "Personalized") return false;
    if (role === "suction" && this._state("hot_water")?.attributes.raw_value !== 0 && this._state("hot_water")?.state !== "Off") return false;
    return true;
  }
  _ready(role) { return this._contextReady(role) && this._online() && !this._pending && isUsable(this._state(role), this._roleMap[role]?.[0]); }
  async _discover(retry = false) {
    this._resolving = true;
    const generation = this._generation;
    const hass = this._hass;
    const cacheKey = hass.connection || hass;
    try {
      if (retry) registryCache.delete(cacheKey);
      if (!registryCache.has(cacheKey)) registryCache.set(cacheKey, Promise.all([
        hass.callWS({ type: "config/device_registry/list" }), hass.callWS({ type: "config/entity_registry/list" }),
      ]));
      const [devices, entries] = await registryCache.get(cacheKey);
      if (generation !== this._generation) return;
      this._entries = entries;
      this._device = resolveDevice(this._config, devices, entries);
      this._detectedProfile = deviceProfile(this._device, entries);
      this._roles = resolveRoles(this._device, entries, this._config.entities, this._detectedProfile);
      this._alerts = entries.filter((e) => this._device && e.device_id === this._device.id && e.platform === DREAME_DOMAIN &&
        /^binary_sensor\./.test(e.entity_id) && /_h15_(warn|error)_\d+_\d+$/.test(e.unique_id) && !e.disabled_by && !e.hidden_by);
      this._registryError = "";
    } catch {
      if (generation !== this._generation) return;
      registryCache.delete(cacheKey);
      this._registryError = this._t("registry_error");
    } finally {
      if (generation === this._generation) {
        this._resolved = true;
        this._resolving = false;
        this._render();
      }
    }
  }
  _value(role) {
    const state = this._state(role);
    if (!state || BAD_STATES.has(state.state)) return this._t(state?.state === "unavailable" ? "unavailable" : "unknown");
    if (role === "online") return this._t(state.state === "on" ? "connected" : state.state === "off" ? "disconnected" : "unknown");
    if (role === "charging") return this._t(state.state === "on" ? "yes" : "no");
    if (this._hass.formatEntityState) return this._hass.formatEntityState(state);
    return `${state.state}${state.attributes.unit_of_measurement ? ` ${state.attributes.unit_of_measurement}` : ""}`;
  }
  _metric(role, icon) {
    if (!this._roles[role]) return "";
    const connection = role === "online" ? ` data-connection="${this._state(role)?.state === "on" ? "online" : this._state(role)?.state === "off" ? "offline" : "unknown"}"` : "";
    return `<div class="metric metric-${role}"${connection}><ha-icon icon="${icon}"></ha-icon><span>${escapeHTML(this._t(role))}</span><strong>${escapeHTML(this._value(role))}</strong></div>`;
  }
  _button(role, icon) {
    if (!this._roles[role]) return "";
    if (["resume_clean", "stop_clean", "stop_dry"].includes(role) &&
      !isUsable(this._state(role), "button")) return "";
    const setting = { start_clean: "wash_mode", start_dry: "dry_mode" }[role];
    const subtitle = setting && this._roles[setting] ? `<small>${escapeHTML(this._value(setting))}</small>` : "";
    return `<button class="action" data-command="${role}" data-active="${(role === "start_clean" && this._activityTone() === "cleaning") || (role === "start_dry" && this._activityTone() === "drying")}" ${this._ready(role) ? "" : "disabled"}><ha-icon icon="${icon}"></ha-icon><span>${escapeHTML(this._t(role))}${subtitle}</span></button>`;
  }
  _control(role) {
    if (!this._roles[role] || !this._state(role) || !this._roleMap[role]) return "";
    if (this._profile === "H15" && ["suction", "water"].includes(role) && this._state("mode")?.state !== "Personalized" && this._state("mode")?.attributes.raw_value !== 4) return "";
    const state = this._state(role);
    const disabled = this._ready(role) ? "" : "disabled";
    let input = "";
    const label = escapeHTML(this._t(role));
    const options = state.attributes.options || [];
    if (this._roleMap[role][0] === "select") {
      input = `<button class="setting-value" data-setting="${role}" aria-label="${label}" ${disabled || (!options.length ? "disabled" : "")}>${escapeHTML(this._value(role))}<ha-icon icon="mdi:chevron-down"></ha-icon></button>`;
    } else if (this._roleMap[role][0] === "switch") {
      input = `<input aria-label="${label}" type="checkbox" role="switch" data-role="${role}" ${state.state === "on" ? "checked" : ""} ${disabled}>`;
      if (BAD_STATES.has(state.state)) input += `<small>${escapeHTML(this._value(role))}</small>`;
    } else if (role === "volume" && this._profile === "H15") {
      const known = !BAD_STATES.has(state.state) && [0, 1, 2].includes(Number(state.state));
      const levels = [this._t("silent"), this._t("low"), this._t("high")];
      input = `<div class="volume" dir="${this._direction}"><input dir="${this._direction}" aria-label="${label}" aria-valuetext="${escapeHTML(known ? levels[Number(state.state)] : this._t("unknown"))}" type="range" min="0" max="2" step="1" data-role="volume" value="${known ? Number(state.state) : 0}" ${known ? disabled : "disabled"}>
        <div class="levels">${levels.map((l, i) => `<span class="${known && Number(state.state) === i ? "selected" : ""}">${l}</span>`).join("")}</div>${known ? "" : `<small>${escapeHTML(this._value(role))}</small>`}</div>`;
    } else if (role === "schedule_time") {
      const raw = Number(state.state);
      const time = !BAD_STATES.has(state.state) && Number.isInteger(raw) && raw >= 0 && raw < 1440 ? `${String(Math.floor(raw / 60)).padStart(2, "0")}:${String(raw % 60).padStart(2, "0")}` : "";
      input = `<input aria-label="${label}" type="time" step="60" data-role="${role}" value="${time}" ${disabled}>`;
    }
    if (!input && this._roleMap[role][0] === "number") {
      const { min, max, step } = state.attributes;
      const known = !BAD_STATES.has(state.state) && Number.isFinite(Number(state.state));
      input = `<input aria-label="${label}" type="range" min="${escapeHTML(min)}" max="${escapeHTML(max)}" step="${escapeHTML(step)}" data-role="${role}" value="${escapeHTML(known ? state.state : min)}" ${known ? disabled : "disabled"}><small>${escapeHTML(this._value(role))}</small>`;
    }
    return `<div class="row"><span>${label}</span><div class="input">${input}</div></div>`;
  }
  _alertEntries() {
    const entries = [...this._alerts];
    for (const role of ["clean_empty", "clean_empty_error", "dirty_missing", "dirty_full", "dirty_cleaning", "dirty_blocked", "filter_worn", "brush_worn"]) {
      const id = this._roles[role];
      if (id && !entries.some((e) => e.entity_id === id)) entries.push({ entity_id: id, original_name: this._t(role) });
    }
    return entries;
  }
  _activeAlerts() {
    return this._alertEntries().filter((e) => this._hass.states[e.entity_id]?.state === "on");
  }
  _reportedCode(role) {
    const state = this._state(role);
    if (!state || BAD_STATES.has(state.state)) return undefined;
    const raw = state.attributes.raw_value;
    if (!(typeof raw === "number" || typeof raw === "string" && /^\d+$/.test(raw))) return undefined;
    const value = Number(raw);
    return Number.isSafeInteger(value) && value >= 0 ? value : undefined;
  }
  _faultNotice() {
    const active = this._activeAlerts();
    if (!active.length && !(this._reportedCode("errors") > 0) && !(this._reportedCode("warnings") > 0) && this._state("vacuum")?.state !== "error") return "";
    const fault = active.find((e) => /_h15_error_/.test(e.unique_id || "") || ["clean_empty_error", "dirty_missing", "dirty_full", "dirty_blocked"].some((r) => this._roles[r] === e.entity_id));
    const chosen = fault || (this._reportedCode("errors") > 0 || this._state("vacuum")?.state === "error" ? undefined : active[0]);
    const label = chosen ? this._hass.states[chosen.entity_id].attributes.friendly_name || chosen.original_name : this._t(this._reportedCode("errors") > 0 || this._state("vacuum")?.state === "error" ? "fault_reported" : "warning_reported");
    return `<button class="fault-notice" data-tab="maintenance"><ha-icon icon="mdi:alert-circle-outline"></ha-icon><span>${escapeHTML(label)}<small>${this._t("show_maintenance")}</small></span><ha-icon icon="${this._navIcon()}"></ha-icon></button>`;
  }
  _tank(kind) {
    const roles = kind === "clean" ? ["clean_empty", "clean_empty_error"] : ["dirty_full", "dirty_missing", "dirty_blocked", "dirty_cleaning"];
    const active = this._online() ? roles.filter((r) => this._state(r)?.state === "on") : [];
    const complete = this._online() && roles.every((r) => ["on", "off"].includes(this._state(r)?.state));
    const rawTankState = kind === "dirty" && this._online() ? this._state("dirty_tank_status")?.state?.toLowerCase() : undefined;
    const knownTankState = rawTankState === "normal" || rawTankState === "full";
    const tankFull = rawTankState === "full";
    const value = active.length ? [...new Set(active.map((r) => this._t(r)))].join(" · ")
      : knownTankState ? this._t(tankFull ? "dirty_full" : "tank_normal")
        : this._t(complete ? "tank_no_alert" : "unknown");
    const indicatorsComplete = complete || knownTankState;
    return `<section class="tank" data-alert="${active.length > 0 || tankFull}"><div class="row"><ha-icon icon="${kind === "clean" ? "mdi:water-outline" : "mdi:water-alert-outline"}"></ha-icon><strong>${this._t(`${kind}_tank`)}</strong></div><div class="tank-status">${escapeHTML(value)}</div>${!indicatorsComplete ? `<small>${this._t("tank_partial")}</small>` : ""}<small>${this._t("tank_note")}</small></section>`;
  }
  _alertList() {
    const active = this._activeAlerts();
    const decoded = [...new Set(["errors", "warnings"].flatMap((role) => {
      const state = this._state(role);
      if (!state || BAD_STATES.has(state.state)) return [];
      const values = state.attributes.active_alerts || state.attributes.alerts || [];
      return Array.isArray(values) ? values.filter((v) => typeof v === "string") : [];
    }))];
    const decodedHTML = decoded.map((text) => `<div class="alert"><ha-icon icon="mdi:alert-outline"></ha-icon>${escapeHTML(text)}</div>`).join("");
    const reported = this._reportedCode("errors") > 0 || this._reportedCode("warnings") > 0 || this._state("vacuum")?.state === "error";
    const missingFault = (this._reportedCode("errors") > 0 || this._state("vacuum")?.state === "error") && !active.some((e) => /_h15_error_/.test(e.unique_id || "") || ["clean_empty_error", "dirty_missing", "dirty_full", "dirty_blocked"].some((r) => this._roles[r] === e.entity_id));
    // No alert entries means no verification, not a healthy device.
    const entries = this._alertEntries();
    const unknown = !entries.length || entries.some((e) => !["on", "off"].includes(this._hass.states[e.entity_id]?.state)) || this._reportedCode("errors") === undefined || this._reportedCode("warnings") === undefined;
    return `${decodedHTML}${!decoded.length && active.length ? active.map((e) => `<div class="alert"><ha-icon icon="mdi:alert-outline"></ha-icon>${escapeHTML(this._hass.states[e.entity_id].attributes.friendly_name || e.original_name || e.entity_id)}</div>`).join("") : !decoded.length && reported ? `<div class="alert">${this._t(this._reportedCode("errors") > 0 || this._state("vacuum")?.state === "error" ? "fault_reported" : "warning_reported")}</div>` : !decoded.length ? `<p class="muted">${escapeHTML(this._t("no_alerts"))}</p>` : ""}
      ${active.length && missingFault ? `<div class="alert">${this._t("fault_reported")}</div>` : ""}${unknown ? `<p class="muted">${escapeHTML(this._t("alert_unknown"))}</p>` : ""}`;
  }
  _consumable(role, reset) {
    const state = this._state(role);
    if (!state) return "";
    const { percent, hours, required } = this._maintenanceState(role);
    const value = percent !== undefined ? `${percent}% ${this._t("remaining")}` : hours !== undefined ? `~${hours} h ${this._t("remaining")}` : this._t("unknown");
    return `<section class="consumable" data-maintenance="${required ? "required" : percent === undefined ? "unknown" : "normal"}"><div class="row"><strong>${escapeHTML(this._t(role))}</strong><span>${escapeHTML(value)}</span></div>
      ${percent !== undefined ? `<progress dir="${this._direction}" value="${percent}" max="100" aria-label="${escapeHTML(this._t(role))}"></progress>` : ""}
      <small class="maintenance-status">${this._t(required ? "maintenance_required" : percent === undefined ? hours === undefined ? "maintenance_percent_unknown" : "maintenance_hours_unknown" : "maintenance_counter_ok")}</small>
      ${this._button(reset, "mdi:restart")}</section>`;
  }
  _maintenanceState(role) {
    const state = this._state(role);
    let percent;
    const hours = this._reportedHours(role, state);
    if (state && !BAD_STATES.has(state.state) && state.attributes.full_life_source !== "unknown") {
      // Use verified attributes or an explicitly selected percentage sensor.
      // Never infer a maximum lifetime from the remaining hours.
      const raw = state.attributes.percent_remaining ?? (state.attributes.unit_of_measurement === "%" ? state.state : undefined);
      if (typeof raw === "number" || typeof raw === "string" && /^\d+(\.\d+)?$/.test(raw)) {
        const value = Number(raw);
        if (Number.isFinite(value) && value >= 0 && value <= 100) percent = value;
      }
    }
    return { percent, hours, required: this._state(`${role}_worn`)?.state === "on" || percent !== undefined && percent <= MAINTENANCE_THRESHOLD };
  }
  _reportedHours(role, state) {
    const candidates = [state];
    const registryEntry = this._entries.find((entry) => entry.entity_id === this._roles[role]);
    if (registryEntry?.unique_id?.endsWith("_percent")) {
      const baseUniqueId = registryEntry.unique_id.slice(0, -"_percent".length);
      const base = this._entries.find((entry) => entry.device_id === registryEntry.device_id && entry.unique_id === baseUniqueId && !entry.disabled_by && !entry.hidden_by);
      if (base?.entity_id && this._hass?.states?.[base.entity_id]) candidates.push(this._hass.states[base.entity_id]);
    }
    for (const candidate of candidates) {
      if (!candidate) continue;
      const rawMinutes = candidate.attributes?.minutes_remaining;
      const minutes = rawMinutes === null || rawMinutes === undefined || rawMinutes === "" ? NaN : Number(rawMinutes);
      if (Number.isFinite(minutes) && minutes >= 0) return Math.round(minutes / 60);
      const rawHours = candidate.attributes?.hours_remaining ?? (candidate.attributes?.unit_of_measurement === "h" ? candidate.state : undefined);
      const hours = rawHours === null || rawHours === undefined || rawHours === "" ? NaN : Number(rawHours);
      if (Number.isFinite(hours) && hours >= 0 && !BAD_STATES.has(candidate.state)) return Math.round(hours);
    }
    return undefined;
  }
  _maintenanceNotice() {
    const due = ["filter", "brush"].filter((role) => this._maintenanceState(role).required);
    if (!due.length) return "";
    return `<button class="maintenance-notice" data-tab="maintenance"><ha-icon icon="mdi:tools"></ha-icon><span>${this._t("maintenance_due")} — ${due.map((r) => this._t(r)).join(" · ")}</span><ha-icon icon="${this._navIcon()}"></ha-icon></button>`;
  }
  _panel() {
    if (this._tab === "operation") {
      if (this._choice) {
        const options = this._state(this._choice)?.attributes.options || [];
        return `<div class="subheading"><button data-back aria-label="${this._t("back")}"><ha-icon icon="${this._navIcon(true)}"></ha-icon></button><strong>${escapeHTML(this._t(this._choice))}</strong></div>
          <div class="choice-list">${options.map((option) => `<button data-option="${escapeHTML(option)}" aria-pressed="${option === this._draftOption}" ${this._ready(this._choice) ? "" : "disabled"}><span>${escapeHTML(option)}</span><ha-icon icon="${option === this._draftOption ? "mdi:check-circle" : "mdi:circle-outline"}"></ha-icon></button>`).join("")}</div>
          <button class="save-choice" data-save-option ${this._ready(this._choice) && options.includes(this._draftOption) ? "" : "disabled"}>${this._t("save")}</button>`;
      }
      const groups = {
        cleaning_settings: ["mode", "suction", "water", "hot_water", "detergent"],
        wash_settings: ["wash_mode", "dry_mode", "auto_dry", "smart_dry", "auto_wash", "protection"],
        device_settings: ["traction", "arm_smart", "arm_hot", "arm_suction", "arm_custom", "volume", "language"],
        advanced: ["moisture", "timed_dry", "schedule_time", "repeat"],
      };
      if (groups[this._settings]) {
        const controls = groups[this._settings].map((role) => this._control(role)).join("");
        return `<div class="subheading"><button data-back aria-label="${this._t("back")}"><ha-icon icon="${this._navIcon(true)}"></ha-icon></button><strong>${this._t(this._settings)}</strong></div>${controls || `<p class="muted">${this._t("empty")}</p>`}${this._settings === "advanced" ? `<p class="muted">${this._t("schedule_note")}</p>` : ""}`;
      }
      const row = (group, subtitle) => groups[group].some((r) => this._roles[r]) ? `<button class="setting-group" data-group="${group}"><div><strong>${this._t(group)}</strong><small>${escapeHTML(subtitle)}</small></div><ha-icon icon="${this._navIcon()}"></ha-icon></button>` : "";
      return `<div class="actions">${this._button("start_clean", "mdi:water-sync")}${this._button("resume_clean", "mdi:play")}${this._button("stop_clean", "mdi:stop")}${this._button("start_dry", "mdi:hair-dryer")}${this._button("stop_dry", "mdi:stop")}</div>
        ${this._control("custom")}${row("cleaning_settings", this._value("mode"))}${row("wash_settings", ["wash_mode", "dry_mode"].filter((r) => this._roles[r]).map((r) => this._value(r)).join(" · "))}${row("device_settings", `${this._t("traction")} · ${this._t("arm")} · ${this._t("volume")}`)}${row("advanced", this._t("schedule_note"))}`;
    }
    if (this._tab === "status") return `<div class="metrics">${this._metric("work", "mdi:state-machine")}${this._metric("charging", "mdi:battery-charging")}${this._metric("clean_progress", "mdi:water-sync")}${this._metric("dry_progress", "mdi:hair-dryer")}${this._metric("clean_count", "mdi:counter")}${this._metric("runtime", "mdi:timer-outline")}</div><h3>${this._t("alerts")}</h3>${this._alertList()}`;
    return `<h3>${this._t("tanks")}</h3>${this._tank("clean")}${this._tank("dirty")}${this._consumable("filter", "reset_filter")}${this._consumable("brush", "reset_brush")}<h3>${this._t("alerts")}</h3>${this._alertList()}`;
  }
  _render() {
    if (!this._config || !this._hass) return;
    const view = this._viewKey();
    // Keep the scroller DOM alive throughout touch/momentum scrolling.
    if (this._scrolling && view === this._renderedView) { this._renderDeferred = true; return; }
    // Don't replace a select/range/time input while the user is interacting.
    const focused = this.shadowRoot.activeElement;
    if (focused && ["INPUT", "SELECT"].includes(focused.tagName)) return;
    this._advanced = this.shadowRoot.querySelector("details")?.open ?? this._advanced;
    const ready = Object.keys(this._roles).length > 0;
    const title = this._config.title || this._device?.name_by_user || this._device?.name || "Dreame H15 Pro Heat";
    const image = this._config.image ? `<img src="${escapeHTML(this._config.image)}" alt="${escapeHTML(title)}">` : DEVICE_ART;
    const progress = this._progressValue();
    const ring = progress === undefined ? "" : `<svg class="progress-ring" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="45" pathLength="100"></circle><circle class="progress-value" cx="50" cy="50" r="45" pathLength="100" stroke-dasharray="100" stroke-dashoffset="${100 - progress}"></circle></svg>`;
    const progressLabel = progress === undefined ? "" : `<div class="progress-label" role="progressbar" aria-label="${escapeHTML(this._t(this._activityTone() === "cleaning" ? "clean_progress" : "dry_progress"))}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress}">${progress}%</div>`;
    const confirm = this._confirm ? `<div class="confirmation" role="alertdialog" aria-label="${this._t(this._confirm)}"><p>${this._t("reset_confirm")}</p><div class="actions"><button data-cancel>${this._t("cancel")}</button><button data-confirm class="danger">${this._t("confirm")}</button></div></div>` : "";
    const html = `<style>${DREAME_STYLES}</style><ha-card dir="${this._direction}" data-device-state="${this._activityTone()}" data-battery="${this._batteryTone()}">
      <header><div class="heading"><div class="eyebrow">DREAME · WET & DRY</div><h2>${escapeHTML(title)}</h2><div class="activity">${escapeHTML(this._value("work"))}</div>${this._roles.vacuum ? `<button class="native-link" data-native>${this._t("native")}</button>` : ""}</div><div class="device-badge"><div class="hero">${ring}${image}</div>${progressLabel}</div></header>
      <div class="summary">${this._metric("battery", "mdi:battery")}${this._metric("online", "mdi:wifi")}</div>
      ${this._faultNotice()}
      ${this._maintenanceNotice()}
      <nav role="tablist" aria-label="Dreame">${["operation", "status", "maintenance"].map((tab) => `<button role="tab" id="tab-${tab}" aria-controls="device-panel" aria-selected="${this._tab === tab}" data-tab="${tab}">${this._t(tab)}</button>`).join("")}</nav>
      ${this._registryError ? `<p class="notice">${escapeHTML(this._registryError)} <button data-retry>${this._t("retry")}</button></p>` : ""}
      ${!ready ? `<p class="notice">${this._t(this._resolving ? "loading" : "setup")} ${!this._resolving ? `<button data-retry>${this._t("retry")}</button>` : ""}</p>` : ""}
      ${ready && !this._online() ? `<p class="notice">${this._t("offline")}</p>` : ""}
      ${this._message ? `<p class="notice" role="status">${escapeHTML(this._message)}</p>` : ""}
      ${confirm}<div id="device-panel" role="tabpanel" aria-labelledby="tab-${this._tab}" class="panel">${ready ? this._panel() : ""}</div>
      <footer>${this._t("wip")}</footer></ha-card>`;
    // Unrelated HA updates must not recreate controls or reset scrolling.
    if (html === this._renderedHTML) return;
    const previousPanel = this.shadowRoot.querySelector("#device-panel");
    if (previousPanel && this._renderedView) this._scrollPositions.set(this._renderedView, previousPanel.scrollTop);
    this.shadowRoot.innerHTML = html;
    this._renderedHTML = html;
    this._renderedView = view;
    const panel = this.shadowRoot.querySelector("#device-panel");
    if (panel) panel.scrollTop = this._scrollPositions.get(view) || 0;
    this.shadowRoot.querySelector("img")?.addEventListener("error", (event) => { event.target.parentNode.innerHTML = DEVICE_ART; }, { once: true });
  }
  _click(event) {
    const target = event.target.closest("button");
    if (!target || target.disabled) return;
    if (target.dataset.tab) {
      this._tab = target.dataset.tab;
      this._confirm = undefined;
      this._settings = undefined;
      this._choice = undefined;
      this._render();
      this.shadowRoot.querySelector(`[data-tab="${this._tab}"]`)?.focus({ preventScroll: true });
    } else if (target.hasAttribute("data-native") && this._roles.vacuum) {
      this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId: this._roles.vacuum }, bubbles: true, composed: true }));
    } else if (target.dataset.group) {
      this._settings = target.dataset.group;
      this._message = "";
      this._render();
    } else if (target.dataset.setting && this._ready(target.dataset.setting)) {
      this._choice = target.dataset.setting;
      this._draftOption = this._state(this._choice)?.state;
      this._render();
    } else if (target.hasAttribute("data-option")) {
      if (!this._choice || !this._state(this._choice)?.attributes.options?.includes(target.dataset.option)) return;
      this._draftOption = target.dataset.option;
      this._render();
    } else if (target.hasAttribute("data-save-option")) {
      if (!this._choice) return;
      this._act(this._choice, this._draftOption);
    } else if (target.hasAttribute("data-back")) {
      if (this._choice) this._choice = undefined;
      else this._settings = undefined;
      this._render();
    } else if (target.hasAttribute("data-retry")) this._discover(true);
    else if (target.hasAttribute("data-cancel")) { this._confirm = undefined; this._render(); }
    else if (target.hasAttribute("data-confirm")) {
      const role = this._confirm;
      this._confirm = undefined;
      this._act(role, undefined, true);
    } else if (target.dataset.command) {
      const role = target.dataset.command;
      if (!this._ready(role)) return;
      if (role.startsWith("reset_")) { this._confirm = role; this._render(); }
      else this._act(role);
    }
  }
  _change(event) {
    const target = event.target;
    const role = target.dataset.role;
    if (!role) return;
    let value = target.type === "checkbox" ? target.checked : target.value;
    if (role === "schedule_time") {
      if (!/^\d{2}:\d{2}$/.test(value)) return;
      const [hours, minutes] = value.split(":").map(Number);
      if (hours > 23 || minutes > 59) return;
      value = hours * 60 + minutes;
    }
    target.blur();
    this._act(role, value);
  }
  async _act(role, value, confirmed = false) {
    if (!this._ready(role) || (role.startsWith("reset_") && !confirmed)) return;
    const generation = this._generation;
    try {
      const [domain, service, data] = serviceFor(role, this._state(role), value, this._roleMap);
      this._pending = true;
      this._message = "";
      this._render();
      await this._hass.callService(domain, service, { entity_id: this._roles[role], ...data });
      if (generation === this._generation) {
        this._message = this._t("waiting");
        if (this._choice === role) this._choice = undefined;
      }
    } catch (err) {
      if (generation === this._generation) this._message = `${this._t("error")}: ${err.message || err}`;
    } finally {
      this._pending = false;
      this._render();
    }
  }
}

const DREAME_STYLES = `
  :host{display:block;font-family:var(--paper-font-body1_-_font-family,system-ui);color:var(--primary-text-color)}
  ha-card{display:block;overflow:hidden;border-radius:var(--ha-card-border-radius,24px);background:var(--ha-card-background,var(--card-background-color));border:1px solid var(--divider-color);padding:22px;box-sizing:border-box}
  header{text-align:center}.eyebrow{font-size:10px;letter-spacing:.2em;color:var(--secondary-text-color)}h2{font-size:23px;margin:8px 0}h3{font-size:16px;margin:22px 0 12px}.activity{font-size:19px;color:var(--primary-color);min-height:24px}
  .summary,.metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:20px}.metric{display:grid;grid-template-columns:24px 1fr;gap:6px 10px;align-items:center;padding:12px;border-radius:16px;background:var(--secondary-background-color);min-width:0}.metric ha-icon{grid-row:span 2;color:var(--primary-color)}.metric span{font-size:11px;color:var(--secondary-text-color)}.metric strong{font-size:15px;overflow-wrap:anywhere}
  .hero{height:215px;display:flex;justify-content:center;margin:4px auto 12px}.hero svg{height:100%;max-width:100%}.hero img{height:100%;max-width:100%;object-fit:contain}
  nav{display:flex;background:var(--secondary-background-color);padding:4px;border-radius:14px;gap:4px}nav button{flex:1;font-size:12px;min-width:0;padding:12px 5px;border:0;border-radius:10px;background:transparent}nav button[aria-selected=true]{background:var(--ha-card-background,var(--card-background-color));color:var(--primary-color);box-shadow:var(--ha-card-box-shadow,none)}
  button,input,select{font:inherit;color:inherit}button{cursor:pointer;border:1px solid var(--divider-color);border-radius:12px;background:var(--secondary-background-color);min-height:44px;padding:10px 14px}button:disabled,input:disabled,select:disabled{opacity:.45;cursor:not-allowed}button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:2px solid var(--primary-color);outline-offset:3px}
  .panel{padding-top:18px}.actions{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px}.action{display:flex;align-items:center;justify-content:center;gap:7px;flex:1 1 120px;font-size:12px}.action ha-icon{--mdc-icon-size:20px;color:var(--primary-color)}
  .row{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:14px 0;border-bottom:1px solid var(--divider-color);font-size:13px}.row>span:first-child{flex:1;min-width:0}.input{flex:0 1 58%;min-width:0}.input select{width:100%;text-overflow:ellipsis}.input:has(input[type=checkbox]){flex:none;display:flex;align-items:center;gap:8px}select,input[type=time]{border:1px solid var(--divider-color);border-radius:9px;background:var(--secondary-background-color);padding:10px;min-height:44px;box-sizing:border-box;max-width:100%}input[type=checkbox]{width:38px;height:24px;accent-color:var(--primary-color);cursor:pointer}input[type=range]{width:100%;accent-color:var(--primary-color);min-height:32px;margin:0}.levels{display:flex;justify-content:space-between;font-size:10px;color:var(--secondary-text-color)}.levels .selected{color:var(--primary-color);font-weight:700}
  details{margin-top:18px}summary{cursor:pointer;min-height:44px;line-height:44px;font-size:13px}.muted,small{font-size:12px;color:var(--secondary-text-color);line-height:1.6}.notice,.confirmation{font-size:13px;line-height:1.6;padding:12px;border-radius:12px;background:var(--secondary-background-color)}.notice button{font-size:12px}.alert{display:flex;align-items:center;gap:8px;font-size:13px;padding:12px;margin-bottom:8px;background:var(--secondary-background-color);border-inline-start:3px solid var(--error-color);border-radius:8px}.alert ha-icon,.danger{color:var(--error-color)}.consumable{padding:4px 14px 14px;border:1px solid var(--divider-color);border-radius:16px;margin-bottom:14px}.consumable .row{border:0}.consumable progress{width:100%;height:8px;accent-color:var(--primary-color)}.consumable small{display:block;margin:4px 0 12px}.consumable .action{width:100%}footer{text-align:center;font-size:10px;color:var(--secondary-text-color);line-height:1.6;margin-top:18px}
  /* Compact native-card presentation; HA theme owns the colors and surface. */
  ha-card{padding:16px;border-radius:var(--ha-card-border-radius,18px)}
  header{display:flex;align-items:center;justify-content:space-between;gap:12px;text-align:start;min-height:82px}
  .heading{flex:1;min-width:0}.eyebrow{font-size:9px;letter-spacing:.14em}h2{font-size:19px;margin:6px 0;overflow-wrap:anywhere}.activity{font-size:14px;min-height:18px}
  .hero{height:82px;flex:0 0 62px;margin:0}.hero svg,.hero img{width:100%;height:100%;object-fit:contain}
  .summary{display:flex;flex-wrap:wrap;gap:16px;margin:8px 0 14px}.summary .metric{display:flex;gap:6px;padding:0;background:transparent;border-radius:0}.summary .metric span{font-size:11px}.summary .metric strong{font-size:12px;font-weight:500}.summary ha-icon{--mdc-icon-size:16px}
  nav{border-radius:10px;padding:3px;gap:2px}nav button{font-size:11px;border-radius:8px;padding:8px 4px;min-height:40px}nav button[aria-selected=true]{box-shadow:none}
  .panel{padding-top:12px}.actions{gap:6px;margin-bottom:6px}.action{flex-basis:105px;font-size:11px;min-height:44px;padding:8px;border-radius:10px}.row{padding:8px 0;gap:10px;font-size:12px}.input{flex-basis:54%}select,input[type=time]{padding:7px;font-size:12px;border-radius:8px}.levels{font-size:10px}
  details{margin-top:6px}summary{font-size:12px}h3{font-size:14px;margin:16px 0 8px}.metrics{margin-top:0;gap:8px}.metrics .metric{padding:10px;border-radius:12px}.metrics .metric strong{font-size:13px}
  .consumable{padding:4px 10px 10px;border-radius:12px;margin-bottom:10px}.notice,.confirmation,.alert{font-size:12px;padding:10px}.muted,small{font-size:11px}footer{margin-top:10px;font-size:9px}
  @media(max-width:380px){ha-card{padding:12px}.row{gap:8px}.input{flex-basis:54%}.hero{height:72px;flex-basis:54px}.metric strong{font-size:12px}}
  .panel{max-height:340px;overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;-webkit-overflow-scrolling:touch;overflow-anchor:none}
  .setting-group{display:flex;align-items:center;justify-content:space-between;gap:12px;width:100%;background:transparent;text-align:start;border:0;border-bottom:1px solid var(--divider-color);border-radius:0;padding:12px 2px;font-size:12px}
  .setting-group strong{font-weight:500}.setting-group small{display:block;font-size:10px;margin-top:4px;color:var(--secondary-text-color)}.setting-group ha-icon{--mdc-icon-size:18px;color:var(--secondary-text-color)}
  .setting-value{display:flex;align-items:center;justify-content:space-between;gap:6px;width:100%;font-size:11px;padding:7px;text-align:start;overflow-wrap:anywhere}.setting-value ha-icon{--mdc-icon-size:16px;flex-shrink:0}
  .subheading{display:flex;align-items:center;gap:10px;font-size:13px;margin-bottom:8px}.subheading button{padding:8px;border:0;background:transparent}.subheading ha-icon{--mdc-icon-size:20px}
  .choice-list{display:grid;gap:8px}.choice-list button{display:flex;align-items:center;justify-content:space-between;gap:12px;font-size:12px;text-align:start;padding:12px}.choice-list button[aria-pressed=true]{border-color:var(--primary-color);color:var(--primary-color)}.choice-list ha-icon{--mdc-icon-size:20px}
  .save-choice{width:100%;margin-top:12px;font-size:12px}
  .action small{display:block;font-size:9px;line-height:1.4;margin-top:3px}
  /* Semantic state colors follow HA themes; no fixed app gold/green accents. */
  ha-card{--dreame-activity-color:var(--secondary-text-color)}
  ha-card[data-device-state=cleaning]{--dreame-activity-color:var(--state-vacuum-cleaning-color,var(--state-active-color,var(--primary-color)))}
  ha-card[data-device-state=drying]{--dreame-activity-color:var(--state-fan-active-color,var(--state-active-color,var(--primary-color)))}
  ha-card[data-device-state=charging]{--dreame-activity-color:var(--state-binary_sensor-battery_charging-on-color,var(--state-active-color,var(--primary-color)))}
  ha-card[data-device-state=paused]{--dreame-activity-color:var(--state-vacuum-paused-color,var(--warning-color,var(--primary-color)))}
  ha-card[data-device-state=alert]{--dreame-activity-color:var(--state-binary_sensor-problem-on-color,var(--error-color))}
  .activity{color:var(--dreame-activity-color)}.metric ha-icon,.action ha-icon{color:var(--secondary-text-color)}
  .action[data-active=true] ha-icon{color:var(--dreame-activity-color)}
  .metric-clean_progress ha-icon,.metric-dry_progress ha-icon{color:var(--dreame-activity-color)}
  ha-card[data-device-state=charging] .metric-charging ha-icon{color:var(--dreame-activity-color)}
  ha-card[data-battery=low] .metric-battery ha-icon{color:var(--state-sensor-battery-low-color,var(--warning-color,var(--error-color)))}
  ha-card[data-device-state=offline] .metric-online{color:var(--disabled-text-color,var(--secondary-text-color));opacity:.65}
  input[type=checkbox]{accent-color:var(--state-switch-active-color,var(--state-active-color,var(--primary-color)))}
  .consumable progress{accent-color:var(--success-color,var(--primary-color))}
  /* Inherit the theme surface exactly; transparency/blur are theme decisions. */
  ha-card{position:relative;background:var(--ha-card-background,var(--card-background-color));box-shadow:var(--ha-card-box-shadow,none);border-color:var(--ha-card-border-color,var(--divider-color));backdrop-filter:var(--ha-card-backdrop-filter,var(--card-backdrop-filter,none));-webkit-backdrop-filter:var(--ha-card-backdrop-filter,var(--card-backdrop-filter,none))}
  ha-card{--dreame-badge-size:100px}
  .device-badge{flex:0 0 calc(var(--dreame-badge-size) + 4px);text-align:center}.hero{position:relative;width:var(--dreame-badge-size);height:var(--dreame-badge-size);margin:auto;border-radius:50%;background:var(--secondary-background-color)}
  .hero>svg:not(.progress-ring),.hero>img{position:absolute;inset:5px;width:calc(var(--dreame-badge-size) - 10px);height:calc(var(--dreame-badge-size) - 10px);object-fit:contain}
  .hero .progress-ring{position:absolute;inset:0;width:var(--dreame-badge-size);height:var(--dreame-badge-size);overflow:visible;transform:rotate(-90deg)}
  .progress-ring circle{fill:none;stroke:var(--divider-color);stroke-width:3}.progress-ring .progress-value{stroke:var(--dreame-activity-color);stroke-linecap:round}
  .progress-label{font-size:10px;color:var(--dreame-activity-color);margin-top:3px}
  .summary .metric-online{padding:4px 8px;border-radius:14px;background:var(--secondary-background-color)}
  @media(max-width:380px){ha-card{--dreame-badge-size:92px}}
  .tank{border:1px solid var(--divider-color);border-radius:12px;padding:8px 12px;margin-bottom:10px}.tank .row{justify-content:flex-start;padding:4px 0;border:0;gap:8px}.tank ha-icon{--mdc-icon-size:20px;color:var(--secondary-text-color)}.tank-status{font-size:13px;margin:6px 0}.tank small{display:block;font-size:10px}.tank[data-alert=true]{border-color:var(--error-color)}.tank[data-alert=true] ha-icon,.tank[data-alert=true] .tank-status{color:var(--error-color)}
  .fault-notice{display:flex;align-items:center;gap:8px;width:100%;font-size:12px;text-align:start;border-color:var(--error-color);margin:10px 0;color:var(--error-color)}.fault-notice span{flex:1}.fault-notice small{display:block;font-size:10px}.fault-notice ha-icon{--mdc-icon-size:20px}.native-link{padding:0;border:0;background:transparent;min-height:28px;font-size:10px;color:var(--primary-color)}
  .consumable[data-maintenance=required]{border-color:var(--warning-color,var(--error-color))}.consumable[data-maintenance=required] .maintenance-status{color:var(--warning-color,var(--error-color));font-weight:600}.consumable[data-maintenance=required] progress{accent-color:var(--warning-color,var(--error-color))}
  .maintenance-notice{display:flex;gap:8px;align-items:center;width:100%;font-size:12px;text-align:start;margin:10px 0;border-color:var(--warning-color,var(--error-color));color:var(--warning-color,var(--error-color))}.maintenance-notice span{flex:1}.maintenance-notice ha-icon{--mdc-icon-size:20px}
  .metric-online[data-connection=online],.metric-online[data-connection=online] ha-icon{color:var(--success-color,var(--green-color,#43a047));opacity:1}
  .metric-online[data-connection=offline],.metric-online[data-connection=offline] ha-icon{color:var(--error-color,var(--red-color,#db4437));opacity:1}
  .metric-online[data-connection=unknown],.metric-online[data-connection=unknown] ha-icon{color:var(--disabled-text-color,var(--secondary-text-color))}
`;
class DreameDeviceCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._groups = new Set();
    this.shadowRoot.addEventListener("change", (event) => this._change(event));
    this.shadowRoot.addEventListener("focusout", () => queueMicrotask(() => this._render()));
    this.shadowRoot.addEventListener("toggle", (event) => {
      const group = event.target.dataset.group;
      if (!group || this._groups.has(group) === event.target.open) return;
      if (event.target.open) this._groups.add(group); else this._groups.delete(group);
      this._render();
    }, true);
  }
  setConfig(config) { this._config = validateConfig(config); this._render(); }
  set hass(hass) {
    this._hass = hass;
    if (hass.callWS && !this._loadingRegistry && !this._devices) {
      this._loadingRegistry = true;
      Promise.all([hass.callWS({ type: "config/device_registry/list" }), hass.callWS({ type: "config/entity_registry/list" })])
        .then(([devices, entries]) => { this._devices = devices; this._entries = entries; this._render(); })
        .catch(() => { this._loadingRegistry = false; });
    }
    this._render();
  }
  _t(key) { return TEXT[this._config?.language || (this._hass?.language?.startsWith("he") ? "he" : "en")][key] || key; }
  _change(event) {
    const { role, field } = event.target.dataset;
    const value = event.target.value;
    const config = { ...this._config, entities: { ...this._config.entities } };
    if (role) {
      if (value) config.entities[role] = value;
      else delete config.entities[role];
    } else if (field) {
      if (field === "model" && value !== config.model) {
        delete config.device_id; delete config.entity; config.entities = {};
      }
      if (value) config[field] = value;
      else delete config[field];
    } else return;
    this._config = validateConfig(config);
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
    this._render();
  }
  _picker(role) {
    const selected = this._config.entities?.[role] || "";
    const domain = profileRoles(this._config.model === "auto" ? deviceProfile((this._devices || []).find((d) => d.id === this._config.device_id), this._entries) : this._config.model)[role]?.[0];
    if (!domain) return "";
    const entries = Object.entries(this._hass?.states || {}).filter(([id]) => id.startsWith(`${domain}.`));
    if (selected && !entries.some(([id]) => id === selected)) entries.unshift([selected, { attributes: {} }]);
    const options = entries.sort(([a], [b]) => a.localeCompare(b)).map(([id, state]) => `<option value="${escapeHTML(id)}" ${id === selected ? "selected" : ""}>${escapeHTML(state.attributes?.friendly_name ? `${state.attributes.friendly_name} — ${id}` : id)}</option>`).join("");
    return `<label>${escapeHTML(this._t(role))}<select data-role="${role}"><option value="" ${!selected ? "selected" : ""}>${this._t("automatic")}</option>${options}</select></label>`;
  }
  _render() {
    if (!this._config) return;
    // Do not replace a native picker while it is open on mobile.
    if (["INPUT", "SELECT"].includes(this.shadowRoot.activeElement?.tagName)) return;
    const lang = this._config.language || "";
    const profile = this._config.model || "H15";
    const devices = (this._devices || []).filter((d) => profile === "auto" ? deviceProfile(d, this._entries) : deviceProfile(d, this._entries) === profile);
    const profilePicker = `<label>${this._t("device_type")}<select data-field="model">${["H15", "H14", "auto"].map((p) => `<option value="${p}" ${p === profile ? "selected" : ""}>${p === "auto" ? this._t("automatic") : p}</option>`).join("")}</select></label><label>${this._t("device")}<select data-field="device_id"><option value="">${this._t("automatic")}</option>${devices.map((d) => `<option value="${escapeHTML(d.id)}" ${d.id === this._config.device_id ? "selected" : ""}>${escapeHTML(d.name_by_user || d.name || d.model)}</option>`).join("")}</select></label><small>${this._t("profile_note")}</small>`;
    const groups = {
      status: ["vacuum", "battery", "work", "online", "charging", "clean_progress", "dry_progress", "clean_count", "runtime"],
      tanks: ["clean_empty", "clean_empty_error", "dirty_full", "dirty_missing", "dirty_cleaning", "dirty_blocked", "warnings", "errors"],
      maintenance: ["filter", "brush", "filter_worn", "brush_worn", "reset_filter", "reset_brush"],
      operation: Object.keys(ROLES).filter((r) => !["vacuum", "battery", "work", "online", "charging", "clean_progress", "dry_progress", "clean_count", "runtime", "clean_empty", "clean_empty_error", "dirty_full", "dirty_missing", "dirty_cleaning", "dirty_blocked", "warnings", "errors", "filter", "brush", "filter_worn", "brush_worn", "reset_filter", "reset_brush"].includes(r)),
    };
    const html = `<style>:host{display:block;color:var(--primary-text-color);font:inherit}label{display:grid;gap:6px;font-size:13px;margin:12px 0}input,select{font:inherit;color:inherit;background:var(--secondary-background-color);border:1px solid var(--divider-color);border-radius:8px;padding:10px;box-sizing:border-box;width:100%;min-height:44px}small{display:block;color:var(--secondary-text-color);line-height:1.5}details{border-top:1px solid var(--divider-color);margin-top:14px}summary{padding:14px 0;cursor:pointer}h3{font-size:15px}</style>
      <div dir="${(lang || this._hass?.language || "en").startsWith("he") ? "rtl" : "ltr"}">
      <label>${this._t("editor_title")}<input data-field="title" value="${escapeHTML(this._config.title || "")}"></label>
      <label>${this._t("editor_language")}<select data-field="language"><option value="" ${!lang ? "selected" : ""}>${this._t("automatic")}</option><option value="he" ${lang === "he" ? "selected" : ""}>עברית</option><option value="en" ${lang === "en" ? "selected" : ""}>English</option></select></label>
      <h3>${this._t("editor_entities")}</h3><small>${this._t("editor_note")}</small>
      ${profilePicker}${Object.entries(groups).map(([group, roles]) => `<details data-group="${group}" ${this._groups.has(group) ? "open" : ""}><summary>${this._t(group)}</summary>${this._groups.has(group) ? roles.map((r) => this._picker(r)).join("") : ""}</details>`).join("")}</div>`;
    if (html === this._html) return;
    this.shadowRoot.innerHTML = html;
    this._html = html;
  }
}
if (!customElements.get("dreame-device-card-editor")) customElements.define("dreame-device-card-editor", DreameDeviceCardEditor);
if (!customElements.get("dreame-device-card")) customElements.define("dreame-device-card", DreameDeviceCard);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "dreame-device-card")) window.customCards.push({
  type: "dreame-device-card", name: "Dreame device", description: "Operation, device status and maintenance. Work-in-progress H15 mapping.",
});
