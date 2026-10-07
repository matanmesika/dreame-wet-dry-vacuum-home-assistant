"""Model-specific profiles for Dreame wet & dry vacuums."""
from __future__ import annotations

from typing import Any

H15_PRO_HEAT_MODEL = "dreame.hold.w2449e"

# The H15 profile is intentionally conservative. A semantic name is only used
# when it is confirmed on the H15 itself or clearly marked as a candidate.
# Unknown properties remain raw so H14 assumptions are not presented as H15 facts.
H15_PROPERTY_META: dict[tuple[int, int], dict[str, Any]] = {
    (3, 1): {
        "name": "Battery",
        "confidence": "confirmed",
        "icon": "mdi:battery",
        "unit": "%",
        "device_class": "battery",
        "state_class": "measurement",
        "diagnostic": False,
        "note": "Battery percentage.",
    },
    (2, 1): {
        "name": "Status code",
        "confidence": "confirmed",
        "icon": "mdi:state-machine",
        "diagnostic": False,
        "note": "Primary H15 status code. H14 status labels are not applied.",
    },
    (1, 28): {
        "name": "Status mirror",
        "confidence": "confirmed",
        "icon": "mdi:state-machine",
        "diagnostic": True,
        "note": "Observed mirroring property 2.1 on the H15 Pro Heat.",
    },
    (6, 7): {
        "name": "Front roller brush remaining",
        "confidence": "confirmed",
        "icon": "mdi:rotate-right",
        "unit": "min",
        "diagnostic": True,
        "remaining_time": True,
        "note": "Remaining front roller brush life in minutes.",
    },
    (19, 3): {
        "name": "Filter remaining",
        "confidence": "confirmed",
        "icon": "mdi:air-filter",
        "unit": "min",
        "diagnostic": True,
        "remaining_time": True,
        "note": "Remaining filter life in minutes.",
    },
    (4, 1): {
        "name": "Warnings raw",
        "confidence": "candidate",
        "icon": "mdi:alert-outline",
        "diagnostic": True,
        "bitfield": True,
        "note": "Candidate warning bitfield; individual H15 bits are still being validated.",
    },
    (4, 2): {
        "name": "Errors raw",
        "confidence": "candidate",
        "icon": "mdi:alert-circle-outline",
        "diagnostic": True,
        "bitfield": True,
        "note": "Candidate error bitfield; individual H15 bits are still being validated.",
    },
    (4, 3): {
        "name": "Alert push raw",
        "confidence": "candidate",
        "icon": "mdi:bell-alert-outline",
        "diagnostic": True,
        "bitfield": True,
        "note": "Raw H15 alert/push property.",
    },
    (4, 5): {
        "name": "Water setting raw",
        "confidence": "candidate",
        "icon": "mdi:water-cog",
        "diagnostic": True,
        "note": "Observed as a list value on H15; exact semantics are not yet confirmed.",
    },
    (4, 6): {
        "name": "Water state raw",
        "confidence": "candidate",
        "icon": "mdi:water",
        "diagnostic": True,
        "note": "H15 water-related state; exact semantics are not yet confirmed.",
    },
    (4, 7): {
        "name": "Suction setting raw",
        "confidence": "candidate",
        "icon": "mdi:fan",
        "diagnostic": True,
        "note": "Observed as a list value on H15; exact semantics are not yet confirmed.",
    },
    (16, 1): {
        "name": "Custom suction setting raw",
        "confidence": "candidate",
        "icon": "mdi:fan",
        "diagnostic": True,
        "note": "Likely custom-mode suction setting. Read-only until H15 writes are validated.",
    },
    (16, 2): {
        "name": "Custom water setting raw",
        "confidence": "candidate",
        "icon": "mdi:water",
        "diagnostic": True,
        "note": "Likely custom-mode water setting. Read-only until H15 writes are validated.",
    },
    (16, 6): {
        "name": "Custom mode flag raw",
        "confidence": "candidate",
        "icon": "mdi:tune-variant",
        "diagnostic": True,
        "note": "Likely custom-mode state; H15 semantics are still being validated.",
    },
    (16, 7): {
        "name": "Cleaning mode code raw",
        "confidence": "candidate",
        "icon": "mdi:broom",
        "diagnostic": True,
        "note": "Likely active cleaning-mode code; H15 values are still being mapped.",
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
    """Return whether a device uses the validated H15 Pro Heat profile."""
    return str(model or "").lower() == H15_PRO_HEAT_MODEL
