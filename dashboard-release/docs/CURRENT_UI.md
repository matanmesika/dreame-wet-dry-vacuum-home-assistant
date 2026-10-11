# Dreame dashboard — verified UI structure

## Source of truth: the actual H15 Pro Heat card

The installable card in this repository is `dist/dreame-device-card.js`,
originally copied byte-for-byte from the integration development's
`www/dreame-device-card.js`.
This UI was compared with an H15 Pro Heat iPhone Home Assistant screenshot
provided by the project owner on October 11, 2026.

The screenshot was used as a **private visual reference** only. It is not
uploaded to this public repository, to avoid publishing a homeowner's actual
device state, dashboard navigation and account environment.

### What the real card looks like

```text
┌────────────────────────────────────────────┐
│ DREAME · WET & DRY         [vacuum drawing] │
│ H15 Pro Heat                               │
│ Sleeping                  Native device    │
│                           dialog           │
│ Battery 100%       Connectivity Connected │
│ ┌────────────────────────────────────────┐ │
│ │ Operation | Device status | Maintenance│ │
│ └────────────────────────────────────────┘ │
│ [Self-clean]           [Start drying]       │
│ Personalized cleaning  [toggle]            │
│ Cleaning settings                         >│
│ Wash & dry                                >│
│ Device settings                           >│
│ More settings & scheduling                >│
│ Mapping in progress · some controls ...    │
└────────────────────────────────────────────┘
```

This is a **structural diagram**, not a screenshot or substitute image.
Actual values, badges and controls are supplied by Home Assistant and
depend on the connected device's real entity state.

### What is *not* part of the card

The screenshot also has a top navigation bar, a separate title panel
`🤖 Vacuum / Mode • Maintenance • Settings`, and a floating bottom
navigation dock. Those elements belong to the user's Home Assistant
dashboard/theme, **not** the `custom:dreame-device-card` component.
Do not replicate them inside the standalone card or its HACS documentation.

### Visual and behavioral acceptance points

1. The heading, battery/connection summary, round device illustration,
   three tabs and nested setting groups use Home Assistant theme variables.
2. iPhone/narrow viewports (600 CSS pixels or less) let the *page* scroll;
   the card's settings panel no longer imposes its former 340-pixel
   inner-scrolling limit. The last setting rows remain reachable.
3. On wider screens, the original inner scroll and scroll preservation
   behavior remains unchanged.
4. **Unknown** states shown under self-clean and wash/dry are honest
   missing/unknown integration readbacks, not successful confirmations or
   hard-coded operating modes. H15 device mapping still needs physical checks.
5. Only controls returned by the integration are rendered. Offline,
   unsupported or unavailable controls stay disabled; reset commands
   require confirmation.
6. A custom `image` or a real device `device_id` can be configured,
   but no synthetic sensors, identifiers or APIs are added by the card.

## How to report mismatches

If the displayed card deviates from this source, provide the *active*
Lovelace YAML and the currently registered resource URL, since an old
`/local/` card resource may remain cached in iOS even when the repo file
has been updated. No claim of end-to-end iOS acceptance testing is made
on the basis of automated tests or one screenshot.
