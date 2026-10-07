"""H15-only settings and write plans derived from the Dreamehome UI."""
from __future__ import annotations

from typing import Any

from .profiles import (
    H15_CLEANING_MODE_MAP,
    H15_DETERGENT_MODE_MAP,
    H15_DRY_MODE_MAP,
    H15_HOT_WATER_MAP,
    H15_MOISTURE_SENSITIVITY_MAP,
    H15_PROPERTY_META,
    H15_SUCTION_MAP,
    H15_TRACTION_MAP,
)

H15_SELECT_SETTINGS: dict[tuple[int, int], dict[int, str]] = {
    (16, 7): H15_CLEANING_MODE_MAP,
    (16, 1): H15_SUCTION_MAP,
    (16, 2): {2: "Standard", 3: "High"},
    (16, 8): H15_HOT_WATER_MAP,
    (1, 8): {4: "Auto-Adjust", 2: "Standard", 3: "Deep-Clean"},
    (1, 10): H15_DRY_MODE_MAP,
    (23, 1): {1: H15_TRACTION_MAP[1], 0: H15_TRACTION_MAP[0], 2: H15_TRACTION_MAP[2]},
    (26, 3): H15_MOISTURE_SENSITIVITY_MAP,
    (1, 67): H15_DETERGENT_MODE_MAP,
}

# (on, off) values differ from the legacy H14 switch implementation.
H15_SWITCH_SETTINGS: dict[tuple[int, int], tuple[int, int]] = {
    (1, 7): (0, 1),
    (1, 9): (0, 1),
    (26, 1): (0, 1),
    (26, 2): (0, 1),
    (16, 6): (1, 0),
}

H15_ARM_MODES: dict[int, str] = {0: "Smart", 3: "Hot Water", 2: "Suction", 4: "Custom"}
H15_NUMBER_SETTINGS: dict[tuple[int, int], tuple[int, int, int]] = {(1, 14): (0, 100, 1)}
H15_CONTROL_KEYS = (
    set(H15_SELECT_SETTINGS) | set(H15_SWITCH_SETTINGS) | set(H15_NUMBER_SETTINGS) | {(24, 1)}
)


def h15_setting_name(key: tuple[int, int]) -> str:
    """Return the profile name without duplicating H15/H14 mappings."""
    if key == (16, 6):
        return "Custom cleaning enabled"
    return H15_PROPERTY_META[key]["name"]


def _current(props: dict[tuple[int, int], Any], key: tuple[int, int]) -> int:
    try:
        value = props[key]
        number = int(value)
        if isinstance(value, bool) or number != float(value) or number < 0:
            raise ValueError
        return number
    except (KeyError, TypeError, ValueError, OverflowError) as err:
        raise ValueError(f"Current H15 property {key[0]}.{key[1]} is unknown; refresh the device first") from err


def build_h15_write_plan(
    key: tuple[int, int], value: int, props: dict[tuple[int, int], Any], *, arm_bit: int | None = None,
) -> dict[tuple[int, int], int]:
    """Validate a setting and preserve the app's coupled setting behavior.

    Never write status/telemetry, unknown enums, schedule encodings or H14
    controls. The arm is read-modify-write with inverted bits.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("H15 setting values must be integers")  # noqa: TRY004 -- user-facing validation
    if arm_bit is not None:
        if key != (24, 1) or arm_bit not in H15_ARM_MODES or value not in (0, 1):
            raise ValueError("Invalid H15 lifting arm setting")
        current = _current(props, key)
        if current > 31:
            raise ValueError("Unknown H15 lifting arm encoding")
        updated = current & ~(1 << arm_bit) if value else current | (1 << arm_bit)
        return {key: updated}

    if key in H15_SELECT_SETTINGS:
        if value not in H15_SELECT_SETTINGS[key]:
            raise ValueError("Unsupported H15 option")
    elif key in H15_SWITCH_SETTINGS:
        if value not in H15_SWITCH_SETTINGS[key]:
            raise ValueError("Unsupported H15 switch value")
    elif key in H15_NUMBER_SETTINGS:
        minimum, maximum, step = H15_NUMBER_SETTINGS[key]
        if not minimum <= value <= maximum or (value - minimum) % step:
            raise ValueError("H15 number is outside its supported range")
    else:
        raise ValueError("This H15 property is not a writable setting")

    if key in {(1, 8), (1, 10)}:
        # The w2449e app synchronizes manual, return-to-base and scheduled
        # wash/dry preferences. Update all three copies of the changed setting.
        siblings = (8, 81, 75) if key == (1, 8) else (10, 82, 83)
        return {(1, piid): value for piid in siblings}

    if key in {(16, 1), (16, 2), (16, 7), (16, 8)}:
        if key == (16, 8) and value == 0:
            return {key: value}
        hot = value if key == (16, 8) else _current(props, (16, 8))
        if hot not in H15_HOT_WATER_MAP:
            raise ValueError("Unknown H15 hot water setting")
        if key == (16, 1) and hot:
            raise ValueError("Suction is fixed to Gentle while hot water is enabled")
        if key == (16, 7):
            power, water = {1: (1, 2), 3: (3, 3), 4: (1 if hot else 2, 2)}[value]
            if hot and value != 4:
                raise ValueError("Turn hot water off before selecting Quiet or Turbo")
            return {(16, 7): value, (16, 1): power, (16, 2): water, (16, 6): 1}
        water = value if key == (16, 2) else _current(props, (16, 2))
        power = value if key == (16, 1) else (1 if hot or key == (16, 8) else _current(props, (16, 1)))
        if water not in H15_SELECT_SETTINGS[(16, 2)] or power not in H15_SUCTION_MAP:
            raise ValueError("Refresh current H15 suction and water settings first")
        result = {(16, 1): power, (16, 2): water, (16, 7): 4, (16, 6): 1}
        if key == (16, 8):
            result[key] = value
        return result

    return {key: value}
