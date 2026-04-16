from __future__ import annotations

from collections.abc import Callable
from html import escape
import re
import time
from typing import Any
from uuid import uuid4

import streamlit as st

from lib.api import (
    api_post,
    ensure_state,
    fetch_case_payload,
    fetch_cases,
    fetch_health,
    open_case_workspace_create_flow,
    safe_call,
    select_case,
)
from lib.components import render_sources
from lib.feature_flags import is_chat_ui_enabled, is_demo_user_mode

CHAT_MODES = {"select", "general"}
CHAT_SESSION_KEY = "chat_session_id"
CHAT_ROLES = {"admin", "demo"}


def _inject_page_styles() -> None:
    st.markdown(
        """
        <style>
        .stMainBlockContainer {
            background:
                radial-gradient(circle at 4% 7%, rgba(108, 184, 255, 0.08), transparent 30%),
                radial-gradient(circle at 96% 10%, rgba(118, 219, 195, 0.09), transparent 34%);
        }
        .chat-hero {
            padding: 1.35rem 1.5rem;
            border-radius: 24px;
            background:
                radial-gradient(circle at 8% 12%, rgba(255, 205, 133, 0.34), transparent 35%),
                radial-gradient(circle at 97% -8%, rgba(125, 209, 198, 0.35), transparent 33%),
                radial-gradient(circle at 74% 88%, rgba(118, 192, 204, 0.18), transparent 42%),
                linear-gradient(126deg, #f8fcfc 0%, #e8f5f5 52%, #d7eceb 100%);
            color: #173533;
            margin-bottom: 1rem;
            border: 1px solid #c5dbd8;
            box-shadow: 0 16px 34px rgba(22, 46, 43, 0.16);
            position: relative;
            overflow: hidden;
        }
        .chat-hero::before {
            content: "";
            position: absolute;
            width: 250px;
            height: 250px;
            top: -128px;
            right: -95px;
            border-radius: 999px;
            background: rgba(136, 209, 198, 0.34);
        }
        .chat-hero::after {
            content: "";
            position: absolute;
            inset: 0;
            background:
                radial-gradient(circle, rgba(39, 122, 116, 0.1) 1.05px, transparent 1.2px),
                linear-gradient(90deg, rgba(255, 255, 255, 0.22) 0%, rgba(255, 255, 255, 0) 46%);
            background-size: 18px 18px, 100% 100%;
            opacity: 0.38;
            pointer-events: none;
            mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.35) 0%, rgba(0, 0, 0, 0) 72%);
        }
        .chat-hero > * {
            position: relative;
            z-index: 1;
        }
        .chat-kicker {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.75rem;
            color: #2a6662;
            margin-bottom: 0.35rem;
        }
        .chat-hero h2 {
            margin: 0;
            font-size: 2rem;
            line-height: 1.1;
            color: #173533;
        }
        .chat-hero p {
            margin: 0.55rem 0 0;
            max-width: 48rem;
            color: #325a58;
        }
        .section-label {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.72rem;
            font-weight: 700;
            color: color-mix(in srgb, var(--primary-color, #2f6f99) 68%, var(--text-color, currentColor) 32%);
            margin-bottom: 0.45rem;
        }
        .chat-glance-strip {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.64rem;
            margin: 0.2rem 0 1rem;
        }
        .chat-glance-card {
            border-radius: 14px;
            padding: 0.66rem 0.72rem;
            border: 1px solid #bad8e5;
            background:
                radial-gradient(circle at 85% 12%, rgba(102, 180, 245, 0.16), transparent 36%),
                linear-gradient(140deg, #f2fbff 0%, #e7f8f4 56%, #e8f1ff 100%);
            box-shadow: 0 8px 18px rgba(22, 78, 110, 0.11);
        }
        .chat-glance-kicker {
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            font-size: 0.64rem;
            font-weight: 800;
            color: #2f6f99;
        }
        .chat-glance-value {
            margin: 0.18rem 0 0;
            font-size: 1.12rem;
            font-weight: 800;
            line-height: 1.2;
            color: #193f61;
            overflow-wrap: anywhere;
        }
        .chat-glance-note {
            margin: 0.24rem 0 0;
            font-size: 0.78rem;
            line-height: 1.36;
            color: #48647c;
        }
        .chat-flow-rail {
            height: 7px;
            border-radius: 999px;
            margin: 0.15rem 0 0.86rem;
            background: linear-gradient(90deg, #71d9be 0%, #64c5eb 48%, #8fa7ff 100%);
            box-shadow: 0 8px 18px rgba(63, 126, 176, 0.23);
        }
        .chat-mode-kicker {
            margin: 0.02rem 0 0.2rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            font-size: 0.66rem;
            font-weight: 800;
            color: #347093;
        }
        .chat-mode-title {
            margin: 0;
            font-size: 1.38rem;
            line-height: 1.18;
            font-weight: 800;
            color: #1d3644;
        }
        .chat-mode-copy {
            margin: 0.34rem 0 0.72rem;
            font-size: 0.92rem;
            line-height: 1.42;
            color: #496174;
        }
        .chat-mode-current {
            margin: 0;
            padding: 0.52rem 0.7rem;
            border-radius: 12px;
            border: 1px solid #b8d8e6;
            background: linear-gradient(135deg, rgba(111, 196, 236, 0.15), rgba(126, 219, 194, 0.14));
            color: #2c5976;
            font-size: 0.9rem;
            line-height: 1.35;
        }
        .chat-mode-note {
            display: block;
            margin-top: 0.22rem;
            font-size: 0.82rem;
            color: #4f6f84;
        }
        .chat-panel-title {
            margin: 0;
            font-size: 1.5rem;
            line-height: 1.15;
            font-weight: 800;
            color: #1f3646;
        }
        .chat-panel-copy {
            margin: 0.35rem 0 0.6rem;
            font-size: 0.9rem;
            line-height: 1.45;
            color: #526577;
        }
        .chat-general-banner {
            margin: 0.38rem 0 0.1rem;
            padding: 0.62rem 0.75rem;
            border-radius: 12px;
            border: 1px solid #e5c890;
            background: linear-gradient(135deg, rgba(255, 227, 170, 0.28), rgba(255, 236, 196, 0.2));
            color: #8a5a00;
            font-size: 0.9rem;
            line-height: 1.42;
            font-weight: 600;
        }
        .stButton > button {
            border-radius: 12px !important;
            border: 1px solid rgba(48, 92, 130, 0.3) !important;
            box-shadow: 0 8px 18px rgba(30, 71, 106, 0.08);
            transition: transform 120ms ease, box-shadow 120ms ease;
        }
        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 20px rgba(30, 71, 106, 0.14);
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 16px;
            border: 1px solid rgba(124, 165, 196, 0.34);
            background:
                radial-gradient(circle at 96% -18%, rgba(121, 194, 234, 0.13), transparent 44%),
                linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(246, 252, 253, 0.92));
            box-shadow: 0 10px 20px rgba(18, 53, 85, 0.08);
        }
        [data-testid="stMetric"] {
            border: 1px solid #b8d8e6;
            border-radius: 13px;
            padding: 0.3rem 0.5rem;
            background:
                radial-gradient(circle at 85% 10%, rgba(111, 186, 240, 0.14), transparent 38%),
                linear-gradient(140deg, #f4fbff 0%, #ecf9f3 56%, #edf4ff 100%);
            box-shadow: 0 8px 18px rgba(24, 78, 112, 0.08);
        }
        [data-testid="stChatInput"] {
            border: 1px solid rgba(86, 130, 162, 0.32);
            border-radius: 12px;
            box-shadow: 0 8px 16px rgba(30, 73, 108, 0.08);
        }
        @media (max-width: 980px) {
            .chat-glance-strip {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 620px) {
            .chat-glance-strip {
                grid-template-columns: 1fr;
            }
        }
        [data-theme="dark"] .chat-glance-card {
            border-color: rgba(120, 172, 213, 0.54);
            background:
                radial-gradient(circle at 85% 12%, rgba(85, 146, 223, 0.3), transparent 36%),
                linear-gradient(140deg, rgba(19, 45, 67, 0.9) 0%, rgba(16, 58, 50, 0.9) 56%, rgba(30, 41, 77, 0.92) 100%);
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.33);
        }
        [data-theme="dark"] .chat-glance-kicker {
            color: rgba(173, 215, 250, 0.95);
        }
        [data-theme="dark"] .chat-glance-value {
            color: rgba(231, 245, 255, 0.98);
        }
        [data-theme="dark"] .chat-glance-note {
            color: rgba(192, 222, 242, 0.88);
        }
        [data-theme="dark"] .chat-flow-rail {
            background: linear-gradient(90deg, #2f9f80 0%, #2f83b6 48%, #5d77d8 100%);
            box-shadow: 0 8px 18px rgba(19, 53, 82, 0.46);
        }
        [data-theme="dark"] .chat-mode-kicker {
            color: rgba(169, 214, 248, 0.92);
        }
        [data-theme="dark"] .chat-mode-title {
            color: rgba(234, 247, 255, 0.98);
        }
        [data-theme="dark"] .chat-mode-copy,
        [data-theme="dark"] .chat-panel-copy {
            color: rgba(196, 224, 241, 0.9);
        }
        [data-theme="dark"] .chat-mode-current {
            border-color: rgba(129, 170, 204, 0.5);
            background: linear-gradient(135deg, rgba(61, 123, 171, 0.3), rgba(44, 132, 102, 0.28));
            color: rgba(209, 232, 248, 0.96);
        }
        [data-theme="dark"] .chat-mode-note {
            color: rgba(182, 215, 239, 0.9);
        }
        [data-theme="dark"] .chat-panel-title {
            color: rgba(236, 248, 255, 0.98);
        }
        [data-theme="dark"] .chat-general-banner {
            border-color: rgba(218, 186, 111, 0.56);
            background: linear-gradient(135deg, rgba(138, 104, 24, 0.35), rgba(104, 84, 35, 0.3));
            color: rgba(248, 231, 185, 0.98);
        }
        [data-theme="dark"] .stButton > button {
            border-color: rgba(129, 170, 203, 0.5) !important;
            box-shadow: 0 10px 22px rgba(0, 0, 0, 0.35);
        }
        [data-theme="dark"] [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: rgba(118, 167, 204, 0.44);
            background:
                radial-gradient(circle at 96% -18%, rgba(90, 145, 209, 0.24), transparent 44%),
                linear-gradient(180deg, rgba(13, 34, 54, 0.9), rgba(8, 25, 43, 0.88));
            box-shadow: 0 14px 28px rgba(0, 0, 0, 0.36);
        }
        [data-theme="dark"] [data-testid="stMetric"] {
            border-color: rgba(126, 172, 212, 0.55);
            background:
                radial-gradient(circle at 85% 10%, rgba(83, 146, 224, 0.3), transparent 38%),
                linear-gradient(140deg, rgba(20, 45, 68, 0.9) 0%, rgba(16, 58, 50, 0.9) 56%, rgba(30, 42, 78, 0.92) 100%);
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.33);
        }
        [data-theme="dark"] [data-testid="stChatInput"] {
            border-color: rgba(125, 165, 199, 0.45);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.36);
        }
        .chat-shell {
            padding: 1rem 1.1rem;
            border-radius: 22px;
            background: linear-gradient(180deg, rgba(255,255,255,0.97) 0%, rgba(243,247,244,0.9) 100%);
            border: 1px solid rgba(26, 40, 51, 0.08);
        }
        .chat-title {
            font-size: 1.25rem;
            font-weight: 800;
            color: #1a2833;
            margin: 0.1rem 0 0.35rem;
        }
        .chat-copy {
            color: #5a6662;
            margin-bottom: 0.25rem;
        }
        .status-pill {
            display: inline-block;
            padding: 0.22rem 0.6rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: capitalize;
            border: 1px solid transparent;
        }
        .status-open {
            background: #fff3d6;
            color: #8a5a00;
            border-color: #f1c56d;
        }
        .status-pending {
            background: #e7f2ff;
            color: #0f4e8a;
            border-color: #a6caef;
        }
        .status-done {
            background: #e7f6ee;
            color: #16623f;
            border-color: #9fd5b7;
        }
        .status-badge {
            display: inline-block;
            padding: 0.14rem 0.45rem;
            border-radius: 999px;
            font-size: 0.8rem;
            line-height: 1.2;
            font-weight: 700;
            border: 1px solid transparent;
        }
        .status-badge-good {
            background: #e7f6ee;
            color: #16623f;
            border-color: #9fd5b7;
        }
        .status-badge-bad {
            background: #fdecec;
            color: #9f2d2d;
            border-color: #efb3b3;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _status_class(status: str | None) -> str:
    normalized = (status or "open").strip().lower()
    if normalized in {"done", "completed", "closed"}:
        return "status-done"
    if normalized in {"waiting", "pending", "in review"}:
        return "status-pending"
    return "status-open"


def _render_active_case_header(case_payload: dict | None, case_id: str | None) -> None:
    if not case_id:
        st.markdown('<p class="section-label">Active Case</p>', unsafe_allow_html=True)
        st.info("Create or select a case to start case-context chat.")
        return

    case = (case_payload or {}).get("case", {})
    status = case.get("status", "open")
    pill = _status_class(status)
    extraction = (case_payload or {}).get("extraction")
    extraction_state = extraction.get("mode", "not run") if extraction else "not run"
    docs = len((case_payload or {}).get("documents", []))

    st.markdown(
        f"""
        <div class="chat-shell">
            <div class="section-label">Active Case</div>
            <div class="chat-title">{case.get('title', 'Untitled Case')}</div>
            <div class="chat-copy">
                <span class="status-pill {pill}">{status}</span>
                &nbsp;&nbsp;Case ID: <strong>{case_id}</strong>
            </div>
            <div class="chat-copy">Documents: <strong>{docs}</strong> | Extraction: <strong>{extraction_state}</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar_status_item(label: str, value: str, *, tone: str = "neutral") -> None:
    if tone in {"good", "bad"}:
        badge_class = "status-badge-good" if tone == "good" else "status-badge-bad"
        st.markdown(f'{label}: <span class="status-badge {badge_class}">{value}</span>', unsafe_allow_html=True)
        return
    st.write(f"{label}: `{value}`")


def _mode_label(mode: str | None) -> str:
    labels = {
        "select": "Select Case",
        "general": "General Chat",
    }
    return labels.get(mode or "", "Not selected")


def _render_mode_choice(cases: list[dict[str, Any]], cases_err: str | None) -> None:
    demo_mode = is_demo_user_mode()
    st.markdown('<p class="section-label">Choose Chat Type</p>', unsafe_allow_html=True)
    st.markdown("### Start Here")

    select_col, general_col = st.columns(2, gap="large")

    with select_col:
        with st.container(border=True):
            st.subheader("Select a Case")
            st.caption("Pick an existing case and chat with full case-specific context.")
            select_disabled = bool(cases_err) or not bool(cases)
            if st.button(
                "Choose Select Case",
                icon=":material/folder_open:",
                use_container_width=True,
                key="chat_mode_select_btn",
                disabled=select_disabled,
            ):
                st.session_state["chat_entry_mode"] = "select"
                st.rerun()

            if cases_err:
                st.caption("Unavailable while case API is down.")
            elif not cases:
                st.caption("No cases yet. Create one in Case Workspace.")

            if st.button(
                "Create Case in Workspace",
                icon=":material/add_circle:",
                use_container_width=True,
                key="chat_mode_choice_create_case_btn",
                disabled=demo_mode,
            ):
                open_case_workspace_create_flow()
            if demo_mode:
                st.caption("Demo mode is enabled. New case creation is temporarily disabled.")

    with general_col:
        with st.container(border=True):
            st.subheader("General Chat")
            st.caption("Ask general appeal questions without case context.")
            if st.button(
                "Choose General Chat",
                icon=":material/chat:",
                use_container_width=True,
                key="chat_mode_general_btn",
            ):
                st.session_state["chat_entry_mode"] = "general"
                st.rerun()


def _render_mode_bar(mode: str) -> None:
    bar_col1, bar_col2 = st.columns([4, 1], gap="large")
    with bar_col1:
        st.caption(f"Current chat type: **{_mode_label(mode)}**")
    with bar_col2:
        if st.button("Change Option", icon=":material/swap_horiz:", use_container_width=True):
            st.session_state["chat_entry_mode"] = None
            st.rerun()


def _display_value(value: Any) -> str:
    if value is None:
        return "—"
    text = str(value).strip()
    if not text or text.lower() == "unknown":
        return "—"
    return text


def _reason_label(label: str | None) -> str:
    mapping = {
        "administrative": "Administrative",
        "medical_necessity": "Medical Necessity",
        "prior_authorization": "Prior Authorization",
        "coding_billing": "Coding / Billing",
        "out_of_network": "Out of Network",
    }
    normalized = (label or "").strip().lower()
    if normalized in mapping:
        return mapping[normalized]
    if not normalized:
        return "Unspecified"
    return normalized.replace("_", " ").title()


def _get_chat_session_id() -> str:
    session_id = st.session_state.get(CHAT_SESSION_KEY)
    if session_id:
        return str(session_id)
    session_id = f"chat_{uuid4().hex}"
    st.session_state[CHAT_SESSION_KEY] = session_id
    return session_id


def _get_chat_user_role() -> str:
    role = str(st.session_state.get("auth_role") or "demo").strip().lower()
    if role not in CHAT_ROLES:
        return "demo"
    return role


def _render_case_context(case_payload: dict[str, Any]) -> None:
    with st.container(border=True):
        st.markdown('<p class="section-label">Context</p>', unsafe_allow_html=True)
        st.subheader("Case Context")
        extraction = case_payload.get("extraction")
        if not extraction:
            st.info("No extraction yet. Run extraction from Case Workspace for richer context.")
            return

        case_json = extraction.get("case_json") or {}
        reasons = case_json.get("denial_reasons") or []
        deadlines = case_json.get("deadlines") or []
        parties = case_json.get("parties") if isinstance(case_json.get("parties"), dict) else {}
        identifiers = case_json.get("identifiers") if isinstance(case_json.get("identifiers"), dict) else {}
        channels = case_json.get("submission_channels") if isinstance(case_json.get("submission_channels"), list) else []
        requested_docs = case_json.get("requested_documents") if isinstance(case_json.get("requested_documents"), list) else []

        c1, c2, c3 = st.columns(3)
        c1.metric("Payer", str(case_json.get("payer") or "unknown"))
        c2.metric("Denial Reasons", str(len(reasons)))
        c3.metric("Deadlines", str(len(deadlines)))

        with st.expander("View extracted context details", expanded=False):
            with st.container(border=True):
                st.markdown("#### Parties")
                st.write(f"Patient: **{_display_value(parties.get('patient_name'))}**")
                st.write(f"Claimant: **{_display_value(parties.get('claimant_name'))}**")
                st.write(f"Payer: **{_display_value(case_json.get('payer'))}**")
                st.write(f"Plan Type: **{_display_value(case_json.get('plan_type'))}**")

            with st.container(border=True):
                st.markdown("#### Claim Identifiers")
                st.write(f"Claim Number: **{_display_value(identifiers.get('claim_number'))}**")
                st.write(f"Auth Number: **{_display_value(identifiers.get('auth_number'))}**")
                st.write(f"Member ID: **{_display_value(identifiers.get('member_id'))}**")

            st.markdown("#### Denial Reasons")
            if reasons:
                for idx, reason in enumerate(reasons, 1):
                    if isinstance(reason, dict):
                        label = _reason_label(reason.get("label"))
                        quote = _display_value(reason.get("supporting_quote"))
                        citation = reason.get("citation") if isinstance(reason.get("citation"), dict) else {}
                        file_name = _display_value(citation.get("file_name"))
                        page_no = _display_value(citation.get("page_number"))
                    else:
                        label = _reason_label(str(reason))
                        quote = "—"
                        file_name = "—"
                        page_no = "—"

                    with st.container(border=True):
                        st.markdown(f"**{idx}. {label}**")
                        if quote != "—":
                            st.caption(quote)
                        if file_name != "—" or page_no != "—":
                            st.caption(f"Source: {file_name} · p.{page_no}")
            else:
                st.info("No denial reasons were extracted yet.")

            with st.container(border=True):
                st.markdown("#### Deadlines")
                if deadlines:
                    rows = []
                    for item in deadlines:
                        if isinstance(item, dict):
                            citation = item.get("citation") if isinstance(item.get("citation"), dict) else {}
                            source_file = _display_value(citation.get("file_name"))
                            source_page = _display_value(citation.get("page_number"))
                            source = "—"
                            if source_file != "—" or source_page != "—":
                                source = f"{source_file} · p.{source_page}"
                            rows.append({"Deadline": _display_value(item.get("value")), "Source": source})
                        else:
                            rows.append({"Deadline": _display_value(item), "Source": "—"})
                    st.dataframe(rows, hide_index=True, use_container_width=True)
                else:
                    st.info("No explicit deadlines detected.")

            with st.container(border=True):
                st.markdown("#### Submission Channels")
                if channels:
                    for channel in channels:
                        st.write(f"- {_display_value(channel).title()}")
                else:
                    st.info("No submission channels detected.")

                st.markdown("#### Requested Documents")
                if requested_docs:
                    for doc in requested_docs:
                        st.write(f"- {_display_value(doc).replace('_', ' ').title()}")
                else:
                    st.info("No missing document requests detected.")


def _ask_case_question(case_id: str, question: str) -> tuple[dict[str, Any] | None, str | None]:
    session_id = _get_chat_session_id()
    user_role = _get_chat_user_role()
    return safe_call(
        api_post,
        f"/cases/{case_id}/chat",
        json_body={"question": question, "session_id": session_id, "user_role": user_role},
        headers={"X-Chat-Session-Id": session_id, "X-User-Role": user_role},
    )


def _ask_general_question(question: str) -> tuple[dict[str, Any] | None, str | None]:
    session_id = _get_chat_session_id()
    user_role = _get_chat_user_role()
    body, err = safe_call(
        api_post,
        "/chat",
        json_body={"question": question, "session_id": session_id, "user_role": user_role},
        headers={"X-Chat-Session-Id": session_id, "X-User-Role": user_role},
    )
    if err and "/chat" in err and "404" in err:
        return (
            {
                "answer": (
                    "General Chat is not available on the currently running backend. "
                    "Restart the backend so it picks up the new `POST /chat` endpoint, then try again."
                ),
                "sources": [],
                "mode": "general_setup_required",
                "warning": "Backend restart required for General Chat.",
            },
            None,
        )
    return body, err


def _render_conversation(
    *,
    chat_key: str,
    prompt_caption: str,
    input_placeholder: str,
    question_handler: Callable[[str], tuple[dict[str, Any] | None, str | None]],
    show_inline_warnings: bool = True,
) -> None:
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []
    pending_key = f"{chat_key}_pending_question"
    pending_question = st.session_state.get(pending_key)

    if pending_question:
        st.session_state[chat_key].append({"role": "user", "content": pending_question})
        st.session_state[pending_key] = None

    def _messages_container(height: int = 440):
        try:
            return st.container(height=height, border=True)
        except TypeError:
            # Older Streamlit versions may not support fixed-height containers.
            return st.container(border=True)

    with st.container(border=True):
        header_col1, header_col2 = st.columns([3, 1])
        header_col1.markdown("### Conversation")
        header_col1.caption(prompt_caption)
        if header_col2.button("Clear Chat", key=f"chat_clear_{chat_key}", use_container_width=True):
            st.session_state[chat_key] = []
            st.session_state[pending_key] = None
            st.rerun()

        with _messages_container():
            for msg in st.session_state[chat_key]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if msg["role"] == "assistant":
                        st.caption(f"Mode: {msg.get('mode', 'unknown')}")
                        if show_inline_warnings and msg.get("warning"):
                            st.warning(msg["warning"])
                        if msg.get("sources"):
                            with st.expander("Sources", expanded=False):
                                render_sources(msg.get("sources", []))

            if pending_question:
                with st.chat_message("assistant"):
                    thinking_placeholder = st.empty()
                    thinking_placeholder.markdown("_Thinking..._")

                    body, chat_err = question_handler(pending_question)
                    assistant_message: dict[str, Any]
                    if chat_err:
                        assistant_message = {
                            "role": "assistant",
                            "content": f"Chat request failed: {chat_err}",
                            "sources": [],
                            "mode": "error",
                        }
                    else:
                        assistant_message = {
                            "role": "assistant",
                            "content": str((body or {}).get("answer", "")),
                            "sources": (body or {}).get("sources", []),
                            "mode": (body or {}).get("mode", "unknown"),
                            "warning": (body or {}).get("warning"),
                        }

                    thinking_placeholder.empty()
                    response_text = assistant_message.get("content", "")
                    if response_text:
                        tokens = re.findall(r"\S+\s*|\n", response_text)
                        if tokens:
                            delay = min(0.02, max(0.004, 1.8 / len(tokens)))

                            def _typing_stream():
                                for token in tokens:
                                    yield token
                                    time.sleep(delay)

                            streamed = st.write_stream(_typing_stream())
                            if isinstance(streamed, str) and streamed.strip():
                                assistant_message["content"] = streamed
                        else:
                            st.markdown(response_text)
                    else:
                        st.markdown("No response returned.")

                    st.caption(f"Mode: {assistant_message.get('mode', 'unknown')}")
                    if show_inline_warnings and assistant_message.get("warning"):
                        st.warning(assistant_message["warning"])
                    if assistant_message.get("sources"):
                        with st.expander("Sources", expanded=False):
                            render_sources(assistant_message.get("sources", []))

                st.session_state[chat_key].append(assistant_message)
                st.rerun()

        question = st.chat_input(input_placeholder)
        if question:
            st.session_state[pending_key] = question
            st.rerun()


def _render_conversation_waiting(message: str) -> None:
    with st.container(border=True):
        st.markdown("### Conversation")
        st.caption("Case-context chat becomes available after you choose a case on the right.")
        st.info(message)


def main() -> None:
    st.set_page_config(page_title="AI Chatbox", page_icon="💬", layout="wide")
    ensure_state()
    _inject_page_styles()
    chat_ui_enabled = is_chat_ui_enabled()
    demo_mode = is_demo_user_mode()

    if not chat_ui_enabled:
        st.warning("Chat is temporarily disabled by the presenter for this demo.")
        if st.button(
            "Back to Dashboard",
            icon=":material/dashboard:",
            key="chat_disabled_back_dashboard_btn",
            use_container_width=True,
        ):
            st.switch_page("pages/2_My_Cases.py")
        st.stop()

    st.session_state.setdefault("chat_entry_mode", None)

    st.markdown(
        """
        <div class="chat-hero">
            <div class="chat-kicker">Case Assistant</div>
            <h2>AI Chatbox</h2>
            <p>Choose how you want to chat: use an existing case with context, or ask general questions without case context.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    nav_spacer, nav_col = st.columns([4, 1.3], gap="small")
    with nav_col:
        if st.button(
            "Back to Dashboard",
            icon=":material/dashboard:",
            key="chat_back_dashboard_btn",
            use_container_width=True,
        ):
            st.switch_page("pages/2_My_Cases.py")

    cases, cases_err = fetch_cases()
    health, health_err = fetch_health()
    cases = cases or []

    mode = st.session_state.get("chat_entry_mode")
    if mode not in CHAT_MODES:
        mode = None

    selected_case_id = st.session_state.get("selected_case_id")
    if selected_case_id and cases and not any(c.get("case_id") == selected_case_id for c in cases):
        st.session_state["selected_case_id"] = None
        selected_case_id = None

    case_payload = None
    payload_err = None

    chat_ready = False
    if mode == "general":
        chat_ready = True
    elif mode == "select" and selected_case_id and not cases_err:
        chat_ready = True

    with st.sidebar:
        st.markdown("### Status")
        _render_sidebar_status_item("Chat Type", _mode_label(mode))
        _render_sidebar_status_item("Available Cases", str(len(cases)))
        _render_sidebar_status_item("Chat Ready", "Yes" if chat_ready else "No", tone="good" if chat_ready else "bad")
        if health_err:
            st.error("API/Ollama status unavailable")
        else:
            _render_sidebar_status_item("API", "Online", tone="good")
            _render_sidebar_status_item(
                "Ollama",
                "Available" if health.get("ollama_available") else "Unavailable",
                tone="good" if health.get("ollama_available") else "bad",
            )

    if mode is None:
        _render_mode_choice(cases, cases_err)
        return

    _render_mode_bar(mode)

    if mode == "select":
        left_col, right_col = st.columns([2, 1], gap="large")
        with right_col:
            with st.container(border=True):
                st.markdown('<p class="section-label">Select Case</p>', unsafe_allow_html=True)
                st.subheader("Choose Existing Case")
                if cases_err:
                    st.error(f"Could not load cases: {cases_err}")
                elif not cases:
                    st.info("No existing cases found yet. Create one in your workspace first.")
                    if st.button(
                        "Create Case in Workspace",
                        icon=":material/add_circle:",
                        use_container_width=True,
                        key="chat_select_empty_create_case_btn",
                        disabled=demo_mode,
                    ):
                        open_case_workspace_create_flow()
                else:
                    select_case(cases, key_prefix="chat_select_mode", label="Active case")
                    if st.button(
                        "Need a new case? Create in Workspace",
                        icon=":material/add_circle:",
                        use_container_width=True,
                        key="chat_select_create_case_btn",
                        disabled=demo_mode,
                    ):
                        open_case_workspace_create_flow()

            selected_case_id = st.session_state.get("selected_case_id")
            if selected_case_id:
                case_payload, payload_err = fetch_case_payload(selected_case_id)

            if payload_err:
                st.error(f"Could not load selected case: {payload_err}")
            _render_active_case_header(case_payload, selected_case_id)
            if selected_case_id and case_payload and not payload_err:
                _render_case_context(case_payload)

        with left_col:
            selected_case_id = st.session_state.get("selected_case_id")
            if cases_err:
                _render_conversation_waiting("Case data is unavailable right now.")
                return
            if not cases:
                _render_conversation_waiting("No existing cases found. Create one in Case Workspace to begin.")
                return
            if not selected_case_id:
                _render_conversation_waiting("Choose an existing case on the right to begin chatting.")
                return
            if payload_err or not case_payload:
                _render_conversation_waiting("We couldn't load the selected case yet.")
                return
            _render_conversation(
                chat_key=f"assistant_messages_case_{selected_case_id}",
                prompt_caption="Examples: `Summarize this denial.` or `What should I do next?`",
                input_placeholder="Ask about denial reasons, evidence, policy context, and next steps...",
                question_handler=lambda q: _ask_case_question(selected_case_id, q),
            )
        return

    # mode == "general"
    with st.container(border=True):
        st.markdown('<p class="section-label">General Chat</p>', unsafe_allow_html=True)
        st.subheader("General Appeal Guidance")
        st.warning("This is general guidance without case-specific context. Create or select a case for personalized appeal support.")

    _render_conversation(
        chat_key="assistant_messages_general",
        prompt_caption="Examples: `How do appeals usually work?` or `What documents are commonly needed?`",
        input_placeholder="Ask a general question about denied-claim appeals...",
        question_handler=_ask_general_question,
        show_inline_warnings=False,
    )


if __name__ == "__main__":
    main()
