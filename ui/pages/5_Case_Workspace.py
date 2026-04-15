from __future__ import annotations

from html import escape
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
    render_documents,
    render_event_form,
    render_overview,
    render_packet,
    render_upload_documents_card,
    render_tasks,
    render_tracking_table,
    render_workflow_actions_card,
)

WORKSPACE_FLOW_KEY = "case_workspace_flow"
WORKSPACE_PENDING_TITLE_KEY = "case_workspace_pending_title"
WORKSPACE_DETAIL_SECTION_KEY = "case_workspace_detail_section"
WORKSPACE_DETAIL_SECTION_PENDING_KEY = "case_workspace_detail_section_pending"
WORKSPACE_DETAIL_SECTIONS = ["Overview", "Documents", "Tasks", "Packet Builder", "Tracking"]


def _inject_page_styles() -> None:
    st.markdown(
        """
        <style>
        .stMainBlockContainer {
            background:
                radial-gradient(circle at 4% 6%, rgba(111, 184, 255, 0.08), transparent 28%),
                radial-gradient(circle at 96% 11%, rgba(118, 211, 179, 0.09), transparent 30%);
        }
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
        .workspace-select-title {
            margin: 0.08rem 0 0.18rem;
            font-size: 1.54rem;
            line-height: 1.15;
            font-weight: 800;
            color: inherit;
        }
        .workspace-select-help {
            margin: 0.08rem 0 0.6rem;
            font-size: 0.93rem;
            line-height: 1.52;
            color: color-mix(in srgb, currentColor 78%, transparent);
        }
        .workspace-selector-ribbon {
            height: 8px;
            border-radius: 999px;
            margin: 0.28rem 0 0.8rem;
            background:
                linear-gradient(90deg, #7ddfc2 0%, #78c7ec 46%, #9cb2ff 100%);
            box-shadow: 0 10px 24px rgba(57, 129, 179, 0.28);
        }
        .workspace-selector-metrics {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.58rem;
            margin: 0.15rem 0 0.75rem;
        }
        .workspace-selector-metric {
            padding: 0.56rem 0.64rem;
            border-radius: 12px;
            border: 1px solid #b8d8ea;
            background:
                radial-gradient(circle at 86% 12%, rgba(123, 183, 246, 0.18), transparent 36%),
                linear-gradient(140deg, #f5fbff 0%, #edf8f4 50%, #e9f1ff 100%);
            box-shadow: 0 8px 18px rgba(24, 68, 105, 0.1);
        }
        .workspace-selector-metric-kicker {
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            font-size: 0.62rem;
            font-weight: 800;
            color: #3473a2;
        }
        .workspace-selector-metric-value {
            margin: 0.16rem 0 0;
            font-size: 1.15rem;
            line-height: 1.15;
            font-weight: 800;
            color: #183f63;
        }
        .workspace-selector-tip {
            margin: 0.1rem 0 0.62rem;
            padding: 0.48rem 0.64rem;
            border-radius: 11px;
            border: 1px solid #b8d8ea;
            background: linear-gradient(135deg, rgba(110, 183, 232, 0.14), rgba(129, 217, 185, 0.12));
            color: #2f5678;
            font-size: 0.82rem;
            line-height: 1.35;
        }
        .workspace-case-highlight {
            margin-top: 0.55rem;
            margin-bottom: 0.9rem;
            padding: 0.86rem 0.92rem;
            border-radius: 15px;
            border: 1px solid color-mix(in srgb, currentColor 22%, transparent);
            background: linear-gradient(
                180deg,
                color-mix(in srgb, currentColor 5%, transparent) 0%,
                color-mix(in srgb, currentColor 10%, transparent) 100%
            );
            box-shadow: 0 10px 18px rgba(17, 53, 43, 0.12);
        }
        .workspace-case-kicker {
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            font-size: 0.68rem;
            font-weight: 800;
            color: color-mix(in srgb, currentColor 72%, transparent);
        }
        .workspace-quick-actions-wrap {
            padding: 0.58rem 0.65rem 0.2rem;
            border-radius: 14px;
            border: 1px solid #b9d7e8;
            background:
                radial-gradient(circle at 85% 12%, rgba(134, 197, 247, 0.16), transparent 34%),
                linear-gradient(145deg, #f3fbff 0%, #eef8f3 54%, #ecf3ff 100%);
            box-shadow: 0 10px 22px rgba(24, 67, 103, 0.12);
        }
        .workspace-quick-actions-title {
            margin: 0 0 0.48rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.68rem;
            font-weight: 800;
            color: #316c98;
        }
        .workspace-case-title {
            margin: 0.28rem 0 0.34rem;
            font-size: 1.13rem;
            line-height: 1.2;
            font-weight: 800;
            color: inherit;
        }
        .workspace-case-meta {
            margin: 0.24rem 0 0;
            font-size: 0.88rem;
            line-height: 1.45;
            color: color-mix(in srgb, currentColor 80%, transparent);
        }
        .workspace-glance-strip {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.62rem;
            margin: 0.7rem 0 0.9rem;
        }
        .workspace-glance-card {
            border-radius: 14px;
            padding: 0.62rem 0.74rem;
            border: 1px solid #b9d4e7;
            background:
                radial-gradient(circle at 85% 10%, rgba(110, 176, 255, 0.15), transparent 36%),
                linear-gradient(140deg, #f4f9ff 0%, #e8f5f0 56%, #e9f1ff 100%);
            box-shadow: 0 8px 18px rgba(27, 72, 110, 0.09);
        }
        .workspace-glance-kicker {
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            font-size: 0.66rem;
            font-weight: 800;
            color: #2a688f;
            opacity: 0.9;
        }
        .workspace-glance-value {
            margin: 0.22rem 0 0.02rem;
            font-size: 1.14rem;
            font-weight: 800;
            color: #173d5f;
            line-height: 1.2;
        }
        .workspace-glance-note {
            margin: 0;
            font-size: 0.79rem;
            line-height: 1.35;
            color: #3f6483;
            opacity: 0.9;
        }
        .workspace-accent-rail {
            height: 7px;
            border-radius: 999px;
            margin: 0.08rem 0 0.8rem;
            background:
                linear-gradient(90deg, #66d6b5 0%, #5fb9ea 48%, #8ca2ff 100%);
            box-shadow: 0 8px 18px rgba(70, 130, 183, 0.22);
        }
        .workspace-block-gap {
            height: 0.65rem;
        }
        @media (max-width: 980px) {
            .workspace-glance-strip {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .workspace-selector-metrics {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 620px) {
            .workspace-glance-strip {
                grid-template-columns: 1fr;
            }
            .workspace-selector-metrics {
                grid-template-columns: 1fr;
            }
        }
        [data-theme="dark"] .workspace-select-help,
        [data-theme="dark"] .workspace-case-meta {
            color: rgba(230, 244, 236, 0.82);
        }
        [data-theme="dark"] .workspace-selector-ribbon {
            background: linear-gradient(90deg, #2f9f80 0%, #2f82b6 46%, #6278d9 100%);
            box-shadow: 0 10px 24px rgba(14, 42, 69, 0.5);
        }
        [data-theme="dark"] .workspace-selector-metric {
            border-color: rgba(132, 176, 215, 0.55);
            background:
                radial-gradient(circle at 86% 10%, rgba(92, 146, 224, 0.3), transparent 35%),
                linear-gradient(145deg, rgba(18, 44, 68, 0.9), rgba(15, 55, 48, 0.9) 54%, rgba(29, 40, 76, 0.92));
            box-shadow: 0 12px 25px rgba(0, 0, 0, 0.32);
        }
        [data-theme="dark"] .workspace-selector-metric-kicker {
            color: rgba(169, 214, 250, 0.93);
        }
        [data-theme="dark"] .workspace-selector-metric-value {
            color: rgba(233, 246, 255, 0.98);
        }
        [data-theme="dark"] .workspace-selector-tip {
            border-color: rgba(129, 173, 212, 0.52);
            background: linear-gradient(135deg, rgba(66, 124, 175, 0.3), rgba(52, 137, 108, 0.24));
            color: rgba(214, 234, 249, 0.95);
        }
        [data-theme="dark"] .workspace-quick-actions-wrap {
            border-color: rgba(134, 177, 215, 0.56);
            background:
                radial-gradient(circle at 85% 12%, rgba(81, 136, 212, 0.29), transparent 34%),
                linear-gradient(145deg, rgba(18, 45, 69, 0.92), rgba(16, 56, 49, 0.9) 54%, rgba(29, 40, 76, 0.92));
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.34);
        }
        [data-theme="dark"] .workspace-quick-actions-title {
            color: rgba(166, 212, 248, 0.95);
        }
        [data-theme="dark"] .workspace-glance-card {
            border-color: rgba(128, 174, 220, 0.5);
            background:
                radial-gradient(circle at 85% 12%, rgba(88, 148, 229, 0.25), transparent 34%),
                linear-gradient(140deg, rgba(20, 45, 70, 0.9) 0%, rgba(17, 56, 47, 0.9) 52%, rgba(33, 43, 78, 0.9) 100%);
            box-shadow: 0 12px 26px rgba(0, 0, 0, 0.34);
        }
        [data-theme="dark"] .workspace-glance-kicker {
            color: rgba(165, 216, 255, 0.94);
        }
        [data-theme="dark"] .workspace-glance-value {
            color: rgba(233, 246, 255, 0.98);
        }
        [data-theme="dark"] .workspace-glance-note {
            color: rgba(196, 223, 244, 0.92);
        }
        [data-theme="dark"] .workspace-accent-rail {
            background: linear-gradient(90deg, #2f9f80 0%, #2f82b6 48%, #5c76d6 100%);
            box-shadow: 0 8px 18px rgba(20, 55, 89, 0.45);
        }
        [data-theme="dark"] .workspace-case-highlight {
            border-color: rgba(141, 188, 168, 0.46);
            background: linear-gradient(180deg, rgba(22, 56, 46, 0.84), rgba(16, 42, 35, 0.9));
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.35);
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


def _render_workspace_glance_strip(case_payload: dict) -> None:
    documents = case_payload.get("documents") if isinstance(case_payload.get("documents"), list) else []
    tasks = case_payload.get("tasks") if isinstance(case_payload.get("tasks"), list) else []
    artifacts = case_payload.get("artifacts") if isinstance(case_payload.get("artifacts"), list) else []
    extraction = case_payload.get("extraction") if isinstance(case_payload.get("extraction"), dict) else None

    done_tasks = sum(1 for task in tasks if str(task.get("status") or "").strip().lower() == "done")
    packet_count = sum(1 for artifact in artifacts if artifact.get("type") == "packet_pdf")
    letter_count = sum(1 for artifact in artifacts if artifact.get("type") == "letter")
    extraction_mode = str(extraction.get("mode") or "pending") if extraction else "pending"

    st.markdown(
        f"""
        <div class="workspace-glance-strip">
            <div class="workspace-glance-card">
                <p class="workspace-glance-kicker">Documents</p>
                <p class="workspace-glance-value">{len(documents)}</p>
                <p class="workspace-glance-note">Files in workspace</p>
            </div>
            <div class="workspace-glance-card">
                <p class="workspace-glance-kicker">Tasks</p>
                <p class="workspace-glance-value">{done_tasks}/{len(tasks) if tasks else 0}</p>
                <p class="workspace-glance-note">Completed checklist</p>
            </div>
            <div class="workspace-glance-card">
                <p class="workspace-glance-kicker">Extraction</p>
                <p class="workspace-glance-value">{escape(extraction_mode.replace('_', ' ').title())}</p>
                <p class="workspace-glance-note">Current case context mode</p>
            </div>
            <div class="workspace-glance-card">
                <p class="workspace-glance-kicker">Outputs</p>
                <p class="workspace-glance-value">{letter_count} Letters · {packet_count} Packets</p>
                <p class="workspace-glance-note">Generated artifacts</p>
            </div>
        </div>
        <div class="workspace-accent-rail"></div>
        """,
        unsafe_allow_html=True,
    )


def _ensure_workspace_flow_state() -> None:
    if WORKSPACE_FLOW_KEY not in st.session_state:
        st.session_state[WORKSPACE_FLOW_KEY] = "entry"
    if WORKSPACE_PENDING_TITLE_KEY not in st.session_state:
        st.session_state[WORKSPACE_PENDING_TITLE_KEY] = ""
    if WORKSPACE_DETAIL_SECTION_KEY not in st.session_state:
        st.session_state[WORKSPACE_DETAIL_SECTION_KEY] = "Overview"


def _clear_pending_create_title() -> None:
    st.session_state[WORKSPACE_PENDING_TITLE_KEY] = ""


def _safe_text_filename(title: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_-]+", "_", title.strip().lower()).strip("_")
    if not base:
        base = "manual_case_intake"
    return f"{base}.txt"


def _suggest_doc_type_for_filename(file_name: str) -> str:
    name = (file_name or "").strip().lower()
    if not name:
        return "other"
    if "denial" in name:
        return "denial_letter"
    if "eob" in name or "explanation_of_benefits" in name:
        return "eob"
    if "prior_auth" in name or "prior-auth" in name or "authorization" in name or "preauth" in name:
        return "prior_auth"
    if "record" in name or "clinical" in name or "note" in name or "chart" in name:
        return "medical_records"
    return "other"


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

    selected_doc_types: list[str] = []

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
        if uploaded_files:
            st.caption("Choose a document type for each selected file.")
            for idx, uploaded_file in enumerate(uploaded_files):
                suggested = _suggest_doc_type_for_filename(uploaded_file.name)
                default_doc_type = suggested if suggested in DOC_TYPES else "other"
                if default_doc_type not in DOC_TYPES:
                    default_doc_type = DOC_TYPES[0]
                default_index = DOC_TYPES.index(default_doc_type)
                selected_type = st.selectbox(
                    f"Doc type for `{uploaded_file.name}`",
                    DOC_TYPES,
                    index=default_index,
                    key=f"case_workspace_create_upload_doc_type_{idx}",
                )
                selected_doc_types.append(selected_type)
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
        for idx, uploaded_file in enumerate(uploaded_files or []):
            file_doc_type = selected_doc_types[idx] if idx < len(selected_doc_types) else DOC_TYPES[0]
            upload_err = _upload_document_to_case(
                case_id=created_case_id,
                file_name=uploaded_file.name,
                file_bytes=uploaded_file.getvalue(),
                mime_type=uploaded_file.type or "application/octet-stream",
                doc_type=file_doc_type,
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
    requested_section = st.session_state.pop(WORKSPACE_DETAIL_SECTION_PENDING_KEY, None)
    if requested_section in WORKSPACE_DETAIL_SECTIONS:
        st.session_state[WORKSPACE_DETAIL_SECTION_KEY] = requested_section
    if st.session_state.get(WORKSPACE_DETAIL_SECTION_KEY) not in WORKSPACE_DETAIL_SECTIONS:
        st.session_state[WORKSPACE_DETAIL_SECTION_KEY] = "Overview"

    case_detail_col, workflow_col = st.columns([2, 1], gap="large")

    with case_detail_col:
        st.markdown('<p class="section-label">Case Detail</p>', unsafe_allow_html=True)
        st.markdown(f"### Workspace for `{case_id}`")
        _render_workspace_glance_strip(case_payload)
        selected_section = st.segmented_control(
            "Case detail section",
            WORKSPACE_DETAIL_SECTIONS,
            key=WORKSPACE_DETAIL_SECTION_KEY,
            label_visibility="collapsed",
        )
        selected_section = str(selected_section or st.session_state.get(WORKSPACE_DETAIL_SECTION_KEY) or "Overview")

        if selected_section == "Overview":
            render_overview(case_payload)

        elif selected_section == "Documents":
            render_upload_documents_card(case_id, key_prefix="case_workspace")
            st.markdown('<div class="workspace-block-gap"></div>', unsafe_allow_html=True)
            render_documents(case_payload)

        elif selected_section == "Tasks":
            render_tasks(case_id, case_payload, key_prefix="case_workspace")

        elif selected_section == "Packet Builder":
            render_packet(case_payload)

        elif selected_section == "Tracking":
            render_event_form(case_id, key_prefix="case_workspace")
            st.divider()
            render_tracking_table(case_payload)

    with workflow_col:
        render_workflow_actions_card(
            case_id,
            key_prefix="case_workspace",
            case_payload=case_payload,
            tab_jump_state_key=WORKSPACE_DETAIL_SECTION_PENDING_KEY,
        )


def _render_active_workspace(cases: list[dict]) -> None:
    st.markdown('<p class="section-label">Select</p>', unsafe_allow_html=True)
    st.subheader("Case Selection")
    st.caption("Pick a case to load the workspace and continue execution.")

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
        st.markdown('<p class="section-label">Case Selector</p>', unsafe_allow_html=True)
        st.markdown('<p class="workspace-select-title">Choose Existing Case</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="workspace-select-help">Use the dropdown to pick which case you want to open below.</p>',
            unsafe_allow_html=True,
        )
        status_counts: dict[str, int] = {}
        for case in cases:
            normalized_status = str(case.get("status") or "open").strip().lower()
            status_counts[normalized_status] = status_counts.get(normalized_status, 0) + 1
        ready_count = status_counts.get("ready", 0)
        waiting_count = status_counts.get("waiting_on_docs", 0) + status_counts.get("open", 0)
        submitted_count = status_counts.get("submitted", 0)
        resolved_count = (
            status_counts.get("resolved", 0)
            + status_counts.get("done", 0)
            + status_counts.get("closed", 0)
            + status_counts.get("completed", 0)
        )
        st.markdown(
            f"""
            <div class="workspace-selector-ribbon"></div>
            <div class="workspace-selector-metrics">
                <div class="workspace-selector-metric">
                    <p class="workspace-selector-metric-kicker">Portfolio</p>
                    <p class="workspace-selector-metric-value">{len(cases)}</p>
                </div>
                <div class="workspace-selector-metric">
                    <p class="workspace-selector-metric-kicker">Ready</p>
                    <p class="workspace-selector-metric-value">{ready_count}</p>
                </div>
                <div class="workspace-selector-metric">
                    <p class="workspace-selector-metric-kicker">In Progress</p>
                    <p class="workspace-selector-metric-value">{waiting_count + submitted_count}</p>
                </div>
                <div class="workspace-selector-metric">
                    <p class="workspace-selector-metric-kicker">Resolved</p>
                    <p class="workspace-selector-metric-value">{resolved_count}</p>
                </div>
            </div>
            <div class="workspace-selector-tip">
                Tip: choose your active case first, then use Quick Actions for dashboard/library/navigation shortcuts.
            </div>
            """,
            unsafe_allow_html=True,
        )
        case_id = select_case(cases, key_prefix="case_workspace_active", label="Current case")
        selected_case = next((case for case in cases if case.get("case_id") == case_id), {})
        if case_id and selected_case:
            status = str(selected_case.get("status") or "open")
            pill_class = _status_class(status)
            selected_col, actions_col = st.columns([1.8, 1], gap="large")
            with selected_col:
                st.markdown(
                    f"""
                    <div class="workspace-case-highlight">
                        <p class="workspace-case-kicker">Selected Case</p>
                        <p class="workspace-case-title">{escape(str(selected_case.get("title") or "Untitled Case"))}</p>
                        <div class="workspace-case-meta">
                            <span class="status-pill {pill_class}">{escape(status)}</span>
                            &nbsp;&nbsp;Case ID: <strong>{escape(str(case_id))}</strong>
                        </div>
                        <p class="workspace-case-meta">
                            Updated: {escape(str(selected_case.get("updated_at") or "n/a"))}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with actions_col:
                st.markdown('<p class="workspace-quick-actions-title">Quick Actions</p>', unsafe_allow_html=True)
                top_left, top_right = st.columns(2, gap="small")
                with top_left:
                    if st.button(
                        "Case Library",
                        icon=":material/library_books:",
                        use_container_width=True,
                        key="case_workspace_active_open_library_btn",
                    ):
                        st.switch_page("pages/4_Case_Library.py")
                with top_right:
                    if st.button(
                        "Dashboard",
                        icon=":material/dashboard:",
                        use_container_width=True,
                        key="case_workspace_active_open_dashboard_btn",
                    ):
                        st.switch_page("pages/2_My_Cases.py")

                bottom_left, bottom_right = st.columns(2, gap="small")
                with bottom_left:
                    if st.button(
                        "New Case",
                        icon=":material/add_circle:",
                        use_container_width=True,
                        key="case_workspace_active_to_create_btn",
                    ):
                        _clear_pending_create_title()
                        st.session_state[WORKSPACE_FLOW_KEY] = "create"
                        st.rerun()
                with bottom_right:
                    if st.button(
                        "Start Options",
                        icon=":material/home:",
                        use_container_width=True,
                        key="case_workspace_active_back_to_entry_btn",
                    ):
                        st.session_state[WORKSPACE_FLOW_KEY] = "entry"
                        st.rerun()

    if not case_id:
        st.info("Select a case to continue.")
        return

    st.markdown('<div class="workspace-block-gap"></div>', unsafe_allow_html=True)

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
