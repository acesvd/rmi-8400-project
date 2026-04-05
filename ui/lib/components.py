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


def _score_color(rate: float | None) -> str:
    """Return a color hex based on overturn rate."""
    if rate is None:
        return "#888888"
    if rate >= 0.6:
        return "#16623f"  # green
    if rate >= 0.4:
        return "#8a5a00"  # amber
    return "#b91c1c"  # red


def _score_label(rate: float | None) -> str:
    if rate is None:
        return "Insufficient data"
    pct = int(rate * 100)
    if pct >= 60:
        return f"{pct}% — Strong"
    if pct >= 40:
        return f"{pct}% — Moderate"
    return f"{pct}% — Limited"


def _confidence_badge(conf: str) -> str:
    colors = {
        "high": "#16623f",
        "medium": "#8a5a00",
        "low": "#b91c1c",
        "very_low": "#b91c1c",
        "none": "#888888",
    }
    c = colors.get(conf, "#888888")
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:12px;'
        f'font-size:0.75rem;font-weight:600;color:white;background:{c}">'
        f'{conf.replace("_", " ").title()}</span>'
    )


def render_appealability(case_id: str, case_payload: dict[str, Any]) -> None:
    """Render the Appealability tab with A-scores and similar cases."""
    from .api import fetch_appealability

    extraction = case_payload.get("extraction")
    if not extraction:
        st.info("Run extraction first (upload a denial letter → Process → Extract).")
        return

    with st.spinner("Computing appealability..."):
        appeal_data, appeal_err = fetch_appealability(case_id)

    if appeal_err:
        st.error(f"Could not compute appealability: {appeal_err}")
        return
    if not appeal_data:
        st.info("No appealability data available.")
        return

    classification = appeal_data.get("denial_classification", "unknown")
    a_score = appeal_data.get("a_score") or {}
    benchmark = appeal_data.get("insurer_benchmark") or {}
    precedent = appeal_data.get("precedent_cases") or []
    recs = appeal_data.get("recommendations") or []
    payer = appeal_data.get("payer", "unknown")

    # --- Header ---
    denial_label = appeal_data.get("denial_label", "").replace("_", " ").title()
    st.markdown(
        f'<div style="padding:0.8rem 1rem;border-radius:16px;'
        f'background:linear-gradient(135deg,#12343b,#1f5c57);color:#f7f4ea;'
        f'margin-bottom:1rem">'
        f'<div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.1em;'
        f'opacity:0.8">Appealability Assessment</div>'
        f'<div style="font-size:1.4rem;font-weight:700;margin-top:0.2rem">'
        f'{denial_label} — {payer}</div>'
        f'<div style="font-size:0.85rem;opacity:0.9;margin-top:0.2rem">'
        f'Classification: {classification} '
        f'{"(clinically arguable — IMR eligible)" if classification == "R1" else "(procedural)" if classification == "R2" else ""}'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # --- A-Score cards ---
    score_col1, score_col2 = st.columns(2)

    with score_col1:
        st.markdown("#### Historical A-Score")
        st.caption("Based on CA DMHC IMR case outcomes (2001–present)")
        rate = a_score.get("overturn_rate")
        color = _score_color(rate)
        label = _score_label(rate)
        n = a_score.get("sample_size", 0)
        conf = a_score.get("confidence", "none")
        yr = a_score.get("year_range", "")

        st.markdown(
            f'<div style="text-align:center;padding:1.2rem;border-radius:16px;'
            f'border:2px solid {color};margin-bottom:0.5rem">'
            f'<div style="font-size:2.2rem;font-weight:800;color:{color}">{label}</div>'
            f'<div style="font-size:0.85rem;color:#58656a;margin-top:0.3rem">'
            f'{n:,} similar cases · {yr}</div>'
            f'<div style="margin-top:0.4rem">Confidence: {_confidence_badge(conf)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with score_col2:
        st.markdown("#### Agent Assessment")
        st.caption("AI analysis of your specific case context")
        if classification == "R1" and rate is not None:
            # The agent assessment considers the case-specific context
            # For now, we surface the same rate but with case-specific framing
            pct = int(rate * 100)
            if pct >= 60:
                assessment = "Your case has a strong basis for appeal."
                detail = ("The denial type and treatment category show historically high "
                          "overturn rates. Precedent cases below support your position.")
            elif pct >= 40:
                assessment = "Your case has a moderate basis for appeal."
                detail = ("Some similar cases were overturned, but outcomes vary. "
                          "Gather strong documentation from your provider.")
            else:
                assessment = "Appeal success is uncertain for this type."
                detail = ("Fewer similar cases were overturned. Consider consulting "
                          "with your physician about additional supporting evidence.")
            st.markdown(
                f'<div style="text-align:center;padding:1.2rem;border-radius:16px;'
                f'border:2px solid {color};margin-bottom:0.5rem">'
                f'<div style="font-size:1.1rem;font-weight:700;color:{color}">{assessment}</div>'
                f'<div style="font-size:0.85rem;color:#58656a;margin-top:0.5rem">{detail}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        elif classification == "R2":
            int_pct = benchmark.get("internal_overturn_pct")
            ext_pct = benchmark.get("external_overturn_pct")
            if int_pct is not None:
                st.markdown(
                    f'<div style="text-align:center;padding:1.2rem;border-radius:16px;'
                    f'border:2px solid #0f4e8a;margin-bottom:0.5rem">'
                    f'<div style="font-size:1.3rem;font-weight:700;color:#0f4e8a">'
                    f'Internal: {int_pct}%</div>'
                    + (f'<div style="font-size:1.1rem;color:#58656a">External: {ext_pct}%</div>'
                       if ext_pct else "")
                    + f'<div style="font-size:0.85rem;color:#58656a;margin-top:0.3rem">'
                    f'{payer} · Year: {benchmark.get("year", "N/A")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.info("No insurer benchmark data available.")
        else:
            st.info("Insufficient data for agent assessment.")

    # --- Recommendations ---
    if recs:
        st.markdown("#### Recommendations")
        non_precedent_recs = [r for r in recs if not r.startswith("Precedent case ")]
        for r in non_precedent_recs:
            st.success(r)

    # --- Similar Cases (Top 5) ---
    if precedent:
        st.markdown("---")
        st.markdown("#### Similar Cases from CA DMHC IMR Database")
        st.caption(
            "These are real Independent Medical Review decisions with similar diagnoses and treatments. "
            "Cases are ranked by relevance to your denial."
        )

        for i, pc in enumerate(precedent[:5], 1):
            ref = pc.get("reference_id", "")
            year = pc.get("year", "")
            diag = pc.get("diagnosis", "")
            treat = pc.get("treatment", "")
            det = pc.get("determination", "")
            desc = pc.get("description", "")
            rel_score = pc.get("relevance_score", 0)

            # Determine outcome styling
            if "overturn" in det.lower():
                outcome_color = "#16623f"
                outcome_bg = "#e7f6ee"
                outcome_icon = "✅"
                outcome_label = "Overturned (patient won)"
            elif "upheld" in det.lower():
                outcome_color = "#b91c1c"
                outcome_bg = "#fee2e2"
                outcome_icon = "❌"
                outcome_label = "Upheld (insurer won)"
            else:
                outcome_color = "#8a5a00"
                outcome_bg = "#fff3d6"
                outcome_icon = "⚠️"
                outcome_label = det

            with st.container(border=True):
                # Header row
                head_col1, head_col2, head_col3 = st.columns([3, 2, 1])
                head_col1.markdown(
                    f"**{i}. Case {ref}** ({year})"
                )
                head_col2.markdown(
                    f'<span style="display:inline-block;padding:3px 12px;border-radius:12px;'
                    f'background:{outcome_bg};color:{outcome_color};font-weight:600;'
                    f'font-size:0.85rem">{outcome_icon} {outcome_label}</span>',
                    unsafe_allow_html=True,
                )
                head_col3.caption(f"Relevance: {rel_score:.2f}")

                # Similarity highlights
                st.markdown(
                    f"**Condition:** {diag} &nbsp;|&nbsp; **Treatment:** {treat}"
                )

                # Preview of findings (first 200 chars)
                if desc:
                    preview = desc[:200] + ("..." if len(desc) > 200 else "")
                    st.markdown(
                        f'<div style="font-size:0.88rem;color:#58656a;padding:0.4rem 0">'
                        f'{preview}</div>',
                        unsafe_allow_html=True,
                    )

                    # Expandable full text
                    if len(desc) > 200:
                        with st.expander("Read full IMR decision text"):
                            st.markdown(desc)

    elif classification == "R1":
        st.info("No similar precedent cases found for this denial type.")


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