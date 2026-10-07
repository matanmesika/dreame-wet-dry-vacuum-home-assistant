# H15 Pro Heat mapping — 0.2.2

Model: `dreame.hold.w2449e`. Updated: 2026-10-07.

These mappings apply only to H15 Pro Heat. H14 continues to use the existing tables in `const.py` and its legacy entity implementations. The H15 profile creates telemetry sensors, diagnostic buttons, and app-derived configuration controls. H15 write plans and switch polarity are separate from H14. Physical write verification on the device remains pending.

## Evidence levels

- `confirmed`: observed on the H15 and matched to the app during the mapping work.
- `plugin`: decoded from the app plugin; still needs a matching live value on the device.
- `candidate`: interpretation needs a controlled comparison.
- `unmapped`: no semantic interpretation is applied.

A sensor appears only after the device returns its property. A definition in this table does not prove that the current firmware exposes it. All received raw properties remain available for mapping, including properties without definitions.

## Configuration controls

| Type | Settings | Properties |
|---|---|---|
| Select (9) | Cleaning mode, suction, water, hot water, self-cleaning, drying, traction, moisture sensitivity, detergent mode | `16.7`, `16.1`, `16.2`, `16.8`, `1.8`, `1.10`, `23.1`, `26.3`, `1.67` |
| Switch (5) | Return automatic wash/dry, automatic roller drying, smart drying, moisture protection, custom cleaning | `1.7`, `1.9`, `26.1`, `26.2`, `16.6` |
| Switch (4) | Lifting arm: Smart, Hot Water, Suction, Custom | `24.1`, inverted bits 0, 3, 2, 4 |
| Slider (1) | Voice volume, integral 0–100% | `1.14` |

Controls use the H15 app options: water 2/3; self-cleaning 4/2/3. Legacy values remain readable but cannot be selected. Hot water fixes suction to Gentle; Quiet/Turbo require hot water off. Changing water or suction selects Personalized mode. Preset selection updates coupled suction/water fields. Wash/dry choices synchronize their manual, return and scheduled preference copies, without changing schedule times or enabling a schedule.

Arm changes read the current bitfield, preserve other bits, and serialize writes. Missing/invalid arm state disables these controls. Only complete successful acknowledgements update displayed state; rejected/incomplete responses raise a Home Assistant error. A later device update supplies authoritative state. No motor start/stop or unsupported remote movement commands are added.

Duplicate H15 setting sensors are disabled once during migration and remain available as optional diagnostics. Other telemetry and all H14 entities retain their behavior.

## Property catalog

| Property | Name | Evidence | Values / units |
|---|---|---|---|
| `1.1` | Self-cleaning command raw | plugin | Raw |
| `1.2` | Self-drying command raw | plugin | Raw |
| `1.3` | Roller brush head light raw | plugin | Raw |
| `1.4` | Auto detergent mixing raw | plugin | Raw |
| `1.6` | High-level mode raw | plugin | Raw |
| `1.7` | Return to automatic wash & dry | confirmed | 0=On; 1=Off |
| `1.8` | Self-cleaning mode | plugin | 2=Standard Immersive Self-Cleaning; 3=Deep-Clean Immersive Self-Cleaning; 4=Smart Self-Cleaning; 5=Hot-Water Self-Cleaning |
| `1.9` | Auto roller brush drying | plugin | 0=On; 1=Off |
| `1.10` | Drying mode | confirmed | 1=High-Speed; 3=Super-Speed |
| `1.11` | Timed drying after cleaning | plugin | Raw |
| `1.12` | Scheduled drying time raw | plugin | Raw |
| `1.13` | Scheduled drying repeat raw | plugin | Raw |
| `1.14` | Voice volume | plugin | % |
| `1.17` | Voice language pack | plugin | Raw |
| `1.28` | Work mode | confirmed | 1=Power on; 2=Power off; 3=Standby; 4=Charging; 5=Self-cleaning; 6=Self-drying; 7=Sleeping; 8=Convenient; 9=Adding clean water; 10=Washing paused; 11=Cleaning paused; 12=Drying paused; 13=OTA upgrading; 14=Voice upgrading; 15=Charging complete; 16=Auto cleaning; 17=Degerming; 18=Water suction; 19=Quiet cleaning; 20=Quick cleaning; 21=Strong cleaning; 22=Personalized cleaning; 23=Fast drying; 24=Faster drying; 25=Quiet drying; 26=Fast self-cleaning; 27=Deep self-cleaning; 28=Smart self-cleaning; 29=Convenient paused; 30=Fast self-cleaning paused; 31=Deep self-cleaning paused; 32=Fast self-cleaning drying; 33=Deep self-cleaning drying; 34=Smart self-cleaning drying; 35=Retry drying; 36=Retry self-cleaning; 37=Smart self-cleaning paused; 40=Power mode; 41=Hot water cleaning; 42=Hot water self-cleaning; 43=Hot water self-cleaning paused |
| `1.29` | Washing level | plugin | Raw |
| `1.30` | Drying level | plugin | Raw |
| `1.47` | Last-clean timestamp candidate | candidate | Raw |
| `1.53` | Total working time | plugin | Raw |
| `1.54` | Clean count | plugin | Raw |
| `1.55` | Start time raw | plugin | Raw |
| `1.56` | Total self-dry time raw | plugin | Raw |
| `1.57` | Total self-clean time raw | plugin | Raw |
| `1.64` | Last clean mild-dirt time raw | candidate | Raw |
| `1.65` | Last clean moderate-dirt time raw | candidate | Raw |
| `1.66` | Last clean severe-dirt time raw | candidate | Raw |
| `1.67` | Cleaning solution ratio mode | plugin | 2=Smart Mode; 3=Powerful stain removal |
| `1.75` | Scheduled wash & dry mode | plugin | Raw |
| `1.76` | Scheduled wash & dry start time raw | plugin | Raw |
| `1.77` | Scheduled wash & dry repeat raw | plugin | Raw |
| `1.81` | Return self-cleaning wash mode | plugin | Raw |
| `1.82` | Return self-cleaning dry mode | plugin | Raw |
| `1.83` | Scheduled self-dry mode | plugin | Raw |
| `2.1` | Cloud status code raw | candidate | Raw |
| `3.1` | Battery | confirmed | % |
| `4.1` | Warnings raw | plugin | Raw |
| `4.2` | Errors raw | plugin | Raw |
| `4.3` | Warning push raw | plugin | Raw |
| `4.5` | Raw 4.5 | unmapped | Raw |
| `4.6` | Raw 4.6 | unmapped | Raw |
| `4.7` | Raw 4.7 | unmapped | Raw |
| `4.38` | Raw 4.38 | unmapped | Raw |
| `6.6` | Roller brush maximum life raw | plugin | min |
| `6.7` | Roller brush remaining | confirmed | min |
| `7.6` | Rear brush maximum life raw | plugin | min |
| `7.7` | Rear brush remaining raw | plugin | min |
| `10.1` | Dip angle level | plugin | Raw |
| `13.2` | Electrolyzed water setting raw | plugin | Raw |
| `16.1` | Suction setting | confirmed | 1=Gentle; 2=Standard; 3=Strong |
| `16.2` | Water level | confirmed | 1=Low / legacy; 2=Standard; 3=High |
| `16.3` | Electrolyzed water raw | plugin | Raw |
| `16.4` | Brush speed raw | plugin | Raw |
| `16.6` | Personalized mode flag | plugin | Raw |
| `16.7` | Cleaning mode | confirmed | 1=Quiet; 3=Turbo; 4=Personalized |
| `16.8` | Hot water mode | confirmed | 0=Off; 1=Mild; 2=Standard; 3=Thermal |
| `19.2` | Filter maximum life raw | plugin | min |
| `19.3` | Filter remaining | confirmed | min |
| `20.2` | Dust bag maximum life raw | plugin | min |
| `20.3` | Dust bag remaining raw | plugin | min |
| `21.6` | Suction brush maximum life raw | plugin | min |
| `21.7` | Suction brush remaining raw | plugin | min |
| `22.6` | Suction filter maximum life raw | plugin | min |
| `22.7` | Suction filter remaining raw | plugin | min |
| `23.1` | GlideWheel traction | plugin | 0=Balanced; 1=Gentle; 2=Turbo |
| `24.1` | Lifting robotic arm modes raw | plugin | Raw |
| `25.1` | Global hot water mode raw | candidate | Raw |
| `26.1` | Smart drying | plugin | 0=On; 1=Off |
| `26.2` | Smart moisture protection | plugin | 0=On; 1=Off |
| `26.3` | Roller brush moisture sensitivity | plugin | 2=Low; 3=Medium; 4=High |
| `26.4` | Raw 26.4 | unmapped | Raw |
| `26.5` | Raw 26.5 | unmapped | Raw |
| `100.1` | Remote forward raw | plugin | Raw |
| `100.2` | Remote backward raw | plugin | Raw |
| `100.3` | Remote left raw | plugin | Raw |
| `100.4` | Remote right raw | plugin | Raw |
| `100.5` | Remote left-back raw | plugin | Raw |
| `100.6` | Remote right-back raw | plugin | Raw |

## Remaining validation

- Properties already mapped in the plugin but missing from the last uploaded 47-property snapshot: self-clean mode (1.8), automatic roller drying (1.9), voice volume/language (1.14/1.17), detergent mode (1.67), schedule settings (1.75–1.77), traction (23.1), lifting arm (24.1), smart drying/moisture settings (26.1–26.3). Read these while the device is awake.
- The last snapshot also contains unnamed properties 1.33–1.36, 1.49–1.52, 1.68–1.71, 1.73, 4.5–4.7, 4.38 and 26.4/26.5. Compare one app setting at a time before assigning meanings.
- Verify H15 alert/error bits, timing units and schedule encodings.
- Validate live state transitions while cleaning, self-cleaning and drying; work-mode enum entries come from the common plugin and some may not be used by this model.
- Language-pack IDs and schedule encodings are not yet validated. The 0.2.2 writes follow the app implementation and passed unit tests, but still require physical-device testing.

## Diagnostic workflow

Use **Refresh mapping snapshot** before a setting change and again after the change. The **Mapping changes** sensor reports old/new values. **Export Dreame app metadata** writes `/config/dreame_h15_probe/metadata_share.json`, which includes the integration version, UTC export time, refresh result, current raw values, mapping profile, observed flags, scan differences and targeted read results. A sleeping device may return no live values while cached values remain available.

Targeted reads use the current profile plus returned properties; the catalog contains 77 definitions. Discovery scans SIIDs 1–40 and 100, PIIDs 1–120, with bounded requests. Normal periodic polling reads only discovered properties.
