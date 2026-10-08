"""Native primary vacuum entity, backed by the existing device coordinator."""
from __future__ import annotations

from typing import Any

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import DreameAPIError
from .const import (
    H15_DRY_STATES,
    H15_ERROR_FIELDS,
    H15_SELECT_SETTINGS,
    H15_SUCTION_MAP,
    H15_WARN_FIELDS,
    H15_WASH_PAUSED_STATES,
    H15_WASH_STATES,
    H15_WORK_MODE_MAP,
    build_h15_command_plan,
    decode_h15_alerts,
)
from .entity import build_device_info


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Add the primary H15 entity without changing legacy H14 entities."""
    if entry.runtime_data.is_h15_pro_heat:
        async_add_entities([DreameWetDryVacuum(entry.runtime_data)])


class DreameWetDryVacuum(CoordinatorEntity, StateVacuumEntity):
    """Expose only verified H15 commands through HA's standard vacuum UI.

    START means self-cleaning on the dock (or resuming self-cleaning).
    STOP stops the currently reported self-cleaning or drying task.
    Physical floor cleaning is performed by the user, not remotely started.
    """

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "wet_dry"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_vacuum"
        self._attr_device_info = build_device_info(coordinator)

    def _number(self, key: str) -> int | None:
        raw = self.coordinator.data.get(key)
        try:
            value = int(raw)
            return value if not isinstance(raw, bool) and value >= 0 and value == float(raw) else None
        except (TypeError, ValueError, OverflowError):
            return None

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        snap = self.coordinator.snapshot or self.coordinator.device_info_raw
        if snap.get("online") is not None:
            return snap["online"] is True
        mqtt = self.coordinator.mqtt
        return bool(mqtt and mqtt.connected)

    @property
    def activity(self) -> VacuumActivity | None:
        if (error := self._number("4.2")) is not None and error > 0:
            return VacuumActivity.ERROR
        state = self._number("1.28")
        if state not in H15_WORK_MODE_MAP:
            return None
        if state in H15_WASH_PAUSED_STATES | {10, 12, 29}:
            return VacuumActivity.PAUSED
        if state in H15_WASH_STATES | H15_DRY_STATES | {16, 17, 18, 19, 20, 21, 22, 36, 40, 41}:
            # HA has no separate drying activity; work_mode preserves it below.
            return VacuumActivity.CLEANING
        if state in {4, 15}:
            return VacuumActivity.DOCKED
        # Sleeping alone does not prove that the device is on the dock.
        return VacuumActivity.IDLE

    @property
    def battery_level(self) -> int | None:
        value = self._number("3.1")
        return value if value is not None and value <= 100 else None

    @property
    def fan_speed(self) -> str | None:
        return H15_SUCTION_MAP.get(self._number("16.1"))

    @property
    def fan_speed_list(self) -> list[str]:
        return list(H15_SUCTION_MAP.values())

    def _can_command(self, command: str) -> bool:
        if not self.available:
            return False
        if command in {"start_self_clean", "resume_self_clean"} and self._number("4.2") not in (None, 0):
            return False
        try:
            build_h15_command_plan(command, self.coordinator.props)
        except (ValueError, TypeError):
            return False
        return True

    @property
    def supported_features(self) -> VacuumEntityFeature:
        features = VacuumEntityFeature.STATE
        # BATTERY was removed from newer HA releases in favour of the related
        # battery sensor. Keep older native dialogs working when it exists.
        features |= getattr(VacuumEntityFeature, "BATTERY", 0)
        if self._can_command("start_self_clean") or self._can_command("resume_self_clean"):
            features |= VacuumEntityFeature.START
        if self._can_command("stop_self_clean") or self._can_command("stop_self_dry"):
            features |= VacuumEntityFeature.STOP
        if self.available and self.fan_speed is not None and self._number("16.8") == 0:
            features |= VacuumEntityFeature.FAN_SPEED
        return features

    async def _command(self, command: str) -> None:
        if not self._can_command(command):
            raise HomeAssistantError("This operation is not available in the current device state")
        try:
            await self.coordinator.async_send_h15_command(command)
        except (ValueError, DreameAPIError) as err:
            raise HomeAssistantError(str(err)) from err

    async def async_start(self) -> None:
        command = "resume_self_clean" if self._number("1.28") in H15_WASH_PAUSED_STATES else "start_self_clean"
        await self._command(command)

    async def async_stop(self, **kwargs: Any) -> None:
        command = "stop_self_dry" if self._number("1.28") in H15_DRY_STATES else "stop_self_clean"
        await self._command(command)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        if not self.supported_features & VacuumEntityFeature.FAN_SPEED:
            raise HomeAssistantError("Suction control requires an online device with hot water disabled")
        value = next((value for value, label in H15_SUCTION_MAP.items() if label == fan_speed), None)
        if value is None:
            raise HomeAssistantError("Unknown suction setting")
        try:
            await self.coordinator.async_set_h15_setting((16, 1), value)
        except (ValueError, DreameAPIError) as err:
            raise HomeAssistantError(str(err)) from err

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Relevant telemetry only; unknown values are never guessed."""
        attributes = {
            "work_mode": H15_WORK_MODE_MAP.get(self._number("1.28")),
            "battery_level": self.battery_level,
            "charging": self._number("1.28") == 4 if self._number("1.28") is not None else None,
            "start_action": "Self-cleaning / resume self-cleaning",
            "clean_count": self._number("1.54"),
            "roller_brush_remaining_minutes": self._number("6.7"),
            "filter_remaining_minutes": self._number("19.3"),
            "warnings": decode_h15_alerts(self.coordinator.data.get("4.1"), H15_WARN_FIELDS),
            "errors": decode_h15_alerts(self.coordinator.data.get("4.2"), H15_ERROR_FIELDS),
        }
        for name, key in {
            "cleaning_mode": (16, 7), "self_cleaning_mode": (1, 8),
            "drying_mode": (1, 10), "water_level": (16, 2), "hot_water_mode": (16, 8),
        }.items():
            attributes[name] = H15_SELECT_SETTINGS[key].get(self._number(f"{key[0]}.{key[1]}"))
        attributes["volume_level"] = {0: "Silent", 30: "Low", 60: "High"}.get(self._number("1.14"))
        for name, key, maximum_key in (
            ("roller_brush_remaining_percent", "6.7", "6.6"),
            ("filter_remaining_percent", "19.3", "19.2"),
        ):
            remaining, maximum = self._number(key), self._number(maximum_key)
            if maximum and remaining is not None and remaining <= maximum:
                attributes[name] = 100 * remaining // maximum
        return attributes
