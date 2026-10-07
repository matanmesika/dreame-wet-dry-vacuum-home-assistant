"""H15 writes must follow app enums, coupled settings and inverted bitfields."""
import pytest

from custom_components.dreame_wet_dry_vacuum.h15_settings import (
    H15_CONTROL_KEYS,
    build_h15_write_plan,
)


@pytest.mark.parametrize("key,value", [
    ((16, 7), 2), ((16, 2), 1), ((1, 8), 5), ((1, 10), 2),
    ((23, 1), 3), ((26, 3), 1), ((1, 14), 101), ((1, 14), -1),
    ((1, 28), 4), ((3, 1), 50), ((1, 17), 1), ((100, 1), 1),
])
def test_unmapped_or_unsupported_setting_is_not_written(key, value):
    with pytest.raises(ValueError):
        build_h15_write_plan(key, value, {})


@pytest.mark.parametrize("value", [0, 100])
def test_volume_range_includes_mute_and_full(value):
    assert build_h15_write_plan((1, 14), value, {}) == {(1, 14): value}


def test_custom_water_change_preserves_suction_and_enables_custom_mode():
    plan = build_h15_write_plan((16, 2), 3, {(16, 1): 2, (16, 8): 0})
    assert plan == {(16, 1): 2, (16, 2): 3, (16, 7): 4, (16, 6): 1}


def test_hot_water_forces_gentle_suction_and_preserves_water():
    plan = build_h15_write_plan((16, 8), 3, {(16, 1): 3, (16, 2): 3})
    assert plan == {(16, 1): 1, (16, 2): 3, (16, 7): 4, (16, 6): 1, (16, 8): 3}
    assert build_h15_write_plan((16, 8), 0, {}) == {(16, 8): 0}


@pytest.mark.parametrize("key,value", [((16, 1), 3), ((16, 7), 3)])
def test_incompatible_suction_or_preset_is_rejected_while_hot(key, value):
    with pytest.raises(ValueError):
        build_h15_write_plan(key, value, {(16, 8): 1})


@pytest.mark.parametrize("mode,power,water", [(1, 1, 2), (3, 3, 3), (4, 2, 2)])
def test_cleaning_preset_sets_matching_power_and_water(mode, power, water):
    assert build_h15_write_plan((16, 7), mode, {(16, 8): 0}) == {
        (16, 7): mode, (16, 1): power, (16, 2): water, (16, 6): 1,
    }


@pytest.mark.parametrize("key,value,siblings", [
    ((1, 8), 3, (8, 81, 75)), ((1, 10), 3, (10, 82, 83)),
])
def test_wash_dry_preferences_match_all_three_app_profiles(key, value, siblings):
    assert build_h15_write_plan(key, value, {}) == {(1, p): value for p in siblings}


def test_arm_mode_change_preserves_other_modes_and_unused_bit():
    # 2: all four modes selected, unused bit1 set. Disable Smart only.
    assert build_h15_write_plan((24, 1), 0, {(24, 1): 2}, arm_bit=0) == {(24, 1): 3}
    # Re-enable Smart while Suction remains off (bit2=1).
    assert build_h15_write_plan((24, 1), 1, {(24, 1): 7}, arm_bit=0) == {(24, 1): 6}


@pytest.mark.parametrize("props", [{}, {(24, 1): -1}, {(24, 1): 32}])
def test_arm_never_overwrites_unknown_state(props):
    with pytest.raises(ValueError):
        build_h15_write_plan((24, 1), 1, props, arm_bit=0)


def test_missing_custom_setting_dependency_is_not_invented():
    with pytest.raises(ValueError):
        build_h15_write_plan((16, 1), 3, {})
    assert (1, 28) not in H15_CONTROL_KEYS
    assert (3, 1) not in H15_CONTROL_KEYS
