"""Exercise actual H15 entity/platform/coordinator methods without HA or cloud."""
import asyncio
import importlib
import sys
import types
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def component(monkeypatch):
    class HAError(Exception):
        pass

    class Generic:
        def __class_getitem__(cls, item):
            return cls

    class Entity(Generic):
        def __init__(self, coordinator):
            self.coordinator = coordinator

        @property
        def available(self):
            return self.coordinator.last_update_success

    class Coordinator(Generic):
        def __init__(self, hass, *args, **kwargs):
            self.hass = hass
            self.last_update_success = True
            self.data = {}

        def async_set_updated_data(self, data):
            self.data = data

    class PlatformEntity:
        pass

    adapters = {
        "homeassistant": {}, "homeassistant.components": {},
        "homeassistant.helpers": {},
        "homeassistant.components.persistent_notification": {"async_create": lambda *args, **kw: None},
        "homeassistant.components.button": {"ButtonEntity": PlatformEntity},
        "homeassistant.components.binary_sensor": {"BinarySensorEntity": PlatformEntity, "BinarySensorDeviceClass": types.SimpleNamespace(RUNNING="running", CONNECTIVITY="connectivity", PROBLEM="problem", BATTERY_CHARGING="battery_charging")},
        "homeassistant.components.select": {"SelectEntity": PlatformEntity},
        "homeassistant.components.switch": {"SwitchEntity": PlatformEntity},
        "homeassistant.components.number": {
            "NumberEntity": PlatformEntity, "NumberMode": types.SimpleNamespace(SLIDER="slider"),
        },
        "homeassistant.components.sensor": {
            "SensorEntity": PlatformEntity,
            "SensorDeviceClass": types.SimpleNamespace(BATTERY="battery", DURATION="duration", TIMESTAMP="timestamp"),
            "SensorStateClass": types.SimpleNamespace(MEASUREMENT="measurement", TOTAL_INCREASING="total_increasing"),
        },
        "homeassistant.config_entries": {"ConfigEntry": Generic},
        "homeassistant.const": {
            "EntityCategory": types.SimpleNamespace(CONFIG="config", DIAGNOSTIC="diagnostic"),
            "CONF_PASSWORD": "password", "CONF_USERNAME": "username",
            "Platform": types.SimpleNamespace(SENSOR="sensor", BINARY_SENSOR="binary_sensor", SWITCH="switch", NUMBER="number", SELECT="select", BUTTON="button"),
        },
        "homeassistant.core": {"HomeAssistant": Generic, "callback": lambda f: f},
        "homeassistant.exceptions": {
            "ConfigEntryAuthFailed": HAError, "HomeAssistantError": HAError, "ConfigEntryNotReady": HAError,
        },
        "homeassistant.helpers.event": {"async_track_time_interval": lambda *args: None},
        "homeassistant.helpers.device_registry": {"DeviceInfo": dict},
        "homeassistant.helpers.entity_platform": {"AddEntitiesCallback": Generic},
        "homeassistant.helpers.update_coordinator": {
            "CoordinatorEntity": Entity, "DataUpdateCoordinator": Coordinator, "UpdateFailed": HAError,
        },
    }
    for name, attrs in adapters.items():
        module = types.ModuleType(name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
    package = "custom_components.dreame_wet_dry_vacuum"
    monkeypatch.setattr(sys.modules[package], "DreameWetDryConfigEntry", Generic, raising=False)
    imported = ["coordinator", "entity", "select", "switch", "number", "sensor", "button", "binary_sensor"]
    for name in imported:
        monkeypatch.delitem(sys.modules, f"{package}.{name}", raising=False)
    modules = {name: importlib.import_module(f"{package}.{name}") for name in imported}
    modules["error"] = HAError
    yield modules
    for name in imported:
        sys.modules.pop(f"{package}.{name}", None)


@pytest.mark.parametrize("model,expected,layout_schema", [("dreame.hold.w2449e", ["sensor.old_setting"], 1), ("dreame.hold.w2449e", ["sensor.old_setting", "sensor.raw_data"], 0), ("dreame.hold.w2306e", [], 0)])
def test_upgrade_only_disables_superseded_h15_setting_sensors(component, monkeypatch, model, expected, layout_schema):
    from pathlib import Path

    changed = []
    def update_entity(entity_id, **kwargs):
        changed.append(entity_id)
        next(e for e in entries if e.entity_id == entity_id).disabled_by = kwargs["disabled_by"]

    registry = types.SimpleNamespace(async_update_entity=update_entity)
    entries = [
        types.SimpleNamespace(entity_id="sensor.old_setting", domain="sensor", unique_id="test-device_h15_property_16_1", disabled_by=None),
        types.SimpleNamespace(entity_id="sensor.raw_data", domain="sensor", unique_id="test-device_h15_property_1_68", disabled_by=None),
        types.SimpleNamespace(entity_id="sensor.h14_status", domain="sensor", unique_id="test-device_2.1", disabled_by=None),
    ]
    adapter = types.ModuleType("homeassistant.helpers.entity_registry")
    adapter.async_get = lambda hass: registry
    adapter.async_entries_for_config_entry = lambda reg, entry_id: entries
    adapter.RegistryEntryDisabler = types.SimpleNamespace(INTEGRATION="integration")
    monkeypatch.setitem(sys.modules, adapter.__name__, adapter)
    monkeypatch.setattr(sys.modules["homeassistant.helpers"], "entity_registry", adapter, raising=False)
    client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    client.async_get_clientsession = lambda hass: None
    monkeypatch.setitem(sys.modules, client.__name__, client)
    source = Path(component["coordinator"].__file__).with_name("__init__.py")
    spec = importlib.util.spec_from_file_location(
        "custom_components.dreame_wet_dry_vacuum.setup_validation", source,
        submodule_search_locations=None,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    api = types.SimpleNamespace(
        login=AsyncMock(), get_devices=AsyncMock(return_value=[{"did": "test-device", "model": model}]),
    )
    monkeypatch.setattr(module, "DreameAPI", lambda **kwargs: api)
    coordinator = make_coordinator(component, model)
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.start_polling = lambda: None
    coordinator.start_mqtt = lambda: None
    monkeypatch.setattr(module, "DreameWetDryCoordinator", lambda *args: coordinator)
    entry = types.SimpleNamespace(entry_id="test-entry", data={
        "username": "user", "password": "pw", "country": "IL", "region": "auto",
        "device_id": "test-device", "_h15_entity_schema": 2, "_h15_layout_schema": layout_schema,
    })

    async def executor(func, *args):
        return func(*args)

    hass = types.SimpleNamespace(
        config=types.SimpleNamespace(country="IL"), async_add_executor_job=executor,
        config_entries=types.SimpleNamespace(
            async_update_entry=lambda entry, data: setattr(entry, "data", data),
            async_forward_entry_setups=AsyncMock(),
        ),
    )
    assert asyncio.run(module.async_setup_entry(hass, entry))
    assert changed == expected
    if expected:
        # A user's later decision to re-enable a diagnostic is respected.
        assert asyncio.run(module.async_setup_entry(hass, entry))
        assert changed == expected


def make_coordinator(component, model="dreame.hold.w2449e"):
    api = types.SimpleNamespace(
        get_properties=AsyncMock(return_value=[]),
        set_h15_properties=AsyncMock(return_value=True),
    )
    coordinator = component["coordinator"].DreameWetDryCoordinator(
        object(), object(), api, "test-device", {"model": model}
    )
    coordinator.props.update({(16, 1): 2, (16, 2): 2, (16, 7): 4, (16, 8): 0, (24, 1): 2})
    coordinator.data = coordinator._build_data()
    return coordinator


def test_platforms_create_proper_h15_entities_and_keep_h14_controls(component):
    from custom_components.dreame_wet_dry_vacuum.const import (
        KNOWN_NUMBER_PROPS,
        KNOWN_SELECT_PROPS,
        KNOWN_SWITCH_PROPS,
    )
    for model, sizes in [
        ("dreame.hold.w2449e", (17, 17, 2)),
        ("dreame.hold.w2306e", (len(KNOWN_SELECT_PROPS), len(KNOWN_SWITCH_PROPS), len(KNOWN_NUMBER_PROPS))),
    ]:
        coordinator = make_coordinator(component, model)
        entry = types.SimpleNamespace(runtime_data=coordinator)
        for platform, size in zip(("select", "switch", "number"), sizes, strict=True):
            entities = []
            asyncio.run(component[platform].async_setup_entry(None, entry, entities.extend))
            assert len(entities) == size
            assert all((e._attr_unique_id.startswith("test-device_h15_setting_")) == coordinator.is_h15_pro_heat for e in entities)


def test_h15_switch_polarity_and_invalid_select_are_handled(component):
    coordinator = make_coordinator(component)
    coordinator.props[(1, 9)] = 0
    coordinator.data = coordinator._build_data()
    controls = types.SimpleNamespace(**{name: getattr(component[platform], name) for platform, name in [("select", "DreameH15Select"), ("switch", "DreameH15Switch"), ("number", "DreameH15Number")]})
    switch = controls.DreameH15Switch(coordinator, (1, 9))
    assert switch.is_on is True
    asyncio.run(switch.async_turn_off())
    assert switch.is_on is False
    assert coordinator.api.set_h15_properties.call_args.args[1] == {(1, 9): 1}
    select = controls.DreameH15Select(coordinator, (23, 1))
    with pytest.raises(component["error"]):
        asyncio.run(select.async_select_option("Unknown"))
    assert coordinator.api.set_h15_properties.call_count == 1


def test_rejected_batch_keeps_local_setting_values(component):
    coordinator = make_coordinator(component)
    coordinator.api.set_h15_properties.return_value = False
    before = dict(coordinator.props)
    select = component["select"].DreameH15Select(coordinator, (16, 7))
    with pytest.raises(component["error"]):
        asyncio.run(select.async_select_option("Turbo"))
    assert coordinator.props == before
    assert select.current_option == "Personalized"


def test_suction_unavailable_while_hot_and_arm_unavailable_if_unknown(component):
    coordinator = make_coordinator(component)
    controls = types.SimpleNamespace(**{name: getattr(component[platform], name) for platform, name in [("select", "DreameH15Select"), ("switch", "DreameH15Switch"), ("number", "DreameH15Number")]})
    suction = controls.DreameH15Select(coordinator, (16, 1))
    assert suction.available
    coordinator.data["16.8"] = 1
    assert not suction.available
    arm = controls.DreameH15Switch(coordinator, (24, 1), arm_bit=0)
    coordinator.data.pop("24.1")
    assert not arm.available
    assert arm.is_on is None


def test_concurrent_arm_switches_preserve_each_other(component):
    coordinator = make_coordinator(component)
    calls = []

    async def acknowledge(did, plan):
        calls.append(dict(plan))
        await asyncio.sleep(0)
        return True

    coordinator.api.set_h15_properties.side_effect = acknowledge

    async def write_both():
        await asyncio.gather(
            coordinator.async_set_h15_setting((24, 1), 0, arm_bit=0),
            coordinator.async_set_h15_setting((24, 1), 0, arm_bit=3),
        )

    asyncio.run(write_both())
    assert calls == [{(24, 1): 3}, {(24, 1): 11}]
    assert coordinator.props[(24, 1)] == 11


def test_h15_write_path_rejects_h14_device(component):
    coordinator = make_coordinator(component, "dreame.hold.w2306e")
    with pytest.raises(ValueError):
        asyncio.run(coordinator.async_set_h15_setting((23, 1), 0))
    coordinator.api.set_h15_properties.assert_not_called()


def test_raw_setting_sensors_are_optional_diagnostics_only_on_h15(component):
    coordinator = make_coordinator(component)
    h15 = component["sensor"].DreameH15PropertySensor(coordinator, (16, 1))
    assert h15._attr_entity_registry_enabled_default is False
    assert h15._attr_entity_category == "diagnostic"
    battery = component["sensor"].DreameH15PropertySensor(coordinator, (3, 1))
    assert getattr(battery, "_attr_entity_registry_enabled_default", True)
    legacy = component["sensor"].DreameWetDrySensor(
        make_coordinator(component, "dreame.hold.w2306e"), (2, 1)
    )
    assert getattr(legacy, "_attr_entity_registry_enabled_default", True)


def test_reset_waits_for_real_counter_readback(component):
    coordinator = make_coordinator(component)
    coordinator.props[(19, 3)] = 3473
    coordinator.data = coordinator._build_data()
    asyncio.run(coordinator.async_send_h15_command('reset_filter'))
    assert coordinator.api.set_h15_properties.call_args.args[1] == {(19, 1): 1}
    assert coordinator.data['19.3'] == 3473
    assert (19, 1) not in coordinator.props
    coordinator.api.get_properties.side_effect = [[], [{'siid': 19, 'piid': 3, 'code': 0, 'value': 3600}]]
    asyncio.run(coordinator.async_send_h15_command('reset_filter'))
    assert coordinator.data['19.3'] == 3600


def test_rejected_command_does_not_change_sensor_state(component):
    coordinator = make_coordinator(component)
    coordinator.props[(6, 7)] = 3413
    coordinator.api.set_h15_properties.return_value = False
    with pytest.raises(component['error']):
        asyncio.run(coordinator.async_send_h15_command('reset_front_brush'))
    assert coordinator.props[(6, 7)] == 3413


def test_h14_rejects_new_command_path(component):
    coordinator = make_coordinator(component, 'dreame.hold.w2306e')
    with pytest.raises(ValueError):
        asyncio.run(coordinator.async_send_h15_command('reset_filter'))
    coordinator.api.set_h15_properties.assert_not_called()


def test_actual_buttons_and_h14_button_platform(component):
    coordinator = make_coordinator(component)
    coordinator.props.update({(1, 28): 7, (1, 8): 4, (1, 10): 3, (3, 1): 100, (6, 7): 3413, (19, 3): 3473, (7, 7): -1})
    entry = types.SimpleNamespace(runtime_data=coordinator)
    buttons = []
    asyncio.run(component['button'].async_setup_entry(None, entry, buttons.extend))
    commands = {b._command: b for b in buttons if hasattr(b, '_command')}
    assert commands['start_self_clean'].available
    assert commands['start_self_dry'].available
    assert not commands['stop_self_clean'].available
    assert not commands['reset_back_brush'].available
    asyncio.run(commands['start_self_dry'].async_press())
    assert coordinator.api.set_h15_properties.call_args.args[1] == {(1, 2): 4}
    entry.runtime_data = make_coordinator(component, 'dreame.hold.w2306e')
    buttons = []
    asyncio.run(component['button'].async_setup_entry(None, entry, buttons.extend))
    assert len(buttons) == 2
    assert all(type(b).__name__ == 'DreameWetDryButton' for b in buttons)


def test_actual_alerts_do_not_mislabel_brush_missing_as_blocked(component):
    from custom_components.dreame_wet_dry_vacuum.const import H15_ALERT_BINARY_SENSORS
    coordinator = make_coordinator(component)
    alerts = [component['binary_sensor'].DreameWetDryMappedAlert(coordinator, meta) for meta in H15_ALERT_BINARY_SENSORS]
    blocked = next(a for a in alerts if a._attr_name == 'Roller brush blocked')
    missing = next(a for a in alerts if a._attr_name == 'Roller brush missing')
    coordinator.data['4.2'] = 16
    assert missing.is_on is True
    assert blocked.is_on is False
    coordinator.data['4.2'] = 23 << 4
    assert blocked.is_on is True
    assert missing.is_on is False
    coordinator.data['4.2'] = -1
    assert blocked.is_on is None


def test_schedule_slider_uses_minutes_but_writes_seconds(component):
    coordinator = make_coordinator(component)
    coordinator.props.update({(1, 76): 7200, (1, 77): 11111})
    coordinator.data = coordinator._build_data()
    number = component['number'].DreameH15Number(coordinator, (1, 76))
    assert number.native_value == 120
    assert number.extra_state_attributes['time'] == '02:00'
    asyncio.run(number.async_set_native_value(90))
    assert coordinator.api.set_h15_properties.call_args.args[1] == {(1, 76): 5400, (1, 77): 11111}


def test_movement_always_sends_stop_after_start_rejection(component):
    coordinator = make_coordinator(component)
    coordinator.props[(10, 1)] = 2
    coordinator.snapshot['online'] = True
    coordinator.api.set_h15_properties.side_effect = [False, True]
    with pytest.raises(component['error']):
        asyncio.run(coordinator.async_send_h15_command('move_forward'))
    assert [call.args[1] for call in coordinator.api.set_h15_properties.call_args_list] == [{(100, 1): 1}, {(100, 1): 0}]


def test_cancelled_movement_still_stops_device(component, monkeypatch):
    coordinator = make_coordinator(component)
    coordinator.props[(10, 1)] = 2
    coordinator.snapshot['online'] = True
    async def cancel(_seconds):
        raise asyncio.CancelledError
    monkeypatch.setattr(component['coordinator'].asyncio, 'sleep', cancel)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(coordinator.async_send_h15_command('move_backward'))
    assert [call.args[1] for call in coordinator.api.set_h15_properties.call_args_list] == [{(100, 2): 1}, {(100, 2): 0}]


def test_sleeping_snapshot_does_not_infer_tank_removal(component):
    coordinator = make_coordinator(component)
    coordinator.data.update({'1.28': 7, '4.1': 0, '4.2': 0, '4.83': -1})
    from custom_components.dreame_wet_dry_vacuum.const import H15_ALERT_BINARY_SENSORS
    for meta in H15_ALERT_BINARY_SENSORS:
        alert = component['binary_sensor'].DreameWetDryMappedAlert(coordinator, meta)
        assert alert.is_on is False
    raw = component['sensor'].DreameH15PropertySensor(coordinator, (4, 83))
    assert raw.native_value == -1
    assert raw.extra_state_attributes['mapping_status'] == 'unmapped'


def test_arm_mode_dropdown_reads_and_writes_without_losing_reserved_bit(component):
    coordinator = make_coordinator(component)
    dropdown = component['select'].DreameH15Select(coordinator, (24, 1))
    assert dropdown.current_option == 'All modes'
    assert len(dropdown.options) == 16
    asyncio.run(dropdown.async_select_option('None'))
    assert coordinator.api.set_h15_properties.call_args.args[1] == {(24, 1): 31}
    assert dropdown.current_option == 'None'


def test_uploaded_dirty_tank_full_state_is_confirmed_and_not_percent(component):
    from custom_components.dreame_wet_dry_vacuum.const import H15_ALERT_BINARY_SENSORS
    coordinator = make_coordinator(component)
    coordinator.data.update({'4.2': 4096, '4.6': 81})
    meta = next(meta for meta in H15_ALERT_BINARY_SENSORS if meta['name'] == 'Dirty water tank full')
    alert = component['binary_sensor'].DreameWetDryMappedAlert(coordinator, meta)
    assert alert.is_on is True
    assert alert.extra_state_attributes['mapping_status'] == 'confirmed'
    raw = component['sensor'].DreameH15PropertySensor(coordinator, (4, 6))
    assert raw.native_value == 81
    assert raw.extra_state_attributes['mapping_status'] == 'candidate'
    assert '_attr_native_unit_of_measurement' not in raw.__dict__


@pytest.mark.parametrize("position,raw,label", [(0, 0, "Silent"), (1, 30, "Low"), (2, 60, "High")])
def test_three_position_volume_slider_sends_app_values(component, position, raw, label):
    coordinator = make_coordinator(component)
    slider = component["number"].DreameH15Number(coordinator, (1, 14))
    assert (slider._attr_native_min_value, slider._attr_native_max_value, slider._attr_native_step) == (0, 2, 1)
    assert slider._attr_mode == "slider"
    asyncio.run(slider.async_set_native_value(position))
    assert coordinator.api.set_h15_properties.call_args.args[1] == {(1, 14): raw}
    assert slider.native_value == position
    assert slider.extra_state_attributes["volume_level"] == label


def test_volume_slider_rejects_invalid_or_unacknowledged_values(component):
    coordinator = make_coordinator(component)
    coordinator.props[(1, 14)] = 30
    coordinator.data = coordinator._build_data()
    slider = component["number"].DreameH15Number(coordinator, (1, 14))
    for value in (-1, 0.5, 3, float("nan")):
        with pytest.raises(component["error"]):
            asyncio.run(slider.async_set_native_value(value))
    coordinator.api.set_h15_properties.assert_not_called()
    coordinator.api.set_h15_properties.return_value = False
    with pytest.raises(component["error"]):
        asyncio.run(slider.async_set_native_value(2))
    assert slider.native_value == 1
    # Unsupported returned values remain unknown instead of rounding to a level.
    coordinator.data["1.14"] = 45
    assert slider.native_value is None


def test_h15_native_device_cards_and_h14_presentation(component):
    from custom_components.dreame_wet_dry_vacuum.const import (
        H15_ALERT_BINARY_SENSORS,
        H15_BUTTON_COMMANDS,
    )
    coordinator = make_coordinator(component)
    for platform in ("select", "switch", "number", "button"):
        entities = []
        asyncio.run(component[platform].async_setup_entry(None, types.SimpleNamespace(runtime_data=coordinator), lambda items, target=entities: target.extend(items)))
        assert all(getattr(e, "_attr_entity_category", None) != "config" for e in entities)
    for key in ((3, 1), (1, 28), (1, 29), (1, 53)):
        entity = component["sensor"].DreameH15PropertySensor(coordinator, key)
        assert entity._attr_entity_category is None
    for key in ((6, 7), (19, 3), (4, 2)):
        entity = component["sensor"].DreameH15PropertySensor(coordinator, key)
        assert entity._attr_entity_category == "diagnostic"
        assert getattr(entity, "_attr_entity_registry_enabled_default", True)
    raw = component["sensor"].DreameH15PropertySensor(coordinator, (1, 68))
    assert raw._attr_entity_registry_enabled_default is False
    for meta in H15_ALERT_BINARY_SENSORS:
        assert component["binary_sensor"].DreameWetDryMappedAlert(coordinator, meta)._attr_entity_category == "diagnostic"
    for command, meta in H15_BUTTON_COMMANDS.items():
        entity = component["button"].DreameWetDryCommandButton(coordinator, command, meta)
        assert getattr(entity, "_attr_entity_category", None) == ("diagnostic" if "reset" in meta else None)
    from custom_components.dreame_wet_dry_vacuum.const import CONSUMABLE_SENSORS
    for model, expected in (("dreame.hold.w2449e", "diagnostic"), ("dreame.hold.w2306e", None)):
        entity = component["sensor"].DreameWetDryConsumableSensor(make_coordinator(component, model), CONSUMABLE_SENSORS[0])
        assert getattr(entity, "_attr_entity_category", None) == expected
