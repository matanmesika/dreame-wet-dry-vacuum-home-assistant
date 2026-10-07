"""Data coordinator for Dreame wet & dry vacuum (MQTT push + HTTP seed)."""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
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
from .profiles import is_h15_pro_heat

_LOGGER = logging.getLogger(__name__)

HTTP_REFRESH = timedelta(minutes=5)

# Normal H14/legacy polling set.
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

# H15 discovery is intentionally broad so the integration does not need a
# hardcoded list of every property before a model is mapped.
_H15_SIID_RANGE = range(1, 31)
_H15_PIID_RANGE = range(1, 81)
_H15_DISCOVERY_CHUNK = 100


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

    @property
    def model(self) -> str:
        """Return the Dreame model identifier."""
        return self._model

    @property
    def is_h15_pro_heat(self) -> bool:
        """Return whether this coordinator is for the H15 Pro Heat profile."""
        return self._is_h15

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

    def _handle_mqtt_update(self, state: dict[tuple[int, int], Any]) -> None:
        """Receive an MQTT update from the MQTT thread."""
        self.hass.loop.call_soon_threadsafe(self._apply_mqtt_state, dict(state))

    @callback
    def _apply_mqtt_state(self, state: dict[tuple[int, int], Any]) -> None:
        """Apply MQTT properties on the Home Assistant event loop."""
        new_keys = set(state) - set(self.props)
        self.props.update(state)

        if self._is_h15 and new_keys:
            for siid, piid in sorted(new_keys):
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

    def _build_data(self) -> dict[str, Any]:
        """Flatten properties for Home Assistant entities."""
        data: dict[str, Any] = {
            f"{siid}.{piid}": value
            for (siid, piid), value in self.props.items()
        }

        # H14 status labels are not applied to H15 until its status enum is
        # independently validated.
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
        """Read status properties in bounded chunks."""
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

    async def _async_discover_h15_properties(self) -> None:
        """Discover every cloud-cached property exposed by the H15 profile."""
        if self._h15_discovery_done:
            return

        keys = [
            f"{siid}.{piid}"
            for siid in _H15_SIID_RANGE
            for piid in _H15_PIID_RANGE
        ]
        values = await self._get_status_props_chunked(keys)

        discovered: list[str] = []
        for key, value in values.items():
            if value is None:
                continue
            try:
                siid_text, piid_text = key.split(".", 1)
                pair = (int(siid_text), int(piid_text))
            except (TypeError, ValueError):
                continue
            self.props[pair] = value
            discovered.append(key)

        self._h15_poll_keys = sorted(set(discovered), key=self._property_sort_key)
        self._h15_discovery_done = True

        _LOGGER.info(
            "H15 Pro Heat profile discovered %d properties for model=%s",
            len(self._h15_poll_keys),
            self._model,
        )

    async def _async_poll_h15_properties(self) -> None:
        """Refresh all properties discovered for the H15."""
        if not self._h15_discovery_done:
            await self._async_discover_h15_properties()
            return

        if not self._h15_poll_keys:
            return

        values = await self._get_status_props_chunked(self._h15_poll_keys)
        for key, value in values.items():
            if value is None:
                continue
            try:
                siid_text, piid_text = key.split(".", 1)
                self.props[(int(siid_text), int(piid_text))] = value
            except (TypeError, ValueError):
                continue

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
