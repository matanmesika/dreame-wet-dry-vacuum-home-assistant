"""Dreame wet & dry vacuum integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DreameAPI, DreameAPIError, DreameAuthError
from .const import CONF_COUNTRY, CONF_DEVICE_ID, CONF_REGION
from .coordinator import DreameWetDryCoordinator

_LOGGER = logging.getLogger(__name__)

_H15_ENTITY_SCHEMA_KEY = "_h15_entity_schema"
_H15_ENTITY_SCHEMA_VERSION = 2

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

    coordinator = DreameWetDryCoordinator(hass, entry, api, device_id, device_info)

    # Raises ConfigEntryNotReady / ConfigEntryAuthFailed on failure
    await coordinator.async_config_entry_first_refresh()

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

    entry.runtime_data = coordinator
    coordinator.start_polling()

    # Start the real-time MQTT feed. start() builds an SSL context (blocking
    # disk I/O), so keep it off the event loop.
    await hass.async_add_executor_job(coordinator.start_mqtt)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DreameWetDryConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator = entry.runtime_data
        coordinator.stop_polling()
        if coordinator.mqtt:
            await hass.async_add_executor_job(coordinator.mqtt.stop)
    return unloaded
