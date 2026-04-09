from __future__ import annotations

import re

import streamlit as st

from lib.api import (
    DOC_TYPES,
    api_post,
    delete_case,
    ensure_state,
    fetch_case_payload,
    fetch_cases,
    safe_call,
    select_case,
)
from lib.components import (
    render_case_actions_panel,
    render_documents,
    render_event_form,
    render_overview,
    render_packet,
    render_tasks,
    render_tracking_table,
)

WORKSPACE_FLOW_KEY = "case_workspace_flow"
WORKSPACE_PENDING_TITLE_KEY = "case_workspace_pending_title"


def _inject_page_styles() -> None:
    st.markdown(
        """
        <style>
        .workspace-hero {
            padding: 1.35rem 1.45rem;
            border-radius: 24px;
            background:
                radial-gradient(circle at 8% 12%, rgba(255, 208, 135, 0.34), transparent 35%),
                radial-gradient(circle at 97% -8%, rgba(161, 214, 191, 0.4), transparent 33%),
                radial-gradient(circle at 74% 88%, rgba(146, 214, 194, 0.2), transparent 42%),
                linear-gradient(126deg, #fbfcfa 0%, #eef6f1 52%, #dceee6 100%);
            color: #1d3d33;
            margin-bottom: 1rem;
            border: 1px solid #c8ddd2;
            box-shadow: 0 16px 34px rgba(20, 60, 49, 0.16);
            position: relative;
            overflow: hidden;
        }
        .workspace-hero::before {
            content: "";
            position: absolute;
            width: 255px;
            height: 255px;
            top: -130px;
            right: -92px;
            border-radius: 999px;
            background: rgba(160, 214, 190, 0.36);
        }
        .workspace-hero::after {
            content: "";
            position: absolute;
            inset: 0;
            background:
                radial-gradient(circle, rgba(52, 128, 96, 0.1) 1.05px, transparent 1.2px),
                linear-gradient(90deg, rgba(255, 255, 255, 0.2) 0%, rgba(255, 255, 255, 0) 46%);
            background-size: 18px 18px, 100% 100%;
            opacity: 0.36;
            pointer-events: none;
            mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.35) 0%, rgba(0, 0, 0, 0) 72%);
        }
        .workspace-hero > * {
            position: relative;
            z-index: 1;
        }
        .workspace-kicker {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.75rem;
            color: #2f6a56;
            margin-bottom: 0.35rem;
            font-weight: 700;
        }
        .workspace-hero h2 {
            margin: 0;
            font-size: 2rem;
            line-height: 1.08;
            color: #1d3d33;
        }
        .workspace-hero p {
            margin: 0.55rem 0 0;
            max-width: 48rem;
            color: #3f6255;
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
            border-radius: 18px;
            border: 1px solid color-mix(in srgb, currentColor 20%, transparent);
            background: linear-gradient(
                180deg,
                color-mix(in srgb, currentColor 6%, transparent) 0%,
                color-mix(in srgb, currentColor 9%, transparent) 100%
            );
        }
        .active-case-title {
            font-size: 1.28rem;
            font-weight: 800;
            margin: 0.12rem 0 0.35rem;
            color: inherit;
        }
        .active-case-copy {
            margin-bottom: 0.25rem;
            color: color-mix(in srgb, currentColor 86%, transparent);
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


def _ensure_workspace_flow_state() -> None:
    if WORKSPACE_FLOW_KEY not in st.session_state:
        st.session_state[WORKSPACE_FLOW_KEY] = "entry"
    if WORKSPACE_PENDING_TITLE_KEY not in st.session_state:
        st.session_state[WORKSPACE_PENDING_TITLE_KEY] = ""


def _clear_pending_create_title() -> None:
    st.session_state[WORKSPACE_PENDING_TITLE_KEY] = ""


def _safe_text_filename(title: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_-]+", "_", title.strip().lower()).strip("_")
    if not base:
        base = "manual_case_intake"
    return f"{base}.txt"


def _manual_value(value: str) -> str:
    cleaned = value.strip()
    return cleaned if cleaned else "Not provided"


def _build_manual_intake_document(fields: dict[str, str]) -> str:
    lines = [
        "ClaimRight Manual Intake",
        "",
        "Member Information",
        f"- Member name: {_manual_value(fields.get('member_name', ''))}",
        f"- Member ID: {_manual_value(fields.get('member_id', ''))}",
        f"- Date of birth: {_manual_value(fields.get('member_dob', ''))}",
        "",
        "Insurance and Claim Details",
        f"- Payer: {_manual_value(fields.get('payer_name', ''))}",
        f"- Plan type: {_manual_value(fields.get('plan_type', ''))}",
        f"- Claim number: {_manual_value(fields.get('claim_number', ''))}",
        f"- Authorization number: {_manual_value(fields.get('authorization_number', ''))}",
        f"- Service requested: {_manual_value(fields.get('service_requested', ''))}",
        "",
        "Denial Details",
        f"- Denial type/reason: {_manual_value(fields.get('denial_reason', ''))}",
        f"- Denial date: {_manual_value(fields.get('denial_date', ''))}",
        f"- Appeal deadline: {_manual_value(fields.get('appeal_deadline', ''))}",
        "",
        "Care Team and Clinical Context",
        f"- Provider name: {_manual_value(fields.get('provider_name', ''))}",
        f"- Facility: {_manual_value(fields.get('facility_name', ''))}",
        f"- Diagnosis or condition summary: {_manual_value(fields.get('clinical_summary', ''))}",
        "",
        "Timeline and Evidence",
        f"- Timeline summary: {_manual_value(fields.get('timeline_summary', ''))}",
        f"- Supporting evidence available: {_manual_value(fields.get('supporting_evidence', ''))}",
        f"- Requested outcome: {_manual_value(fields.get('requested_outcome', ''))}",
        "",
        "Additional Notes",
        _manual_value(fields.get("additional_notes", "")),
    ]
    return "\n".join(lines).strip()


def _open_active_workspace(case_id: str | None = None) -> None:
    if case_id:
        st.session_state.selected_case_id = case_id
    _clear_pending_create_title()
    st.session_state[WORKSPACE_FLOW_KEY] = "active"
    st.rerun()


def _upload_document_to_case(
    *,
    case_id: str,
    file_name: str,
    file_bytes: bytes,
    mime_type: str,
    doc_type: str,
    auto_process: bool,
) -> str | None:
    files = {"file": (file_name, file_bytes, mime_type)}
    data = {
        "doc_type": doc_type,
        "auto_process": str(auto_process).lower(),
    }
    _, upload_err = safe_call(api_post, f"/cases/{case_id}/documents", files=files, data=data)
    return upload_err


def _render_selected_case_header(case_payload: dict | None, case_id: str | None) -> None:
    if not case_id:
        st.markdown('<p class="section-label">Selected Case</p>', unsafe_allow_html=True)
        st.info("Choose a case to continue.")
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


def _render_entry_screen(cases: list[dict]) -> None:
    st.markdown('<p class="section-label">Start Here</p>', unsafe_allow_html=True)
    st.subheader("Create a new case or continue an existing one")
    st.caption("Choose one path to enter the workspace flow.")

    choose_col, create_col = st.columns(2, gap="large")

    with choose_col:
        with st.container(border=True):
            st.markdown("### Select Existing Case")
            if not cases:
                st.info("No existing cases yet.")
            if st.button(
                "Select Case",
                icon=":material/folder_open:",
                use_container_width=True,
                disabled=not cases,
                key="case_workspace_entry_select_btn",
            ):
                if not st.session_state.get("selected_case_id") and cases:
                    st.session_state.selected_case_id = cases[0].get("case_id")
                st.session_state[WORKSPACE_FLOW_KEY] = "active"
                st.rerun()

    with create_col:
        with st.container(border=True):
            st.markdown("### Create New Case")
            st.caption("Start a new case and add your first document or manual intake details.")
            if st.button(
                "Create Case",
                icon=":material/add_circle:",
                use_container_width=True,
                key="case_workspace_entry_create_btn",
            ):
                _clear_pending_create_title()
                st.session_state[WORKSPACE_FLOW_KEY] = "create"
                st.rerun()


def _render_create_case_setup(cases: list[dict]) -> None:
    st.markdown('<p class="section-label">Create Flow</p>', unsafe_allow_html=True)
    st.subheader("Create a case and add initial context")

    top_actions = st.columns(2, gap="small")
    with top_actions[0]:
        if st.button(
            "Use Existing Case Instead",
            icon=":material/folder_open:",
            use_container_width=True,
            disabled=not cases,
            key="case_workspace_create_use_existing_btn",
        ):
            _clear_pending_create_title()
            st.session_state[WORKSPACE_FLOW_KEY] = "active"
            st.rerun()
    with top_actions[1]:
        if st.button(
            "Back to Start",
            icon=":material/arrow_back:",
            use_container_width=True,
            key="case_workspace_create_back_btn",
        ):
            _clear_pending_create_title()
            st.session_state[WORKSPACE_FLOW_KEY] = "entry"
            st.rerun()

    pending_title = (st.session_state.get(WORKSPACE_PENDING_TITLE_KEY) or "").strip()
    if not pending_title:
        with st.container(border=True):
            st.markdown('<p class="section-label">Create</p>', unsafe_allow_html=True)
            st.subheader("New Case")
            with st.form("case_workspace_create_path_form"):
                title = st.text_input("Case title")
                continue_clicked = st.form_submit_button("Continue to Intake", use_container_width=True)
            if continue_clicked:
                title = title.strip()
                if not title:
                    st.error("Case title is required.")
                    return
                st.session_state[WORKSPACE_PENDING_TITLE_KEY] = title
                st.rerun()
        return

    st.info("Add initial context to unlock the full workspace.")
    st.caption(
        "You can upload documents, complete manual intake, or do both before submitting."
    )
    st.caption(f"New case title: **{pending_title}**")
    if st.button(
        "Change Case Title",
        icon=":material/edit:",
        key="case_workspace_change_pending_title_btn",
    ):
        _clear_pending_create_title()
        st.rerun()

    with st.container(border=True):
        st.markdown('<p class="section-label">Option 1</p>', unsafe_allow_html=True)
        st.subheader("Upload Documents")
        st.caption("Upload denial letters, EOBs, prior auth files, or supporting records.")
        uploaded_files = st.file_uploader(
            "Choose files",
            type=["pdf", "txt", "docx", "png", "jpg", "jpeg", "tiff"],
            accept_multiple_files=True,
            key="case_workspace_create_upload_file",
        )
        doc_type = st.selectbox("Doc type", DOC_TYPES, key="case_workspace_create_upload_doc_type")
        auto_process = st.toggle(
            "Auto process on upload",
            value=True,
            key="case_workspace_create_auto_process",
        )

    with st.container(border=True):
        st.markdown('<p class="section-label">Option 2</p>', unsafe_allow_html=True)
        st.subheader("Manual Intake")
        st.caption("Fill in guided case fields. We save this as a structured document for extraction.")
        intake_title = st.text_input(
            "Intake document title",
            value="manual_case_intake",
            key="case_workspace_manual_intake_title",
        )
        intake_doc_type = st.selectbox(
            "Save as type",
            DOC_TYPES,
            index=DOC_TYPES.index("other") if "other" in DOC_TYPES else 0,
            key="case_workspace_manual_intake_doc_type",
        )

        st.markdown("##### Member Information")
        member_col1, member_col2 = st.columns(2, gap="small")
        with member_col1:
            member_name = st.text_input("Member name *", key="case_workspace_manual_member_name")
            member_id = st.text_input("Member ID", key="case_workspace_manual_member_id")
        with member_col2:
            member_dob = st.text_input("Date of birth", key="case_workspace_manual_member_dob")

        st.markdown("##### Insurance and Claim")
        claim_col1, claim_col2 = st.columns(2, gap="small")
        with claim_col1:
            payer_name = st.text_input("Payer / insurer *", key="case_workspace_manual_payer_name")
            plan_type = st.text_input("Plan type", key="case_workspace_manual_plan_type")
            claim_number = st.text_input("Claim number", key="case_workspace_manual_claim_number")
        with claim_col2:
            authorization_number = st.text_input(
                "Authorization number",
                key="case_workspace_manual_auth_number",
            )
            service_requested = st.text_input(
                "Service requested *",
                key="case_workspace_manual_service_requested",
            )

        st.markdown("##### Denial Details")
        denial_reason = st.text_area(
            "Denial reason *",
            height=110,
            placeholder="Use denial language if possible (for example: medical necessity, out of network, missing prior auth).",
            key="case_workspace_manual_denial_reason",
        )
        denial_date_col, appeal_deadline_col = st.columns(2, gap="small")
        with denial_date_col:
            denial_date = st.text_input("Denial date", key="case_workspace_manual_denial_date")
        with appeal_deadline_col:
            appeal_deadline = st.text_input("Appeal deadline", key="case_workspace_manual_appeal_deadline")

        st.markdown("##### Clinical and Support")
        provider_col1, provider_col2 = st.columns(2, gap="small")
        with provider_col1:
            provider_name = st.text_input("Treating provider", key="case_workspace_manual_provider_name")
            facility_name = st.text_input("Facility / clinic", key="case_workspace_manual_facility_name")
        with provider_col2:
            requested_outcome = st.text_input("Requested outcome", key="case_workspace_manual_requested_outcome")

        clinical_summary = st.text_area(
            "Diagnosis / condition summary",
            height=90,
            placeholder="Primary diagnosis, symptoms, severity, and why treatment was recommended.",
            key="case_workspace_manual_clinical_summary",
        )
        timeline_summary = st.text_area(
            "Timeline summary",
            height=90,
            placeholder="Key dates and events related to the denial and care progression.",
            key="case_workspace_manual_timeline_summary",
        )
        supporting_evidence = st.text_area(
            "Supporting evidence available",
            height=90,
            placeholder="Examples: physician letter, labs, imaging, prior treatment history, guideline citations.",
            key="case_workspace_manual_supporting_evidence",
        )
        additional_notes = st.text_area(
            "Additional notes",
            height=80,
            key="case_workspace_manual_additional_notes",
        )

    submit_clicked = st.button(
        "Submit and Continue",
        icon=":material/arrow_forward:",
        use_container_width=True,
        key="case_workspace_create_submit_btn",
    )

    if submit_clicked:
        manual_fields = {
            "member_name": member_name,
            "member_id": member_id,
            "member_dob": member_dob,
            "payer_name": payer_name,
            "plan_type": plan_type,
            "claim_number": claim_number,
            "authorization_number": authorization_number,
            "service_requested": service_requested,
            "denial_reason": denial_reason,
            "denial_date": denial_date,
            "appeal_deadline": appeal_deadline,
            "provider_name": provider_name,
            "facility_name": facility_name,
            "clinical_summary": clinical_summary,
            "timeline_summary": timeline_summary,
            "supporting_evidence": supporting_evidence,
            "requested_outcome": requested_outcome,
            "additional_notes": additional_notes,
        }
        required_fields = [
            ("Member name", member_name),
            ("Payer / insurer", payer_name),
            ("Service requested", service_requested),
            ("Denial reason", denial_reason),
        ]
        missing_required = [label for label, value in required_fields if not value.strip()]
        has_uploaded_docs = bool(uploaded_files)
        has_any_manual_input = any((value or "").strip() for value in manual_fields.values())

        if not has_uploaded_docs and missing_required:
            st.error(
                "Upload at least one document, or complete required manual fields: "
                f"{', '.join(missing_required)}."
            )
            return

        created, create_err = safe_call(api_post, "/cases", json_body={"title": pending_title})
        if create_err:
            st.error(f"Could not create case: {create_err}")
            return

        created_case_id = (created or {}).get("case_id")
        if not created_case_id:
            st.error("Case creation succeeded but no case ID was returned.")
            return

        upload_errors: list[str] = []
        for uploaded_file in uploaded_files or []:
            upload_err = _upload_document_to_case(
                case_id=created_case_id,
                file_name=uploaded_file.name,
                file_bytes=uploaded_file.getvalue(),
                mime_type=uploaded_file.type or "application/octet-stream",
                doc_type=doc_type,
                auto_process=auto_process,
            )
            if upload_err:
                upload_errors.append(f"{uploaded_file.name}: {upload_err}")

        if has_any_manual_input:
            text_value = _build_manual_intake_document(manual_fields)
            title_value = intake_title.strip() or f"manual_case_intake_{member_name.strip()}"
            manual_file_name = _safe_text_filename(title_value)
            manual_err = _upload_document_to_case(
                case_id=created_case_id,
                file_name=manual_file_name,
                file_bytes=text_value.encode("utf-8"),
                mime_type="text/plain",
                doc_type=intake_doc_type,
                auto_process=True,
            )
            if manual_err:
                upload_errors.append(f"Manual intake: {manual_err}")

        if upload_errors:
            _, rollback_err = delete_case(created_case_id)
            if rollback_err:
                st.error(
                    "Initial intake could not be saved and cleanup failed. "
                    f"Upload errors: {' | '.join(upload_errors)} | Cleanup error: {rollback_err}"
                )
            else:
                st.error(
                    "Initial intake could not be saved. "
                    f"Errors: {' | '.join(upload_errors)}. The case was not created."
                )
            return

        uploaded_count = len(uploaded_files or [])
        manual_label = " with manual intake" if has_any_manual_input else ""
        st.success(f"Case created with {uploaded_count} uploaded document(s){manual_label}.")
        _open_active_workspace(created_case_id)


def _render_workspace_content(case_id: str, case_payload: dict) -> None:
    _render_selected_case_header(case_payload, case_id)

    with st.container(border=True):
        render_case_actions_panel(case_id, key_prefix="case_workspace")

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
        render_tasks(case_id, case_payload, key_prefix="case_workspace")

    with tab_packet:
        render_packet(case_payload)

    with tab_tracking:
        render_event_form(case_id, key_prefix="case_workspace")
        st.divider()
        render_tracking_table(case_payload)


def _render_active_workspace(cases: list[dict]) -> None:
    st.markdown('<p class="section-label">Select</p>', unsafe_allow_html=True)
    st.subheader("Active Case")

    if not cases:
        st.info("No cases yet. Create one to begin.")
        if st.button(
            "Create New Case",
            icon=":material/add_circle:",
            use_container_width=True,
            key="case_workspace_active_create_btn",
        ):
            _clear_pending_create_title()
            st.session_state[WORKSPACE_FLOW_KEY] = "create"
            st.rerun()
        return

    valid_ids = [c.get("case_id") for c in cases if c.get("case_id")]
    if st.session_state.get("selected_case_id") not in valid_ids and valid_ids:
        st.session_state.selected_case_id = valid_ids[0]

    with st.container(border=True):
        case_id = select_case(cases, key_prefix="case_workspace_active", label="Current case")
        action_col1, action_col2 = st.columns(2, gap="small")
        with action_col1:
            if st.button(
                "Back to Start Options",
                icon=":material/home:",
                use_container_width=True,
                key="case_workspace_active_back_to_entry_btn",
            ):
                st.session_state[WORKSPACE_FLOW_KEY] = "entry"
                st.rerun()
        with action_col2:
            if st.button(
                "Create New Case",
                icon=":material/add_circle:",
                use_container_width=True,
                key="case_workspace_active_to_create_btn",
            ):
                _clear_pending_create_title()
                st.session_state[WORKSPACE_FLOW_KEY] = "create"
                st.rerun()

    if not case_id:
        st.info("Select a case to continue.")
        return

    case_payload, payload_err = fetch_case_payload(case_id)
    if payload_err or not case_payload:
        st.error(f"Could not load selected case: {payload_err}")
        return

    _render_workspace_content(case_id, case_payload)


def main() -> None:
    st.set_page_config(page_title="Case Workspace", page_icon="🧰", layout="wide")
    ensure_state()
    _ensure_workspace_flow_state()
    _inject_page_styles()

    st.markdown(
        """
        <div class="workspace-hero">
            <div class="workspace-kicker">Case Execution</div>
            <h2>Case Workspace</h2>
            <p>
                Focused workspace for one active case: upload documents, run extraction and generation,
                and manage case details end to end.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cases, cases_err = fetch_cases()
    if cases_err:
        st.error(f"Could not load cases: {cases_err}")
        st.stop()

    cases = cases or []
    flow = st.session_state.get(WORKSPACE_FLOW_KEY, "entry")

    if flow == "entry":
        _render_entry_screen(cases)
        return

    if flow == "create":
        _render_create_case_setup(cases)
        return

    _render_active_workspace(cases)


if __name__ == "__main__":
    main()
