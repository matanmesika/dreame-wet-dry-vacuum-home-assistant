"""Read-only H15 Dreamehome app metadata exporter."""
from __future__ import annotations

import json
import logging
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DreameAPIError
from .profiles import H15_PRO_HEAT_MODEL, H15_PROPERTY_META, H15_TARGETED_KEYS

_LOGGER = logging.getLogger(__name__)

_MAX_DOWNLOAD_BYTES = 150 * 1024 * 1024

_SENSITIVE_KEYS = {
    "accesstoken",
    "refreshtoken",
    "authorization",
    "binddomain",
    "deviceid",
    "did",
    "email",
    "mac",
    "masteruid",
    "masteruid2uuid",
    "password",
    "serial",
    "serialnumber",
    "sn",
    "ssid",
    "token",
    "uid",
    "uuid",
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

    # Dreame sometimes nests device metadata as JSON serialized inside a
    # string. Sanitize that payload too so metadata_share.json stays safe.
    if isinstance(value, str):
        stripped = value.strip()
        if (
            len(stripped) >= 2
            and stripped[0] in "[{"
            and stripped[-1] in "]}"
        ):
            try:
                decoded = json.loads(stripped)
            except (TypeError, ValueError, json.JSONDecodeError):
                decoded = None
            if isinstance(decoded, (dict, list)):
                return json.dumps(
                    _redact_for_sharing(decoded),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )

        # Last-resort redaction for MAC addresses embedded in opaque strings.
        return re.sub(
            r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])",
            "<redacted-mac>",
            value,
        )

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



_TEXT_EXTENSIONS = {
    ".js", ".json", ".txt", ".xml", ".html", ".htm", ".css",
    ".map", ".plist", ".properties", ".yaml", ".yml",
}
_MAX_SCAN_FILE_BYTES = 8 * 1024 * 1024
_MAX_SCAN_TOTAL_BYTES = 40 * 1024 * 1024
_MAX_HITS_PER_FILE = 100

_H15_SEARCH_TERMS = (
    "siid",
    "piid",
    "get_properties",
    "set_properties",
    "action",
    "battery",
    "charging",
    "dock",
    "suction",
    "water",
    "detergent",
    "dirty",
    "tank",
    "drying",
    "self-clean",
    "self clean",
    "roller",
    "brush",
    "filter",
    "traction",
    "mode",
    "hot water",
    "temperature",
)


def _safe_snippet(text: str, start: int, end: int, radius: int = 120) -> str:
    """Return a compact printable context snippet."""
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    snippet = text[left:right].replace("\x00", " ")
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return snippet[:600]


def _inspect_archive_sync(path: Path) -> dict[str, Any]:
    """Inventory a downloaded plugin/archive without executing its contents."""
    result: dict[str, Any] = {
        "path": str(path),
        "is_zip": False,
        "files": [],
        "miot_pairs": [],
        "keyword_hits": [],
    }

    if not path.exists():
        result["error"] = "file does not exist"
        return result

    if not zipfile.is_zipfile(path):
        result["error"] = "download is not a ZIP archive"
        return result

    result["is_zip"] = True
    scanned_total = 0
    pair_seen: set[tuple[int, int, str]] = set()

    pair_patterns = (
        re.compile(
            r"""["']?siid["']?\s*[:=]\s*(\d+).{0,120}?["']?piid["']?\s*[:=]\s*(\d+)""",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"""["']?piid["']?\s*[:=]\s*(\d+).{0,120}?["']?siid["']?\s*[:=]\s*(\d+)""",
            re.IGNORECASE | re.DOTALL,
        ),
    )

    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        result["file_count"] = len(infos)
        result["uncompressed_bytes"] = sum(info.file_size for info in infos)

        for info in infos:
            if info.is_dir():
                continue

            result["files"].append(
                {
                    "name": info.filename,
                    "bytes": info.file_size,
                    "compressed_bytes": info.compress_size,
                }
            )

            suffix = Path(info.filename).suffix.lower()
            likely_text = (
                suffix in _TEXT_EXTENSIONS
                or "bundle" in info.filename.lower()
                or info.filename.lower().endswith("index")
            )
            if not likely_text:
                continue
            if info.file_size <= 0 or info.file_size > _MAX_SCAN_FILE_BYTES:
                continue
            if scanned_total + info.file_size > _MAX_SCAN_TOTAL_BYTES:
                break

            try:
                raw = archive.read(info)
            except (OSError, RuntimeError, zipfile.BadZipFile) as err:
                _LOGGER.debug("Could not inspect archive member %s: %s", info.filename, err)
                continue

            scanned_total += len(raw)
            text = raw.decode("utf-8", errors="ignore")
            if not text:
                continue

            # Extract likely MIoT pair definitions from JavaScript/config.
            for pattern_index, pattern in enumerate(pair_patterns):
                for match in pattern.finditer(text):
                    if pattern_index == 0:
                        siid, piid = int(match.group(1)), int(match.group(2))
                    else:
                        piid, siid = int(match.group(1)), int(match.group(2))

                    marker = (siid, piid, info.filename)
                    if marker in pair_seen:
                        continue
                    pair_seen.add(marker)

                    result["miot_pairs"].append(
                        {
                            "siid": siid,
                            "piid": piid,
                            "property": f"{siid}.{piid}",
                            "file": info.filename,
                            "context": _safe_snippet(
                                text, match.start(), match.end()
                            ),
                        }
                    )

            # Find semantic words near property definitions / UI strings.
            lower = text.lower()
            per_file_hits = 0
            for term in _H15_SEARCH_TERMS:
                start = 0
                while per_file_hits < _MAX_HITS_PER_FILE:
                    pos = lower.find(term, start)
                    if pos < 0:
                        break
                    result["keyword_hits"].append(
                        {
                            "term": term,
                            "file": info.filename,
                            "context": _safe_snippet(
                                text, pos, pos + len(term)
                            ),
                        }
                    )
                    per_file_hits += 1
                    start = pos + len(term)

    result["scanned_text_bytes"] = scanned_total
    result["miot_pairs"].sort(
        key=lambda item: (item["siid"], item["piid"], item["file"])
    )
    return result


async def _write_archive_report(coordinator, archive_path: Path) -> str | None:
    """Create a JSON inventory/search report for a downloaded package."""
    if not archive_path.exists():
        return None

    report = await coordinator.hass.async_add_executor_job(
        _inspect_archive_sync, archive_path
    )
    report_path = archive_path.with_name(
        f"{archive_path.stem}_inventory.json"
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    await coordinator.hass.async_add_executor_job(
        report_path.write_text, text, "utf-8"
    )
    return str(report_path)


async def async_export_h15_app_probe(coordinator) -> dict[str, Any]:
    """Collect Dreamehome app metadata and download the H15 model plugin.

    All cloud operations are read-only. No property/action write is performed.
    """
    model = str(coordinator.device_info_raw.get("model") or coordinator.model or "")
    if model.lower() != H15_PRO_HEAT_MODEL:
        raise ValueError(f"H15 app probe only supports {H15_PRO_HEAT_MODEL}, got {model}")

    api = coordinator.api
    did = coordinator.device_id

    # Refresh the expanded read-only H15 profile first so the exported
    # properties represent the newest cache/live values available.
    refresh: dict[str, Any] = {"ok": True}
    try:
        await coordinator.async_refresh_h15_mapping()
    except Exception as err:  # noqa: BLE001 -- diagnostic export preserves partial results
        refresh = {"ok": False, "error": f"{type(err).__name__}: {err}"}
        _LOGGER.debug("H15 pre-export refresh failed (non-fatal): %s", err)

    manifest = await coordinator.hass.async_add_executor_job(
        (Path(__file__).parent / "manifest.json").read_text, "utf-8"
    )

    probe: dict[str, Any] = {
        "model": model,
        "exported_at": datetime.now(UTC).isoformat(),
        "integration_version": json.loads(manifest)["version"],
        "mapping_refresh": refresh,
        "last_mapping_scan": (
            coordinator.h15_last_scan.isoformat()
            if coordinator.h15_last_scan is not None else None
        ),
        "mapping_changes": coordinator.h15_last_changes,
        "mapping_profile": {
            f"{siid}.{piid}": {
                **meta,
                "observed": (siid, piid) in coordinator.props,
            }
            for (siid, piid), meta in sorted(H15_PROPERTY_META.items())
        },
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
        except Exception as err:  # noqa: BLE001 -- report individual diagnostic failures
            probe[name] = {"_error": f"{type(err).__name__}: {err}"}

    await capture("device_info", api.get_device_info_full(did))
    await capture("dev_otc_info", api.get_dev_otc_info(did))
    await capture("device_data", api.get_device_data_probe(did))
    await capture("app_plugin", api.get_app_plugin_info(model))

    # Export the exact app-derived keys through both available read paths.
    targeted_key_strings = [f"{siid}.{piid}" for siid, piid in H15_TARGETED_KEYS]
    await capture(
        "targeted_status_props",
        coordinator._get_status_props_chunked(targeted_key_strings),
    )

    async def read_targeted_live() -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for start in range(0, len(H15_TARGETED_KEYS), 50):
            chunk = H15_TARGETED_KEYS[start : start + 50]
            rows.extend(await api.get_properties(
                did, [{"siid": siid, "piid": piid} for siid, piid in chunk]
            ))
        return rows

    await capture(
        "targeted_live_props",
        read_targeted_live(),
    )

    output_dir = Path(coordinator.hass.config.path("dreame_h15_probe"))
    await coordinator.hass.async_add_executor_job(
        output_dir.mkdir, 0o777, True, True
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

    inventories: dict[str, str] = {}

    appplugin_path = output_dir / "appplugin.zip"
    if (
        isinstance(downloads.get("appplugin"), dict)
        and downloads["appplugin"].get("ok")
    ):
        report = await _write_archive_report(coordinator, appplugin_path)
        if report:
            inventories["appplugin"] = report

    resources_path = output_dir / "resources.zip"
    if (
        isinstance(downloads.get("resources"), dict)
        and downloads["resources"].get("ok")
    ):
        report = await _write_archive_report(coordinator, resources_path)
        if report:
            inventories["resources"] = report

    result = {
        "output_dir": str(output_dir),
        "share_metadata": str(share_json),
        "private_metadata": str(private_json),
        "downloads": downloads,
        "inventories": inventories,
    }

    _LOGGER.warning(
        "H15 app metadata probe completed. Output: %s",
        result,
    )
    return result
