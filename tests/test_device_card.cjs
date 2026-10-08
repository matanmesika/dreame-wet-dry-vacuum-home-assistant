const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const elements = new Map();
const context = vm.createContext({
  HTMLElement: class {
    attachShadow() {
      this.shadowRoot = { addEventListener() {}, querySelector() { return null; }, innerHTML: '' };
    }
    dispatchEvent(event) { (this.events ||= []).push(event); return true; }
  },
  customElements: { get: (name) => elements.get(name), define: (name, value) => elements.set(name, value) },
  window: {}, queueMicrotask, setTimeout, clearTimeout,
  CustomEvent: class { constructor(type, options) { this.type = type; Object.assign(this, options); } },
});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../www/dreame-device-card.js'), 'utf8'), context);
const get = (name) => vm.runInContext(name, context);
const state = (value, attributes = {}) => ({ state: value, attributes });
function card() {
  const result = new (elements.get('dreame-device-card'))();
  const calls = [];
  result._config = { language: 'en' };
  result._roles = { online: 'binary_sensor.online', mode: 'select.mode', volume: 'number.volume', reset_filter: 'button.reset', custom: 'switch.custom', hot_water: 'select.hot' };
  result._hass = {
    states: {
      'binary_sensor.online': state('on'),
      'switch.custom': state('on'), 'select.hot': state('Off'),
      'select.mode': state('Quiet', { options: ['Quiet', 'Turbo', 'Personalized'] }),
      'number.volume': state('1', { min: 0, max: 2, step: 1 }),
      'button.reset': state('unknown'),
    },
    callService: async (...args) => calls.push(args),
  };
  result.calls = calls;
  return result;
}
function click(card, dataset, attributes = []) {
  card._click({ target: { closest: () => ({ dataset, disabled: false, hasAttribute: (attr) => attributes.includes(attr) || Object.hasOwn(dataset, attr.replace(/^data-/, '').replace(/-([a-z])/g, (_, c) => c.toUpperCase())) }) } });
}

test('renamed entities resolve by registry ID; disabled and other-device entries are excluded', () => {
  const device = { id: 'ha-id', identifiers: [['dreame_wet_dry_vacuum', 'cloud-id']] };
  const entry = { device_id: 'ha-id', platform: 'dreame_wet_dry_vacuum', unique_id: 'cloud-id_h15_setting_16_7', entity_id: 'select.user_renamed' };
  assert.equal(get('resolveRoles')(device, [entry]).mode, 'select.user_renamed');
  assert.equal(get('resolveRoles')(device, [{ ...entry, disabled_by: 'user' }]).mode, undefined);
  assert.equal(get('resolveRoles')(device, [{ ...entry, device_id: 'other' }]).mode, undefined);
  assert.equal(get('ROLES').brush[1], 'consumable_front_brush');
});
test('automatic detection never picks H14 or an ambiguous pair of devices', () => {
  const entries = ['h14', 'a', 'b'].map((id) => ({ device_id: id, platform: 'dreame_wet_dry_vacuum' }));
  const devices = [{ id: 'h14', model: 'dreame.hold.w2306e' }, { id: 'a', model: 'dreame.hold.w2449e' }];
  assert.equal(get('resolveDevice')({}, devices, entries).id, 'a');
  assert.equal(get('resolveDevice')({}, [...devices, { id: 'b', model: 'dreame.hold.w2449e' }], entries), undefined);
});
test('choice selection is a draft; only confirmation sends the supported HA option', async () => {
  const c = card();
  click(c, { group: 'cleaning_settings' });
  click(c, { setting: 'mode' });
  click(c, { option: 'Turbo' });
  assert.equal(c.calls.length, 0);
  assert.equal(c._hass.states['select.mode'].state, 'Quiet');
  click(c, {}, ['data-save-option']);
  await Promise.resolve();
  assert.equal(c.calls.length, 1);
  assert.equal(c.calls[0][0], 'select');
  assert.equal(c.calls[0][1], 'select_option');
  assert.equal(c.calls[0][2].option, 'Turbo');
  assert.equal(c._hass.states['select.mode'].state, 'Quiet');
});
test('back navigation and tab switching discard an unconfirmed choice', () => {
  const c = card();
  click(c, { group: 'cleaning_settings' });
  click(c, { setting: 'mode' });
  click(c, { option: 'Turbo' });
  click(c, {}, ['data-back']);
  assert.equal(c._choice, undefined);
  assert.equal(c._settings, 'cleaning_settings');
  click(c, { tab: 'maintenance' });
  assert.equal(c._settings, undefined);
  assert.equal(c.calls.length, 0);
});
test('offline and unavailable entities cannot write or reset', async () => {
  const c = card();
  c._hass.states['binary_sensor.online'].state = 'off';
  await c._act('mode', 'Turbo');
  await c._act('reset_filter', undefined, true);
  assert.equal(c.calls.length, 0);
  c._hass.states['binary_sensor.online'].state = 'on';
  c._hass.states['select.mode'].state = 'unavailable';
  await c._act('mode', 'Turbo');
  assert.equal(c.calls.length, 0);
});
test('volume uses only native 0/1/2; raw values and unknown select options are rejected', () => {
  const service = get('serviceFor');
  assert.equal(service('volume', state('1', { min: 0, max: 2, step: 1 }), 2)[2].value, 2);
  for (const value of [30, 60, 1.5, NaN]) assert.throws(() => service('volume', state('1', { min: 0, max: 2, step: 1 }), value));
  assert.throws(() => service('mode', state('Quiet', { options: ['Quiet'] }), 'Power off'));
});
test('maintenance reset requires explicit confirmation and leaves telemetry untouched', async () => {
  const c = card();
  await c._act('reset_filter');
  assert.equal(c.calls.length, 0);
  await c._act('reset_filter', undefined, true);
  assert.equal(c.calls[0][1], 'press');
  assert.equal(c._hass.states['button.reset'].state, 'unknown');
});
test('no alert data is not presented as proof of device health; values are escaped', () => {
  const c = card();
  assert.match(c._alertList(), /does not prove/);
  assert.equal(get('escapeHTML')('<img onerror="x">'), '&lt;img onerror=&quot;x&quot;&gt;');
  assert.throws(() => get('validateConfig')({ image: 'https://example.com/image.png' }));
});
test('activity colors distinguish idle, cleaning, drying, pause, charging, alerts and offline', () => {
  const c = card();
  c._roles.work = 'sensor.work';
  const work = c._hass.states['sensor.work'] = state('Sleeping', { raw_value: 7 });
  assert.equal(c._activityTone(), 'idle');
  for (const [raw, tone] of [[5, 'cleaning'], [42, 'cleaning'], [6, 'drying'], [12, 'paused'], [4, 'charging'], [15, 'idle']]) {
    work.attributes.raw_value = raw;
    assert.equal(c._activityTone(), tone);
  }
  work.state = 'unknown';
  assert.equal(c._activityTone(), 'unknown');
  c._alerts = [{ entity_id: 'binary_sensor.fault' }];
  c._hass.states['binary_sensor.fault'] = state('on');
  assert.equal(c._activityTone(), 'alert');
  c._hass.states['binary_sensor.online'].state = 'off';
  assert.equal(c._activityTone(), 'offline');
});
test('only a known low battery receives a battery warning color', () => {
  const c = card();
  c._roles.battery = 'sensor.battery';
  for (const [value, tone] of [['100', 'normal'], ['20', 'low'], ['0', 'low'], ['unknown', 'unknown'], ['-1', 'unknown']]) {
    c._hass.states['sensor.battery'] = state(value);
    assert.equal(c._batteryTone(), tone);
  }
});
test('progress ring appears only for active tasks with valid reported progress', () => {
  const c = card();
  Object.assign(c._roles, { work: 'sensor.work', clean_progress: 'sensor.clean_progress', dry_progress: 'sensor.dry_progress' });
  c._hass.states['sensor.work'] = state('Sleeping', { raw_value: 7 });
  c._hass.states['sensor.clean_progress'] = state('50');
  c._hass.states['sensor.dry_progress'] = state('25');
  assert.equal(c._progressValue(), undefined);
  c._hass.states['sensor.work'].attributes.raw_value = 5;
  assert.equal(c._progressValue(), 50);
  c._hass.states['sensor.work'].attributes.raw_value = 6;
  assert.equal(c._progressValue(), 25);
  for (const value of ['unknown', 'unavailable', '-1', '101']) {
    c._hass.states['sensor.dry_progress'].state = value;
    assert.equal(c._progressValue(), undefined);
  }
});

test('water tanks show unknown level instead of invented percentages or installation', () => {
  const c = card();
  assert.match(c._tank('clean'), /Unknown/);
  assert.match(c._tank('dirty'), /Unknown/);
  for (const role of ['clean_empty', 'clean_empty_error', 'dirty_full', 'dirty_missing', 'dirty_blocked', 'dirty_cleaning']) {
    c._roles[role] = `binary_sensor.${role}`;
    c._hass.states[c._roles[role]] = state('off');
  }
  assert.match(c._tank('clean'), /No reported alert/);
  assert.match(c._tank('dirty'), /No percentage or continuous water level is reported/);
  assert.doesNotMatch(c._tank('dirty'), /81%|100%|Tank full/);
  c._hass.states['binary_sensor.dirty_full'].state = 'on';
  assert.match(c._tank('dirty'), /Tank full — empty it/);
  assert.match(c._tank('dirty'), /data-alert="true"/);
  c._hass.states['binary_sensor.dirty_full'].state = 'unavailable';
  assert.match(c._tank('dirty'), /Unknown/);
  c._hass.states['binary_sensor.clean_empty'].state = 'on';
  assert.match(c._tank('clean'), /Clean water shortage alert/);
  c._hass.states['binary_sensor.online'].state = 'off';
  assert.match(c._tank('clean'), /Unknown/);
});

test('confirmed dirty tank status shows Normal or Full while unknown raw values stay unknown', () => {
  const c = card();
  c._roles.dirty_tank_status = 'sensor.dirty_tank_status';
  c._hass.states['sensor.dirty_tank_status'] = state('Normal');
  assert.match(c._tank('dirty'), />Normal</);
  c._hass.states['sensor.dirty_tank_status'].state = 'Full';
  assert.match(c._tank('dirty'), /Tank full — empty it/);
  assert.match(c._tank('dirty'), /data-alert="true"/);
  c._hass.states['sensor.dirty_tank_status'].state = 'Unknown \(82\)';
  assert.match(c._tank('dirty'), /Unknown/);
});

test('confirmed full-tank role resolves from renamed HA registry entities', () => {
  const device = { id: 'ha-id', identifiers: [['dreame_wet_dry_vacuum', 'cloud-id']] };
  const entries = ['h15_error_12_1', 'vacuum'].map((suffix, i) => ({
    device_id: 'ha-id', platform: 'dreame_wet_dry_vacuum', unique_id: `cloud-id_${suffix}`,
    entity_id: i ? 'vacuum.changed_name' : 'binary_sensor.changed_name',
  }));
  assert.equal(get('resolveRoles')(device, entries).dirty_full, 'binary_sensor.changed_name');
  assert.equal(get('resolveRoles')(device, entries).vacuum, 'vacuum.changed_name');
});

test('unknown raw device errors stay visible even without a mapped binary fault', () => {
  const c = card();
  c._roles.errors = 'sensor.errors';
  c._roles.warnings = 'sensor.warnings';
  c._hass.states['sensor.errors'] = state('0', { raw_value: '1073741824' });
  c._hass.states['sensor.warnings'] = state('0', { raw_value: 0 });
  assert.equal(c._activityTone(), 'alert');
  assert.match(c._faultNotice(), /Device reports a fault/);
  assert.match(c._alertList(), /Device reports a fault/);
  assert.doesNotMatch(c._alertList(), /No reported active alerts/);
  click(c, { tab: 'maintenance' });
  assert.equal(c._tab, 'maintenance');
  assert.equal(c.calls.length, 0);
  c._hass.states['sensor.errors'] = state('unknown', { raw_value: 1073741824 });
  assert.equal(c._reportedCode('errors'), undefined);
  for (const raw of [true, -1, '', [], Infinity, 'bad']) {
    c._hass.states['sensor.errors'] = state('0', { raw_value: raw });
    assert.equal(c._reportedCode('errors'), undefined);
  }
});

test('tank warnings are visible in the header and the maintenance tab without cloud writes', () => {
  const c = card();
  c._roles.dirty_full = 'binary_sensor.used_tank';
  c._hass.states['binary_sensor.used_tank'] = state('on', { friendly_name: '<Tank full>' });
  assert.match(c._faultNotice(), /&lt;Tank full&gt;/);
  assert.match(c._faultNotice(), /data-tab="maintenance"/);
  c._tab = 'maintenance';
  assert.match(c._panel(), /Clean water tank/);
  assert.match(c._panel(), /Used water tank/);
  assert.equal(c.calls.length, 0);
});

function scroller(c) {
  let panel = { id: 'device-panel', scrollTop: 0 };
  let writes = 0;
  const root = {
    addEventListener() {}, activeElement: null,
    querySelector(selector) { return selector === '#device-panel' ? panel : null; },
    set innerHTML(value) { this.html = value; panel = { id: 'device-panel', scrollTop: 0 }; writes++; },
  };
  c.shadowRoot = root;
  c._render();
  return { panel: () => panel, writes: () => writes };
}

test('unrelated HA updates do not replace the scroller; changed telemetry preserves its position', () => {
  const c = card();
  c._tab = 'maintenance';
  const dom = scroller(c);
  dom.panel().scrollTop = 125;
  const node = dom.panel();
  c._render();
  assert.equal(dom.writes(), 1);
  assert.equal(dom.panel(), node);
  c._roles.dirty_full = 'binary_sensor.full';
  c._hass.states['binary_sensor.full'] = state('on');
  c._render();
  assert.equal(dom.writes(), 2);
  assert.equal(dom.panel().scrollTop, 125);
});

test('momentum scrolling defers telemetry rendering until idle without losing the latest state', async () => {
  const c = card();
  c._tab = 'maintenance';
  const dom = scroller(c);
  dom.panel().scrollTop = 178;
  c._onScroll({ target: dom.panel() });
  c._roles.dirty_full = 'binary_sensor.full';
  c._hass.states['binary_sensor.full'] = state('on');
  c._render();
  assert.equal(dom.writes(), 1);
  await new Promise((resolve) => setTimeout(resolve, 220));
  assert.equal(dom.writes(), 2);
  assert.equal(dom.panel().scrollTop, 178);
  assert.match(c.shadowRoot.html, /Tank full/);
  c.disconnectedCallback();
});

test('each tab and settings page restores its own scroll position', () => {
  const c = card();
  const dom = scroller(c);
  dom.panel().scrollTop = 30;
  c._tab = 'maintenance'; c._render();
  assert.equal(dom.panel().scrollTop, 0);
  dom.panel().scrollTop = 130;
  c._tab = 'operation'; c._render();
  assert.equal(dom.panel().scrollTop, 30);
  c._tab = 'maintenance'; c._render();
  assert.equal(dom.panel().scrollTop, 130);
});

test('English and Hebrew navigation arrows and sliders follow the card direction', () => {
  const c = card();
  assert.equal(c._navIcon(), 'mdi:chevron-right');
  assert.equal(c._navIcon(true), 'mdi:arrow-left');
  assert.match(c._control('volume'), /dir="ltr"/);
  c._settings = 'cleaning_settings';
  assert.match(c._panel(), /mdi:arrow-left/);
  c._config.language = 'he';
  assert.equal(c._navIcon(), 'mdi:chevron-left');
  assert.equal(c._navIcon(true), 'mdi:arrow-right');
  assert.match(c._control('volume'), /dir="rtl"/);
});

test('visual editor offers domain-filtered entities and preserves other overrides', () => {
  const editor = new (elements.get('dreame-device-card-editor'))();
  editor.setConfig({ type: 'custom:dreame-device-card', language: 'en', entities: { battery: 'sensor.old', work: 'sensor.work' } });
  editor.hass = { states: { 'sensor.new': state('100', { friendly_name: 'Battery' }), 'switch.other': state('on') } };
  assert.match(editor._picker('battery'), /sensor.new/);
  assert.doesNotMatch(editor._picker('battery'), /switch.other/);
  editor._change({ target: { dataset: { role: 'battery' }, value: 'sensor.new' } });
  assert.equal(editor.events.at(-1).type, 'config-changed');
  assert.equal(editor.events.at(-1).detail.config.entities.battery, 'sensor.new');
  assert.equal(editor.events.at(-1).detail.config.entities.work, 'sensor.work');
  editor._change({ target: { dataset: { role: 'battery' }, value: '' } });
  assert.equal(editor.events.at(-1).detail.config.entities.battery, undefined);
  assert.throws(() => editor._change({ target: { dataset: { role: 'battery' }, value: 'switch.other' } }));
});

test('verified maintenance percentages replace hours and include the 0–10 percent boundary', () => {
  const c = card();
  c._roles.filter = 'sensor.filter';
  for (const [percent, required] of [[0, true], [5, true], [10, true], [10.1, false], [100, false]]) {
    c._hass.states['sensor.filter'] = state('57.9', { unit_of_measurement: 'h', percent_remaining: percent, full_life_source: 'device' });
    assert.equal(c._maintenanceState('filter').required, required);
    const html = c._consumable('filter', 'reset_filter');
    assert.match(html, new RegExp(`${percent}% remaining`));
    assert.doesNotMatch(html, /57\.9/);
    assert.equal(c._maintenanceNotice().length > 0, required);
  }
  c._hass.states['sensor.filter'] = state('57.9', { unit_of_measurement: 'h', full_life_source: 'unknown' });
  assert.match(c._consumable('filter', 'reset_filter'), /Percentage unavailable; showing time reported by the device/);
  assert.match(c._consumable('filter', 'reset_filter'), /~58 h remaining/);
  assert.doesNotMatch(c._consumable('filter', 'reset_filter'), /57\.9|% remaining|<progress/);
  c._hass.states['sensor.filter'] = state('unknown', { unit_of_measurement: '%', full_life_source: 'unknown', minutes_remaining: 3473 });
  const fromRawMinutes = c._consumable('filter', 'reset_filter');
  assert.match(fromRawMinutes, /~58 h remaining/);
  assert.match(fromRawMinutes, /Percentage unavailable/);
  assert.equal(c._maintenanceState('filter').required, false);
  const percentEntry = { entity_id: 'sensor.filter_percent', unique_id: 'cloud_consumable_filter_percent', device_id: 'device' };
  const hoursEntry = { entity_id: 'sensor.filter_hours', unique_id: 'cloud_consumable_filter', device_id: 'device' };
  c._roles.filter = 'sensor.filter_percent';
  c._entries = [percentEntry, hoursEntry];
  c._hass.states['sensor.filter_percent'] = state('unknown', { unit_of_measurement: '%', full_life_source: 'unknown' });
  c._hass.states['sensor.filter_hours'] = state('56.9', { unit_of_measurement: 'h' });
  assert.equal(c._maintenanceState('filter').hours, 57);
  assert.match(c._consumable('filter', 'reset_filter'), /~57 h remaining/);
});

test('manual percentage sensors work while unavailable or invalid percentages never trigger a guessed reminder', () => {
  const c = card();
  c._roles.filter = 'sensor.filter';
  c._hass.states['sensor.filter'] = state('8', { unit_of_measurement: '%' });
  assert.equal(c._maintenanceState('filter').percent, 8);
  assert.equal(c._maintenanceState('filter').required, true);
  for (const percent of [undefined, null, true, '', -1, 101, Infinity, NaN]) {
    c._hass.states['sensor.filter'] = state('57.9', { unit_of_measurement: 'h', percent_remaining: percent });
    assert.equal(c._maintenanceState('filter').percent, undefined);
    assert.equal(c._maintenanceState('filter').required, false);
  }
  c._hass.states['sensor.filter'] = state('unavailable', { percent_remaining: 5 });
  assert.equal(c._maintenanceState('filter').percent, undefined);
  c._roles.filter_worn = 'binary_sensor.filter_worn';
  c._hass.states['binary_sensor.filter_worn'] = state('on');
  assert.equal(c._maintenanceState('filter').required, true);
  assert.match(c._consumable('filter', 'reset_filter'), /Maintenance required/);
  assert.equal(c.calls.length, 0);
});

test('connection indicators distinguish connected, disconnected and unknown states', () => {
  const c = card();
  for (const [value, connection, text] of [['on', 'online', 'Connected'], ['off', 'offline', 'Disconnected'], ['unknown', 'unknown', 'Unknown'], ['invalid', 'unknown', 'Unknown']]) {
    c._hass.states['binary_sensor.online'] = state(value);
    const html = c._metric('online', 'mdi:wifi');
    assert.match(html, new RegExp(`data-connection="${connection}"`));
    assert.match(html, new RegExp(`<strong>${text}</strong>`));
  }
});

test('automatic maintenance roles prefer new percentage entities with legacy fallback', () => {
  const device = { id: 'ha-id', identifiers: [['dreame_wet_dry_vacuum', 'cloud-id']] };
  const hours = { device_id: 'ha-id', platform: 'dreame_wet_dry_vacuum', unique_id: 'cloud-id_consumable_filter', entity_id: 'sensor.hours' };
  const percent = { ...hours, unique_id: 'cloud-id_consumable_filter_percent', entity_id: 'sensor.percent' };
  assert.equal(get('resolveRoles')(device, [hours, percent]).filter, 'sensor.percent');
  assert.equal(get('resolveRoles')(device, [hours]).filter, 'sensor.hours');
  assert.equal(get('resolveRoles')(device, [hours, percent], { filter: 'sensor.manual' }).filter, 'sensor.manual');
});

test('explicit H14/H15 profiles resolve renamed entities without mixing write domains', () => {
  const devices = [{ id: 'h14', model: 'dreame.hold.w2306e', identifiers: [['dreame_wet_dry_vacuum', 'old']] }, { id: 'h15', model: 'dreame.hold.w2449e', identifiers: [['dreame_wet_dry_vacuum', 'new']] }];
  const entries = [
    { device_id: 'h14', platform: 'dreame_wet_dry_vacuum', unique_id: 'old_battery', entity_id: 'sensor.renamed_battery' },
    { device_id: 'h14', platform: 'dreame_wet_dry_vacuum', unique_id: 'old_clean_power', entity_id: 'number.renamed_power' },
    { device_id: 'h15', platform: 'dreame_wet_dry_vacuum', unique_id: 'new_h15_property_3_1', entity_id: 'sensor.new_battery' },
  ];
  assert.equal(get('resolveDevice')({ model: 'H14' }, devices, entries).id, 'h14');
  assert.equal(get('resolveDevice')({ model: 'H15' }, devices, entries).id, 'h15');
  assert.equal(get('resolveDevice')({ model: 'auto' }, devices, entries), undefined);
  assert.equal(get('resolveDevice')({ model: 'H15', device_id: 'h14' }, devices, entries), undefined);
  const roles = get('resolveRoles')(devices[0], entries);
  assert.equal(roles.suction, 'number.renamed_power');
  assert.equal(roles.battery, 'sensor.renamed_battery');
  assert.deepEqual(Array.from(get('serviceFor')('suction', state('2', { min: 0, max: 3, step: 1 }), 3, get('H14_ROLES'))).slice(0, 2), ['number', 'set_value']);
  assert.throws(() => get('validateConfig')({ model: 'H14', entities: { suction: 'select.wrong' } }));
});

test('H15 card dependencies follow live custom mode and hot water values', () => {
  const c = card();
  c._roles.suction = 'select.suction'; c._roles.water = 'select.water';
  c._hass.states['select.suction'] = state('Gentle', { options: ['Gentle', 'Standard', 'Strong'] });
  c._hass.states['select.water'] = state('High', { options: ['Standard', 'High'] });
  assert.equal(c._control('suction'), '');
  c._hass.states['select.mode'].state = 'Personalized';
  assert.ok(c._ready('suction'));
  c._hass.states['select.hot'].state = 'Mild';
  assert.equal(c._ready('suction'), false);
  assert.equal(c._ready('water'), true);
  c._hass.states['switch.custom'].state = 'off';
  assert.equal(c._ready('mode'), false); assert.equal(c._ready('water'), false);
});

test('aggregate decoded alerts remain visible without individual alarm entities', () => {
  const c = card(); c._roles.errors = 'sensor.errors';
  c._hass.states['sensor.errors'] = state('4096', { raw_value: 4096, active_alerts: ['Dirty water tank full', '<unsafe>'] });
  const html = c._alertList();
  assert.match(html, /Dirty water tank full/); assert.match(html, /&lt;unsafe&gt;/);
  assert.doesNotMatch(html, /No active alerts/);
});

test('editor changes profile and resets stale manual overrides without device writes', () => {
  const editor = new (elements.get('dreame-device-card-editor'))();
  editor.setConfig({ model: 'H15', device_id: 'old', entities: { suction: 'select.old' } });
  editor._change({ target: { dataset: { field: 'model' }, value: 'H14' } });
  const config = editor.events.at(-1).detail.config;
  assert.equal(config.model, 'H14'); assert.equal(config.device_id, undefined);
  assert.equal(Object.keys(config.entities).length, 0);
  assert.match(editor.shadowRoot.innerHTML, /Device type/);
});
