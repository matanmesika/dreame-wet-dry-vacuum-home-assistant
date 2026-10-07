"""Sensor platform for Dreame wet & dry vacuum."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DreameWetDryConfigEntry
from .const import (
    CONSUMABLE_SENSORS,
    DEVICE_STATUS,
    ERROR_DECODE,
    KNOWN_MQTT_PROPS,
    WARN_DECODE,
    decode_field_alerts,
)
from .coordinator import DreameWetDryCoordinator
from .entity import build_device_info
from .profiles import H15_PROPERTY_META

_LOGGER = logging.getLogger(__name__)

_DECODE_TABLES = {"warn": WARN_DECODE, "error": ERROR_DECODE}

_DEVICE_CLASSES = {
    "battery": SensorDeviceClass.BATTERY,
    "duration": SensorDeviceClass.DURATION,
    "timestamp": SensorDeviceClass.TIMESTAMP,
}
_STATE_CLASSES = {
    "measurement": SensorStateClass.MEASUREMENT,
    "total_increasing": SensorStateClass.TOTAL_INCREASING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DreameWetDryConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator: DreameWetDryCoordinator = entry.runtime_data

    if coordinator.is_h15_pro_heat:
        _setup_h15_sensors(coordinator, async_add_entities)
        return

    added: set[tuple[int, int]] = set()

    @callback
    def _add_new(keys: set[tuple[int, int]]) -> None:
        entities = []
        for key in keys:
            if key in added or key not in KNOWN_MQTT_PROPS:
                continue
            added.add(key)
            entities.append(DreameWetDrySensor(coordinator, key))
        if entities:
            async_add_entities(entities)

    coordinator.new_prop_callback = _add_new
    _add_new(set(KNOWN_MQTT_PROPS))

    async_add_entities(
        DreameWetDryConsumableSensor(coordinator, meta)
        for meta in CONSUMABLE_SENSORS
    )


def _setup_h15_sensors(
    coordinator: DreameWetDryCoordinator,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Expose every property discovered from the H15 as a safe read-only sensor."""
    added: set[tuple[int, int]] = set()

    @callback
    def _add_new(keys: set[tuple[int, int]]) -> None:
        entities: list[SensorEntity] = []
        for key in sorted(keys):
            if key in added:
                continue
            added.add(key)
            entities.append(DreameH15PropertySensor(coordinator, key))
        if entities:
            async_add_entities(entities)

    coordinator.new_prop_callback = _add_new
    _add_new(set(coordinator.props))
    async_add_entities([DreameH15MappingChangesSensor(coordinator)])

    _LOGGER.info(
        "Created %d H15 Pro Heat property sensors for model=%s",
        len(added),
        coordinator.model,
    )


class DreameH15MappingChangesSensor(
    CoordinatorEntity[DreameWetDryCoordinator], SensorEntity
):
    """Show the result of the last explicit H15 mapping snapshot comparison."""

    _attr_has_entity_name = True
    _attr_name = "Mapping changes"
    _attr_icon = "mdi:compare"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DreameWetDryCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_h15_mapping_changes"
        self._attr_device_info = build_device_info(coordinator)

    @property
    def native_value(self) -> int:
        return len(self.coordinator.h15_last_changes)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        changes = self.coordinator.h15_last_changes
        attrs: dict[str, Any] = {
            "model": self.coordinator.model,
            "changed_properties": list(changes),
            "changes": changes,
        }
        if self.coordinator.h15_last_scan is not None:
            attrs["last_scan"] = self.coordinator.h15_last_scan.isoformat()
        return attrs


class DreameH15PropertySensor(
    CoordinatorEntity[DreameWetDryCoordinator], SensorEntity
):
    """Read-only H15 property sensor.

    Confirmed/candidate names come from the model profile. Anything not mapped
    remains a Raw SIID.PIID sensor instead of inheriting H14 semantics.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DreameWetDryCoordinator,
        key: tuple[int, int],
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._data_key = f"{key[0]}.{key[1]}"
        self._meta = H15_PROPERTY_META.get(key, {})

        # H15-specific IDs prevent old H14 sensor semantics from being reused.
        self._attr_unique_id = (
            f"{coordinator.device_id}_h15_property_{key[0]}_{key[1]}"
        )
        self._attr_name = self._meta.get("name", f"Raw {self._data_key}")
        self._attr_icon = self._meta.get("icon", "mdi:code-tags")
        self._attr_device_info = build_device_info(coordinator)

        if self._meta.get("diagnostic", True):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

        device_class = self._meta.get("device_class")
        if device_class == "battery":
            self._attr_device_class = SensorDeviceClass.BATTERY
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif device_class == "duration":
            self._attr_device_class = SensorDeviceClass.DURATION

        state_class = self._meta.get("state_class")
        if state_class == "measurement":
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif state_class == "total_increasing":
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

        if unit := self._meta.get("unit"):
            self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> Any:
        raw = self.coordinator.data.get(self._data_key)
        if raw is None:
            return None

        # Lists/dicts are valid raw Dreame values, but HA sensor state itself
        # must be scalar. Preserve the exact value in raw_value attributes.
        if isinstance(raw, (list, dict, tuple)):
            return json.dumps(raw, ensure_ascii=False, separators=(",", ":"))

        value_map = self._meta.get("value_map")
        if isinstance(value_map, dict):
            try:
                numeric = int(raw)
            except (TypeError, ValueError):
                return str(raw)
            return value_map.get(numeric, f"Unknown ({raw})")

        return raw

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        raw = self.coordinator.data.get(self._data_key)
        attrs: dict[str, Any] = {
            "model": self.coordinator.model,
            "siid": self._key[0],
            "piid": self._key[1],
            "property": self._data_key,
            "mapping_status": self._meta.get("confidence", "unmapped"),
            "raw_value": raw,
        }

        if note := self._meta.get("note"):
            attrs["mapping_note"] = note

        value_map = self._meta.get("value_map")
        if isinstance(value_map, dict):
            attrs["known_values"] = {
                str(key): value for key, value in value_map.items()
            }

        if self._meta.get("bitfield") and raw is not None:
            try:
                value = int(raw)
                attrs["active_bits"] = [
                    1 << bit for bit in range(32) if value & (1 << bit)
                ]
            except (TypeError, ValueError):
                pass

        if self._meta.get("remaining_time") and raw is not None:
            try:
                minutes = int(raw)
                if minutes >= 0:
                    attrs["hours_remaining"] = round(minutes / 60, 1)
            except (TypeError, ValueError):
                pass

        return attrs


class DreameWetDrySensor(
    CoordinatorEntity[DreameWetDryCoordinator], SensorEntity
):
    """One legacy/H14 sensor per (siid, piid) property."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DreameWetDryCoordinator,
        key: tuple[int, int],
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._data_key = f"{key[0]}.{key[1]}"
        meta = KNOWN_MQTT_PROPS.get(key, {})
        self._meta = meta
        self._is_enum = meta.get("enum", False)
        self._list_scalar = meta.get("list_scalar", False)
        self._is_timestamp = meta.get("timestamp", False)
        self._is_bitmask = meta.get("bitmask", False)
        self._decode = meta.get("decode")

        self._attr_unique_id = f"{coordinator.device_id}_{self._data_key}"
        self._attr_translation_key = meta["key"]
        self._attr_icon = meta.get("icon")

        if dc := _DEVICE_CLASSES.get(meta.get("device_class")):
            self._attr_device_class = dc
        if sc := _STATE_CLASSES.get(meta.get("state_class")):
            self._attr_state_class = sc
        if meta.get("unit"):
            self._attr_native_unit_of_measurement = meta["unit"]
        if meta.get("device_class") == "battery":
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if meta.get("diagnostic") or not meta:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

        self._attr_device_info = build_device_info(coordinator)

    def _scalar(self, raw: Any) -> Any:
        if self._list_scalar and isinstance(raw, list):
            return raw[0] if raw else None
        return raw

    @property
    def native_value(self) -> Any:
        raw = self.coordinator.data.get(self._data_key)
        if raw is None:
            return None
        raw = self._scalar(raw)
        if raw is None:
            return None
        if self._is_timestamp:
            try:
                return datetime.fromtimestamp(int(raw), tz=timezone.utc)
            except (ValueError, TypeError, OSError):
                return None
        if self._is_enum:
            try:
                return DEVICE_STATUS.get(int(raw), str(raw))
            except (ValueError, TypeError):
                return str(raw)
        if isinstance(raw, list):
            return ", ".join(str(x) for x in raw)
        return raw

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = {"siid": self._key[0], "piid": self._key[1]}
        raw = self.coordinator.data.get(self._data_key)
        if self._is_enum or self._is_timestamp or self._list_scalar:
            attrs["raw_value"] = raw
        if self._is_bitmask and raw is not None:
            try:
                ival = int(raw)
                bits = [bit for bit in range(32) if ival & (1 << bit)]
                attrs["active_bits"] = [1 << bit for bit in bits]
                if self._decode and self._decode in _DECODE_TABLES:
                    attrs["alerts"] = decode_field_alerts(
                        ival, _DECODE_TABLES[self._decode]
                    )
            except (ValueError, TypeError):
                pass
        return attrs


class DreameWetDryConsumableSensor(
    CoordinatorEntity[DreameWetDryCoordinator], SensorEntity
):
    """Legacy/H14 consumable remaining-life sensor."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "h"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DreameWetDryCoordinator, meta: dict) -> None:
        super().__init__(coordinator)
        self._left_key = meta["left"]
        self._max_key = meta["max"]
        self._full_life_min = meta["full_life_min"]
        self._attr_unique_id = (
            f"{coordinator.device_id}_consumable_{meta['key']}"
        )
        self._attr_translation_key = f"consumable_{meta['key']}"
        self._attr_icon = meta.get("icon")
        self._attr_device_info = build_device_info(coordinator)

    def _left_minutes(self) -> int | None:
        try:
            return int(self.coordinator.data.get(self._left_key))
        except (ValueError, TypeError):
            return None

    @property
    def native_value(self) -> float | None:
        left = self._left_minutes()
        return None if left is None else round(left / 60, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        left = self._left_minutes()
        if left is None:
            return {}

        raw_max = self.coordinator.data.get(self._max_key)
        try:
            full = int(raw_max)
        except (ValueError, TypeError):
            full = -1

        from_device = full > 0
        if not from_device:
            full = self._full_life_min

        attrs: dict[str, Any] = {
            "minutes_remaining": left,
            "full_life_hours": round(full / 60, 1),
            "full_life_source": "device" if from_device else "default (60 h)",
        }
        if full > 0:
            attrs["percent_remaining"] = max(
                0, min(100, round(left / full * 100))
            )
        return attrs
