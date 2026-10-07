"""Model-specific profiles for Dreame wet & dry vacuums."""
from __future__ import annotations

from typing import Any

H15_PRO_HEAT_MODEL = "dreame.hold.w2449e"

# H15 mapping is intentionally being rebuilt from the device itself.
# Only mappings that are independently verified on w2449e should become
# "confirmed". Everything else stays candidate/raw even if an H14 model uses
# the same SIID/PIID.
H15_PROPERTY_META: dict[tuple[int, int], dict[str, Any]] = {
    (3, 1): {
        "name": "Battery",
        "confidence": "confirmed",
        "icon": "mdi:battery",
        "unit": "%",
        "device_class": "battery",
        "state_class": "measurement",
        "diagnostic": False,
        "note": "Confirmed battery percentage on dreame.hold.w2449e.",
    },
    (2, 1): {
        "name": "Status code raw",
        "confidence": "candidate",
        "icon": "mdi:state-machine",
        "diagnostic": False,
        "note": "Changes with device state. H15 status values still need a fresh mapping.",
    },
    (1, 28): {
        "name": "Status mirror raw",
        "confidence": "candidate",
        "icon": "mdi:state-machine",
        "diagnostic": True,
        "note": "Observed changing together with 2.1; exact H15 semantics are being remapped.",
    },
    (6, 7): {
        "name": "Raw 6.7",
        "confidence": "candidate",
        "icon": "mdi:rotate-right",
        "diagnostic": True,
        "note": "Looks like a consumable/time value, but the H15 meaning is being re-verified.",
    },
    (19, 3): {
        "name": "Raw 19.3",
        "confidence": "candidate",
        "icon": "mdi:air-filter",
        "diagnostic": True,
        "note": "Looks like a consumable/time value, but the H15 meaning is being re-verified.",
    },
    (4, 1): {
        "name": "Warnings raw",
        "confidence": "candidate",
        "icon": "mdi:alert-outline",
        "diagnostic": True,
        "bitfield": True,
        "note": "Possible warning bitfield. Individual H15 bits are not mapped yet.",
    },
    (4, 2): {
        "name": "Errors raw",
        "confidence": "candidate",
        "icon": "mdi:alert-circle-outline",
        "diagnostic": True,
        "bitfield": True,
        "note": "Possible error bitfield. Individual H15 bits are not mapped yet.",
    },
    (4, 3): {
        "name": "Alert push raw",
        "confidence": "candidate",
        "icon": "mdi:bell-alert-outline",
        "diagnostic": True,
        "bitfield": True,
        "note": "Raw alert/push property; exact H15 semantics are not mapped yet.",
    },
    (4, 5): {
        "name": "Raw 4.5",
        "confidence": "candidate",
        "icon": "mdi:water-cog",
        "diagnostic": True,
        "note": "Observed as a list value. H15 meaning is being remapped from scratch.",
    },
    (4, 6): {
        "name": "Raw 4.6",
        "confidence": "candidate",
        "icon": "mdi:water",
        "diagnostic": True,
        "note": "H15 meaning is being remapped from scratch.",
    },
    (4, 7): {
        "name": "Raw 4.7",
        "confidence": "candidate",
        "icon": "mdi:fan",
        "diagnostic": True,
        "note": "Observed as a list value. H15 meaning is being remapped from scratch.",
    },
    (16, 1): {
        "name": "Raw 16.1",
        "confidence": "candidate",
        "icon": "mdi:fan",
        "diagnostic": True,
        "note": "Value changes with settings, but H15 semantics and write behavior are unverified.",
    },
    (16, 2): {
        "name": "Raw 16.2",
        "confidence": "candidate",
        "icon": "mdi:water",
        "diagnostic": True,
        "note": "Value changes with settings, but H15 semantics and write behavior are unverified.",
    },
    (16, 6): {
        "name": "Raw 16.6",
        "confidence": "candidate",
        "icon": "mdi:tune-variant",
        "diagnostic": True,
        "note": "H15 semantics are being remapped from scratch.",
    },
    (16, 7): {
        "name": "Raw 16.7",
        "confidence": "candidate",
        "icon": "mdi:broom",
        "diagnostic": True,
        "note": "Changes with cleaning behavior; H15 mode values are not mapped yet.",
    },
    (16, 8): {
        "name": "Raw 16.8",
        "confidence": "unmapped",
        "icon": "mdi:code-tags",
        "diagnostic": True,
        "note": "Additional property observed on dreame.hold.w2449e.",
    },
}


def is_h15_pro_heat(model: str | None) -> bool:
    """Return whether a device uses the H15 Pro Heat profile."""
    return str(model or "").lower() == H15_PRO_HEAT_MODEL
