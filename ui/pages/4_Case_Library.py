from __future__ import annotations

import streamlit as st

from lib.api import delete_case, ensure_state, fetch_cases, open_case_workspace_create_flow, select_case


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .library-hero {
            padding: 1.35rem 1.45rem;
            border-radius: 24px;
            background:
                radial-gradient(circle at 8% 12%, rgba(254, 209, 138, 0.32), transparent 35%),
                radial-gradient(circle at 97% -8%, rgba(154, 177, 231, 0.38), transparent 33%),
                radial-gradient(circle at 72% 88%, rgba(166, 193, 238, 0.2), transparent 42%),
                linear-gradient(126deg, #f8fbff 0%, #e9effb 52%, #dbe5f8 100%);
            color: #1a3154;
            margin-bottom: 1rem;
            border: 1px solid #c8d4ea;
            box-shadow: 0 16px 32px rgba(20, 45, 80, 0.16);
            position: relative;
            overflow: hidden;
        }
        .library-hero::before {
            content: "";
            position: absolute;
            width: 255px;
            height: 255px;
            top: -128px;
            right: -92px;
            border-radius: 999px;
            background: rgba(165, 188, 233, 0.34);
        }
        .library-hero::after {
            content: "";
            position: absolute;
            inset: 0;
            background:
                radial-gradient(circle, rgba(60, 96, 166, 0.1) 1.05px, transparent 1.2px),
                linear-gradient(90deg, rgba(255, 255, 255, 0.22) 0%, rgba(255, 255, 255, 0) 46%);
            background-size: 18px 18px, 100% 100%;
            opacity: 0.36;
            pointer-events: none;
            mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.35) 0%, rgba(0, 0, 0, 0) 72%);
        }
        .library-hero > * {
            position: relative;
            z-index: 1;
        }
        .library-kicker {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.74rem;
            font-weight: 700;
            color: #325a95;
            margin-bottom: 0.35rem;
        }
        .library-hero h2 {
            margin: 0;
            font-size: 1.95rem;
            line-height: 1.08;
            color: #1a3154;
        }
        .library-hero p {
            margin: 0.55rem 0 0;
            max-width: 46rem;
            color: #425d82;
            line-height: 1.54;
        }
        .section-label {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.72rem;
            font-weight: 700;
            opacity: 0.72;
            margin-bottom: 0.45rem;
        }
        .case-title {
            margin: 0;
            font-size: 1.02rem;
            font-weight: 800;
            line-height: 1.25;
        }
        .case-meta {
            margin: 0.28rem 0 0;
            opacity: 0.84;
            font-size: 0.88rem;
        }
        .status-pill {
            display: inline-block;
            margin-top: 0.42rem;
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


def _set_active_case(case_id: str) -> None:
    st.session_state.selected_case_id = case_id


def _open_workspace(case_id: str) -> None:
    st.session_state.selected_case_id = case_id
    st.switch_page("pages/5_Case_Workspace.py")


def _confirm_delete(case_id: str) -> None:
    st.session_state.case_library_confirm_delete_id = case_id


def _cancel_delete() -> None:
    st.session_state.case_library_confirm_delete_id = None


def _delete_case(case_id: str) -> None:
    _, delete_err = delete_case(case_id)
    if delete_err:
        st.error(f"Could not delete case: {delete_err}")
        return

    if st.session_state.get("selected_case_id") == case_id:
        st.session_state.selected_case_id = None

    _cancel_delete()
    st.success("Case deleted.")
    st.rerun()


def main() -> None:
    st.set_page_config(page_title="Case Library", page_icon="📚", layout="wide")
    ensure_state()
    if "case_library_confirm_delete_id" not in st.session_state:
        st.session_state.case_library_confirm_delete_id = None
    _inject_styles()

    st.markdown(
        """
        <div class="library-hero">
            <div class="library-kicker">Case Management</div>
            <h2>Case Library</h2>
            <p>
                Browse all cases in one place, set your active case, and jump directly into the
                Case Workspace when you are ready to continue.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    nav_spacer, nav_col = st.columns([4, 1.3], gap="small")
    with nav_col:
        if st.button(
            "Back to Dashboard",
            icon=":material/dashboard:",
            key="case_library_back_dashboard_btn",
            use_container_width=True,
        ):
            st.switch_page("pages/2_My_Cases.py")

    cases, cases_err = fetch_cases()
    if cases_err:
        st.error(f"Could not load cases: {cases_err}")
        st.stop()

    cases = cases or []

    top_col1, top_col2 = st.columns(2, gap="large")
    with top_col1:
        with st.container(border=True):
            st.markdown('<p class="section-label">Create</p>', unsafe_allow_html=True)
            st.subheader("New Case")
            st.caption("Start guided intake to create a new denied-claim workspace.")
            if st.button(
                "Create New Case",
                icon=":material/add_circle:",
                use_container_width=True,
                key="case_library_create_case_btn",
            ):
                open_case_workspace_create_flow()

    with top_col2:
        with st.container(border=True):
            st.markdown('<p class="section-label">Active Case</p>', unsafe_allow_html=True)
            st.subheader("Current Selection")
            if not cases:
                st.info("No cases yet. Create one to get started.")
            else:
                selected_id = select_case(cases, key_prefix="case_library", label="Active case")
                open_active_clicked = st.button(
                    "Open Active Case Workspace",
                    icon=":material/lab_profile:",
                    use_container_width=True,
                )
                if open_active_clicked:
                    _open_workspace(selected_id)

    st.markdown('<p class="section-label">Browse</p>', unsafe_allow_html=True)
    st.markdown("### All Cases")

    if not cases:
        st.info("No cases found.")
        return

    status_filter = st.selectbox(
        "Filter by status",
        ["All", "Open", "Pending", "Done"],
        index=0,
        key="case_library_filter",
    )

    filtered_cases = []
    for case in cases:
        status = (case.get("status") or "open").strip().lower()
        bucket = "Open"
        if status in {"done", "completed", "closed"}:
            bucket = "Done"
        elif status in {"waiting", "pending", "in review"}:
            bucket = "Pending"

        if status_filter == "All" or status_filter == bucket:
            filtered_cases.append(case)

    if not filtered_cases:
        st.info("No cases match this filter.")
        return

    for case in filtered_cases:
        case_id = case.get("case_id")
        status = case.get("status", "open")
        status_class = _status_class(status)
        delete_pending = st.session_state.get("case_library_confirm_delete_id") == case_id
        with st.container(border=True):
            c1, c2 = st.columns([3.2, 1], gap="medium")
            with c1:
                st.markdown(
                    f"""
                    <p class="case-title">{case.get('title', 'Untitled case')}</p>
                    <span class="status-pill {status_class}">{status}</span>
                    <p class="case-meta">Case ID: {case_id}</p>
                    <p class="case-meta">Updated: {case.get('updated_at', 'n/a')}</p>
                    """,
                    unsafe_allow_html=True,
                )
            with c2:
                set_active_clicked = st.button(
                    "Set Active",
                    key=f"case_library_set_{case_id}",
                    use_container_width=True,
                )
                if set_active_clicked:
                    _set_active_case(case_id)
                    st.rerun()

                open_workspace_clicked = st.button(
                    "Open Workspace",
                    key=f"case_library_open_{case_id}",
                    use_container_width=True,
                )
                if open_workspace_clicked:
                    _open_workspace(case_id)

                if delete_pending:
                    st.warning("Delete this case and all related documents/artifacts?")
                    confirm_col, cancel_col = st.columns(2, gap="small")
                    with confirm_col:
                        confirm_delete_clicked = st.button(
                            "Confirm",
                            key=f"case_library_delete_confirm_{case_id}",
                            use_container_width=True,
                        )
                        if confirm_delete_clicked:
                            _delete_case(case_id)
                    with cancel_col:
                        cancel_delete_clicked = st.button(
                            "Cancel",
                            key=f"case_library_delete_cancel_{case_id}",
                            use_container_width=True,
                        )
                        if cancel_delete_clicked:
                            _cancel_delete()
                            st.rerun()
                else:
                    delete_clicked = st.button(
                        "Delete Case",
                        key=f"case_library_delete_{case_id}",
                        use_container_width=True,
                    )
                    if delete_clicked:
                        _confirm_delete(case_id)
                        st.rerun()


if __name__ == "__main__":
    main()
