from __future__ import annotations

import os

_TRUTHY_VALUES = {"1", "true", "yes", "on"}


def is_demo_mode() -> bool:
    """Return True when demo-mode UI restrictions should be enabled."""
    value = os.getenv("DEMO_MODE", "true")
    return value.strip().lower() in _TRUTHY_VALUES
