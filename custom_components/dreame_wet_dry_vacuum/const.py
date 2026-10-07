"""Constants for Dreame wet & dry vacuum integration."""

DOMAIN = "dreame_wet_dry_vacuum"
MANUFACTURER = "Dreame"
MODEL = "H14 Pro"

# API
EU_BASE_URL = "https://eu.iot.dreame.tech:13267"
CN_BASE_URL = "https://cn.iot.dreame.tech:13267"

# DREAME_BASIC_AUTH = base64("dreame_appv1:AP^dv@z@SQYVxN88") — app client credentials
DREAME_BASIC_AUTH = "Basic ZHJlYW1lX2FwcHYxOkFQXmR2QHpAU1FZVnhOODg="
DREAME_TENANT_ID = "000000"
DREAME_PASSWORD_SALT = "RAylYC%fmSKp7%Tq"
DREAME_RLC_KEY = b"EETjszu*XI5znHsI"
DREAME_IOT_PREFIX = "10000"

ENDPOINTS = {
    "token": "/dreame-auth/oauth/token",
    "device_list": "/dreame-user-iot/iotuserbind/device/listV2",
    "send_command": "/dreame-iot-com-{prefix}/device/sendCommand",
    # Reads the cloud-cached property values by key ("siid.piid"). Works on this
    # model where the realtime get_properties RPC returns null. Verified live.
    "status_props": "/dreame-user-iot/iotstatus/props",
}

# Device status codes for the H14 Pro (model dreame.hold.w2306e).
# Source: official Dreame keyDefine file, property 2.1.
# This mirrors the `latestStatus` field returned by device/listV2.
DEVICE_STATUS = {
    1: "Washing",
    2: "Offline",
    3: "Standby",
    4: "Charging",
    5: "Self-cleaning",
    6: "Self-drying",
    7: "Sleeping",
    8: "Vacuuming",
    9: "Adding clean water",
    10: "Washing paused",
    11: "Self-cleaning paused",
    12: "Self-drying paused",
    13: "OTA upgrade",
    14: "Voice package upgrade",
    15: "Charging complete",
    # 16-22 : "Lavage en cours" dans le dictionnaire officiel, mais chaque code
    # correspond en réalité à un MODE de nettoyage distinct (confirmé par l'utilisateur).
    16: "Washing — Auto mode",
    17: "Washing — Ultra mode",
    18: "Washing — Suction mode",
    19: "Washing",
    20: "Washing",
    21: "Washing",
    22: "Washing",
    23: "Self-drying",
    24: "Self-drying",
    25: "Self-drying",
    26: "Self-cleaning",
    27: "Self-cleaning",
    28: "Self-cleaning",
    29: "Convenient mode paused",
}

# Status enum names decoded from the official app plugin (index.android.bundle):
# StandBy:3 Charging:4 SelfCleaning:5 SelfDrying:6 Sleeping:7 Convenient:8
# AddWater:9 WashingPause:10 CleaningPause:11 DryingPause:12 OTAUpgrading:13
# ... SelfDrying_Quite:25 SelfCleaning_Fast:26 SelfCleaning_Deep:27
# SelfCleaning_Smart:28 ConvenientPause:29

# Coarse activity grouping (useful for automations / binary states)
STATUS_GROUP = {
    1: "mopping", 16: "mopping", 17: "mopping", 18: "mopping",
    19: "mopping", 20: "mopping", 21: "mopping", 22: "mopping",
    8: "vacuuming",
    3: "idle", 7: "idle",
    4: "charging", 15: "charging",
    5: "self_cleaning", 11: "self_cleaning", 26: "self_cleaning",
    27: "self_cleaning", 28: "self_cleaning",
    6: "drying", 12: "drying", 23: "drying", 24: "drying", 25: "drying",
    9: "filling_water",
    10: "paused", 29: "paused",
    13: "updating", 14: "updating",
    2: "offline",
}

# Property siid/piid known for this model
PROP_STATUS = (2, 1)  # device status (matches latestStatus)

# Known MQTT properties for the H14 Pro, discovered by live capture.
# (siid, piid): metadata for entity creation and value decoding.
# Confidence: HIGH for status/battery/progress; the rest are exposed raw.
# Meta schema per property:
#   key, name, icon, unit, device_class ("battery"|"duration"|"timestamp")
#   enum=True            -> map int via DEVICE_STATUS
#   list_scalar=True     -> value arrives as a list; use first element
#   timestamp=True       -> value is a Unix epoch (seconds)
#   diagnostic=True      -> entity category Diagnostic
# Names are kept in English in source; UI localization is handled by translations.
# Dreame's SIID/PIID mapping is authoritative; see debug/dumps/DECODED_SPEC.md.
# "name" is a source-code fallback; UI names use translation_key = "key"
# (section "entity" de translations/en.json et fr.json).
KNOWN_MQTT_PROPS: dict[tuple[int, int], dict] = {
    # --- Service principal (SIID 1) ---
    (2, 1): {"key": "status", "name": "Status", "enum": True, "icon": "mdi:robot-vacuum-variant"},
    (3, 1): {"key": "battery", "name": "Battery", "unit": "%", "device_class": "battery"},
    (1, 28): {"key": "work_mode", "name": "Work mode", "icon": "mdi:state-machine", "diagnostic": True},
    (1, 29): {"key": "level_washing", "name": "Washing level", "icon": "mdi:water-percent", "state_class": "measurement"},
    (1, 30): {"key": "level_drying", "name": "Drying level", "icon": "mdi:hair-dryer", "state_class": "measurement"},
    (1, 53): {"key": "total_time", "name": "Total runtime", "unit": "s", "device_class": "duration", "icon": "mdi:timer-cog", "diagnostic": True},
    (1, 54): {"key": "total_clean_count", "name": "Total clean count", "icon": "mdi:counter", "state_class": "total_increasing"},
    (1, 55): {"key": "start_time", "name": "Start time", "device_class": "timestamp", "timestamp": True, "icon": "mdi:clock-start", "diagnostic": True},
    (1, 56): {"key": "total_time_self_dry", "name": "Total self-dry time", "unit": "s", "device_class": "duration", "icon": "mdi:timer-sand", "diagnostic": True},
    (1, 57): {"key": "total_time_self_clean", "name": "Total self-clean time", "unit": "s", "device_class": "duration", "icon": "mdi:timer-sand", "diagnostic": True},
    # Champs lus via l'API cleanLog (hors modèle Prop du plugin) — mapping empirique conservé
    (1, 47): {"key": "last_clean_time", "name": "Last clean", "device_class": "timestamp", "timestamp": True, "icon": "mdi:clock-check"},
    (1, 64): {"key": "last_clean_duration", "name": "Last clean duration", "unit": "s", "device_class": "duration", "icon": "mdi:timer"},
    (1, 49): {"key": "clean_count_2", "name": "Clean counter (alt.)", "icon": "mdi:counter", "state_class": "total_increasing", "diagnostic": True},
    (1, 68): {"key": "last_vacuum_duration", "name": "Last vacuum duration", "unit": "s", "device_class": "duration", "diagnostic": True},
    (1, 69): {"key": "last_mop_duration", "name": "Last mop duration", "unit": "s", "device_class": "duration", "diagnostic": True},
    # --- Consommables : "vie restante" = MINUTES restantes (raw, diagnostic).
    #     Les heures/% sont exposés par des capteurs dédiés (CONSUMABLE_SENSORS).
    #     Les props "max" (x.6/x.2) ne sont jamais publiées par le cloud → non mappées.
    (6, 7): {"key": "front_brush_left", "name": "Front roller brush — minutes left", "unit": "min", "icon": "mdi:rotate-right", "diagnostic": True},
    (7, 7): {"key": "back_brush_left", "name": "Back roller brush — minutes left", "unit": "min", "icon": "mdi:rotate-right", "diagnostic": True},
    (19, 3): {"key": "filter_left", "name": "Filter — minutes left", "unit": "min", "icon": "mdi:air-filter", "diagnostic": True},
    # Jamais rapportés à ce jour (sac à poussière, brosse/filtre d'aspiration) — gardés bruts au cas où.
    (20, 3): {"key": "dustbag_left", "name": "Dust bag — minutes left", "unit": "min", "icon": "mdi:sack", "diagnostic": True},
    (21, 7): {"key": "suck_brush_left", "name": "Suction brush — minutes left", "unit": "min", "icon": "mdi:rotate-right", "diagnostic": True},
    (22, 7): {"key": "suck_filter_left", "name": "Suction filter — minutes left", "unit": "min", "icon": "mdi:air-filter", "diagnostic": True},
    # --- Réglages reflétés en lecture (aussi exposés comme contrôles, voir plus bas) ---
    (16, 3): {"key": "elec_water", "name": "Electrolysis / detergent", "icon": "mdi:flash", "diagnostic": True},
    (1, 67): {"key": "detergent_fav", "name": "Detergent preference", "icon": "mdi:bottle-tonic-plus", "diagnostic": True},
    # --- Alertes / défauts (SIID 4, noms du plugin : warn/error/warnPush) ---
    (4, 1): {"key": "warn", "name": "Warnings", "icon": "mdi:alert", "bitmask": True, "decode": "warn", "diagnostic": True},
    (4, 2): {"key": "error", "name": "Error codes", "icon": "mdi:alert-circle", "bitmask": True, "decode": "error", "diagnostic": True},
    (4, 3): {"key": "warn_push", "name": "Push notification (raw)", "icon": "mdi:bell-alert", "bitmask": True, "diagnostic": True},
    # --- Niveau d'eau / aspiration : non modélisés par le plugin sous SIID 4,
    #     mapping empirique conservé (vu en capture live) ---
    (4, 5): {"key": "water_level_set", "name": "Water level (setting)", "unit": "%", "list_scalar": True, "icon": "mdi:water-percent"},
    (4, 6): {"key": "water_level", "name": "Water level", "unit": "%", "icon": "mdi:water"},
    (4, 7): {"key": "suction_mode", "name": "Suction mode", "list_scalar": True, "icon": "mdi:fan"},
}

# Consumable sensors.
# The "left" value is remaining minutes. Hours are derived as left / 60.
# If a device exposes the "max" property it is used for percentage; otherwise
# full_life_min is used as a documented fallback.
CONSUMABLE_SENSORS: list[dict] = [
    {"key": "front_brush", "name": "Front roller brush", "left": "6.7", "max": "6.6",
     "full_life_min": 3600, "icon": "mdi:rotate-right"},
    {"key": "back_brush", "name": "Back roller brush", "left": "7.7", "max": "7.6",
     "full_life_min": 3600, "icon": "mdi:rotate-right"},
    {"key": "filter", "name": "Filter", "left": "19.3", "max": "19.2",
     "full_life_min": 3600, "icon": "mdi:air-filter"},
]

# Query the optional maximum-life keys as well. If the device exposes them,
# percentage calculations automatically use the real device value.
CONSUMABLE_MAX_KEYS: list[str] = [c["max"] for c in CONSUMABLE_SENSORS]

# ---------------------------------------------------------------------------
# Warning / error bitfield decoding
# ---------------------------------------------------------------------------
WARN_DECODE: list[tuple[int, int, dict[int, str]]] = [
    (0, 1, {1: "Clean water tank empty"}),
    (1, 1, {1: "Detergent empty"}),
    (1, 3, {1: "Brush/tube dirty — run self-cleaning",
            2: "Brush/tube dirty — run self-cleaning",
            3: "Brush/tube dirty — run self-cleaning"}),
    (2, 1, {}), (1, 1, {}), (1, 1, {}), (1, 1, {}),
    (1, 1, {1: "Dirty water tank needs cleaning after self-cleaning"}),  # bit 8
    (1, 1, {}), (1, 1, {}), (1, 1, {}), (1, 1, {}), (1, 1, {}), (1, 1, {}), (1, 1, {}),
    (1, 1, {1: "Station water supply low"}),   # bit 16
    (1, 1, {1: "Station filter needs replacement"}),  # bit 17
]
ERROR_DECODE: list[tuple[int, int, dict[int, str]]] = [
    (0, 15, {}),
    (4, 63, {1: "Roller brush not installed",
             3: "Roller brush blocked — clean it"}),  # bits 4-9
    (6, 1, {}),
    (1, 1, {1: "Dirty water tank not installed"}),   # bit 11
    (1, 1, {1: "Dirty water tank full — empty it"}),  # bit 12
    (1, 7, {}), (3, 15, {}), (4, 1, {}), (1, 1, {}), (1, 1, {}), (1, 1, {}),
    (1, 1, {1: "Vacuum tube blocked"}),   # bit 24
    (1, 1, {}),
    (1, 1, {1: "Station tube blocked"}),   # bit 26
    (1, 1, {}),
    (1, 1, {1: "Dirty water tank blocked"}),  # bit 28
]


def decode_field_alerts(value: int, table: list[tuple[int, int, dict[int, str]]]) -> list[str]:
    """Decode a warning/error bitfield into active English labels."""
    alerts: list[str] = []
    v = value
    for pos, cal, labels in table:
        if pos:
            v >>= pos
        field = v & cal
        if field in labels:
            alerts.append(labels[field])
    return alerts


# Binary alert sensors derived from warning/error bitfields.
ALERT_BINARY_SENSORS: list[dict] = [
    {"key": "dirty_tank_full", "name": "Dirty water tank full", "data_key": "4.2",
     "bit_mask": 4096, "device_class": "problem", "icon": "mdi:cup-water"},
    {"key": "dirty_tank_not_clean", "name": "Dirty water tank needs cleaning", "data_key": "4.1",
     "bit_mask": 256, "device_class": "problem", "icon": "mdi:cup-water"},
    {"key": "dirty_tank_missing", "name": "Dirty water tank missing", "data_key": "4.2",
     "bit_mask": 2048, "device_class": "problem", "icon": "mdi:cup-off-outline"},
    {"key": "clean_water_empty", "name": "Clean water tank empty", "data_key": "4.1",
     "bit_mask": 1, "device_class": "problem", "icon": "mdi:water-alert"},
    {"key": "detergent_empty", "name": "Detergent empty", "data_key": "4.1",
     "bit_mask": 2, "device_class": "problem", "icon": "mdi:bottle-tonic-outline"},
    {"key": "needs_self_clean", "name": "Self-cleaning recommended (dirty brush/tube)", "data_key": "4.1",
     "bit_mask": 12, "device_class": "problem", "icon": "mdi:broom"},
]

# Binary properties: (siid, piid): meta.
#   bit_mask=N  -> on when (value & N) != 0 (instead of value != 0)
KNOWN_BINARY_PROPS: dict[tuple[int, int], dict] = {
    # Confirmé par test isolé : 17.8 = ajout auto de détergent (1=activé, 0=désactivé)
    (17, 8): {"key": "auto_detergent_17", "name": "Auto detergent (sensor)", "icon": "mdi:bottle-tonic-plus", "diagnostic": True},
}

# ---------------------------------------------------------------------------
# Writable controls (set_properties)
# ---------------------------------------------------------------------------

# Boolean switches. optimistic=True means the device does not report the
# current value, so Home Assistant reflects the last command sent.
KNOWN_SWITCH_PROPS: dict[tuple[int, int], dict] = {
    (1, 3): {"key": "light_control", "name": "Light", "icon": "mdi:lightbulb", "optimistic": True},
    (1, 4): {"key": "auto_mix_detergent", "name": "Auto detergent mixing", "icon": "mdi:bottle-tonic-plus", "optimistic": True},
    (1, 7): {"key": "auto_backwash", "name": "Auto rinse", "icon": "mdi:water-sync"},
    (1, 9): {"key": "auto_dry_switch", "name": "Auto drying", "icon": "mdi:hair-dryer", "optimistic": True},
    (1, 11): {"key": "time_dry_after_clean", "name": "Timed dry after cleaning", "icon": "mdi:timer-cog", "optimistic": True},
    (16, 6): {"key": "custom_switch", "name": "Custom mode", "icon": "mdi:tune-variant"},
}

# Number controls: {min, max, step, unit} (+ optimistic when unreadable)
KNOWN_NUMBER_PROPS: dict[tuple[int, int], dict] = {
    (1, 14): {"key": "volume", "name": "Voice volume", "icon": "mdi:volume-high", "min": 0, "max": 100, "step": 1, "unit": "%", "optimistic": True},
    (1, 12): {"key": "time_dry_value", "name": "Timed-dry duration", "icon": "mdi:timer-sand", "min": 0, "max": 21600, "step": 600, "unit": "s", "optimistic": True},
        # Custom-mode settings. These are configuration controls rather than
    # primary operational controls.
    (16, 1): {"key": "clean_power", "name": "Suction power (custom)", "icon": "mdi:fan", "min": 0, "max": 3, "step": 1, "config": True},
    (16, 2): {"key": "clean_water", "name": "Water flow (custom)", "icon": "mdi:water", "min": 0, "max": 3, "step": 1, "config": True},
    (16, 4): {"key": "brush_speed", "name": "Brush speed (custom)", "icon": "mdi:rotate-right", "min": 0, "max": 3, "step": 1, "optimistic": True, "config": True},
}

# Select controls: {options: {int_value: label}}
KNOWN_SELECT_PROPS: dict[tuple[int, int], dict] = {
    (23, 1): {
        "key": "power_wheel",
        "name": "Traction force",
        "icon": "mdi:car-traction-control",
        "options": {0: "Light", 1: "Balanced", 2: "Strong"},
        "optimistic": True,
    },
}

# Buttons send a fixed value as a one-shot command
KNOWN_BUTTON_PROPS: dict[tuple[int, int], dict] = {
    (1, 1): {"key": "start_self_clean", "name": "Start self-cleaning", "icon": "mdi:water-sync", "press_value": 1},
    (1, 2): {"key": "start_self_dry", "name": "Start self-drying", "icon": "mdi:hair-dryer", "press_value": 1},
}

# Properties driven only by real-time MQTT push. Slow cloud polling must not
# overwrite these rapidly changing values.
MQTT_ONLY_KEYS: set[tuple[int, int]] = {(1, 29), (1, 30)}

CONF_REGION = "region"
CONF_COUNTRY = "country"
CONF_DEVICE_ID = "device_id"

REGIONS = {
    "auto": "Automatic",
    "eu": "Europe",
    "de": "Germany / Europe",
    "cn": "China",
    "us": "United States",
    "ru": "Russia",
    "tw": "Taiwan",
    "sg": "Singapore / Southeast Asia",
    "in": "India",
    "i2": "International",
    "kr": "South Korea",
}
