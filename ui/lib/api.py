from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st

API_BASE = os.getenv("APPEALS_API_URL", "http://localhost:8000")
TIMEOUT = int(os.getenv("APPEALS_API_TIMEOUT", "120"))

DOC_TYPES = ["denial_letter", "eob", "prior_auth", "medical_records", "other"]
TASK_STATUSES = ["todo", "waiting", "done"]
EVENT_TYPES = ["submitted", "followup", "decision", "phone_call"]


def api_get(path: str):
    r = requests.get(f"{API_BASE}{path}", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def api_post(path: str, *, json_body: dict[str, Any] | None = None, files=None, data=None):
    r = requests.post(f"{API_BASE}{path}", json=json_body, files=files, data=data, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def api_patch(path: str, *, json_body: dict[str, Any]):
    r = requests.patch(f"{API_BASE}{path}", json=json_body, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except requests.RequestException as exc:
        return None, str(exc)


def ensure_state() -> None:
    if "selected_case_id" not in st.session_state:
        st.session_state.selected_case_id = None


def case_label(case: dict[str, Any]) -> str:
    return f"{case['title']} ({case['status']}) - {case['case_id']}"


def fetch_cases() -> tuple[list[dict[str, Any]] | None, str | None]:
    return safe_call(api_get, "/cases")


def fetch_case_payload(case_id: str) -> tuple[dict[str, Any] | None, str | None]:
    return safe_call(api_get, f"/cases/{case_id}")


def fetch_health() -> tuple[dict[str, Any] | None, str | None]:
    return safe_call(api_get, "/health")


def select_case(cases: list[dict[str, Any]], *, key_prefix: str, label: str = "Select case") -> str | None:
    if not cases:
        st.session_state.selected_case_id = None
        return None

    options = {case_label(c): c["case_id"] for c in cases}
    labels = list(options.keys())
    ids = list(options.values())

    selected_id = st.session_state.get("selected_case_id")
    default_idx = ids.index(selected_id) if selected_id in ids else 0

    chosen_label = st.selectbox(label, labels, index=default_idx, key=f"{key_prefix}_case_selector")
    chosen_id = options[chosen_label]
    st.session_state.selected_case_id = chosen_id
    return chosen_id


def create_case_form(*, key_prefix: str) -> None:
    with st.form(f"{key_prefix}_create_case_form"):
        title = st.text_input("New case title")
        create_clicked = st.form_submit_button("Create Case")
        if create_clicked:
            title = title.strip()
            if not title:
                st.error("Case title is required")
                return

            created, create_err = safe_call(api_post, "/cases", json_body={"title": title})
            if create_err:
                st.error(create_err)
                return

            st.session_state.selected_case_id = created["case_id"]
            st.success("Case created")
            st.rerun()
