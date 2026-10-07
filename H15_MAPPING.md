# H15 Pro Heat mapping — work in progress

Model `dreame.hold.w2449e`; app common plugin 728, resource 7, firmware snapshot 2.1.8_1047. **Sensor mapping remains incomplete.** This validation build is tracked in the draft PR while awaiting Dreame engineering feedback. Definitions and write plans live in the existing `const.py`; exporter in `api.py`; entities in the existing platforms. H14 definitions are preserved.

## App feature coverage

| Feature | Home Assistant behavior | Evidence / remaining work |
|---|---|---|
| Cleaning / suction / water / custom heat | Selects, app-coupled write batches | Existing enum captures plus app; physical write tests pending |
| Self-cleaning / drying preferences | Selects; synchronized manual/return/scheduled copies | App PopWashDry / washDryKeyMap |
| Start / resume / stop self-cleaning | Commands 2/3/4 for selected wash, 1 resume, 0 stop | App isNeedCorrectOperation=true; live task test pending |
| Start / stop drying | Setting 1 sends 1; setting 3 sends 4; stop sends 0 | App drySetValueMap; live task test pending |
| Filter / roller life reset | Set 19.1=1 / 6.1=1, then read telemetry | App MaterialDetailPage; live reset pending |
| Optional rear roller | Reset 7.1=1 only with nonnegative remaining life | Current 7.7=-1: unavailable |
| Water / tank / brush / filter alerts | 28 field-specific binary alerts; raw warn/error retained | App warnVersion=2; dirty-tank-full bit 4096 now live-confirmed; clean-tank capture still needed |
| GlideWheel / lifting arm / smart drying | Selects and switches with preserved arm bits | App definitions; live writes pending |
| Default hot-water temperature | Select 25.1=1/2/3 | App PopHotWater |
| Voice language | Installed languages 2/3/4/6/7/16/17 | Resource holdPluginVoiceType=4 / DATA_VOICE4 |
| Voice volume | Three-position slider: 0 Silent / 1 Low / 2 High → raw 0/30/60 | Actual VoiceSettingPage slider levels |
| Wash/dry schedule | Time in minutes after midnight, presets and seven weekday switches | App decimal weekday encoding; device timezone; live writes pending |
| Forward / backward | 0.3 s pulse, explicit stop, horizontal + online guards | isSupportControlS=true; live test pending |
| Left/right and diagonal movement | Diagnostic only | isSupportControl=false |
| Brush light / electrolysis / brush speed | Diagnostic only | Not exposed by w2449e app resource |
| Cleaning history | Existing raw properties / mapped duration and progress | Complete event-history retrieval remains unimplemented |
| Firmware / account management | Dreame app | Outside this control build |

## State and write semantics

H15 commands do not overwrite telemetry or invent reset counters. Responses must acknowledge every requested property with success; `value=-1`, absent/partial rows and errors fail. Commands read state afterward; later MQTT/polls supply authoritative values. Read-modify-write for arm/schedule days is serialized and preserves sibling settings.

Self-cleaning starts only while idle on dock with at least 20% battery and a known wash preference. Drying cannot start during cleaning. Stop and resume buttons follow the current task state. Forward/backward is bounded and sends stop even after a rejected start or cancellation. Six-direction robot controls are not assumed from the common plugin.

Schedule uses eight **decimal digits**, not binary bits: once at 10^7; Sunday at 10^6; Monday–Saturday at 10^0–10^5. Invalid digits remain unknown and cannot be modified as weekdays. A new schedule requires a configured start time; disabling it does not fabricate a different time.

Warning/error fields use the exact app table and JavaScript integer-key iteration order. Roller fault codes are multi-bit values, not simple on/off bits. Unknown bits and physical tank conditions are never cleared by writing a sensor value. App dismissals are UI-only, not device reset commands.

## Evidence levels

`confirmed` means an observed enum matched the app; `plugin` means source-derived but still awaiting corresponding live verification; `candidate` and `unmapped` retain raw data. None of these labels implies a physical write has already been tested.

## Property catalog

| Property | Name | Evidence | Values / units |
|---|---|---|---|
| `1.1` | Self-cleaning command raw | plugin | Raw |
| `1.2` | Self-drying command raw | plugin | Raw |
| `1.3` | Roller brush head light raw | plugin | Raw |
| `1.4` | Auto detergent mixing raw | plugin | Raw |
| `1.6` | Altitude setting raw | plugin | 0=Standard altitude; 1=High altitude |
| `1.7` | Return to automatic wash & dry | confirmed | 0=On; 1=Off |
| `1.8` | Self-cleaning mode | plugin | 2=Standard Immersive Self-Cleaning; 3=Deep-Clean Immersive Self-Cleaning; 4=Smart Self-Cleaning; 5=Hot-Water Self-Cleaning |
| `1.9` | Auto roller brush drying | plugin | 0=On; 1=Off |
| `1.10` | Drying mode | confirmed | 1=High-Speed; 3=Super-Speed |
| `1.11` | Timed drying after cleaning | plugin | Raw |
| `1.12` | Scheduled drying time raw | plugin | Raw |
| `1.13` | Scheduled drying repeat raw | plugin | Raw |
| `1.14` | Voice volume | plugin | % |
| `1.17` | Voice language pack | plugin | 2=English; 3=German; 4=French; 6=Italian; 7=Spanish; 16=Dutch; 17=Portuguese |
| `1.28` | Work state | confirmed | 1=Power on; 2=Power off; 3=Standby; 4=Charging; 5=Self-cleaning; 6=Self-drying; 7=Sleeping; 8=Convenient; 9=Adding clean water; 10=Washing paused; 11=Cleaning paused; 12=Drying paused; 13=OTA upgrading; 14=Voice upgrading; 15=Charging complete; 16=Auto cleaning; 17=Degerming; 18=Water suction; 19=Quiet cleaning; 20=Quick cleaning; 21=Strong cleaning; 22=Personalized cleaning; 23=Fast drying; 24=Faster drying; 25=Quiet drying; 26=Fast self-cleaning; 27=Deep self-cleaning; 28=Smart self-cleaning; 29=Convenient paused; 30=Fast self-cleaning paused; 31=Deep self-cleaning paused; 32=Fast self-cleaning drying; 33=Deep self-cleaning drying; 34=Smart self-cleaning drying; 35=Retry drying; 36=Retry self-cleaning; 37=Smart self-cleaning paused; 40=Power mode; 41=Hot water cleaning; 42=Hot water self-cleaning; 43=Hot water self-cleaning paused |
| `1.29` | Self-cleaning progress | plugin | % |
| `1.30` | Self-drying progress | plugin | % |
| `1.47` | Last-clean timestamp candidate | candidate | Raw |
| `1.53` | Total working time | plugin | min |
| `1.54` | Clean count | plugin | Raw |
| `1.55` | Start time | plugin | Raw |
| `1.56` | Self-drying task duration | plugin | s |
| `1.57` | Self-cleaning task duration | plugin | s |
| `1.64` | Last clean mild-dirt time raw | candidate | Raw |
| `1.65` | Last clean moderate-dirt time raw | candidate | Raw |
| `1.66` | Last clean severe-dirt time raw | candidate | Raw |
| `1.67` | Cleaning solution ratio mode | plugin | 2=Smart Mode; 3=Powerful stain removal |
| `1.75` | Scheduled wash & dry mode | plugin | 4=Auto-Adjust; 2=Standard; 3=Deep-Clean |
| `1.76` | Scheduled wash and dry time | plugin | Raw |
| `1.77` | Scheduled wash and dry repeat | plugin | schedule |
| `1.81` | Return self-cleaning wash mode | plugin | 4=Auto-Adjust; 2=Standard; 3=Deep-Clean |
| `1.82` | Return self-cleaning dry mode | plugin | 1=High-Speed; 3=Super-Speed |
| `1.83` | Scheduled self-dry mode | plugin | 1=High-Speed; 3=Super-Speed |
| `2.1` | Cloud status code raw | candidate | Raw |
| `3.1` | Battery | confirmed | % |
| `4.1` | Warnings | plugin | warnings |
| `4.2` | Errors | plugin | errors |
| `4.3` | Warning push raw | plugin | Raw |
| `4.5` | Raw 4.5 | unmapped | Raw |
| `4.6` | Dirty water tank candidate raw | candidate | Raw |
| `4.7` | Raw 4.7 | unmapped | Raw |
| `4.38` | Raw 4.38 | unmapped | Raw |
| `4.83` | Raw 4.83 | unmapped | Raw |
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
| `24.1` | Lifting arm modes | plugin | mechanical_arm_2449 |
| `25.1` | Default hot water temperature | plugin | 1=Mild; 2=Standard; 3=Thermal |
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

## Remaining telemetry validation

The earlier clean-tank-removal export was taken at 2026-10-07T17:21:37Z from integration 0.2.1. It reports Sleeping (1.28=7), zero warnings/errors (4.1/4.2/4.3=0), no mapping changes and no direct live properties. It cannot establish a tank-missing mapping. The new 4.83=-1 is retained as unknown.

Unresolved returned keys include 1.33–1.36, 1.49–1.52, 1.68–1.71, 1.73, 4.5–4.7, 4.38, 4.83 and 26.4/26.5. The 21:00:25 local export with the app dirty-tank-full alert reports 4.2=4096 (live-confirmed) and 4.6=81 (previously 0). The latter is a candidate field with no percent unit. 4.5=[81] and 4.7=[3] remained unchanged. Confirm the reverse transition after emptying the dirty tank before interpreting 4.6. Compare app changes one at a time with an awake device.

Task duration fields 1.56/1.57 are seconds used by the app's remaining-time calculation, not lifetime totals. Work time 1.53 is minutes; start time 1.55 is epoch seconds. Consumable life remains minutes, with hours/percentage derived only from actual reported maximum life on H15.

## Diagnostic workflow

Refresh mapping before and after a single change. Export `metadata_share.json` (current manifest version) for source profile, raw properties and exact differences. No cloud credentials are needed for unit tests; the user performs device and full Home Assistant validation before considering the implementation ready for release.


## Mode dropdown audit (work in progress)

Writable mode properties 1.8, 1.10, 1.67, 1.75, 1.81, 1.82, 1.83, 16.7, 16.8, 25.1 are selects. Suction, water, traction, moisture, language and schedule preset selects remain available. Arm mode combinations now have a select as well as the four independent switches; every combination preserves reserved bit 1 and requires a known live/cached arm encoding.

The app synchronizes wash and dry preferences across manual, return and scheduled settings, so changing a return/scheduled mode also updates its sibling preferences. This is documented behavior, not independent schedule toggling. Reported Work state (1.28) is telemetry; high-level property 1.6 controls location altitude and is hidden by w2449e, not an extra cleaning mode.

163 unit tests pass, including H14 table preservation and exact capture 4.2=4096 / 4.6=81. Commands still require physical user validation. This remains a draft validation build, not a complete or fully validated sensor mapping.

## Native device presentation (work in progress)

Single device, unchanged identifiers. H15 daily controls have no entity category, general telemetry remains primary sensors, maintenance counters/reset buttons and alerts use Diagnostic. No H15 entity remains in Configuration. HA owns card headings; Diagnostic cannot be renamed Maintenance by the integration. Unresolved/duplicate raw sensors are optional disabled diagnostics, with a one-time reversible registry migration. H14 categories/mappings are unchanged.

Voice volume remains a NumberMode.SLIDER with min=0, max=2, step=1. Levels 0/1/2 encode raw 0/30/60, confirmed against VoiceSettingPage's 0..60, step=30 slider and direct PropVolume write. UI scale is a level, not a percentage. English/French/Hebrew names explain the three positions; attributes expose the level label and raw value. Write acknowledgement rejection does not change the displayed level, and unknown raw values are not rounded to a known level.
