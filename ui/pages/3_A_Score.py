"""A-Score Dashboard."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import streamlit as st

from lib.api import ensure_state, fetch_appealability, fetch_case_payload, fetch_cases, select_case


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .ascore-hero {
            padding: 1.2rem 1.4rem; border-radius: 20px;
            background:
                radial-gradient(circle at 8% 12%, rgba(255, 208, 136, 0.32), transparent 35%),
                radial-gradient(circle at 97% -8%, rgba(236, 196, 95, 0.3), transparent 33%),
                radial-gradient(circle at 72% 88%, rgba(160, 209, 186, 0.22), transparent 42%),
                linear-gradient(125deg, #fffdf8 0%, #f3f7ef 52%, #e6f0df 100%);
            color: #233224; margin-bottom: 1.2rem;
            border: 1px solid #d8d4bf;
            box-shadow: 0 16px 32px rgba(58, 64, 39, 0.16);
            position: relative;
            overflow: hidden;
        }
        .ascore-hero::before {
            content: "";
            position: absolute;
            width: 240px;
            height: 240px;
            top: -122px;
            right: -94px;
            border-radius: 999px;
            background: rgba(236, 196, 95, 0.28);
        }
        .ascore-hero::after {
            content: "";
            position: absolute;
            inset: 0;
            background:
                radial-gradient(circle, rgba(142, 113, 31, 0.09) 1.05px, transparent 1.2px),
                linear-gradient(90deg, rgba(255, 255, 255, 0.22) 0%, rgba(255, 255, 255, 0) 46%);
            background-size: 18px 18px, 100% 100%;
            opacity: 0.35;
            pointer-events: none;
            mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.35) 0%, rgba(0, 0, 0, 0) 72%);
        }
        .ascore-hero > * {
            position: relative;
            z-index: 1;
        }
        .ascore-hero-kicker {
            text-transform: uppercase; letter-spacing: 0.12em;
            font-size: 0.7rem; color: #76611f;
        }
        .ascore-hero h2 { margin: 0.15rem 0 0; font-size: 1.7rem; color: #233224; }
        .ascore-hero p { margin: 0.4rem 0 0; font-size: 0.88rem; color: #52634f; }

        .section-label {
            text-transform: uppercase; letter-spacing: 0.12em;
            font-size: 0.72rem; font-weight: 700;
            color: color-mix(in srgb, currentColor 58%, transparent);
            margin-bottom: 0.5rem;
        }

        /* --- Your Case boxes --- */
        .your-case-box {
            padding: 0.6rem 0.9rem; border-radius: 12px;
            background: linear-gradient(
                180deg,
                color-mix(in srgb, currentColor 5%, transparent) 0%,
                color-mix(in srgb, currentColor 7%, transparent) 100%
            );
            border: 1px solid color-mix(in srgb, currentColor 22%, transparent);
            margin-bottom: 0.5rem;
        }
        .your-case-label {
            font-size: 0.68rem; text-transform: uppercase;
            letter-spacing: 0.1em; font-weight: 700;
            color: color-mix(in srgb, currentColor 58%, transparent);
        }
        .your-case-value {
            font-size: 0.92rem; color: inherit; font-weight: 600; margin-top: 0.1rem;
        }

        /* --- Score cards --- */
        .score-card {
            text-align: center; padding: 1.3rem 1rem;
            border-radius: 16px; border: 2px solid color-mix(in srgb, currentColor 22%, transparent);
            margin-bottom: 0.7rem;
            background: linear-gradient(
                180deg,
                color-mix(in srgb, currentColor 5%, transparent) 0%,
                color-mix(in srgb, currentColor 7%, transparent) 100%
            );
            color: inherit;
        }
        .score-big { font-size: 2.5rem; font-weight: 800; line-height: 1.1; }
        .score-sub {
            font-size: 0.84rem;
            color: color-mix(in srgb, currentColor 58%, transparent);
            margin-top: 0.25rem;
        }
        .score-subtitle {
            font-size: 0.82rem;
            color: color-mix(in srgb, currentColor 60%, transparent);
            margin-bottom: 0.5rem;
        }
        .score-source {
            font-size: 0.78rem;
            color: color-mix(in srgb, currentColor 60%, transparent);
            margin-bottom: 0.4rem;
        }
        .score-assessment {
            margin-top: 0.5rem;
            font-size: 0.86rem;
            line-height: 1.55;
            color: color-mix(in srgb, currentColor 86%, transparent);
            text-align: left;
            padding: 0 0.3rem;
        }

        .conf-pill {
            display: inline-block; padding: 2px 12px; border-radius: 14px;
            font-size: 0.72rem; font-weight: 700; color: #fff; margin-top: 0.35rem;
        }
        .conf-high   { background: #22a06b; }
        .conf-medium { background: #cf8a00; }
        .conf-low    { background: #dc3545; }

        /* --- Precedent case cards --- */
        .outcome-pill {
            display: inline-block; padding: 3px 12px; border-radius: 14px;
            font-size: 0.82rem; font-weight: 600;
            border: 1px solid transparent;
        }
        .outcome-overturned {
            background: color-mix(in srgb, #22a06b 24%, transparent);
            color: color-mix(in srgb, #22a06b 64%, currentColor 36%);
            border-color: color-mix(in srgb, #22a06b 45%, transparent);
        }
        .outcome-upheld {
            background: color-mix(in srgb, #dc3545 24%, transparent);
            color: color-mix(in srgb, #dc3545 64%, currentColor 36%);
            border-color: color-mix(in srgb, #dc3545 44%, transparent);
        }

        .case-card-header { font-size: 1.02rem; font-weight: 700; color: inherit; }
        .case-card-meta {
            font-size: 0.86rem;
            color: color-mix(in srgb, currentColor 60%, transparent);
        }
        .case-meta-label {
            color: color-mix(in srgb, currentColor 74%, transparent);
        }
        .case-card-finding {
            font-size: 0.86rem;
            color: color-mix(in srgb, currentColor 86%, transparent);
            padding: 0.3rem 0;
            line-height: 1.5;
        }

        .agent-comment {
            font-size: 0.86rem;
            color: color-mix(in srgb, currentColor 86%, transparent);
            background: color-mix(in srgb, currentColor 9%, transparent);
            border-left: 3px solid color-mix(in srgb, var(--primary-color, #1f6aa9) 55%, currentColor 45%);
            padding: 0.45rem 0.8rem; border-radius: 8px;
            margin: 0.35rem 0; line-height: 1.45;
        }
        .agent-comment b, .agent-comment strong {
            color: color-mix(in srgb, var(--primary-color, #1f6aa9) 78%, currentColor 22%);
        }

        /* --- Recommendations --- */
        .rec-box {
            padding: 0.55rem 0.85rem; border-radius: 10px;
            background: color-mix(in srgb, currentColor 9%, transparent);
            border-left: 4px solid color-mix(in srgb, var(--primary-color, #1f6aa9) 55%, currentColor 45%);
            margin-bottom: 0.45rem;
            font-size: 0.86rem;
            color: color-mix(in srgb, currentColor 86%, transparent);
        }
        .kw-chip {
            display: inline-block;
            padding: 2px 10px;
            margin: 2px;
            border-radius: 10px;
            background: color-mix(in srgb, currentColor 10%, transparent);
            color: inherit;
            font-size: 0.8rem;
            border: 1px solid color-mix(in srgb, currentColor 30%, transparent);
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _latest_value(items: list[dict[str, Any]], key: str) -> str:
    values = [str(item.get(key)) for item in items if item.get(key)]
    return max(values) if values else ""


def _case_payload_fingerprint(case_payload: dict[str, Any]) -> str:
    case = case_payload.get("case") or {}
    extraction = case_payload.get("extraction") or {}
    documents = case_payload.get("documents") or []
    tasks = case_payload.get("tasks") or []
    artifacts = case_payload.get("artifacts") or []
    events = case_payload.get("events") or []

    projection = {
        "case": {
            "case_id": case.get("case_id"),
            "status": case.get("status"),
            "title": case.get("title"),
            "updated_at": case.get("updated_at"),
        },
        "extraction": {
            "extraction_id": extraction.get("extraction_id"),
            "created_at": extraction.get("created_at"),
            "mode": extraction.get("mode"),
            "warnings_count": len(extraction.get("warnings") or []),
        },
        "documents": {
            "count": len(documents),
            "latest_uploaded_at": _latest_value(documents, "uploaded_at"),
            "status_counts": _count_by(documents, "processed_status"),
        },
        "tasks": {
            "count": len(tasks),
            "latest_created_at": _latest_value(tasks, "created_at"),
            "status_counts": _count_by(tasks, "status"),
        },
        "artifacts": {
            "count": len(artifacts),
            "latest_created_at": _latest_value(artifacts, "created_at"),
            "type_counts": _count_by(artifacts, "type"),
        },
        "events": {
            "count": len(events),
            "latest_timestamp": _latest_value(events, "timestamp"),
            "type_counts": _count_by(events, "type"),
        },
    }
    canonical = json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _score_color(rate: float | None) -> str:
    if rate is None:
        return "#6b7684"
    if rate >= 0.7:
        return "#5ce0a0"
    if rate >= 0.4:
        return "#f0c050"
    return "#f07070"


def _score_pct(rate: float | None) -> str:
    return "—" if rate is None else f"{int(rate * 100)}%"


def _strength(rate: float | None) -> str:
    if rate is None:
        return "Insufficient data"
    pct = int(rate * 100)
    if pct >= 70:
        return "Strong"
    if pct >= 40:
        return "Moderate"
    return "Limited"


def _conf_class(conf: str) -> str:
    if conf == "high":
        return "conf-high"
    if conf == "medium":
        return "conf-medium"
    return "conf-low"


def _generate_comparison(user_diag: str, user_treat: str, pc: dict[str, Any]) -> str:
    pc_diag = pc.get("diagnosis", "")
    pc_treat = pc.get("treatment", "")
    det = pc.get("determination", "")
    desc = (pc.get("description", "") or "")[:300]
    is_overturned = "overturn" in det.lower()

    import re
    similarities = []
    differences = []

    user_d = set(re.findall(r"[a-z]{3,}", user_diag.lower())) - {"other", "unknown", "not", "identified"}
    pc_d = set(re.findall(r"[a-z]{3,}", pc_diag.lower())) - {"other", "unknown"}
    d_overlap = user_d & pc_d
    if d_overlap:
        similarities.append(f"same diagnosis category ({', '.join(sorted(d_overlap))})")
    elif pc_diag:
        differences.append(f"different diagnosis ({pc_diag.split('/')[0].strip()})")

    user_t = set(re.findall(r"[a-z]{3,}", user_treat.lower())) - {"other", "unknown", "not", "identified"}
    pc_t = set(re.findall(r"[a-z]{3,}", pc_treat.lower())) - {"other", "unknown"}
    t_overlap = user_t & pc_t
    if t_overlap:
        similarities.append(f"similar treatment type ({', '.join(sorted(t_overlap))})")
    elif pc_treat:
        differences.append(f"treatment differs ({pc_treat.split('/')[0].strip()})")

    parts = []
    if similarities:
        parts.append(f"<strong>Similarities:</strong> This case shares {'; '.join(similarities)} with your denial.")
    else:
        parts.append("This case involves a different condition but the same denial type (medical necessity).")

    if differences:
        parts.append(f"<strong>Differences:</strong> {'; '.join(differences)}.")

    if is_overturned:
        parts.append(
            "The independent reviewer <strong>overturned</strong> the insurer's denial in this case."
        )
        # Extract a reason from the description if available
        if "medically necessary" in desc.lower() or "appropriate" in desc.lower():
            parts.append(
                "The reviewer found the treatment to be medically necessary based on the patient's "
                "clinical presentation and supporting literature."
            )
        else:
            parts.append(
                "The reviewer's reasoning in this case may provide useful arguments for your own appeal."
            )
    else:
        parts.append("The insurer's denial was <strong>upheld</strong> in this case.")
        parts.append(
            "Understanding why this appeal failed can help you avoid similar weaknesses "
            "in your own submission."
        )

    return " ".join(parts)


def _render_score_card(
    title: str, subtitle: str, rate: float | None,
    detail_lines: list[str], confidence: str | None = None,
) -> None:
    color = _score_color(rate)
    pct = _score_pct(rate)
    strength = _strength(rate)
    conf_html = ""
    if confidence:
        conf_html = (
            '<span class="score-sub" style="font-size:0.82rem;margin-right:0.35rem">'
            'Confidence:</span>'
            f'<span class="conf-pill {_conf_class(confidence)}">'
            f'{confidence.replace("_", " ").title()}</span>'
        )
    detail_html = "<br>".join(f'<span class="score-sub">{l}</span>' for l in detail_lines)

    st.markdown(
        f'<div class="score-card" style="border-color:{color}44">'
        f'<div class="section-label">{title}</div>'
        f'<div class="score-subtitle">{subtitle}</div>'
        f'<div class="score-big" style="color:{color}">{pct}</div>'
        f'<div class="score-sub" style="font-size:0.95rem;font-weight:600;color:{color}">'
        f'{strength}</div>'
        f'{detail_html}'
        f'<div style="margin-top:0.35rem">{conf_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _highlight_shared_words(text: str, query: str) -> str:
    """Highlight words in text that also appear in the query."""
    import re
    if not query:
        return text
    query_words = set(re.findall(r"[a-zA-Z]{4,}", query.lower()))
    # Remove very common words
    query_words -= {
        "patient", "requested", "authorization", "coverage", "treatment",
        "medical", "necessary", "case", "this", "that", "with", "from",
        "have", "been", "record", "review", "found", "nature", "criteria",
        "summary", "statutory",
    }
    if not query_words:
        return text

    def _replacer(match: re.Match) -> str:
        word = match.group(0)
        if word.lower() in query_words:
            return (
                f'<mark style="background:color-mix(in srgb,var(--primary-color,#1f6aa9) 18%,transparent);'
                f'color:inherit;padding:0 2px;border-radius:3px">{word}</mark>'
            )
        return word

    return re.sub(r"[a-zA-Z]{4,}", _replacer, text)


def _strip_case_summary_prefix(text: str) -> str:
    return re.sub(
        r"^\s*Nature\s+of\s+Statutory\s+Criteria\s*/\s*Case\s+Summary\s*:\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )


def _render_case_card(i: int, pc: dict[str, Any], user_diag: str, user_treat: str, query_text: str = "") -> None:
    ref = pc.get("reference_id", "")
    year = pc.get("year", "")
    diag = pc.get("diagnosis", "")
    treat = pc.get("treatment", "")
    det = pc.get("determination", "")
    desc = pc.get("description", "")
    rel = pc.get("relevance_score", 0)

    is_overturned = "overturn" in det.lower()
    outcome_class = "outcome-overturned" if is_overturned else "outcome-upheld"
    outcome_icon = "✅" if is_overturned else "❌"
    outcome_text = "Overturned" if is_overturned else "Upheld"

    with st.container(border=True):
        # Header: case ID, outcome pill, rel score — ALL ON ONE LINE
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:nowrap">'
            f'<span class="case-card-header">{i}. Case {ref} '
            f'<span class="case-card-meta">({year})</span></span>'
            f'<span style="white-space:nowrap">'
            f'<span class="outcome-pill {outcome_class}">'
            f'{outcome_icon} {outcome_text}</span>'
            f'&nbsp;<span class="case-card-meta">Rel: {rel:.2f}</span>'
            f'</span></div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<span class="case-card-meta">'
            f'<b class="case-meta-label">Condition:</b> {diag} '
            f'&nbsp;·&nbsp; '
            f'<b class="case-meta-label">Treatment:</b> {treat}'
            f'</span>',
            unsafe_allow_html=True,
        )

        comparison = _generate_comparison(user_diag, user_treat, pc)
        st.markdown(f'<div class="agent-comment">🤖 {comparison}</div>', unsafe_allow_html=True)

        # Keep long statutory/case-summary text collapsed by default for cleaner cards.
        if desc:
            clean_desc = _strip_case_summary_prefix(desc)
            highlighted = _highlight_shared_words(clean_desc, query_text)
            with st.expander("View Nature of Statutory Criteria / Case Summary", expanded=False):
                st.markdown(
                    f'<div class="case-card-finding">{highlighted}</div>',
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="A-Score Dashboard", page_icon="📊", layout="wide")
    ensure_state()
    _inject_styles()

    st.markdown(
        """
        <div class="ascore-hero">
            <div class="ascore-hero-kicker">Appealability Analysis</div>
            <h2>A-Score Dashboard</h2>
            <p>See your appeal likelihood based on 20+ years of California IMR outcomes,
               and review similar cases that were overturned at independent review.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    nav_spacer, nav_col = st.columns([4, 1.3], gap="small")
    with nav_col:
        if st.button(
            "Back to Dashboard",
            icon=":material/dashboard:",
            key="ascore_back_dashboard_btn",
            use_container_width=True,
        ):
            st.switch_page("pages/2_My_Cases.py")

    cases, cases_err = fetch_cases()
    if cases_err:
        st.error(f"Cannot load cases: {cases_err}")
        st.stop()
    if not cases:
        st.info("No cases yet. Create one from the My Cases page first.")
        st.stop()

    selector_col, compute_col = st.columns([5, 1.6], gap="small")
    with selector_col:
        select_case(cases, key_prefix="ascore", label="Select case to analyze")
    case_id = st.session_state.get("selected_case_id")
    if not case_id:
        st.info("Select a case above to see its appealability analysis.")
        st.stop()

    case_payload, payload_err = fetch_case_payload(case_id)
    if payload_err or not case_payload:
        st.error(f"Could not load case: {payload_err}")
        st.stop()

    extraction = case_payload.get("extraction")
    if not extraction:
        st.warning("No extraction available. Upload a denial letter → Process → Extract first.")
        st.stop()

    case_fingerprint = _case_payload_fingerprint(case_payload)
    cache_by_case = st.session_state.setdefault("ascore_cache_by_case", {})
    cached_entry = cache_by_case.get(case_id)
    cache_valid = (
        isinstance(cached_entry, dict)
        and cached_entry.get("fingerprint") == case_fingerprint
        and isinstance(cached_entry.get("appeal_data"), dict)
    )

    with compute_col:
        # Align with the selectbox input row while keeping the selector label visible.
        st.markdown("<div style='height:1.68rem;'></div>", unsafe_allow_html=True)
        button_label = "Compute A-Score" if not cache_valid else "Recompute A-Score"
        compute_clicked = st.button(
            button_label,
            icon=":material/play_arrow:",
            use_container_width=True,
            key=f"ascore_compute_btn_{case_id}",
        )

    if cache_valid:
        st.caption("Showing cached results for this case. Click recompute if you want a fresh run.")
    elif isinstance(cached_entry, dict):
        st.caption("Case data changed since last run. Click compute to refresh scores.")
    else:
        st.caption("Select a case and click Compute A-Score to run the analysis.")

    appeal_data = None
    if compute_clicked:
        with st.spinner("Computing appealability score..."):
            appeal_data, appeal_err = fetch_appealability(case_id)

        if appeal_err:
            st.error(f"Appealability computation failed: {appeal_err}")
            st.stop()
        if not appeal_data:
            st.info("No appealability data available for this case.")
            st.stop()

        cache_by_case[case_id] = {
            "fingerprint": case_fingerprint,
            "appeal_data": appeal_data,
        }
    elif cache_valid:
        appeal_data = cached_entry["appeal_data"]
    else:
        st.info("Ready to run. Click `Compute A-Score` to generate this case's analysis.")
        st.stop()

    # Unpack
    classification = appeal_data.get("denial_classification", "unknown")
    a_score = appeal_data.get("a_score") or {}
    agent_score = appeal_data.get("agent_score") or {}
    benchmark = appeal_data.get("insurer_benchmark") or {}
    precedent = appeal_data.get("precedent_cases") or []
    recs = appeal_data.get("recommendations") or []
    payer = appeal_data.get("payer", "unknown")
    denial_label = appeal_data.get("denial_label", "").replace("_", " ").title()
    inferred_diag = appeal_data.get("inferred_diagnosis", "Not identified")
    inferred_treat = appeal_data.get("inferred_treatment", "Not identified")
    medical_keywords = appeal_data.get("medical_keywords", [])

    case_json = extraction.get("case_json") or {}
    reasons = case_json.get("denial_reasons") or []
    user_quote = reasons[0].get("supporting_quote", "") if reasons else ""

    # =====================================================================
    # DASHBOARD
    # =====================================================================

    left_col, right_col = st.columns([1, 1.3], gap="large")

    # --- LEFT ---
    with left_col:
        st.markdown('<p class="section-label">Appeal Scores</p>', unsafe_allow_html=True)

        if classification == "R1":
            rate = a_score.get("overturn_rate")
            n = a_score.get("sample_size", 0)
            conf = a_score.get("confidence", "none")
            yr = a_score.get("year_range", "")

            _render_score_card(
                "A-Score",
                "Historical IMR overturn rate",
                rate,
                [f"{n:,} similar cases · {yr}"],
                confidence=conf,
            )

            if agent_score:
                raw_ag_score = agent_score.get("score")
                ag_sc: int | None = None
                if isinstance(raw_ag_score, (int, float)):
                    ag_sc = int(raw_ag_score)
                elif isinstance(raw_ag_score, str):
                    try:
                        ag_sc = int(float(raw_ag_score))
                    except ValueError:
                        ag_sc = None
                if ag_sc is not None:
                    ag_sc = max(0, min(100, ag_sc))
                ag_rate = (ag_sc / 100.0) if ag_sc is not None else None
                ag_str = _strength(ag_rate)
                ag_assess = agent_score.get("assessment", "")
                ag_source = agent_score.get("source", "")
                ag_color = _score_color(ag_rate)
                ag_score_text = f"{ag_sc}%" if ag_sc is not None else "—"

                source_label = "🤖 Ollama" if ag_source == "ollama" else "📊 Rule-based"

                st.markdown(
                    f'<div class="score-card" style="border-color:{ag_color}44">'
                    f'<div class="section-label">AI-Score</div>'
                    f'<div class="score-source">{source_label}</div>'
                    f'<div class="score-big" style="color:{ag_color}">{ag_score_text}</div>'
                    f'<div class="score-sub" style="font-size:0.95rem;font-weight:600;'
                    f'color:{ag_color}">{ag_str}</div>'
                    f'<div class="score-assessment">{ag_assess}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        elif classification == "R2":
            int_pct = benchmark.get("internal_overturn_pct")
            ext_pct = benchmark.get("external_overturn_pct")
            if int_pct is not None:
                _render_score_card("Internal Appeal Rate", payer, int_pct / 100,
                                   [f"Year: {benchmark.get('year', 'N/A')}"])
            if ext_pct is not None:
                _render_score_card("External Review Rate", payer, ext_pct / 100,
                                   [f"Year: {benchmark.get('year', 'N/A')}"])

        non_prec_recs = [r for r in recs if not r.startswith("Precedent case ")]
        if non_prec_recs:
            st.markdown("---")
            st.markdown('<p class="section-label">Recommendations</p>', unsafe_allow_html=True)
            for r in non_prec_recs:
                st.markdown(f'<div class="rec-box">{r}</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown('<p class="section-label">Your Case</p>', unsafe_allow_html=True)

        for label, value in [
            ("Payer", payer),
            ("Denial Type", denial_label),
            ("Diagnosis Category", inferred_diag),
            ("Treatment Category", inferred_treat),
        ]:
            st.markdown(
                f'<div class="your-case-box">'
                f'<div class="your-case-label">{label}</div>'
                f'<div class="your-case-value">{value}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        if user_quote:
            preview_q = user_quote[:180] + ("..." if len(user_quote) > 180 else "")
            st.markdown(
                f'<div class="your-case-box">'
                f'<div class="your-case-label">Denial Context</div>'
                f'<div class="your-case-value" style="font-weight:400;font-size:0.86rem">'
                f'{preview_q}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        if medical_keywords:
            kw_html = " ".join(
                f'<span class="kw-chip">{kw}</span>'
                for kw in medical_keywords
            )
            st.markdown(
                f'<div class="your-case-box">'
                f'<div class="your-case-label">Medical Keywords</div>'
                f'<div style="margin-top:0.3rem">{kw_html}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # --- RIGHT ---
    with right_col:
        if precedent:
            st.markdown(
                '<p class="section-label">Top Similar Cases — CA DMHC IMR Database</p>',
                unsafe_allow_html=True,
            )
            st.caption(
                "Real IMR decisions ranked by relevance. "
                "🤖 comments highlight what's similar to your case. "
                "Matching words from your denial are highlighted in green."
            )

            # Use inferred categories for comparison
            user_diag = appeal_data.get("inferred_diagnosis", denial_label)
            user_treat = appeal_data.get("inferred_treatment", "")

            for i, pc in enumerate(precedent[:5], 1):
                _render_case_card(i, pc, user_diag, user_treat, user_quote)

        elif classification == "R1":
            st.markdown('<p class="section-label">Similar Cases</p>', unsafe_allow_html=True)
            st.info("No similar precedent cases found.")

        elif classification == "R2":
            st.markdown('<p class="section-label">Insurer Appeal Data</p>', unsafe_allow_html=True)
            st.caption("Procedural denials use insurer benchmarks, not clinical precedent.")
            if benchmark and "error" not in benchmark:
                st.json(benchmark)


if __name__ == "__main__":
    main()
