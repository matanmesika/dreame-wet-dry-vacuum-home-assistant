"""Native vacuum entity routes real commands and preserves model isolation."""
import asyncio
import types

import pytest
from test_h15_controls import make_coordinator

pytest_plugins = ("test_h15_controls",)


def device(component, props=None):
    coordinator = make_coordinator(component)
    coordinator.snapshot = {"online": True}
    coordinator.props.update({(1, 28): 7, (1, 8): 2, (1, 10): 1, (3, 1): 100, (4, 2): 0})
    coordinator.props.update(props or {})
    coordinator.data = coordinator._build_data()
    return coordinator, component["vacuum"].DreameWetDryVacuum(coordinator)


def test_primary_entity_uses_existing_device_and_does_not_create_h14_vacuum(component):
    for model, count in (("dreame.hold.w2449e", 1), ("dreame.hold.w2306e", 0)):
        coordinator = make_coordinator(component, model)
        entities = []
        asyncio.run(component["vacuum"].async_setup_entry(None, types.SimpleNamespace(runtime_data=coordinator), entities.extend))
        assert len(entities) == count
        if count:
            assert entities[0]._attr_unique_id == "test-device_vacuum"
            assert entities[0]._attr_name is None
            assert entities[0]._attr_device_info["identifiers"] == {("dreame_wet_dry_vacuum", "test-device")}


@pytest.mark.parametrize("raw,expected", [(4, "docked"), (15, "docked"), (7, "idle"), (5, "cleaning"), (6, "cleaning"), (22, "cleaning"), (12, "paused"), (43, "paused"), (999, None), (-1, None), (None, None), (True, None)])
def test_activity_preserves_drying_and_unknown_without_inventing_docking(component, raw, expected):
    _coordinator, vacuum = device(component, {(1, 28): raw})
    assert vacuum.activity == expected
    if raw == 6:
        assert vacuum.extra_state_attributes["work_mode"] == "Self-drying"
    assert vacuum.activity == expected


@pytest.mark.parametrize("state,method,plan", [(7, "async_start", {(1, 1): 2}), (43, "async_start", {(1, 1): 1}), (5, "async_stop", {(1, 1): 0}), (6, "async_stop", {(1, 2): 0}), (12, "async_stop", {(1, 2): 0})])
def test_native_controls_use_existing_guarded_commands_and_do_not_fake_activity(component, state, method, plan):
    coordinator, vacuum = device(component, {(1, 28): state})
    before = vacuum.activity
    asyncio.run(getattr(vacuum, method)())
    assert coordinator.api.set_h15_properties.call_args.args[1] == plan
    assert vacuum.activity == before


def test_features_hide_unsupported_commands_and_hot_water_suction(component):
    coordinator, vacuum = device(component)
    features = component["vacuum"].VacuumEntityFeature
    assert vacuum.supported_features & features.START
    assert not vacuum.supported_features & features.STOP
    assert vacuum.supported_features & features.FAN_SPEED
    asyncio.run(vacuum.async_set_fan_speed("Strong"))
    assert coordinator.api.set_h15_properties.call_args.args[1][(16, 1)] == 3
    coordinator.data["16.8"] = 1
    assert not vacuum.supported_features & features.FAN_SPEED
    with pytest.raises(component["error"]):
        asyncio.run(vacuum.async_set_fan_speed("Strong"))
    coordinator.data["16.8"] = 0
    with pytest.raises(component["error"]):
        asyncio.run(vacuum.async_set_fan_speed("Unknown"))


@pytest.mark.parametrize("overrides", [{(3, 1): 19}, {(1, 8): -1}, {(1, 28): 22}, {(4, 2): 4096}])
def test_invalid_start_is_never_sent(component, overrides):
    coordinator, vacuum = device(component, overrides)
    with pytest.raises(component["error"]):
        asyncio.run(vacuum.async_start())
    coordinator.api.set_h15_properties.assert_not_called()


def test_offline_or_failed_coordinator_never_accepts_commands(component):
    coordinator, vacuum = device(component)
    for snapshot, success in (({"online": False}, True), ({"online": True}, False)):
        coordinator.snapshot, coordinator.last_update_success = snapshot, success
        assert not vacuum.available
        with pytest.raises(component["error"]):
            asyncio.run(vacuum.async_start())
        coordinator.api.set_h15_properties.assert_not_called()


def test_rejected_command_propagates_and_never_fakes_state(component):
    coordinator, vacuum = device(component)
    coordinator.api.set_h15_properties.return_value = False
    with pytest.raises(component["error"]):
        asyncio.run(vacuum.async_start())
    assert vacuum.activity == "idle"


def test_fresh_fault_blocks_start_even_if_native_dialog_was_idle(component):
    coordinator, vacuum = device(component)
    coordinator.api.get_properties.return_value = [{"siid": 4, "piid": 2, "code": 0, "value": 4096}]
    with pytest.raises(component["error"]):
        asyncio.run(vacuum.async_start())
    coordinator.api.set_h15_properties.assert_not_called()


def test_maintenance_battery_and_faults_use_reported_values_only(component):
    coordinator, vacuum = device(component, {(6, 7): 3413, (19, 3): 3473, (1, 14): 30, (4, 2): 4096})
    attrs = vacuum.extra_state_attributes
    assert vacuum.activity == "error"
    assert "Dirty water tank full" in attrs["errors"]
    assert attrs["roller_brush_remaining_minutes"] == 3413
    assert attrs["volume_level"] == "Low"
    assert "roller_brush_remaining_percent" not in attrs
    coordinator.data.update({"6.6": 3600, "6.7": 3413, "3.1": 101, "19.3": -1, "1.14": 45})
    attrs = vacuum.extra_state_attributes
    assert attrs["roller_brush_remaining_percent"] == 94
    assert attrs["filter_remaining_minutes"] is None
    assert attrs["volume_level"] is None
    assert vacuum.battery_level is None
