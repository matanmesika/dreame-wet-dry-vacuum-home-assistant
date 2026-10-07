"""H15-specific control entities; legacy H14 controls remain unchanged."""
from __future__ import annotations

import math
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.select import SelectEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import DreameAPIError
from .entity import build_device_info
from .h15_settings import (
    H15_ARM_MODES,
    H15_NUMBER_SETTINGS,
    H15_SELECT_SETTINGS,
    H15_SWITCH_SETTINGS,
    h15_setting_name,
)
from .profiles import H15_PROPERTY_META


class DreameH15Setting(CoordinatorEntity):
    """A model-specific setting with explicit write error handling."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, key: tuple[int, int], *, arm_bit: int | None = None) -> None:
        super().__init__(coordinator)
        self._key = key
        self._arm_bit = arm_bit
        suffix = f"_bit_{arm_bit}" if arm_bit is not None else ""
        self._attr_unique_id = f"{coordinator.device_id}_h15_setting_{key[0]}_{key[1]}{suffix}"
        self._attr_name = (
            f"Lifting arm — {H15_ARM_MODES[arm_bit]}"
            if arm_bit is not None else h15_setting_name(key)
        )
        self._attr_icon = H15_PROPERTY_META[key].get("icon")
        self._attr_device_info = build_device_info(coordinator)

    @property
    def _raw(self) -> int | None:
        raw = self.coordinator.data.get(f"{self._key[0]}.{self._key[1]}")
        try:
            value = int(raw)
            return value if value >= 0 and value == float(raw) else None
        except (TypeError, ValueError, OverflowError):
            return None

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if self._arm_bit is not None:
            return self._raw is not None and self._raw <= 31
        if self._key == (16, 1):
            return self.coordinator.data.get("16.8") in (0, "0")
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "property": f"{self._key[0]}.{self._key[1]}",
            "raw_value": self._raw,
            "mapping_status": H15_PROPERTY_META[self._key]["confidence"],
            "write_source": "Dreamehome H15 app",
        }

    async def _write(self, value: int) -> None:
        try:
            await self.coordinator.async_set_h15_setting(self._key, value, arm_bit=self._arm_bit)
        except (ValueError, DreameAPIError) as err:
            raise HomeAssistantError(str(err)) from err


class DreameH15Select(DreameH15Setting, SelectEntity):
    """An H15 enum shown as a dropdown with only app-supported options."""

    def __init__(self, coordinator, key) -> None:
        super().__init__(coordinator, key)
        self._options = H15_SELECT_SETTINGS[key]
        self._attr_options = list(self._options.values())

    @property
    def current_option(self) -> str | None:
        return self._options.get(self._raw)

    async def async_select_option(self, option: str) -> None:
        for raw, label in self._options.items():
            if option == label:
                await self._write(raw)
                return
        raise HomeAssistantError(f"Unsupported H15 option: {option}")


class DreameH15Switch(DreameH15Setting, SwitchEntity):
    """A boolean setting or one inverted lifting-arm mode bit."""

    @property
    def is_on(self) -> bool | None:
        value = self._raw
        if value is None:
            return None
        if self._arm_bit is not None:
            return value <= 31 and not bool(value & (1 << self._arm_bit))
        on, off = H15_SWITCH_SETTINGS[self._key]
        return True if value == on else False if value == off else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._write(1 if self._arm_bit is not None else H15_SWITCH_SETTINGS[self._key][0])

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._write(0 if self._arm_bit is not None else H15_SWITCH_SETTINGS[self._key][1])


class DreameH15Number(DreameH15Setting, NumberEntity):
    """H15 voice volume as a slider."""

    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, key) -> None:
        super().__init__(coordinator, key)
        minimum, maximum, step = H15_NUMBER_SETTINGS[key]
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = "%"

    @property
    def native_value(self) -> float | None:
        value = self._raw
        return value if value is not None and 0 <= value <= 100 else None

    async def async_set_native_value(self, value: float) -> None:
        if not math.isfinite(value) or value != int(value):
            raise HomeAssistantError("H15 voice volume must be a whole percentage")
        await self._write(int(value))
