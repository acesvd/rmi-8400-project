from __future__ import annotations

import streamlit as st

from lib.api import create_case_form, ensure_state, fetch_case_payload, fetch_cases, select_case
from lib.components import (
    render_case_actions_panel,
    render_documents,
    render_event_form,
    render_overview,
    render_packet,
    render_tasks,
    render_tracking_table,
)


def _inject_page_styles() -> None:
    st.markdown(
        """
        <style>
        .mycases-hero {
            padding: 1.4rem 1.5rem;
            border-radius: 24px;
            background:
                radial-gradient(circle at top right, rgba(247, 196, 82, 0.28), transparent 34%),
                linear-gradient(135deg, #12343b 0%, #1f5c57 55%, #ecb64f 100%);
            color: #f7f4ea;
            margin-bottom: 1rem;
            box-shadow: 0 18px 38px rgba(18, 52, 59, 0.22);
        }
        .mycases-kicker {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.75rem;
            opacity: 0.82;
            margin-bottom: 0.35rem;
        }
        .mycases-hero h2 {
            margin: 0;
            font-size: 2rem;
            line-height: 1.1;
        }
        .mycases-hero p {
            margin: 0.55rem 0 0;
            max-width: 46rem;
            color: rgba(247, 244, 234, 0.9);
        }
        .section-label {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.72rem;
            font-weight: 700;
            color: #7c6f57;
            margin-bottom: 0.5rem;
        }
        .case-card {
            padding: 0.2rem 0 0.1rem;
        }
        .case-title {
            font-size: 1.02rem;
            font-weight: 700;
            color: #12343b;
            margin-bottom: 0.35rem;
        }
        .case-meta {
            color: #58656a;
            font-size: 0.9rem;
            margin-top: 0.35rem;
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
            background: #eaf4ff;
            color: #0f4e8a;
            border-color: #a8caef;
        }
        .status-done {
            background: #e7f6ee;
            color: #16623f;
            border-color: #9fd5b7;
        }
        .active-case-shell {
            padding: 1rem 1.1rem;
            border-radius: 22px;
            background: linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(247,244,234,0.88) 100%);
            border: 1px solid rgba(18, 52, 59, 0.09);
        }
        .active-case-title {
            font-size: 1.3rem;
            font-weight: 800;
            color: #12343b;
            margin: 0.1rem 0 0.35rem;
        }
        .active-case-copy {
            color: #58656a;
            margin-bottom: 0.25rem;
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


def _render_selected_case_header(case_payload: dict | None, case_id: str | None) -> None:
    if not case_id:
        st.markdown('<p class="section-label">Selected Case</p>', unsafe_allow_html=True)
        st.info("Choose a case from the list or selector to open its workspace.")
        return

    case = (case_payload or {}).get("case", {})
    documents = len((case_payload or {}).get("documents", []))
    tasks = len((case_payload or {}).get("tasks", []))
    status = case.get("status", "open")
    pill = _status_class(status)

    st.markdown(
        f"""
        <div class="active-case-shell">
            <div class="section-label">Selected Case</div>
            <div class="active-case-title">{case.get('title', 'Untitled Case')}</div>
            <div class="active-case-copy">
                <span class="status-pill {pill}">{status}</span>
                &nbsp;&nbsp;Case ID: <strong>{case_id}</strong>
            </div>
            <div class="active-case-copy">Documents: <strong>{documents}</strong> | Tasks: <strong>{tasks}</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_case_list(cases: list[dict]) -> None:
    st.markdown('<p class="section-label">Case Library</p>', unsafe_allow_html=True)
    st.markdown("### Your Cases")
    st.caption("Open a case from here, or use the selector above if you already know which one you want.")
    for case in cases:
        status = case.get("status", "open")
        pill = _status_class(status)
        with st.container(border=True):
            col1, col2 = st.columns([4.2, 1], gap="medium")
            col1.markdown(
                f"""
                <div class="case-card">
                    <div class="case-title">{case.get('title', 'Untitled')}</div>
                    <span class="status-pill {pill}">{status}</span>
                    <div class="case-meta">Updated {case.get('updated_at', '')}</div>
                    <div class="case-meta">Case ID: {case.get('case_id')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if col2.button("Open", key=f"open_{case.get('case_id')}", use_container_width=True):
                st.session_state.selected_case_id = case.get("case_id")
                st.rerun()


def main() -> None:
    st.set_page_config(page_title="My Cases", page_icon="📁", layout="wide")
    ensure_state()
    _inject_page_styles()

    st.markdown(
        """
        <div class="mycases-hero">
            <div class="mycases-kicker">Claims Workspace</div>
            <h2>My Cases</h2>
            <p>Keep every claim in one place, move through the workflow step by step, and stay oriented while you upload, extract, generate, and track.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cases, cases_err = fetch_cases()
    case_id = st.session_state.get("selected_case_id")
    case_payload = None
    payload_err = None
    if case_id:
        case_payload, payload_err = fetch_case_payload(case_id)

    summary1, summary2, summary3 = st.columns(3)
    summary1.metric("Total Cases", len(cases or []))
    summary2.metric("Active Case", case_payload["case"]["title"] if case_payload else "None selected")
    summary3.metric("Documents in Focus", len(case_payload.get("documents", [])) if case_payload else 0)

    top_col1, top_col2 = st.columns([1, 1], gap="large")
    with top_col1:
        with st.container(border=True):
            st.markdown('<p class="section-label">Start Here</p>', unsafe_allow_html=True)
            st.subheader("Create Case")
            st.caption("Spin up a new appeal workspace in a few seconds.")
            create_case_form(key_prefix="mycases")

    with top_col2:
        with st.container(border=True):
            st.markdown('<p class="section-label">Jump Back In</p>', unsafe_allow_html=True)
            st.subheader("Open Case")
            st.caption("Switch the page focus without leaving the workspace.")
            if cases_err:
                st.error(f"Could not load cases: {cases_err}")
            elif not cases:
                st.info("No cases yet. Create one to get started.")
            else:
                select_case(cases, key_prefix="mycases", label="Current case")

    if cases_err:
        st.error(f"Cannot continue without cases API: {cases_err}")
        st.stop()

    if not cases:
        st.info("Create your first case to begin.")
        st.stop()

    st.divider()
    case_id = st.session_state.get("selected_case_id")
    if case_id and (case_payload is None and payload_err is None):
        case_payload, payload_err = fetch_case_payload(case_id)

    list_col, workspace_col = st.columns([1, 1.4], gap="large")
    with list_col:
        with st.container(border=True):
            _render_case_list(cases)

    with workspace_col:
        _render_selected_case_header(case_payload, case_id)
        if not case_id:
            st.stop()
        if payload_err or not case_payload:
            st.error(f"Could not load selected case: {payload_err}")
            st.stop()
        with st.container(border=True):
            render_case_actions_panel(case_id, key_prefix="mycases")

    st.divider()
    st.markdown('<p class="section-label">Case Detail</p>', unsafe_allow_html=True)
    st.markdown(f"### Workspace for `{case_id}`")

    tab_overview, tab_documents, tab_tasks, tab_packet, tab_tracking = st.tabs(
        ["Overview", "Documents", "Tasks", "Packet Builder", "Tracking"]
    )

    with tab_overview:
        render_overview(case_payload)

    with tab_documents:
        render_documents(case_payload)

    with tab_tasks:
        render_tasks(case_id, case_payload, key_prefix="mycases")

    with tab_packet:
        render_packet(case_payload)

    with tab_tracking:
        render_event_form(case_id, key_prefix="mycases")
        st.divider()
        render_tracking_table(case_payload)


if __name__ == "__main__":
    main()
