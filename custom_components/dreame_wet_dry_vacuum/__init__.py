"""Dreame wet & dry vacuum integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DreameAPI, DreameAPIError, DreameAuthError
from .const import (
    CONF_COUNTRY,
    CONF_DEVICE_ID,
    CONF_REGION,
    CONSUMABLE_SENSORS,
    H15_ALERT_BINARY_SENSORS,
    H15_CONTROL_KEYS,
    H15_PRIMARY_ALERT_KEYS,
    H15_PRIMARY_SELECT_KEYS,
    H15_SELECT_SETTINGS,
    h15_sensor_is_optional,
)
from .coordinator import DreameWetDryCoordinator

_LOGGER = logging.getLogger(__name__)

_H15_ENTITY_SCHEMA_KEY = "_h15_entity_schema"
_H15_ENTITY_SCHEMA_VERSION = 2
_H15_CONTROLS_SCHEMA_KEY = "_h15_controls_schema"
_VACUUM_ENTITY_SCHEMA_KEY = "_vacuum_entity_removed"
_H15_UNREPORTED_KEY = "_h15_unreported_disabled"
# Live reads answered while the unit is awake before a missing property counts as unsupported.
H15_AWAKE_READS_TO_DECIDE = 3

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.BUTTON,
]

type DreameWetDryConfigEntry = ConfigEntry[DreameWetDryCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DreameWetDryConfigEntry) -> bool:
    """Set up Dreame wet & dry vacuum from a config entry."""
    country = str(
        entry.data.get(CONF_COUNTRY) or hass.config.country or ""
    ).upper()
    if len(country) != 2:
        raise ConfigEntryNotReady(
            "Dreame account country is missing; reconfigure the integration and select a country"
        )

    # Migrate legacy entries without silently forcing a specific country.
    if entry.data.get(CONF_COUNTRY) != country or CONF_REGION not in entry.data:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_COUNTRY: country,
                CONF_REGION: entry.data.get(CONF_REGION, "auto"),
            },
        )

    api = DreameAPI(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        region=entry.data.get(CONF_REGION, "auto"),
        country=country,
        session=async_get_clientsession(hass),
    )

    try:
        await api.login()
        devices = await api.get_devices()
    except DreameAuthError as err:
        raise ConfigEntryAuthFailed(f"Dreame credentials rejected: {err}") from err
    except DreameAPIError as err:
        raise ConfigEntryNotReady(f"Cannot connect to Dreame cloud: {err}") from err

    device_id = entry.data[CONF_DEVICE_ID]
    device_info = next((d for d in devices if str(d.get("did")) == str(device_id)), {})
    if not device_info.get("model"):
        try:
            device_info = await api.get_device_record(device_id, devices)
        except DreameAuthError as err:
            raise ConfigEntryAuthFailed(f"Dreame credentials rejected: {err}") from err
        except DreameAPIError as err:
            raise ConfigEntryNotReady(f"Cannot resolve saved Dreame device: {err}") from err

    coordinator = DreameWetDryCoordinator(hass, entry, api, device_id, device_info)

    # Raises ConfigEntryNotReady / ConfigEntryAuthFailed on failure
    await coordinator.async_config_entry_first_refresh()

    # The native vacuum entity duplicated the dedicated controls and looked
    # inconsistent with the device UI. Remove only the old entity created by
    # this integration, for both H14 and H15; preserve every other entity.
    if not entry.data.get(_VACUUM_ENTITY_SCHEMA_KEY):
        registry = er.async_get(hass)
        vacuum_unique_id = f"{coordinator.device_id}_vacuum"
        for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            if entity_entry.domain == "vacuum" and entity_entry.unique_id == vacuum_unique_id:
                registry.async_remove(entity_entry.entity_id)
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, _VACUUM_ENTITY_SCHEMA_KEY: 1}
        )

    # One-time cleanup when an existing H15 entry moves from the inherited H14
    # entity layout to the model-specific H15 profile. This removes stale
    # restored H14 sensors/controls so only entities from the H15 profile are
    # recreated below. The schema flag prevents repeated deletion on restarts.
    if (
        coordinator.is_h15_pro_heat
        and entry.data.get(_H15_ENTITY_SCHEMA_KEY, 0) < _H15_ENTITY_SCHEMA_VERSION
    ):
        registry = er.async_get(hass)
        stale_entries = er.async_entries_for_config_entry(registry, entry.entry_id)
        for stale_entry in stale_entries:
            registry.async_remove(stale_entry.entity_id)

        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                _H15_ENTITY_SCHEMA_KEY: _H15_ENTITY_SCHEMA_VERSION,
            },
        )
        _LOGGER.info(
            "Migrated H15 Pro Heat entity registry to schema version %d",
            _H15_ENTITY_SCHEMA_VERSION,
        )

    # Move only superseded H15 setting sensors into disabled diagnostics.
    # Leave H14 entries and every other H15 sensor/unique ID untouched.
    if coordinator.is_h15_pro_heat and not entry.data.get(_H15_CONTROLS_SCHEMA_KEY):
        registry = er.async_get(hass)
        superseded = {
            f"{coordinator.device_id}_h15_property_{siid}_{piid}"
            for siid, piid in H15_CONTROL_KEYS
        }
        for sensor_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            if (
                sensor_entry.domain == "sensor"
                and sensor_entry.unique_id in superseded
                and sensor_entry.disabled_by is None
            ):
                registry.async_update_entity(
                    sensor_entry.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
                )
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, _H15_CONTROLS_SCHEMA_KEY: 1}
        )

    # Upgrade previous control layouts without disabling diagnostics the user
    # deliberately re-enabled after their first migration.
    if coordinator.is_h15_pro_heat and entry.data.get(_H15_CONTROLS_SCHEMA_KEY, 0) < 2:
        registry = er.async_get(hass)
        mode_ids = {f"{coordinator.device_id}_h15_property_1_{piid}" for piid in (75, 81, 82, 83)}
        for sensor_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            if sensor_entry.domain == "sensor" and sensor_entry.unique_id in mode_ids and sensor_entry.disabled_by is None:
                registry.async_update_entity(sensor_entry.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
        hass.config_entries.async_update_entry(entry, data={**entry.data, _H15_CONTROLS_SCHEMA_KEY: 2})

    # One-time presentation cleanup. Never delete entities or alter their IDs.
    # Later user re-enabling of optional diagnostics is respected.
    if coordinator.is_h15_pro_heat and not entry.data.get("_h15_layout_schema"):
        registry = er.async_get(hass)
        prefix = f"{coordinator.device_id}_h15_property_"
        for sensor_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            optional = sensor_entry.unique_id == f"{coordinator.device_id}_h15_mapping_changes"
            if sensor_entry.unique_id.startswith(prefix):
                parts = sensor_entry.unique_id[len(prefix):].split("_")
                if len(parts) == 2 and all(part.isdigit() for part in parts):
                    key = (int(parts[0]), int(parts[1]))
                    optional = h15_sensor_is_optional(key) or coordinator.props.get(key) == -1
            if sensor_entry.domain == "sensor" and optional and sensor_entry.disabled_by is None:
                registry.async_update_entity(
                    sensor_entry.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
                )
        hass.config_entries.async_update_entry(entry, data={**entry.data, "_h15_layout_schema": 1})

    if coordinator.is_h15_pro_heat and entry.data.get("_h15_layout_schema", 0) < 2:
        registry = er.async_get(hass)
        redundant = {
            *(f"{coordinator.device_id}_h15_setting_{s}_{p}" for s, p in set(H15_SELECT_SETTINGS) - H15_PRIMARY_SELECT_KEYS),
            *(f"{coordinator.device_id}_{meta['key']}" for meta in H15_ALERT_BINARY_SENSORS if meta["key"] not in H15_PRIMARY_ALERT_KEYS),
        }
        prefix = f"{coordinator.device_id}_h15_property_"
        for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            optional = entity_entry.unique_id in redundant
            if entity_entry.unique_id.startswith(prefix):
                parts = entity_entry.unique_id[len(prefix):].split("_")
                if len(parts) == 2 and all(part.isdigit() for part in parts):
                    optional = h15_sensor_is_optional((int(parts[0]), int(parts[1])))
            if optional and entity_entry.disabled_by is None:
                registry.async_update_entity(entity_entry.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
        hass.config_entries.async_update_entry(entry, data={**entry.data, "_h15_layout_schema": 2})

    if coordinator.is_h15_pro_heat:
        _sync_h15_unreported(hass, entry, coordinator)
        state = [None]

        @callback
        def _on_update() -> None:
            seen = (coordinator.h15_awake_reads, len(coordinator.props))
            if seen != state[0]:
                state[0] = seen
                _sync_h15_unreported(hass, entry, coordinator)

        entry.async_on_unload(coordinator.async_add_listener(_on_update))

    entry.runtime_data = coordinator
    coordinator.start_polling()

    # Start the real-time MQTT feed. start() builds an SSL context (blocking
    # disk I/O), so keep it off the event loop.
    await hass.async_add_executor_job(coordinator.start_mqtt)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _h15_unreported(coordinator: DreameWetDryCoordinator, unique_id: str) -> bool | None:
    """Return whether the unit lacks the property behind this entity (None: not applicable)."""
    setting_prefix = f"{coordinator.device_id}_h15_setting_"
    if unique_id.startswith(setting_prefix):
        siid, piid = unique_id[len(setting_prefix):].split("_")[:2]
        return not coordinator.reports((int(siid), int(piid)))
    for meta in CONSUMABLE_SENSORS:
        if unique_id == f"{coordinator.device_id}_consumable_{meta['key']}_percent":
            return not coordinator.reports(meta["max"])
    return None


def _sync_h15_unreported(
    hass: HomeAssistant, entry: DreameWetDryConfigEntry, coordinator: DreameWetDryCoordinator
) -> None:
    """Disable H15 entities for properties the unit does not report, reversibly.

    A sleeping H15 reports nothing, which looks like "unsupported", so a property
    only counts as unsupported after several live reads answered while the unit
    was awake. The entities are disabled, never removed, so a wrong guess keeps
    their customizations; the ones disabled here are enabled again as soon as the
    unit reports the property. A user's own choice is never touched.
    """
    registry = er.async_get(hass)
    ours = set(entry.data.get(_H15_UNREPORTED_KEY, []))
    decided = coordinator.h15_awake_reads >= H15_AWAKE_READS_TO_DECIDE
    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        unique_id = entity_entry.unique_id
        unreported = _h15_unreported(coordinator, unique_id)
        if unreported is None:
            continue
        if not unreported and unique_id in ours:
            ours.discard(unique_id)
            if entity_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION:
                registry.async_update_entity(entity_entry.entity_id, disabled_by=None)
        elif unreported and decided and entity_entry.disabled_by is None:
            ours.add(unique_id)
            registry.async_update_entity(entity_entry.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
    if ours != set(entry.data.get(_H15_UNREPORTED_KEY, [])):
        hass.config_entries.async_update_entry(entry, data={**entry.data, _H15_UNREPORTED_KEY: sorted(ours)})


async def async_unload_entry(hass: HomeAssistant, entry: DreameWetDryConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator = entry.runtime_data
        coordinator.stop_polling()
        if coordinator.mqtt:
            await hass.async_add_executor_job(coordinator.mqtt.stop)
    return unloaded
