from __future__ import annotations

from datetime import datetime, timezone
from html import escape
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
from .feature_flags import is_demo_user_mode


def render_sources(sources: list[dict[str, Any]]) -> None:
    if not sources:
        st.caption("No source snippets returned.")
        return
    for src in sources:
        st.markdown(
            f"- {src.get('file_name', 'document')} p.{src.get('page_number', '?')} (score={src.get('score', 'n/a')})"
        )
        st.caption(src.get("snippet", ""))


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


def _split_multiline_or_csv(value: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for line in value.splitlines():
        for part in line.split(","):
            item = part.strip()
            if not item:
                continue
            if item in seen:
                continue
            seen.add(item)
            tokens.append(item)
    return tokens


def _reason_values_for_edit(reasons: list[Any]) -> list[str]:
    out: list[str] = []
    for reason in reasons:
        if isinstance(reason, dict):
            label = str(reason.get("label") or "").strip()
            if label:
                out.append(label)
        else:
            raw = str(reason).strip()
            if raw:
                out.append(raw)
    return out


def _deadline_values_for_edit(deadlines: list[Any]) -> list[str]:
    out: list[str] = []
    for deadline in deadlines:
        if isinstance(deadline, dict):
            value = str(deadline.get("value") or "").strip()
            if value:
                out.append(value)
        else:
            raw = str(deadline).strip()
            if raw:
                out.append(raw)
    return out


def render_overview(case_payload: dict[str, Any]) -> None:
    case = case_payload["case"]
    extraction = case_payload.get("extraction")

    col1, col2, col3 = st.columns(3)
    col1.metric("Case ID", case["case_id"])
    col2.metric("Status", case["status"])
    col3.metric("Documents", len(case_payload.get("documents", [])))

    if extraction:
        case_json = extraction.get("case_json") or {}
        parties = case_json.get("parties") if isinstance(case_json.get("parties"), dict) else {}
        identifiers = case_json.get("identifiers") if isinstance(case_json.get("identifiers"), dict) else {}
        reasons = case_json.get("denial_reasons") if isinstance(case_json.get("denial_reasons"), list) else []
        deadlines = case_json.get("deadlines") if isinstance(case_json.get("deadlines"), list) else []
        channels = case_json.get("submission_channels") if isinstance(case_json.get("submission_channels"), list) else []
        requested_docs = case_json.get("requested_documents") if isinstance(case_json.get("requested_documents"), list) else []

        st.subheader("Extracted Case Summary")
        st.caption(f"Extraction mode: {extraction.get('mode', 'unknown')}")

        summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
        summary_col1.metric("Payer", _display_value(case_json.get("payer")))
        summary_col2.metric("Denial Reasons", str(len(reasons)))
        summary_col3.metric("Deadlines Found", str(len(deadlines)))
        summary_col4.metric("Requested Docs", str(len(requested_docs)))

        details_col1, details_col2 = st.columns(2, gap="large")
        with details_col1:
            with st.container(border=True):
                st.markdown("### Parties")
                st.write(f"Patient: **{_display_value(parties.get('patient_name'))}**")
                st.write(f"Claimant: **{_display_value(parties.get('claimant_name'))}**")
                st.write(f"Payer: **{_display_value(case_json.get('payer'))}**")
                st.write(f"Plan Type: **{_display_value(case_json.get('plan_type'))}**")

        with details_col2:
            with st.container(border=True):
                st.markdown("### Claim Identifiers")
                st.write(f"Claim Number: **{_display_value(identifiers.get('claim_number'))}**")
                st.write(f"Auth Number: **{_display_value(identifiers.get('auth_number'))}**")
                st.write(f"Member ID: **{_display_value(identifiers.get('member_id'))}**")

        st.markdown("### Denial Reasons")
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

        supplemental_col1, supplemental_col2 = st.columns(2, gap="large")
        with supplemental_col1:
            st.markdown("### Deadlines")
            if deadlines:
                deadline_rows = []
                for item in deadlines:
                    if isinstance(item, dict):
                        citation = item.get("citation") if isinstance(item.get("citation"), dict) else {}
                        source_file = _display_value(citation.get("file_name"))
                        source_page = _display_value(citation.get("page_number"))
                        source = "—"
                        if source_file != "—" or source_page != "—":
                            source = f"{source_file} · p.{source_page}"
                        deadline_rows.append({"Deadline": _display_value(item.get("value")), "Source": source})
                    else:
                        deadline_rows.append({"Deadline": _display_value(item), "Source": "—"})
                st.dataframe(deadline_rows, hide_index=True, use_container_width=True)
            else:
                st.info("No explicit deadlines detected.")

        with supplemental_col2:
            st.markdown("### Submission Channels")
            if channels:
                for channel in channels:
                    st.write(f"- {_display_value(channel).title()}")
            else:
                st.info("No submission channels detected.")

            st.markdown("### Requested Documents")
            if requested_docs:
                for doc in requested_docs:
                    st.write(f"- {_display_value(doc).replace('_', ' ').title()}")
            else:
                st.info("No missing document requests detected.")

        st.markdown("### Manual Edits")
        st.caption("Fill missing extraction fields or correct values before generating tasks/letters.")
        case_id = case.get("case_id")
        edit_flag_key = f"show_extraction_edit_form_{case_id}"
        if st.button(
            "Edit Extracted Data",
            icon=":material/edit_note:",
            key=f"edit_extracted_data_button_{case_id}",
        ):
            st.session_state[edit_flag_key] = not bool(st.session_state.get(edit_flag_key, False))

        if st.session_state.get(edit_flag_key, False):
            with st.container(border=True):
                st.markdown("#### Update Missing Fields")
                with st.form(f"manual_extraction_edit_form_{case_id}"):
                    form_col1, form_col2 = st.columns(2, gap="large")
                    with form_col1:
                        payer_value = st.text_input("Payer", value=str(case_json.get("payer") or ""))
                        plan_type_value = st.text_input("Plan Type", value=str(case_json.get("plan_type") or ""))
                        patient_name_value = st.text_input(
                            "Patient Name",
                            value=str(parties.get("patient_name") or ""),
                        )
                        claimant_name_value = st.text_input(
                            "Claimant Name",
                            value=str(parties.get("claimant_name") or ""),
                        )

                    with form_col2:
                        claim_number_value = st.text_input(
                            "Claim Number",
                            value=str(identifiers.get("claim_number") or ""),
                        )
                        auth_number_value = st.text_input(
                            "Auth Number",
                            value=str(identifiers.get("auth_number") or ""),
                        )
                        member_id_value = st.text_input(
                            "Member ID",
                            value=str(identifiers.get("member_id") or ""),
                        )

                    denial_reasons_value = st.text_area(
                        "Denial Reasons (one per line or comma-separated)",
                        value="\n".join(_reason_values_for_edit(reasons)),
                        help="Use labels like: medical_necessity, prior_authorization, administrative, coding_billing, out_of_network.",
                    )
                    deadlines_value = st.text_area(
                        "Deadlines (one per line or comma-separated)",
                        value="\n".join(_deadline_values_for_edit(deadlines)),
                        help="Example: 30 days from receipt",
                    )
                    channels_value = st.text_area(
                        "Submission Channels (one per line or comma-separated)",
                        value="\n".join(str(c) for c in channels),
                        help="Example: fax, portal, mail",
                    )
                    requested_docs_value = st.text_area(
                        "Requested Documents (one per line or comma-separated)",
                        value="\n".join(str(d) for d in requested_docs),
                        help="Example: denial_letter, eob, prior_auth, medical_records",
                    )

                    save_manual_updates = st.form_submit_button(
                        "Save Manual Updates",
                        use_container_width=True,
                    )

                if save_manual_updates:
                    payload = {
                        "payer": payer_value.strip(),
                        "plan_type": plan_type_value.strip(),
                        "patient_name": patient_name_value.strip(),
                        "claimant_name": claimant_name_value.strip(),
                        "claim_number": claim_number_value.strip(),
                        "auth_number": auth_number_value.strip(),
                        "member_id": member_id_value.strip(),
                        "denial_reasons": _split_multiline_or_csv(denial_reasons_value),
                        "deadlines": _split_multiline_or_csv(deadlines_value),
                        "submission_channels": _split_multiline_or_csv(channels_value),
                        "requested_documents": _split_multiline_or_csv(requested_docs_value),
                    }
                    _, update_err = safe_call(
                        api_patch,
                        f"/cases/{case_id}/extract",
                        json_body=payload,
                    )
                    if update_err:
                        st.error(update_err)
                    else:
                        st.success("Extraction data updated.")
                        st.session_state[edit_flag_key] = False
                        st.rerun()

        warnings = extraction.get("warnings", [])
        if warnings:
            st.markdown("### Extraction Warnings")
            st.warning("\n".join(warnings))

        with st.expander("View Raw Extracted JSON"):
            st.json(case_json)
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


def _parse_iso_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _latest_datetime(rows: list[dict[str, Any]], key: str) -> datetime | None:
    latest: datetime | None = None
    for row in rows:
        parsed = _parse_iso_datetime(row.get(key))
        if parsed and (latest is None or parsed > latest):
            latest = parsed
    return latest


def _format_datetime_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%b %d, %Y %I:%M %p UTC")


def _workflow_button_suffix(state: str) -> str:
    mapping = {
        "complete": "✓ Done",
        "stale": "↻ Re-run",
        "attention": "⚠ Needs Check",
        "pending": "○ Pending",
    }
    return mapping.get(state, "○ Pending")


def _workflow_note_markup(state: str, note: str) -> str:
    icon = {
        "complete": "✓",
        "stale": "↻",
        "attention": "⚠",
        "pending": "•",
    }.get(state, "•")
    palette = {
        "complete": ("#16623f", "rgba(22,98,63,0.11)", "rgba(22,98,63,0.26)"),
        "stale": ("#0f4e8a", "rgba(15,78,138,0.11)", "rgba(15,78,138,0.28)"),
        "attention": ("#8a5a00", "rgba(196,132,30,0.13)", "rgba(196,132,30,0.32)"),
        "pending": ("#4f5f73", "rgba(79,95,115,0.1)", "rgba(79,95,115,0.24)"),
    }
    text_color, bg_color, border_color = palette.get(state, palette["pending"])
    return (
        "<div style='margin:0.28rem 0 0.48rem;padding:0.42rem 0.56rem;border-radius:10px;"
        f"background:{bg_color};border:1px solid {border_color};color:{text_color};"
        "font-size:0.82rem;line-height:1.34;'>"
        f"{icon} {escape(note)}</div>"
    )


def _derive_workflow_states(case_payload: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    states: dict[str, dict[str, str]] = {
        "process": {"state": "pending", "note": "Upload at least one document to begin processing."},
        "extract": {"state": "pending", "note": "Run extraction to build structured case context."},
        "tasks": {"state": "pending", "note": "Generate tasks after extraction is complete."},
        "letter": {"state": "pending", "note": "Generate an appeal letter draft from extracted data."},
        "packet": {"state": "pending", "note": "Generate packet PDF after letter review."},
    }
    if not case_payload:
        return states

    documents = case_payload.get("documents") if isinstance(case_payload.get("documents"), list) else []
    extraction = case_payload.get("extraction") if isinstance(case_payload.get("extraction"), dict) else None
    tasks = case_payload.get("tasks") if isinstance(case_payload.get("tasks"), list) else []
    artifacts = case_payload.get("artifacts") if isinstance(case_payload.get("artifacts"), list) else []

    doc_total = len(documents)
    indexed_docs = [
        doc for doc in documents if str(doc.get("processed_status") or "").strip().lower().startswith("indexed")
    ]
    failed_docs = [
        doc for doc in documents if str(doc.get("processed_status") or "").strip().lower().startswith("failed")
    ]
    latest_doc_upload_dt = _latest_datetime(documents, "uploaded_at")
    latest_indexed_dt = _latest_datetime(indexed_docs, "uploaded_at")

    if doc_total == 0:
        states["process"] = {"state": "pending", "note": "No documents uploaded yet."}
    elif failed_docs:
        states["process"] = {
            "state": "attention",
            "note": f"{len(indexed_docs)}/{doc_total} indexed; {len(failed_docs)} failed. Re-run processing.",
        }
    elif len(indexed_docs) == doc_total:
        process_note = f"{doc_total} document(s) indexed."
        latest_process = _format_datetime_utc(latest_indexed_dt)
        if latest_process:
            process_note = f"{process_note} Last run {latest_process}."
        states["process"] = {"state": "complete", "note": process_note}
    else:
        states["process"] = {
            "state": "pending",
            "note": f"{len(indexed_docs)}/{doc_total} indexed. Run processing to complete indexing.",
        }

    extraction_dt = _parse_iso_datetime(extraction.get("created_at")) if extraction else None
    if not extraction:
        if doc_total:
            states["extract"] = {"state": "pending", "note": "Documents exist, but extraction has not run yet."}
    elif latest_doc_upload_dt and extraction_dt and extraction_dt < latest_doc_upload_dt:
        states["extract"] = {"state": "stale", "note": "New documents were added after last extraction."}
    else:
        mode = str(extraction.get("mode") or "unknown")
        extract_note = f"Extraction complete ({mode})."
        latest_extract = _format_datetime_utc(extraction_dt)
        if latest_extract:
            extract_note = f"{extract_note} Last run {latest_extract}."
        states["extract"] = {"state": "complete", "note": extract_note}

    task_dt = _latest_datetime(tasks, "created_at")
    done_tasks = sum(1 for task in tasks if str(task.get("status") or "").strip().lower() == "done")
    if not extraction:
        states["tasks"] = {"state": "pending", "note": "Run extraction first to generate task suggestions."}
    elif not tasks:
        states["tasks"] = {"state": "pending", "note": "No tasks generated yet."}
    elif extraction_dt and task_dt and task_dt < extraction_dt:
        states["tasks"] = {"state": "stale", "note": "Extraction was updated after tasks were generated."}
    else:
        task_note = f"{done_tasks}/{len(tasks)} tasks marked done."
        latest_tasks = _format_datetime_utc(task_dt)
        if latest_tasks:
            task_note = f"{task_note} Last generated {latest_tasks}."
        states["tasks"] = {"state": "complete", "note": task_note}

    letters = [artifact for artifact in artifacts if artifact.get("type") == "letter"]
    letter_dt = _latest_datetime(letters, "created_at")
    latest_letter_version = max((int(artifact.get("version") or 0) for artifact in letters), default=0)
    if not letters:
        states["letter"] = {"state": "pending", "note": "No letter generated yet."}
    elif extraction_dt and letter_dt and letter_dt < extraction_dt:
        states["letter"] = {"state": "stale", "note": "Extraction is newer than the latest letter draft."}
    else:
        letter_note = f"Latest letter version v{latest_letter_version}."
        latest_letter = _format_datetime_utc(letter_dt)
        if latest_letter:
            letter_note = f"{letter_note} Generated {latest_letter}."
        states["letter"] = {"state": "complete", "note": letter_note}

    packets = [artifact for artifact in artifacts if artifact.get("type") == "packet_pdf"]
    packet_dt = _latest_datetime(packets, "created_at")
    latest_packet_version = max((int(artifact.get("version") or 0) for artifact in packets), default=0)
    if not packets:
        states["packet"] = {"state": "pending", "note": "No packet PDF generated yet."}
    elif (letter_dt and packet_dt and packet_dt < letter_dt) or (extraction_dt and packet_dt and packet_dt < extraction_dt):
        states["packet"] = {"state": "stale", "note": "Packet is older than current letter or extraction context."}
    else:
        packet_note = f"Latest packet version v{latest_packet_version}."
        latest_packet = _format_datetime_utc(packet_dt)
        if latest_packet:
            packet_note = f"{packet_note} Generated {latest_packet}."
        states["packet"] = {"state": "complete", "note": packet_note}

    return states


def render_upload_documents_card(case_id: str | None, *, key_prefix: str) -> None:
    if not case_id:
        st.caption("Select a case to upload documents.")
        return

    demo_mode = is_demo_user_mode()

    with st.container(border=True):
        st.markdown("### Upload Documents")
        st.caption("Add denial letters, EOBs, prior auth records, or supporting medical documents.")
        uploaded = st.file_uploader(
            "Upload document",
            type=["pdf", "txt", "docx", "png", "jpg", "jpeg", "tiff"],
            key=f"{key_prefix}_upload_file",
            disabled=demo_mode,
        )
        doc_type = st.selectbox(
            "Doc type",
            DOC_TYPES,
            key=f"{key_prefix}_doc_type",
            disabled=demo_mode,
        )
        auto_process = st.toggle(
            "Auto process on upload",
            value=True,
            key=f"{key_prefix}_auto_process",
            disabled=demo_mode,
        )
        if demo_mode:
            st.caption("Demo mode is enabled. Uploads are temporarily disabled.")

        if st.button(
            "Upload Document",
            use_container_width=True,
            key=f"{key_prefix}_upload_btn",
            disabled=demo_mode,
        ):
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


def render_workflow_actions_card(
    case_id: str | None,
    *,
    key_prefix: str,
    case_payload: dict[str, Any] | None = None,
    tab_jump_state_key: str | None = None,
) -> None:
    if not case_id:
        st.caption("Select a case to run workflow actions.")
        return

    with st.container(border=True):
        st.markdown("### Workflow Actions")
        st.caption("Follow the workflow in order, or jump to the step you need.")
        st.markdown(
            """
            <div style="display:flex;flex-wrap:wrap;gap:0.38rem;margin:0.12rem 0 0.58rem;">
                <span style="display:inline-flex;align-items:center;gap:0.28rem;padding:0.18rem 0.56rem;border-radius:999px;
                    border:1px solid rgba(22,98,63,0.35);background:rgba(22,98,63,0.11);font-size:0.73rem;font-weight:700;color:#16623f;">✓ Done</span>
                <span style="display:inline-flex;align-items:center;gap:0.28rem;padding:0.18rem 0.56rem;border-radius:999px;
                    border:1px solid rgba(15,78,138,0.35);background:rgba(15,78,138,0.11);font-size:0.73rem;font-weight:700;color:#0f4e8a;">↻ Re-run</span>
                <span style="display:inline-flex;align-items:center;gap:0.28rem;padding:0.18rem 0.56rem;border-radius:999px;
                    border:1px solid rgba(196,132,30,0.35);background:rgba(196,132,30,0.13);font-size:0.73rem;font-weight:700;color:#8a5a00;">⚠ Needs Check</span>
                <span style="display:inline-flex;align-items:center;gap:0.28rem;padding:0.18rem 0.56rem;border-radius:999px;
                    border:1px solid rgba(79,95,115,0.28);background:rgba(79,95,115,0.1);font-size:0.73rem;font-weight:700;color:#4f5f73;">○ Pending</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        state_by_step = _derive_workflow_states(case_payload)
        ordered_actions: list[tuple[str, str, str, str, dict[str, Any], str]] = [
            ("process", "Process Documents", f"/cases/{case_id}/process", "Processing complete", {}, "process_btn"),
            ("extract", "Run Extraction", f"/cases/{case_id}/extract", "Case extraction complete", {}, "extract_btn"),
            ("tasks", "Generate Tasks", f"/cases/{case_id}/tasks/generate", "Tasks generated", {}, "tasks_btn"),
            ("letter", "Generate Letter", f"/cases/{case_id}/letter", "Letter generated", {"style": "formal"}, "letter_btn"),
            (
                "packet",
                "Generate Packet PDF",
                f"/cases/{case_id}/packet",
                "Packet generated",
                {"include_uploaded_pdfs": True},
                "packet_btn",
            ),
        ]
        done_steps = sum(1 for step in state_by_step.values() if step.get("state") == "complete")
        st.progress(
            done_steps / len(ordered_actions),
            text=f"Completed workflow steps: {done_steps}/{len(ordered_actions)}",
        )
        st.markdown("<div style='height:0.2rem;'></div>", unsafe_allow_html=True)

        for idx, (step_key, label, path, success_message, json_body, key_suffix) in enumerate(ordered_actions):
            step_state = state_by_step.get(step_key, {"state": "pending", "note": "Not run yet."})
            button_label = f"{label} · {_workflow_button_suffix(step_state.get('state', 'pending'))}"
            if st.button(button_label, use_container_width=True, key=f"{key_prefix}_{key_suffix}"):
                if tab_jump_state_key:
                    target_section = {
                        "process": "Documents",
                        "extract": "Overview",
                        "tasks": "Tasks",
                        "letter": "Packet Builder",
                        "packet": "Packet Builder",
                    }.get(step_key)
                    if target_section:
                        st.session_state[tab_jump_state_key] = target_section
                _trigger_case_action(case_id, path, success_message, json_body=json_body)
            note = step_state.get("note", "")
            if note:
                st.markdown(_workflow_note_markup(step_state.get("state", "pending"), note), unsafe_allow_html=True)
            if idx < len(ordered_actions) - 1:
                st.markdown(
                    "<div style='height:2.1rem;display:flex;align-items:center;justify-content:center;"
                    "font-size:1.35rem;line-height:1;margin:-0.5rem 0 0.5rem 0;'>↓</div>",
                    unsafe_allow_html=True,
                )

        st.divider()
        st.markdown(
            "<p style='margin:0.2rem 0 0.2rem;font-size:1.4rem;font-weight:700;line-height:1.2;'>"
            "Upload Additional Documents</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='margin:0.2rem 0 0.55rem;font-size:0.95rem;line-height:1.4;opacity:0.82;'>"
            "Need to add more files before continuing the workflow?</p>",
            unsafe_allow_html=True,
        )
        if st.button(
            "Go to Documents Upload",
            icon=":material/upload_file:",
            use_container_width=True,
            key=f"{key_prefix}_upload_more_btn",
        ):
            if tab_jump_state_key:
                st.session_state[tab_jump_state_key] = "Documents"
            st.rerun()


def render_case_actions_panel(
    case_id: str | None,
    *,
    key_prefix: str,
    case_payload: dict[str, Any] | None = None,
) -> None:
    if not case_id:
        st.caption("Select a case to enable uploads and workflow actions.")
        return

    st.markdown("### Case Workspace")
    st.caption("Everything you need for the current case is grouped here, so the workflow stays in the main canvas.")

    upload_col, actions_col = st.columns([1.2, 1], gap="large")
    with upload_col:
        render_upload_documents_card(case_id, key_prefix=key_prefix)
    with actions_col:
        render_workflow_actions_card(case_id, key_prefix=key_prefix, case_payload=case_payload)
