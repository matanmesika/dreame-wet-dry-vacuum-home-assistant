## Dreame Wet & Dry Vacuum v0.2.3-beta.2 (H15 Pro Heat)

Verified against the Dreamehome w2449e app plugin (v1240).

**New**
- Cleaning Record sensors from the app: cleaning time today / 7 days / 30 days with the light, moderate and heavy dirt split, sessions in the last 7 days, last cleaning.
- Firmware update entity (read-only; installing stays in the Dreamehome app).
- Settings cache: the last known app settings survive Home Assistant restarts. Live values always win; the lifting-arm bitfield is never cached.
- New integration icon: the H15 Pro Heat from the Dreamehome app.

**Changed**
- Option names now match the app: Quiet / Turbo / Personalized **Mode**, Low / Medium / High **Sensitivity**, schedule None / Once / Whole Week / Weekday / Weekends. Automations that compare these option texts need the new names.
- Smart Moisture Protection shows the app default (on) until the device reports a value.
- The generic `vacuum` entity is removed (the dedicated controls cover everything it did).

**Dashboard**: use `dreame-device-card` v1.1.0 for the matching tabs, Cleaning Record and Firmware rows.
