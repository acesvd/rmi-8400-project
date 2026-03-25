from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st

from .api import (
    API_BASE,
    DOC_TYPES,
    EVENT_TYPES,
    TASK_STATUSES,
    api_patch,
    api_post,
    safe_call,
)


def render_sources(sources: list[dict[str, Any]]) -> None:
    if not sources:
        st.caption("No source snippets returned.")
        return
    for src in sources:
        st.markdown(
            f"- {src.get('file_name', 'document')} p.{src.get('page_number', '?')} (score={src.get('score', 'n/a')})"
        )
        st.caption(src.get("snippet", ""))


def render_overview(case_payload: dict[str, Any]) -> None:
    case = case_payload["case"]
    extraction = case_payload.get("extraction")

    col1, col2, col3 = st.columns(3)
    col1.metric("Case ID", case["case_id"])
    col2.metric("Status", case["status"])
    col3.metric("Documents", len(case_payload.get("documents", [])))

    if extraction:
        st.subheader("Extracted Case JSON")
        st.caption(f"Extraction mode: {extraction.get('mode', 'unknown')}")
        st.json(extraction.get("case_json", {}))
        warnings = extraction.get("warnings", [])
        if warnings:
            st.warning("\n".join(warnings))
    else:
        st.info("No extraction available yet. Run extraction after uploading documents.")


def render_documents(case_payload: dict[str, Any]) -> None:
    docs = case_payload.get("documents", [])
    if not docs:
        st.info("No documents uploaded yet.")
        return
    st.dataframe(docs, use_container_width=True)


def render_tasks(case_id: str, case_payload: dict[str, Any], *, key_prefix: str) -> None:
    tasks = case_payload.get("tasks", [])
    if not tasks:
        st.info("No tasks generated yet.")
        return

    for task in tasks:
        with st.container(border=True):
            st.markdown(f"**{task['title']}**")
            st.caption(task["description"])
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            col1.write(f"Owner: {task['owner']}")
            col2.write(f"Due: {task.get('due_date') or 'n/a'}")
            col3.write(f"Status: {task['status']}")
            new_status = col4.selectbox(
                "Update",
                TASK_STATUSES,
                index=TASK_STATUSES.index(task["status"]),
                key=f"{key_prefix}_status_{task['task_id']}",
                label_visibility="collapsed",
            )
            if new_status != task["status"]:
                if st.button("Save", key=f"{key_prefix}_save_{task['task_id']}"):
                    _, err = safe_call(
                        api_patch,
                        f"/cases/{case_id}/tasks/{task['task_id']}",
                        json_body={"status": new_status},
                    )
                    if err:
                        st.error(err)
                    else:
                        st.success("Task updated")
                        st.rerun()


def render_packet(case_payload: dict[str, Any]) -> None:
    artifacts = case_payload.get("artifacts", [])
    letters = [a for a in artifacts if a["type"] == "letter"]
    packets = [a for a in artifacts if a["type"] == "packet_pdf"]

    if letters:
        latest_letter = max(letters, key=lambda x: x["version"])
        st.markdown("**Latest Letter Artifact**")
        st.code(f"Version v{latest_letter['version']}\n{latest_letter['storage_path']}")
        link = f"{API_BASE}/artifacts/{latest_letter['artifact_id']}/download"
        st.markdown(f"[Download letter markdown]({link})")

        citations = (latest_letter.get("metadata") or {}).get("citations") or []
        with st.expander("Citations"):
            render_sources(citations)
    else:
        st.info("No letter generated yet.")

    st.divider()
    if packets:
        latest_packet = max(packets, key=lambda x: x["version"])
        st.markdown("**Latest Packet PDF**")
        link = f"{API_BASE}/artifacts/{latest_packet['artifact_id']}/download"
        st.markdown(f"[Download packet PDF v{latest_packet['version']}]({link})")
        st.caption(latest_packet["storage_path"])
    else:
        st.info("No packet PDF generated yet.")


def render_tracking_table(case_payload: dict[str, Any]) -> None:
    events = case_payload.get("events", [])
    if events:
        st.dataframe(events, use_container_width=True)
    else:
        st.info("No tracking events logged yet.")


def render_event_form(case_id: str, *, key_prefix: str) -> None:
    st.subheader("Log Event")
    with st.form(f"{key_prefix}_event_form"):
        event_type = st.selectbox("Event type", EVENT_TYPES)
        event_ts = st.text_input("Timestamp (ISO)", value=datetime.utcnow().replace(microsecond=0).isoformat())
        notes = st.text_area("Notes")
        submit_evt = st.form_submit_button("Add Event")
        if submit_evt:
            if not notes.strip():
                st.error("Notes required")
            else:
                _, evt_err = safe_call(
                    api_post,
                    f"/cases/{case_id}/events",
                    json_body={"type": event_type, "timestamp": event_ts, "notes": notes.strip()},
                )
                if evt_err:
                    st.error(evt_err)
                else:
                    st.success("Event logged")
                    st.rerun()


def _trigger_case_action(case_id: str, path: str, success_message: str, *, json_body: dict[str, Any]) -> None:
    _, err = safe_call(api_post, path, json_body=json_body)
    if err:
        st.error(err)
    else:
        st.success(success_message)
        st.rerun()


def render_case_actions_panel(case_id: str | None, *, key_prefix: str) -> None:
    if not case_id:
        st.caption("Select a case to enable uploads and workflow actions.")
        return

    st.markdown("### Case Workspace")
    st.caption("Everything you need for the current case is grouped here, so the workflow stays in the main canvas.")

    upload_col, actions_col = st.columns([1.2, 1], gap="large")

    with upload_col:
        with st.container(border=True):
            st.markdown("### Upload Documents")
            st.caption("Add denial letters, EOBs, prior auth records, or supporting medical documents.")
            uploaded = st.file_uploader(
                "Upload document",
                type=["pdf", "txt", "docx", "png", "jpg", "jpeg", "tiff"],
                key=f"{key_prefix}_upload_file",
            )
            doc_type = st.selectbox("Doc type", DOC_TYPES, key=f"{key_prefix}_doc_type")
            auto_process = st.toggle("Auto process on upload", value=True, key=f"{key_prefix}_auto_process")

            if st.button("Upload Document", use_container_width=True, key=f"{key_prefix}_upload_btn"):
                if uploaded is None:
                    st.error("Choose a file")
                else:
                    files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")}
                    data = {"doc_type": doc_type, "auto_process": str(auto_process).lower()}
                    _, upload_err = safe_call(api_post, f"/cases/{case_id}/documents", files=files, data=data)
                    if upload_err:
                        st.error(upload_err)
                    else:
                        st.success("Document uploaded")
                        st.rerun()

    with actions_col:
        with st.container(border=True):
            st.markdown("### Workflow Actions")
            st.caption("Follow the workflow in order, or jump to the step you need.")
            st.info("Suggested flow: Process -> Extract -> Generate Tasks -> Generate Letter -> Generate Packet")
            btn_col1, btn_col2 = st.columns(2)

            with btn_col1:
                if st.button("Process Documents", use_container_width=True, key=f"{key_prefix}_process_btn"):
                    _trigger_case_action(case_id, f"/cases/{case_id}/process", "Processing complete", json_body={})
                if st.button("Generate Tasks", use_container_width=True, key=f"{key_prefix}_tasks_btn"):
                    _trigger_case_action(case_id, f"/cases/{case_id}/tasks/generate", "Tasks generated", json_body={})
                if st.button("Generate Packet PDF", use_container_width=True, key=f"{key_prefix}_packet_btn"):
                    _trigger_case_action(
                        case_id,
                        f"/cases/{case_id}/packet",
                        "Packet generated",
                        json_body={"include_uploaded_pdfs": True},
                    )

            with btn_col2:
                if st.button("Run Extraction", use_container_width=True, key=f"{key_prefix}_extract_btn"):
                    _trigger_case_action(case_id, f"/cases/{case_id}/extract", "Case extraction complete", json_body={})
                if st.button("Generate Letter", use_container_width=True, key=f"{key_prefix}_letter_btn"):
                    _trigger_case_action(
                        case_id,
                        f"/cases/{case_id}/letter",
                        "Letter generated",
                        json_body={"style": "formal"},
                    )
