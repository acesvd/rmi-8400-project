from __future__ import annotations

import streamlit as st

from lib.api import create_case_form, ensure_state, fetch_case_payload, fetch_cases, select_case
from lib.components import (
    render_case_actions_sidebar,
    render_documents,
    render_event_form,
    render_overview,
    render_packet,
    render_tasks,
    render_tracking_table,
)


def _render_case_list(cases: list[dict]) -> None:
    st.subheader("Case List")
    for case in cases:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            col1.markdown(f"**{case.get('title', 'Untitled')}**")
            col2.write(f"Status: `{case.get('status', 'unknown')}`")
            col3.write(f"Updated: {case.get('updated_at', '')}")
            if col4.button("Open", key=f"open_{case.get('case_id')}"):
                st.session_state.selected_case_id = case.get("case_id")
                st.rerun()


def main() -> None:
    st.set_page_config(page_title="My Cases", page_icon="📁", layout="wide")
    ensure_state()

    st.title("My Cases")
    st.caption("Create, open, and manage case documents, extraction, tasks, packet artifacts, and tracking.")

    cases, cases_err = fetch_cases()

    with st.sidebar:
        st.subheader("Case Manager")
        create_case_form(key_prefix="mycases")

        st.divider()
        if cases_err:
            st.error(f"Could not load cases: {cases_err}")
        elif not cases:
            st.info("No cases yet. Create one above.")
        else:
            select_case(cases, key_prefix="mycases", label="Open case")

        st.divider()
        render_case_actions_sidebar(st.session_state.get("selected_case_id"), key_prefix="mycases")

    if cases_err:
        st.error(f"Cannot continue without cases API: {cases_err}")
        st.stop()

    if not cases:
        st.info("Create your first case to begin.")
        st.stop()

    _render_case_list(cases)

    case_id = st.session_state.get("selected_case_id")
    if not case_id:
        st.info("Click `Open` on a case or use the sidebar selector.")
        st.stop()

    case_payload, payload_err = fetch_case_payload(case_id)
    if payload_err or not case_payload:
        st.error(f"Could not load selected case: {payload_err}")
        st.stop()

    st.divider()
    st.markdown(f"### Case Detail: `{case_id}`")

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
