"""Data coordinator for Dreame wet & dry vacuum (MQTT push + HTTP seed)."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DreameAPI, DreameAPIError, DreameAuthError
from .const import (
    CONSUMABLE_MAX_KEYS,
    DOMAIN,
    KNOWN_BINARY_PROPS,
    KNOWN_MQTT_PROPS,
    KNOWN_NUMBER_PROPS,
    KNOWN_SELECT_PROPS,
    KNOWN_SWITCH_PROPS,
    MQTT_ONLY_KEYS,
    STATUS_GROUP,
)
from .dreame_mqtt import DreameMqttClient
from .h15_settings import build_h15_write_plan
from .profiles import H15_TARGETED_KEYS, is_h15_pro_heat

_LOGGER = logging.getLogger(__name__)

HTTP_REFRESH = timedelta(minutes=5)

_POLL_KEYS: list[str] = sorted(
    {
        f"{s}.{p}"
        for s, p in (
            set(KNOWN_MQTT_PROPS)
            | set(KNOWN_BINARY_PROPS)
            | set(KNOWN_SWITCH_PROPS)
            | set(KNOWN_NUMBER_PROPS)
            | set(KNOWN_SELECT_PROPS)
        )
        - MQTT_ONLY_KEYS
    }
    | set(CONSUMABLE_MAX_KEYS)
)

# Expanded H15 discovery.
#
# The first mapping build and the explicit "Refresh mapping snapshot" button
# scan these ranges only. The normal 5-minute poll reads only properties that
# were actually discovered, so this does not create a permanent large poll.
#
# The Dreame common plugin defines services through at least SIID 26 and also
# contains SIID 100 (DeviceControl), so we deliberately include 1..40 + 100.
# PIID 120 covers the newly found H15 properties above the previous PIID-80
# limit (for example 1.81, 1.82 and 1.83).
_H15_SCAN_SIIDS: tuple[int, ...] = tuple(range(1, 41)) + (100,)
_H15_PIID_RANGE = range(1, 121)
_H15_DISCOVERY_CHUNK = 100
_H15_DIRECT_CHUNK = 50


class DreameWetDryCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Hold live device state from MQTT plus cloud polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: DreameAPI,
        device_id: str,
        device_info: dict[str, Any],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{device_id}",
            update_interval=None,
        )
        self.api = api
        self.device_id = device_id
        self.device_info_raw = device_info
        self.snapshot: dict[str, Any] = {}
        self.props: dict[tuple[int, int], Any] = {}
        self.new_prop_callback: Callable[[set[tuple[int, int]]], None] | None = None
        self.mqtt: DreameMqttClient | None = None
        self._unsub_poll: Callable[[], None] | None = None

        self._model = str(device_info.get("model") or "")
        self._is_h15 = is_h15_pro_heat(self._model)
        self._h15_discovery_done = False
        self._h15_poll_keys: list[str] = []

        self._h15_mapping_snapshot: dict[str, Any] = {}
        self._h15_last_changes: dict[str, dict[str, Any]] = {}
        self._h15_last_scan: datetime | None = None
        self._h15_write_lock = asyncio.Lock()

    @property
    def model(self) -> str:
        """Return the Dreame model identifier."""
        return self._model

    @property
    def is_h15_pro_heat(self) -> bool:
        """Return whether this coordinator is for the H15 Pro Heat profile."""
        return self._is_h15

    @property
    def h15_last_changes(self) -> dict[str, dict[str, Any]]:
        """Return changes detected by the last manual H15 mapping scan."""
        return self._h15_last_changes

    @property
    def h15_last_scan(self) -> datetime | None:
        """Return timestamp of the last manual/initial H15 mapping scan."""
        return self._h15_last_scan

    @callback
    def start_polling(self) -> None:
        """Start the fixed-interval safety-net poll."""
        self._unsub_poll = async_track_time_interval(
            self.hass, self._async_scheduled_poll, HTTP_REFRESH
        )

    @callback
    def stop_polling(self) -> None:
        """Stop the fixed-interval poll."""
        if self._unsub_poll:
            self._unsub_poll()
            self._unsub_poll = None

    async def _async_scheduled_poll(self, _now: datetime) -> None:
        await self.async_refresh()

    async def async_shutdown(self) -> None:
        self.stop_polling()
        await super().async_shutdown()

    def start_mqtt(self) -> None:
        """Create and start the MQTT client.

        This performs blocking SSL setup and is called from an executor.
        """
        snap = self.device_info_raw
        bind = snap.get("bindDomain") or snap.get("bind_domain")
        if not bind:
            _LOGGER.warning("No bindDomain; MQTT disabled, HTTP polling only")
            return

        self.mqtt = DreameMqttClient(
            uid=self.api.uid,
            access_token=self.api.access_token,
            device_id=self.device_id,
            model=snap.get("model", ""),
            bind_domain=bind,
            on_update=self._handle_mqtt_update,
        )
        self.mqtt.start()

    async def async_set_prop(self, siid: int, piid: int, value: Any) -> bool:
        """Write a property, then optimistically update state on success."""
        ok = await self.api.set_property(self.device_id, siid, piid, value)
        if ok:
            self.props[(siid, piid)] = value
            self.async_set_updated_data(self._build_data())
        else:
            _LOGGER.warning(
                "set_property %s.%s=%s rejected by device", siid, piid, value
            )
        return ok

    async def async_set_h15_setting(
        self, key: tuple[int, int], value: int, *, arm_bit: int | None = None
    ) -> None:
        """Write an H15 setting batch without using legacy H14 mappings."""
        if not self._is_h15:
            raise ValueError("H15 controls cannot write to this device model")
        async with self._h15_write_lock:
            if arm_bit is not None:
                # Refresh the shared bitfield when live RPC is available.
                # A sleeping device may return no value; never invent a default.
                rows = await self.api.get_properties(
                    self.device_id, [{"siid": 24, "piid": 1}]
                )
                for row in rows:
                    if (
                        row.get("code") == 0 and row.get("siid") == 24
                        and row.get("piid") == 1 and row.get("value") is not None
                    ):
                        self.props[(24, 1)] = row["value"]
            plan = build_h15_write_plan(key, value, self.props, arm_bit=arm_bit)
            ok = await self.api.set_h15_properties(self.device_id, plan)
            if not ok:
                raise HomeAssistantError(
                    "Dreame did not confirm the H15 setting change; refresh the device and retry"
                )
            new_keys = self._apply_h15_values({f"{s}.{p}": v for (s, p), v in plan.items()})
            if new_keys and self.new_prop_callback:
                self.new_prop_callback(new_keys)
            self.async_set_updated_data(self._build_data())

    def _handle_mqtt_update(self, state: dict[tuple[int, int], Any]) -> None:
        """Receive an MQTT update from the MQTT thread."""
        self.hass.loop.call_soon_threadsafe(self._apply_mqtt_state, dict(state))

    @callback
    def _apply_mqtt_state(self, state: dict[tuple[int, int], Any]) -> None:
        """Apply MQTT properties on the Home Assistant event loop."""
        new_keys = set(state) - set(self.props)
        self.props.update(state)

        if self._is_h15:
            for siid, piid in sorted(state):
                key = f"{siid}.{piid}"
                if key not in self._h15_poll_keys:
                    self._h15_poll_keys.append(key)
            self._h15_poll_keys.sort(key=self._property_sort_key)

        if new_keys and self.new_prop_callback:
            self.new_prop_callback(new_keys)

        self.async_set_updated_data(self._build_data())

    @staticmethod
    def _property_sort_key(key: str) -> tuple[int, int]:
        try:
            siid, piid = key.split(".", 1)
            return int(siid), int(piid)
        except (TypeError, ValueError):
            return (9999, 9999)

    @staticmethod
    def _all_h15_scan_keys() -> list[str]:
        return [
            f"{siid}.{piid}"
            for siid in _H15_SCAN_SIIDS
            for piid in _H15_PIID_RANGE
        ]

    def _build_data(self) -> dict[str, Any]:
        """Flatten properties for Home Assistant entities."""
        data: dict[str, Any] = {
            f"{siid}.{piid}": value
            for (siid, piid), value in self.props.items()
        }

        # Never apply the inherited H14 status-group table to H15.
        if not self._is_h15:
            status = self.props.get((2, 1))
            if status is not None:
                try:
                    data["status_group"] = STATUS_GROUP.get(int(status), "unknown")
                except (TypeError, ValueError):
                    data["status_group"] = "unknown"

        return data

    async def _get_status_props_chunked(
        self,
        keys: list[str],
        *,
        chunk_size: int = _H15_DISCOVERY_CHUNK,
    ) -> dict[str, Any]:
        """Read cloud-cached status properties in bounded chunks."""
        result: dict[str, Any] = {}
        for start in range(0, len(keys), chunk_size):
            chunk = keys[start : start + chunk_size]
            try:
                values = await self.api.get_status_props(self.device_id, chunk)
            except DreameAuthError:
                raise
            except (DreameAPIError, ValueError) as err:
                _LOGGER.debug("status_props chunk failed (non-fatal): %s", err)
                continue
            if isinstance(values, dict):
                result.update(values)
        return result

    async def _get_h15_targeted_live_props(self) -> dict[str, Any]:
        """Try direct read-only get_properties for app-known H15 keys.

        The cloud cache is the primary source on this model. Direct RPC often
        returns null while the unit sleeps, but it can expose extra settings
        while the vacuum is awake. Only successful, non-null results are merged.
        """
        props = [{"siid": s, "piid": p} for s, p in H15_TARGETED_KEYS]
        result: dict[str, Any] = {}

        for start in range(0, len(props), _H15_DIRECT_CHUNK):
            chunk = props[start : start + _H15_DIRECT_CHUNK]
            try:
                rows = await self.api.get_properties(self.device_id, chunk)
            except DreameAuthError:
                raise
            except (DreameAPIError, ValueError) as err:
                _LOGGER.debug("H15 direct get_properties failed (non-fatal): %s", err)
                continue

            for item in rows or []:
                try:
                    if int(item.get("code", -1)) != 0:
                        continue
                    value = item.get("value")
                    if value is None:
                        continue
                    key = f"{int(item['siid'])}.{int(item['piid'])}"
                except (KeyError, TypeError, ValueError):
                    continue
                result[key] = value

        return result

    async def _read_full_h15_profile(self) -> dict[str, Any]:
        """Read the expanded H15 profile from cache plus targeted live RPC."""
        cached = await self._get_status_props_chunked(self._all_h15_scan_keys())
        usable = {key: value for key, value in cached.items() if value is not None}

        # Prefer a successful live value over an older cached value.
        live = await self._get_h15_targeted_live_props()
        usable.update(live)
        return usable

    def _apply_h15_values(self, values: dict[str, Any]) -> set[tuple[int, int]]:
        """Apply returned H15 values and return newly discovered property keys."""
        new_keys: set[tuple[int, int]] = set()

        for key, value in values.items():
            if value is None:
                continue
            try:
                siid_text, piid_text = key.split(".", 1)
                pair = (int(siid_text), int(piid_text))
            except (TypeError, ValueError):
                continue

            if pair not in self.props:
                new_keys.add(pair)
            self.props[pair] = value

            if key not in self._h15_poll_keys:
                self._h15_poll_keys.append(key)

        self._h15_poll_keys.sort(key=self._property_sort_key)
        return new_keys

    async def _async_discover_h15_properties(self) -> None:
        """Discover all readable properties in the expanded H15 profile."""
        if self._h15_discovery_done:
            return

        usable = await self._read_full_h15_profile()
        new_keys = self._apply_h15_values(usable)

        self._h15_mapping_snapshot = dict(usable)
        self._h15_last_changes = {}
        self._h15_last_scan = datetime.now(UTC)
        self._h15_discovery_done = True

        if new_keys and self.new_prop_callback:
            self.new_prop_callback(new_keys)

        _LOGGER.info(
            "H15 Pro Heat baseline discovered %d properties for model=%s "
            "(scan SIIDs 1-40 + 100, PIIDs 1-120)",
            len(self._h15_mapping_snapshot),
            self._model,
        )

    async def async_refresh_h15_mapping(self) -> dict[str, dict[str, Any]]:
        """Run a fresh expanded H15 scan and compare with the previous snapshot.

        This operation is read-only and never writes to the vacuum.
        """
        if not self._is_h15:
            return {}

        usable = await self._read_full_h15_profile()

        if not self._h15_mapping_snapshot:
            self._h15_mapping_snapshot = dict(usable)

        changes: dict[str, dict[str, Any]] = {}
        for key, new_value in usable.items():
            if key not in self._h15_mapping_snapshot:
                changes[key] = {"old": "<new>", "new": new_value}
                continue

            old_value = self._h15_mapping_snapshot[key]
            if old_value != new_value:
                changes[key] = {"old": old_value, "new": new_value}

        new_keys = self._apply_h15_values(usable)

        self._h15_mapping_snapshot.update(usable)
        self._h15_last_changes = changes
        self._h15_last_scan = datetime.now(UTC)

        if new_keys and self.new_prop_callback:
            self.new_prop_callback(new_keys)

        self.async_set_updated_data(self._build_data())

        if changes:
            lines = [
                f"{key}: {change['old']!r} -> {change['new']!r}"
                for key, change in sorted(
                    changes.items(),
                    key=lambda item: self._property_sort_key(item[0]),
                )
            ]
            _LOGGER.info(
                "H15 mapping scan detected %d change(s):\n%s",
                len(changes),
                "\n".join(lines),
            )
        else:
            _LOGGER.info("H15 mapping scan detected no property changes")

        return changes

    async def _async_poll_h15_properties(self) -> None:
        """Refresh only properties already discovered for the H15."""
        if not self._h15_discovery_done:
            await self._async_discover_h15_properties()
            return

        if not self._h15_poll_keys:
            return

        values = await self._get_status_props_chunked(self._h15_poll_keys)
        self._apply_h15_values(values)

    async def _async_update_data(self) -> dict[str, Any]:
        """Refresh cloud snapshot and cached properties."""
        try:
            snapshot = await self.api.get_device_snapshot(self.device_id)
        except DreameAuthError as err:
            raise ConfigEntryAuthFailed(
                f"Dreame credentials rejected: {err}"
            ) from err
        except DreameAPIError as err:
            if self.props:
                return self._build_data()
            raise UpdateFailed(f"Dreame API error: {err}") from err

        if snapshot:
            self.snapshot = snapshot
            if snapshot.get("battery") is not None and (3, 1) not in self.props:
                self.props[(3, 1)] = snapshot["battery"]
            if snapshot.get("status") is not None and (2, 1) not in self.props:
                self.props[(2, 1)] = snapshot["status"]
            if self.mqtt and self.api.access_token:
                self.mqtt.update_token(self.api.access_token)

        try:
            if self._is_h15:
                await self._async_poll_h15_properties()
            else:
                values = await self.api.get_status_props(self.device_id, _POLL_KEYS)
                for key, value in values.items():
                    siid_text, _, piid_text = key.partition(".")
                    self.props[(int(siid_text), int(piid_text))] = value
        except DreameAuthError as err:
            raise ConfigEntryAuthFailed(
                f"Dreame credentials rejected: {err}"
            ) from err
        except (DreameAPIError, ValueError) as err:
            _LOGGER.debug("status_props poll failed (non-fatal): %s", err)

        return self._build_data()
