# Dreame Dashboard — product tree

This folder is the **Dashboard distribution candidate**, not a second
Home Assistant integration. It uses existing integration entities and does
not ship an API client, integration Python package, or brand logo.

```text
dashboard-release/
├── dist/
│   └── dreame-device-card.js          # Actual Lovelace custom element
├── examples/
│   ├── card.yaml                     # Card configuration
│   └── dashboard.yaml                # Full Lovelace dashboard view
├── docs/
│   ├── CURRENT_UI.md                  # Real iPhone card UI specification
│   └── standalone-hacs.md             # Publication and manual install
├── tests/
│   └── test_device_card.cjs          # Independent Node.js behavior tests
├── CHANGELOG.md
├── LICENSE
├── README.md                         # English guide + Hebrew quick start
├── RELEASE_CHECKLIST.md              # Real-device release gates
├── PRODUCT_TREE.md                    # This complete tree / file roles
├── hacs.json                          # Future HACS Dashboard manifest
└── info.md                            # HACS description
```

## Existing parent repository (integration) tree

```text
custom_components/dreame_wet_dry_vacuum/
├── __init__.py                       # Home Assistant integration
├── manifest.json                     # HA integration metadata
├── brand/                            # **Integration-only branding**
│   ├── icon.png                      # Square Dreame emblem, normal
│   ├── icon@2x.png                   # Square Dreame emblem, retina
│   ├── logo.png                      # Dreame wordmark, normal
│   └── logo@2x.png                   # Dreame wordmark, retina
└── ...                               # Existing API, platforms, device mapping
www/
└── dreame-device-card.js             # Development source (must match dist)
dashboard-release/                     # Standalone dashboard candidate above
assets/branding/                        # Source SVG and asset provenance
scripts/generate_dreame_brand.py        # Integration branding generator
.github/workflows/
├── dashboard-standalone-validate.yml
└── generate-dreame-brand.yml
```

## Scope and constraints

- The **integrated API** is installed as a HACS **Integration**. Its local
  logo and icon are bundled inside its `custom_components` domain path.
- The **dashboard** is a HACS **Dashboard** category, requiring a dedicated
  GitHub repository before it can be distributed separately. Copy the *contents*
  of this candidate folder to the **root** of the future repository.
- No additional sensor, service, command, cloud token flow, or H15 mapping is
  added by packaging the dashboard.
- No XPENG or other project files are included.
- Releases are blocked pending a dedicated repository and physical Home
  Assistant / iPhone checks. See `RELEASE_CHECKLIST.md`.
