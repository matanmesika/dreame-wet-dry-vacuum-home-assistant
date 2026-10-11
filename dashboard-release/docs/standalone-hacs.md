# Standalone HACS Dashboard release procedure

## Current status

The repository `matanmesika/dreame-wet-dry-vacuum-home-assistant` is a HACS
**Integration** repository. The folder `dashboard-release/` is a complete
candidate tree, but it cannot be installed **as an independent HACS Dashboard**
from that same integration repository entry.

## One-time publication (not performed yet)

1. Create a **separate** public GitHub repository for the card (proposed:
   `matanmesika/dreame-device-card`). Enable Issues and add descriptive
   topics and license. Do not confuse this with the integration repository.
2. Copy the **contents** of `dashboard-release/` to the root of the separate
   repository. Keep `dist/dreame-device-card.js` and `hacs.json`.
3. Run `node --check dist/dreame-device-card.js` and
   `node --test tests/test_device_card.cjs`.
4. Verify HACS Dashboard-category checks. HACS should use the
   `filename` property from `hacs.json`; the JS lives in `dist/`.
5. Install in an actual Home Assistant browser and companion app on iOS,
   test H14/H15 device selection and safe maintenance controls.
6. Only after real-device acceptance, tag and publish the repository. Users
   will add the new repository as a **Dashboard** custom repository in HACS.

## Manual local test

While the separate repository has not been created:
- Copy `dashboard-release/dist/dreame-device-card.js` into
  `<config>/www/dreame-device-card.js`.
- Register `/local/dreame-device-card.js` as a JavaScript module in
  Home Assistant Dashboards → Resources.
- Add the YAML in `examples/card.yaml`, using only real device IDs.

## Integration branding

Brand assets belong to the integration's
`custom_components/dreame_wet_dry_vacuum/brand/`, not to this Dashboard
repository. Home Assistant 2026.3+ supports these local icons/logos. HACS
storefront icons may still be absent because of a separate HACS UI issue.

The card does not itself contact cloud services or create new entities.


For current UI layout and iPhone behavior see [CURRENT_UI.md](CURRENT_UI.md).
