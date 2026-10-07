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
    imported = ["coordinator", "entity", "h15_controls", "select", "switch", "number", "sensor"]
    for name in imported:
        monkeypatch.delitem(sys.modules, f"{package}.{name}", raising=False)
    modules = {name: importlib.import_module(f"{package}.{name}") for name in imported}
    modules["error"] = HAError
    yield modules
    for name in imported:
        sys.modules.pop(f"{package}.{name}", None)


@pytest.mark.parametrize("model,expected", [("dreame.hold.w2449e", ["sensor.old_setting"]), ("dreame.hold.w2306e", [])])
def test_upgrade_only_disables_superseded_h15_setting_sensors(component, monkeypatch, model, expected):
    from pathlib import Path

    changed = []
    registry = types.SimpleNamespace(async_update_entity=lambda entity_id, **kw: changed.append(entity_id))
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
        "device_id": "test-device", "_h15_entity_schema": 2,
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
        ("dreame.hold.w2449e", (9, 9, 1)),
        ("dreame.hold.w2306e", (len(KNOWN_SELECT_PROPS), len(KNOWN_SWITCH_PROPS), len(KNOWN_NUMBER_PROPS))),
    ]:
        coordinator = make_coordinator(component, model)
        entry = types.SimpleNamespace(runtime_data=coordinator)
        for platform, size in zip(("select", "switch", "number"), sizes, strict=True):
            entities = []
            asyncio.run(component[platform].async_setup_entry(None, entry, entities.extend))
            assert len(entities) == size
            assert all(("H15" in type(e).__name__) == coordinator.is_h15_pro_heat for e in entities)


def test_h15_switch_polarity_and_invalid_select_are_handled(component):
    coordinator = make_coordinator(component)
    coordinator.props[(1, 9)] = 0
    coordinator.data = coordinator._build_data()
    controls = component["h15_controls"]
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
    select = component["h15_controls"].DreameH15Select(coordinator, (16, 7))
    with pytest.raises(component["error"]):
        asyncio.run(select.async_select_option("Turbo"))
    assert coordinator.props == before
    assert select.current_option == "Personalized"


def test_suction_unavailable_while_hot_and_arm_unavailable_if_unknown(component):
    coordinator = make_coordinator(component)
    controls = component["h15_controls"]
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
