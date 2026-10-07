"""Read-only H15 Dreamehome app metadata exporter."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DreameAPIError
from .profiles import H15_PRO_HEAT_MODEL

_LOGGER = logging.getLogger(__name__)

_MAX_DOWNLOAD_BYTES = 150 * 1024 * 1024

_SENSITIVE_KEYS = {
    "access_token",
    "authorization",
    "binddomain",
    "deviceid",
    "did",
    "email",
    "mac",
    "password",
    "serial",
    "serialnumber",
    "sn",
    "ssid",
    "token",
    "uid",
    "username",
}


def _redact_for_sharing(value: Any) -> Any:
    """Redact account/device identifiers while keeping mapping metadata."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).replace("_", "").replace("-", "").lower()
            if normalized in _SENSITIVE_KEYS:
                out[key] = "<redacted>"
            elif normalized in {"url", "respackageurl"} and isinstance(item, str):
                # Preserve host/path so the source can be identified without
                # exposing a signed query string.
                parts = urlsplit(item)
                out[key] = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
            else:
                out[key] = _redact_for_sharing(item)
        return out
    if isinstance(value, list):
        return [_redact_for_sharing(item) for item in value]
    return value


async def _download(
    coordinator,
    url: str,
    destination: Path,
) -> dict[str, Any]:
    """Download a Dreame-provided plugin resource to a fixed local path."""
    if not url.lower().startswith("https://"):
        return {"ok": False, "error": "Refusing non-HTTPS download URL"}

    session = async_get_clientsession(coordinator.hass)
    timeout = aiohttp.ClientTimeout(total=120)

    try:
        async with session.get(url, timeout=timeout) as response:
            if response.status != 200:
                return {
                    "ok": False,
                    "status": response.status,
                    "error": (await response.text())[:300],
                }

            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > _MAX_DOWNLOAD_BYTES:
                        return {
                            "ok": False,
                            "error": "Plugin resource exceeds 150 MiB safety limit",
                        }
                except ValueError:
                    pass

            data = await response.read()
            if len(data) > _MAX_DOWNLOAD_BYTES:
                return {
                    "ok": False,
                    "error": "Plugin resource exceeds 150 MiB safety limit",
                }

    except (aiohttp.ClientError, TimeoutError) as err:
        return {"ok": False, "error": str(err)}

    await coordinator.hass.async_add_executor_job(destination.write_bytes, data)
    return {
        "ok": True,
        "path": str(destination),
        "bytes": len(data),
    }


async def async_export_h15_app_probe(coordinator) -> dict[str, Any]:
    """Collect Dreamehome app metadata and download the H15 model plugin.

    All cloud operations are read-only. No property/action write is performed.
    """
    model = str(coordinator.device_info_raw.get("model") or coordinator.model or "")
    if model.lower() != H15_PRO_HEAT_MODEL:
        raise ValueError(f"H15 app probe only supports {H15_PRO_HEAT_MODEL}, got {model}")

    api = coordinator.api
    did = coordinator.device_id

    probe: dict[str, Any] = {
        "model": model,
        "properties": {
            f"{siid}.{piid}": value
            for (siid, piid), value in sorted(coordinator.props.items())
        },
    }

    async def capture(name: str, awaitable) -> None:
        try:
            probe[name] = await awaitable
        except DreameAPIError as err:
            probe[name] = {"_error": str(err)}
        except Exception as err:  # diagnostic exporter must not break HA
            probe[name] = {"_error": f"{type(err).__name__}: {err}"}

    await capture("device_info", api.get_device_info_full(did))
    await capture("dev_otc_info", api.get_dev_otc_info(did))
    await capture("device_data", api.get_device_data_probe(did))
    await capture("app_plugin", api.get_app_plugin_info(model))

    output_dir = Path(coordinator.hass.config.path("dreame_h15_probe"))
    await coordinator.hass.async_add_executor_job(
        output_dir.mkdir, parents=True, exist_ok=True
    )

    private_json = output_dir / "metadata_private.json"
    share_json = output_dir / "metadata_share.json"

    private_text = json.dumps(probe, ensure_ascii=False, indent=2, default=str)
    share_text = json.dumps(
        _redact_for_sharing(probe),
        ensure_ascii=False,
        indent=2,
        default=str,
    )

    await coordinator.hass.async_add_executor_job(
        private_json.write_text, private_text, "utf-8"
    )
    await coordinator.hass.async_add_executor_job(
        share_json.write_text, share_text, "utf-8"
    )

    downloads: dict[str, Any] = {}
    plugin_section = probe.get("app_plugin")
    selected = (
        plugin_section.get("selected")
        if isinstance(plugin_section, dict)
        else None
    )
    plugin_data = selected.get("data") if isinstance(selected, dict) else None

    if isinstance(plugin_data, dict):
        plugin_url = plugin_data.get("url")
        if isinstance(plugin_url, str) and plugin_url:
            downloads["appplugin"] = await _download(
                coordinator,
                plugin_url,
                output_dir / "appplugin.zip",
            )

        resource_url = plugin_data.get("resPackageUrl")
        if isinstance(resource_url, str) and resource_url:
            downloads["resources"] = await _download(
                coordinator,
                resource_url,
                output_dir / "resources.zip",
            )

    result = {
        "output_dir": str(output_dir),
        "share_metadata": str(share_json),
        "private_metadata": str(private_json),
        "downloads": downloads,
    }

    _LOGGER.warning(
        "H15 app metadata probe completed. Output: %s",
        result,
    )
    return result
