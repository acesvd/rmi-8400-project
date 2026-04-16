from __future__ import annotations

import os

import streamlit as st

_TRUTHY_VALUES = {"1", "true", "yes", "on"}
_ROLES = {"admin", "demo"}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY_VALUES


def is_demo_mode() -> bool:
    """Return True when demo-mode UI restrictions should be enabled."""
    return _env_bool("DEMO_MODE", True)


def current_auth_role() -> str:
    """Return current authenticated role (`admin` or `demo`)."""
    role = str(st.session_state.get("auth_role") or "").strip().lower()
    if role in _ROLES:
        return role
    # Safe default: unknown role behaves like demo role.
    return "demo"


def is_demo_user_mode() -> bool:
    """
    Return True when demo restrictions should apply to current user.

    Restrictions apply only when DEMO_MODE is on and current role is not admin.
    """
    return is_demo_mode() and current_auth_role() != "admin"


def is_chat_ui_enabled() -> bool:
    """Return True when the Streamlit Chat UI should be available."""
    return _env_bool("CHAT_UI_ENABLED", True)
