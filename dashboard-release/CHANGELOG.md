# Changelog

## Unreleased — standalone dashboard release candidate

- Package existing Dreame device Lovelace card as a standalone HACS Dashboard candidate.
- Add an English-first explanatory README with Hebrew quick start and an accurate, screenshot-informed UI specification; remove misleading illustrative SVGs.
- Keep integration brand icons exclusively in `custom_components/dreame_wet_dry_vacuum/brand/`; the standalone dashboard package ships no brand assets.
- Ship the existing model-aware visual editor and 3-tab user experience without changing supported integration entity mappings.
- Keep the dashboard JavaScript byte-for-byte identical to the development implementation.
- Run the existing JavaScript behavior tests from a standalone `dist/` layout.
- Do not tag or publish a release before integration compatibility and Home Assistant manual checks are complete.

- Keep the actual H15 card and standalone distribution identical; make small-screen panels scroll with the outer HA page rather than hiding settings behind a nested scroll limit.
- Verify that integration icon/logo assets are separate from the Lovelace card and are not shipped with the standalone HACS Dashboard.
