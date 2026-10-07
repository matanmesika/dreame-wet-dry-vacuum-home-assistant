"""Button platform for Dreame wet & dry vacuum."""
from __future__ import annotations

from homeassistant.components import persistent_notification
from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DreameWetDryConfigEntry
from .const import KNOWN_BUTTON_PROPS
from .entity import DreameWetDryEntity, build_device_info
from .h15_probe import async_export_h15_app_probe


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DreameWetDryConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    if coordinator.is_h15_pro_heat:
        # Safe diagnostic-only button: performs a read-only full property scan
        # and compares it with the previous H15 mapping snapshot.
        async_add_entities(
            [
                DreameH15RefreshMappingButton(coordinator),
                DreameH15ExportAppMetadataButton(coordinator),
            ]
        )
        return

    async_add_entities(
        DreameWetDryButton(coordinator, key, meta)
        for key, meta in KNOWN_BUTTON_PROPS.items()
    )


class DreameH15RefreshMappingButton(
    CoordinatorEntity,
    ButtonEntity,
):
    """Refresh the H15 raw-property mapping snapshot."""

    _attr_has_entity_name = True
    _attr_name = "Refresh mapping snapshot"
    _attr_icon = "mdi:compare-horizontal"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_h15_refresh_mapping"
        self._attr_device_info = build_device_info(coordinator)

    async def async_press(self) -> None:
        await self.coordinator.async_refresh_h15_mapping()


class DreameH15ExportAppMetadataButton(
    CoordinatorEntity,
    ButtonEntity,
):
    """Export read-only Dreamehome app metadata for H15 mapping."""

    _attr_has_entity_name = True
    _attr_name = "Export Dreame app metadata"
    _attr_icon = "mdi:cloud-download-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_h15_export_app_metadata"
        self._attr_device_info = build_device_info(coordinator)

    async def async_press(self) -> None:
        try:
            result = await async_export_h15_app_probe(self.coordinator)
        except Exception as err:
            persistent_notification.async_create(
                self.coordinator.hass,
                f"H15 app metadata probe failed: {type(err).__name__}: {err}",
                title="Dreame H15 metadata probe",
                notification_id="dreame_h15_probe",
            )
            raise

        downloads = result.get("downloads") or {}
        downloaded = [
            name
            for name, value in downloads.items()
            if isinstance(value, dict) and value.get("ok")
        ]
        downloaded_text = ", ".join(downloaded) if downloaded else "none"

        persistent_notification.async_create(
            self.coordinator.hass,
            (
                "Read-only H15 metadata export completed.\n\n"
                f"Folder: {result['output_dir']}\n"
                f"Safe-to-share metadata: {result['share_metadata']}\n"
                f"Downloaded plugin resources: {downloaded_text}\n\n"
                "Upload metadata_share.json for the latest values, mapping profile "
                "and scan differences. Add appplugin.zip and resources.zip "
                "only if those packages changed."
            ),
            title="Dreame H15 metadata probe",
            notification_id="dreame_h15_probe",
        )


class DreameWetDryButton(DreameWetDryEntity, ButtonEntity):
    """Send a fixed value to a property when pressed."""

    def __init__(self, coordinator, key, meta) -> None:
        super().__init__(coordinator, key, meta)
        self._press_value = meta.get("press_value", 1)

    async def async_press(self) -> None:
        await self._set(self._press_value)
