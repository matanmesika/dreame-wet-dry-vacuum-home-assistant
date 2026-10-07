"""Dreame Home cloud API client."""
from __future__ import annotations

import hashlib
import json
import logging
import random
import string
import time
from typing import Any

import aiohttp
from Crypto.Cipher import AES

from .const import (
    DREAME_BASIC_AUTH,
    DREAME_IOT_PREFIX,
    DREAME_PASSWORD_SALT,
    DREAME_RLC_KEY,
    DREAME_TENANT_ID,
    ENDPOINTS,
    EU_BASE_URL,
    CN_BASE_URL,
)

_LOGGER = logging.getLogger(__name__)

REGION_URLS = {
    "eu": EU_BASE_URL,
    "de": "https://de.iot.dreame.tech:13267",
    "cn": CN_BASE_URL,
    "us": "https://us.iot.dreame.tech:13267",
    "ru": "https://ru.iot.dreame.tech:13267",
    "tw": "https://tw.iot.dreame.tech:13267",
    "sg": "https://sg.iot.dreame.tech:13267",
    "in": "https://in.iot.dreame.tech:13267",
    "i2": "https://i2.iot.dreame.tech:13267",
    "kr": "https://kr.iot.dreame.tech:13267",
}

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)

# Safe bootstrap choices for automatic discovery. The account country is an ISO
# country code and is deliberately separate from the Dreame cloud backend.
COUNTRY_BOOTSTRAP_REGION = {
    "CN": "cn",
    "US": "us",
    "RU": "ru",
    "TW": "tw",
    "SG": "sg",
    "IN": "in",
    "KR": "kr",
}

AUTO_REGION_ORDER = ("eu", "i2", "de", "sg", "us", "in", "tw", "kr", "ru", "cn")


def _md5_password(password: str) -> str:
    return hashlib.md5((password + DREAME_PASSWORD_SALT).encode()).hexdigest()


def _parse_prop_value(value: Any) -> Any:
    """Parse an iotstatus value (returned as a string) to a native type.

    "0" -> 0, "[81]" -> [81], "abc" -> "abc". Keeps types consistent with the
    MQTT feed, which delivers ints/lists natively.
    """
    if not isinstance(value, str):
        return value
    s = value.strip()
    if s and (s[0] in "[-" or s.isdigit()):
        try:
            return json.loads(s)
        except (ValueError, TypeError):
            pass
    return value


def _compute_rlc(region: str = "eu", country: str = "DE") -> str:
    """Generate the dreame-rlc header value via AES-128-ECB."""
    plain = f"{region}|en|{country.upper()}"
    key = DREAME_RLC_KEY
    cipher = AES.new(key, AES.MODE_ECB)
    # Pad to 16-byte block
    pad_len = 16 - (len(plain) % 16)
    plain_padded = plain + chr(pad_len) * pad_len
    encrypted = cipher.encrypt(plain_padded.encode("utf-8"))
    return encrypted.hex()


def _random_request_id() -> str:
    return "".join(random.choices(string.digits, k=8))


class DreameAPIError(Exception):
    pass


class DreameAuthError(DreameAPIError):
    pass


class DreameAPI:
    """Client for the Dreame Home cloud API."""

    def __init__(
        self,
        username: str,
        password: str,
        region: str = "eu",
        country: str = "",
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._username = username
        self._password = password
        self._requested_region = region
        self._country = country.upper()
        if len(self._country) != 2:
            raise ValueError("Dreame account country must be a two-letter ISO country code")
        if region == "auto":
            self._region = COUNTRY_BOOTSTRAP_REGION.get(self._country, "eu")
        elif region in REGION_URLS:
            self._region = region
        else:
            raise ValueError(f"Unsupported Dreame cloud region: {region}")
        self._base_url = REGION_URLS[self._region]
        self._access_token: str | None = None
        self._uid: str | None = None
        self._session = session
        self._owns_session = session is None
        self._rlc = _compute_rlc(self._region, self._country)

    def _set_region(self, region: str) -> None:
        """Switch to a known Dreame cloud backend without re-authenticating."""
        if region not in REGION_URLS:
            return
        self._region = region
        self._base_url = REGION_URLS[region]
        self._rlc = _compute_rlc(region, self._country)

    def _set_domain(self, domain: str) -> None:
        """Use a Dreame-provided API domain when it is safe to trust."""
        host = domain.removeprefix("https://").removeprefix("http://").split("/", 1)[0]
        host = host.split(":", 1)[0]
        if not host.endswith(".dreame.tech"):
            _LOGGER.warning("Ignoring unexpected Dreame login domain: %s", domain)
            return
        self._base_url = f"https://{host}:13267"
        prefix = host.split(".", 1)[0]
        if prefix in REGION_URLS:
            self._region = prefix
            self._rlc = _compute_rlc(prefix, self._country)

    @property
    def uid(self) -> str | None:
        """Account uid, available after login()."""
        return self._uid

    @property
    def access_token(self) -> str | None:
        """Current access token, available after login()."""
        return self._access_token

    def _get_base_headers(self) -> dict[str, str]:
        return {
            "user-agent": "Dart/3.2 (dart:io)",
            "dreame-meta": "cv=i_829",
            "dreame-rlc": self._rlc,
            "tenant-id": DREAME_TENANT_ID,
        }

    def _get_auth_headers(self) -> dict[str, str]:
        headers = self._get_base_headers()
        headers["dreame-auth"] = f"bearer {self._access_token}"
        headers["content-type"] = "application/json"
        return headers

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        # Only close a session we created ourselves, never a shared one.
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def login(self) -> None:
        """Authenticate and store access token."""
        session = await self._get_session()
        url = self._base_url + ENDPOINTS["token"]

        headers = self._get_base_headers()
        headers["authorization"] = DREAME_BASIC_AUTH
        headers["content-type"] = "application/x-www-form-urlencoded"

        data = {
            "grant_type": "password",
            "scope": "all",
            "platform": "IOS",
            "type": "account",
            "username": self._username,
            "password": _md5_password(self._password),
            "country": self._country,
            "lang": "en",
        }

        try:
            async with session.post(
                url, headers=headers, data=data, timeout=REQUEST_TIMEOUT
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise DreameAuthError(f"Login failed ({resp.status}): {text[:200]}")
                result = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise DreameAPIError(f"Login request failed: {err}") from err

        if "access_token" not in result:
            raise DreameAuthError(f"No access_token in response: {result}")

        self._access_token = result["access_token"]
        self._uid = result.get("uid")

        # Dreame may tell us the account's actual backend in the login response.
        # Prefer that metadata over guessing from the user's physical country.
        response_region = str(result.get("region") or "").lower()
        response_domain = str(result.get("domain") or "").strip().lower()
        if self._requested_region == "auto":
            if response_region in REGION_URLS:
                self._set_region(response_region)
            elif response_domain:
                self._set_domain(response_domain)

        _LOGGER.debug(
            "Dreame login successful, uid=%s requested_region=%s active_region=%s country=%s",
            self._uid,
            self._requested_region,
            self._region,
            self._country,
        )

    async def _authed_post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST with bearer auth; re-login and retry exactly once on 401.

        Raises DreameAuthError if the re-login itself is rejected (bad
        credentials), DreameAPIError for transport/protocol failures.
        """
        await self._ensure_logged_in()
        session = await self._get_session()
        for attempt in (1, 2):
            try:
                async with session.post(
                    url,
                    headers=self._get_auth_headers(),
                    json=payload,
                    timeout=REQUEST_TIMEOUT,
                ) as resp:
                    if resp.status == 401 and attempt == 1:
                        await self.login()
                        continue
                    if resp.status != 200:
                        text = await resp.text()
                        raise DreameAPIError(
                            f"Request failed ({resp.status}): {text[:200]}"
                        )
                    return await resp.json(content_type=None)
            except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                raise DreameAPIError(f"Request failed: {err}") from err
        raise DreameAPIError("Still unauthorized after re-login")

    async def _authed_get(
        self, url: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """GET with the existing Dreame bearer session."""
        await self._ensure_logged_in()
        session = await self._get_session()
        for attempt in (1, 2):
            try:
                async with session.get(
                    url,
                    headers=self._get_auth_headers(),
                    params=params or {},
                    timeout=REQUEST_TIMEOUT,
                ) as resp:
                    if resp.status == 401 and attempt == 1:
                        await self.login()
                        continue
                    if resp.status != 200:
                        body = await resp.text()
                        raise DreameAPIError(
                            f"GET failed ({resp.status}): {body[:200]}"
                        )
                    return await resp.json(content_type=None)
            except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                raise DreameAPIError(f"GET request failed: {err}") from err
        raise DreameAPIError("Still unauthorized after re-login")

    async def get_device_info_full(self, device_id: str) -> dict[str, Any]:
        """Return Dreame's full device/info payload for diagnostics."""
        return await self._authed_post(
            self._base_url + "/dreame-user-iot/iotuserbind/device/info",
            {"did": str(device_id)},
        )

    async def get_dev_otc_info(self, device_id: str) -> dict[str, Any]:
        """Return the app-facing devOTCInfo payload."""
        return await self._authed_post(
            self._base_url + "/dreame-user-iot/iotstatus/devOTCInfo",
            {"did": str(device_id)},
        )

    async def get_device_data_probe(self, device_id: str) -> dict[str, Any]:
        """Probe the app's device-data endpoint using the two known request forms."""
        url = self._base_url + "/dreame-user-iot/iotuserdata/getDeviceData"
        result: dict[str, Any] = {}
        for name, payload in (
            ("keys_empty", {"did": str(device_id), "keys": []}),
            ("model_empty", {"did": str(device_id), "model": []}),
        ):
            try:
                result[name] = await self._authed_post(url, payload)
            except DreameAPIError as err:
                result[name] = {"_error": str(err)}
        return result

    async def get_app_plugin_info(
        self,
        model: str,
        app_versions: tuple[int, ...] = (150, 148),
    ) -> dict[str, Any]:
        """Query the Dreamehome per-model RN plugin metadata.

        The Dreame app uses /dreame-product/upgrades/appplugin with the device
        model and an app/plugin compatibility version. This method is read-only
        and returns both attempts so we can see which version the backend accepts.
        """
        url = self._base_url + "/dreame-product/upgrades/appplugin"
        attempts: dict[str, Any] = {}
        for app_ver in app_versions:
            try:
                response = await self._authed_get(
                    url,
                    {
                        "model": model,
                        "appVer": app_ver,
                        "os": 1,
                    },
                )
                attempts[str(app_ver)] = response
                data = response.get("data") if isinstance(response, dict) else None
                if (
                    isinstance(data, dict)
                    and data.get("url")
                    and int(data.get("version") or 0) > 0
                ):
                    return {
                        "selected_app_version": app_ver,
                        "selected": response,
                        "attempts": attempts,
                    }
            except DreameAPIError as err:
                attempts[str(app_ver)] = {"_error": str(err)}
        return {
            "selected_app_version": None,
            "selected": None,
            "attempts": attempts,
        }

    @staticmethod
    def _extract_device_records(result: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract device records from known Dreame device-list response shapes."""
        data = result.get("data") or {}
        records = (data.get("page") or {}).get("records") or []
        if not records:
            records = data.get("records") or []
        return records

    async def _get_devices_from_url(
        self, base_url: str, *, relogin_on_401: bool
    ) -> list[dict[str, Any]]:
        payload = {
            "sharedStatus": 1,
            "current": 1,
            "size": 100,
            "lang": "en",
            "timestamp": int(time.time() * 1000),
        }
        url = base_url + ENDPOINTS["device_list"]
        if relogin_on_401:
            result = await self._authed_post(url, payload)
            return self._extract_device_records(result)

        # Auto-discovery reuses the already-issued bearer token. It must not
        # retry the user's password against every backend.
        session = await self._get_session()
        try:
            async with session.post(
                url,
                headers=self._get_auth_headers(),
                json=payload,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status != 200:
                    return []
                result = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return []
        return self._extract_device_records(result)

    async def get_devices(self) -> list[dict[str, Any]]:
        """Return devices and auto-detect the correct cloud backend when requested."""
        records = await self._get_devices_from_url(
            self._base_url, relogin_on_401=True
        )

        if not records and self._requested_region == "auto":
            tried = {self._region}
            for region in AUTO_REGION_ORDER:
                if region in tried:
                    continue
                tried.add(region)
                candidate_records = await self._get_devices_from_url(
                    REGION_URLS[region], relogin_on_401=False
                )
                if candidate_records:
                    self._set_region(region)
                    records = candidate_records
                    _LOGGER.info(
                        "Dreame cloud auto-discovery selected region=%s for country=%s",
                        region,
                        self._country,
                    )
                    break

        if records:
            _LOGGER.debug(
                "Dreame device discovery returned %d device(s) for region=%s country=%s; models=%s",
                len(records),
                self._region,
                self._country,
                [record.get("model", "unknown") for record in records],
            )
        else:
            _LOGGER.warning(
                "Dreame device discovery returned no devices for requested_region=%s "
                "active_region=%s country=%s",
                self._requested_region,
                self._region,
                self._country,
            )
        return records

    async def get_device_snapshot(self, device_id: str) -> dict[str, Any]:
        """
        Return the cloud-cached state for a device (battery, status, online).
        This always works, even when the vacuum is docked/asleep, because it
        reads the last state the device reported to the cloud.
        """
        devices = await self.get_devices()
        for d in devices:
            if str(d.get("did")) == str(device_id):
                return {
                    "battery": d.get("battery"),
                    "status": d.get("latestStatus"),
                    "online": d.get("online"),
                    "model": d.get("model"),
                    "name": d.get("deviceInfo", {}).get("displayName")
                    or d.get("customName")
                    or d.get("model"),
                    "firmware": d.get("ver"),
                    "mac": d.get("mac"),
                }
        return {}

    async def get_status_props(
        self, device_id: str, keys: list[str]
    ) -> dict[str, Any]:
        """
        Read cloud-cached property values by key ("siid.piid").
        Uses /dreame-user-iot/iotstatus/props, which works on this model (unlike
        the realtime get_properties RPC that returns null). Returns {key: value}
        with values parsed to native types (int / list), keys never reported are
        simply absent.
        """
        # The endpoint expects keys as a single comma-separated string.
        payload = {"did": device_id, "keys": ",".join(keys)}
        result = await self._authed_post(
            self._base_url + ENDPOINTS["status_props"], payload
        )

        out: dict[str, Any] = {}
        for item in result.get("data") or []:
            key = item.get("key")
            if key is None or "value" not in item:
                continue
            out[key] = _parse_prop_value(item["value"])
        return out

    async def get_properties(
        self, device_id: str, props: list[dict[str, int]]
    ) -> list[dict[str, Any]]:
        """
        Fetch device properties.
        props: list of {siid, piid} dicts
        Returns list of {siid, piid, value, code} dicts.
        """
        url = self._base_url + ENDPOINTS["send_command"].format(prefix=DREAME_IOT_PREFIX)

        req_id = _random_request_id()
        params = [
            {"siid": p["siid"], "piid": p["piid"], "code": 0, "updateTime": 0}
            for p in props
        ]

        payload = {
            "did": device_id,
            "id": req_id,
            "data": {
                "did": device_id,
                "id": req_id,
                "method": "get_properties",
                "params": params,
                "from": "100000",
            },
        }

        result = await self._authed_post(url, payload)
        return result.get("data", {}).get("result", [])

    async def set_property(
        self, device_id: str, siid: int, piid: int, value: Any
    ) -> bool:
        """Set a single device property."""
        url = self._base_url + ENDPOINTS["send_command"].format(prefix=DREAME_IOT_PREFIX)

        req_id = _random_request_id()
        payload = {
            "did": device_id,
            "id": req_id,
            "data": {
                "did": device_id,
                "id": req_id,
                "method": "set_properties",
                "params": [{"siid": siid, "piid": piid, "value": value}],
                "from": "100000",
            },
        }

        result = await self._authed_post(url, payload)
        results = result.get("data", {}).get("result", [])
        return all(r.get("code", -1) == 0 for r in results)

    async def call_action(
        self, device_id: str, siid: int, aiid: int, params: list | None = None
    ) -> bool:
        """Call a device action."""
        url = self._base_url + ENDPOINTS["send_command"].format(prefix=DREAME_IOT_PREFIX)

        req_id = _random_request_id()
        payload = {
            "did": device_id,
            "id": req_id,
            "data": {
                "did": device_id,
                "id": req_id,
                "method": "action",
                "params": {
                    "siid": siid,
                    "aiid": aiid,
                    "did": device_id,
                    "in": params or [],
                },
                "from": "100000",
            },
        }

        result = await self._authed_post(url, payload)
        return result.get("data", {}).get("code", -1) == 0

    async def discover_properties(
        self,
        device_id: str,
        siid_range: range = range(1, 31),
        piid_range: range = range(1, 81),
    ) -> dict[tuple[int, int], Any]:
        """
        Probe SIID/PIID combinations and return properties with valid responses.

        The default range intentionally covers the higher service/property IDs
        already used by Dreame wet & dry vacuums, making it suitable for new
        model discovery such as H15 without assuming H14-only ranges.
        """
        all_props = [
            {"siid": s, "piid": p} for s in siid_range for p in piid_range
        ]
        # Chunk into groups of 50
        results: dict[tuple[int, int], Any] = {}
        chunk_size = 50
        for i in range(0, len(all_props), chunk_size):
            chunk = all_props[i : i + chunk_size]
            try:
                data = await self.get_properties(device_id, chunk)
                for item in data:
                    if item.get("code", -1) == 0:
                        key = (item["siid"], item["piid"])
                        results[key] = item.get("value")
            except DreameAPIError as err:
                _LOGGER.warning("Discovery chunk failed: %s", err)
        return results

    async def _ensure_logged_in(self) -> None:
        if self._access_token is None:
            await self.login()
