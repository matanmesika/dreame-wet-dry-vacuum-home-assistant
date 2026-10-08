# Contributing

Thanks for helping improve Dreame Wet & Dry Vacuum for Home Assistant.

## Before opening a change

- Keep H14 behavior and mappings unchanged unless the change is specifically verified for H14.
- Keep H15 properties model-specific. Do not transfer H14 semantics to H15 without evidence.
- Keep all mapping-profile names, value labels, and mapping notes in English. Use `unknown` for meanings that have not been verified.
- Do not add raw-property write paths or claim a setting is supported without device evidence and safe bounds.
- Never commit credentials, account/device identifiers, exported tokens, or unredacted diagnostic data.

## Validation

Run the applicable checks before submitting:

```bash
python -m compileall -q custom_components
ruff check custom_components tests
pytest -q
node --check www/dreame-device-card.js
node --test tests/test_device_card.cjs
```

For mapping changes, update `H15_MAPPING.md` with the observed source/value and confidence level. Tests and successful cloud calls do not replace physical verification. State exactly which model and firmware were tested and mark any remaining uncertainty.

## Pull requests

Use a focused change with a clear summary, user-visible impact, tests run, and any physical-device verification. Do not create a release tag while the H15 mapping remains incomplete.
