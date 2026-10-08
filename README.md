# Dreame Wet & Dry Vacuum for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://www.hacs.xyz/)
[![Validate](https://github.com/matanmesika/dreame-wet-dry-vacuum-home-assistant/actions/workflows/validate.yml/badge.svg?branch=feature%2Fh15-country-discovery)](https://github.com/matanmesika/dreame-wet-dry-vacuum-home-assistant/actions/workflows/validate.yml)

An unofficial Home Assistant custom integration for supported Dreame wet and dry vacuums. It connects to Dreame cloud services and exposes device state, controls, alerts, and maintenance through Home Assistant entities. A companion Lovelace card is included in `www/` for users who want a compact, theme-aware dashboard.

> **Status:** Work in progress. H14 behavior is kept on its existing mapping path. H15 Pro Heat (`dreame.hold.w2449e`) is being validated separately; its sensor map and some write/readback behavior are not complete. Unknown values stay unknown. Do not rely on this integration for safety-critical tasks.

This community project is not affiliated with or supported by Dreame. It uses undocumented cloud interfaces that can change without notice.

## What it provides

- Cloud account setup with automatic country selection from Home Assistant and an optional server override.
- Device status, battery, connection state, supported alerts, and maintenance entities.
- Model-aware controls and entities, preserving legacy H14 mappings while adding a separate H15 profile.
- H15 wash/dry and cleaning settings where the command path is known, with raw values retained for diagnosis when interpretation is not verified.
- A Lovelace dashboard card with operation, device status, maintenance, theme-aware colors, and manually selectable entities.

Availability depends on the model, firmware, installed accessories, and the values reported by Dreame. A field documented as plugin-derived or candidate is not the same as a confirmed device mapping. Consult [H15_MAPPING.md](H15_MAPPING.md) before using H15 settings. Some writes require physical verification and the device may not confirm a command.

## Requirements

- Home Assistant 2025.1.0 or newer.
- A Dreamehome account with a supported wet and dry vacuum already added.
- Network access from Home Assistant to the relevant Dreame cloud services.

The integration declares its Python runtime dependencies in `manifest.json`; Home Assistant installs them automatically.

## Install the integration

### HACS custom repository

The repository is prepared as a HACS **Integration**. Until it is accepted into the HACS default list:

1. In Home Assistant, open **HACS → Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/matanmesika/dreame-wet-dry-vacuum-home-assistant` with category **Integration**.
3. Download **Dreame Wet & Dry Vacuum** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**, find **Dreame Wet & Dry Vacuum**, and follow the sign-in flow.

The bundled dashboard card is a separate frontend resource. HACS installing the integration does **not** install the card automatically; follow the next section if you want the dashboard.

### Manual integration install

Copy `custom_components/dreame_wet_dry_vacuum/` into `<HA config>/custom_components/dreame_wet_dry_vacuum/`, then restart Home Assistant and add the integration from **Settings → Devices & services**.

## Install the dashboard card

The dashboard card is optional and can be installed independently of the integration:

1. Copy `www/dreame-device-card.js` to `<HA config>/www/community/Dreame-device-card/dreame-device-card.js`.
2. In **Settings → Dashboards → Resources**, add `/local/community/Dreame-device-card/dreame-device-card.js` as a JavaScript module. For YAML-managed dashboards, add the same URL under `resources` with `type: module`.
3. Add a manual card using [www/card-example.yaml](www/card-example.yaml), or start from [www/dashboard-example.yaml](www/dashboard-example.yaml).
4. Hard refresh the browser after replacing the JS file.

The card follows Home Assistant theme variables and supports light/dark themes. English is the example/default display language; Hebrew can be selected explicitly. Device and entity names are read from Home Assistant. You can choose a device or provide entity IDs in card configuration. See [www/README_HE.md](www/README_HE.md) for the current Hebrew card guide.

This repository is currently a HACS **Integration** repository. HACS lists dashboard cards as a separate **Dashboard** category, so the card cannot be listed as an independent HACS dashboard product from this same repository. A separate card repository with its own package metadata and checks is required for that submission.

## Configuration and data handling

- The login flow asks for the Dreame account credentials. Country selection is taken from Home Assistant when available; there is no hard-coded Israel/account-country fallback.
- Automatic server discovery prefers authoritative region/domain data returned during login. Bounded regional discovery is used only if needed; the integration does not continuously submit the password to every region.
- Account credentials and cloud tokens are held by Home Assistant's config-entry storage and are not written to diagnostic exports.
- Diagnostics redact identifiers and credentials before export. Review an export before sharing it publicly because device state and model/firmware metadata may still be present.
- Cloud/MQTT delivery is used when available, with periodic HTTP polling as a fallback.

## H15 mapping status

H15 mappings and evidence are recorded in [H15_MAPPING.md](H15_MAPPING.md). The integration distinguishes confirmed, plugin-derived, candidate, and unmapped values. English names and enum labels are used in the mapping profile. Unverified meanings are not inferred from H14. The profile is incomplete pending vendor information and controlled device tests.

In particular, water-tank status and alert readback are exposed only where the observed value has a verified interpretation. Do not treat an absent warning, `-1`, an empty response, or an unknown enum as proof that a tank is installed, empty, or full. Maintenance percentages are shown only when a valid device maximum is available; no guessed service interval is substituted for unknown H15 data.

The supported H15 commands are limited to settings and maintenance actions present in the integration. Every command should be checked in the Home Assistant state and on the physical device. The integration reports failed or unconfirmed writes rather than claiming the device accepted them.

## Testing and development

Run local checks from the repository root:

```bash
python -m compileall -q custom_components
ruff check custom_components tests
pytest -q
node --check www/dreame-device-card.js
node --test tests/test_device_card.cjs
```

GitHub Actions runs HACS validation, Home Assistant `hassfest`, Ruff, Python tests on supported CI interpreters, and dashboard-card checks. The review ZIP is produced after the code, test, and `hassfest` jobs pass; the HACS repository-metadata check is reported separately because it depends on GitHub settings. A passing CI build does not replace physical-device validation.

See [CONTRIBUTING.md](CONTRIBUTING.md) for change and test expectations and [SECURITY.md](SECURITY.md) for vulnerability reporting.

## HACS publication status

This public repository is being prepared for HACS review. No new release tag or GitHub release is being created while H15 mapping and physical validation are still in progress. HACS can use the default branch for custom-repository integration installs; adding the integration to HACS's default list has additional gates, including a passing HACS Action and `hassfest`, a public repository with a description, issues and topics enabled, an integration brand, and a full GitHub release. The release requirement applies to the default-list request, so that request is deferred until the mapping is ready and you authorize a versioned release.

Before a HACS default-list submission, update the repository's GitHub **About** settings:

- **Description:** `Unofficial Home Assistant integration for Dreame wet & dry vacuums, with model-aware controls and an optional Lovelace dashboard card.`
- **Topics:** `home-assistant`, `home-assistant-custom-component`, `hacs`, `dreame`, `vacuum`, `wet-dry-vacuum`.
- **Issues:** enable GitHub Issues (currently disabled on the repository).

The local integration brand asset exists. HACS checks for `custom_components/dreame_wet_dry_vacuum/brand/icon.png`; the default-list check can also use a registered Home Assistant brand. The card itself must use a separate HACS Dashboard repository if you want it independently discoverable in that HACS category.

## Support

For setup problems or reproducible bugs, open an issue at <https://github.com/matanmesika/dreame-wet-dry-vacuum-home-assistant/issues>. Include the integration version, Home Assistant version, device model/firmware, relevant redacted logs, and steps to reproduce. Never include account passwords, access tokens, or unredacted device identifiers.
