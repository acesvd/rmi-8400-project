"""A-Score Dashboard."""

from __future__ import annotations

import re
from typing import Any

import streamlit as st

from lib.api import ensure_state, fetch_appealability, fetch_case_payload, fetch_cases, select_case
from lib.feature_flags import is_demo_mode


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

        /* --- Insurer benchmark panel (R2) --- */
        .benchmark-shell {
            padding: 0.95rem 1rem;
            border-radius: 14px;
            margin-bottom: 0.75rem;
            border: 1px solid color-mix(in srgb, currentColor 24%, transparent);
            background: linear-gradient(
                180deg,
                color-mix(in srgb, currentColor 4%, transparent) 0%,
                color-mix(in srgb, currentColor 7%, transparent) 100%
            );
        }
        .benchmark-title {
            font-size: 1rem;
            font-weight: 700;
            margin: 0 0 0.2rem 0;
            color: inherit;
        }
        .benchmark-sub {
            margin: 0;
            font-size: 0.84rem;
            color: color-mix(in srgb, currentColor 62%, transparent);
        }
        .benchmark-grid {
            margin-top: 0.7rem;
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.55rem;
        }
        .benchmark-stat {
            border-radius: 11px;
            padding: 0.6rem 0.7rem;
            border: 1px solid color-mix(in srgb, currentColor 18%, transparent);
            background: color-mix(in srgb, currentColor 6%, transparent);
        }
        .benchmark-stat-kicker {
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 0.09em;
            font-size: 0.64rem;
            font-weight: 700;
            color: color-mix(in srgb, currentColor 58%, transparent);
        }
        .benchmark-stat-value {
            margin: 0.1rem 0 0;
            font-size: 1.04rem;
            font-weight: 700;
            color: inherit;
        }
        @media (max-width: 1120px) {
            .benchmark-grid {
                grid-template-columns: 1fr;
            }
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


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


def _parse_agent_score(raw_score: Any) -> int | None:
    if isinstance(raw_score, (int, float)):
        value = int(raw_score)
    elif isinstance(raw_score, str):
        try:
            value = int(float(raw_score))
        except ValueError:
            return None
    else:
        return None
    return max(0, min(100, value))


def _render_agent_score_card(agent_score: dict[str, Any], *, title: str = "AI-Score") -> None:
    if not agent_score:
        return

    ag_sc = _parse_agent_score(agent_score.get("score"))
    ag_rate = (ag_sc / 100.0) if ag_sc is not None else None
    ag_str = _strength(ag_rate)
    ag_assess = str(agent_score.get("assessment") or "")
    ag_source = str(agent_score.get("source") or "")
    ag_color = _score_color(ag_rate)
    ag_score_text = f"{ag_sc}%" if ag_sc is not None else "—"

    source_label = "🤖 Ollama" if ag_source == "ollama" else "📊 Rule-based"

    st.markdown(
        f'<div class="score-card" style="border-color:{ag_color}44">'
        f'<div class="section-label">{title}</div>'
        f'<div class="score-source">{source_label}</div>'
        f'<div class="score-big" style="color:{ag_color}">{ag_score_text}</div>'
        f'<div class="score-sub" style="font-size:0.95rem;font-weight:600;'
        f'color:{ag_color}">{ag_str}</div>'
        f'<div class="score-assessment">{ag_assess}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct_to_rate(value: Any) -> float | None:
    pct = _to_float(value)
    return None if pct is None else (pct / 100.0)


def _fmt_count(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "—"
    return f"{int(number):,}"


def _render_insurer_benchmark_panel(benchmark: dict[str, Any], *, payer: str) -> None:
    insurer = str(benchmark.get("insurer") or payer or "Unknown")
    year = benchmark.get("year")
    requested_insurer = str(benchmark.get("requested_insurer") or "").strip()
    note = str(benchmark.get("note") or "").strip()

    st.markdown(
        f"""
        <div class="benchmark-shell">
            <p class="benchmark-title">{insurer}</p>
            <p class="benchmark-sub">Benchmark year: {year if year else "N/A"}</p>
            <div class="benchmark-grid">
                <div class="benchmark-stat">
                    <p class="benchmark-stat-kicker">Internal Filed</p>
                    <p class="benchmark-stat-value">{_fmt_count(benchmark.get("internal_appeals_filed"))}</p>
                </div>
                <div class="benchmark-stat">
                    <p class="benchmark-stat-kicker">Internal Overturned</p>
                    <p class="benchmark-stat-value">{_fmt_count(benchmark.get("internal_appeals_overturned"))}</p>
                </div>
                <div class="benchmark-stat">
                    <p class="benchmark-stat-kicker">External Filed</p>
                    <p class="benchmark-stat-value">{_fmt_count(benchmark.get("external_appeals_filed"))}</p>
                </div>
                <div class="benchmark-stat">
                    <p class="benchmark-stat-kicker">External Overturned</p>
                    <p class="benchmark-stat-value">{_fmt_count(benchmark.get("external_appeals_overturned"))}</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if note:
        st.info(note)
    if requested_insurer and requested_insurer.lower() != insurer.lower():
        st.caption(f"Requested payer: {requested_insurer}")


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
    demo_mode = is_demo_mode()

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

    saved_data, saved_err = fetch_appealability(case_id, cached_only=True)
    has_saved = isinstance(saved_data, dict)

    with compute_col:
        # Align with the selectbox input row while keeping the selector label visible.
        st.markdown("<div style='height:1.68rem;'></div>", unsafe_allow_html=True)
        button_label = "Recompute A-Score" if has_saved else "Compute A-Score"
        compute_clicked = st.button(
            button_label,
            icon=":material/play_arrow:",
            use_container_width=True,
            key=f"ascore_compute_btn_{case_id}",
            disabled=demo_mode,
        )

    if has_saved:
        cache_meta = saved_data.get("_cache", {}) if isinstance(saved_data, dict) else {}
        if cache_meta.get("fresh", True):
            st.caption("Showing saved results for this case. Click recompute if you want a fresh run.")
        else:
            st.caption("Showing previously saved results. Case data changed since last run; click recompute to refresh.")
    elif saved_err and "404" not in saved_err:
        st.warning(f"Could not load saved A-Score: {saved_err}")
    else:
        st.caption("Select a case and click Compute A-Score to run and save analysis.")

    if demo_mode:
        st.caption("Demo mode is enabled. A-Score recompute is temporarily disabled.")

    appeal_data = None
    if compute_clicked:
        with st.spinner("Computing appealability score..."):
            appeal_data, appeal_err = fetch_appealability(case_id, recompute=has_saved)

        if appeal_err:
            st.error(f"Appealability computation failed: {appeal_err}")
            st.stop()
        if not appeal_data:
            st.info("No appealability data available for this case.")
            st.stop()
    elif has_saved:
        appeal_data = saved_data
    else:
        st.info("Ready to run. Click `Compute A-Score` to generate and save this case's analysis.")
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

            _render_agent_score_card(agent_score, title="AI-Score")

        elif classification == "R2":
            rate = a_score.get("overturn_rate")
            n = a_score.get("sample_size", 0)
            conf = a_score.get("confidence", "none")
            yr = a_score.get("year_range", "")
            detail_lines = [f"{n:,} insurer appeal records · {yr or 'latest year'}"]
            match_type = str(benchmark.get("match_type") or "")
            if match_type == "fallback_all_insurers":
                detail_lines.append("Using pooled insurer benchmark")

            _render_score_card(
                "Procedural A-Score",
                "Insurer benchmark + case readiness",
                rate,
                detail_lines,
                confidence=conf,
            )
            _render_agent_score_card(agent_score, title="Procedural AI-Score")

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
                _render_insurer_benchmark_panel(benchmark, payer=payer)

                int_pct = benchmark.get("internal_overturn_pct")
                ext_pct = benchmark.get("external_overturn_pct")
                insurer_label = str(benchmark.get("insurer") or payer)
                benchmark_year = benchmark.get("year") or "N/A"

                internal_lines = [
                    f"Overturned {_fmt_count(benchmark.get('internal_appeals_overturned'))} "
                    f"of {_fmt_count(benchmark.get('internal_appeals_filed'))} appeals",
                    f"Year: {benchmark_year}",
                ]
                external_lines = [
                    f"Overturned {_fmt_count(benchmark.get('external_appeals_overturned'))} "
                    f"of {_fmt_count(benchmark.get('external_appeals_filed'))} appeals",
                    f"Year: {benchmark_year}",
                ]

                rates_col1, rates_col2 = st.columns(2, gap="small")
                with rates_col1:
                    _render_score_card(
                        "Internal Appeal Rate",
                        insurer_label,
                        _pct_to_rate(int_pct),
                        internal_lines,
                    )
                with rates_col2:
                    _render_score_card(
                        "External Review Rate",
                        insurer_label,
                        _pct_to_rate(ext_pct),
                        external_lines,
                    )
            elif benchmark and benchmark.get("error"):
                st.warning(str(benchmark.get("error")))
            else:
                st.info("No insurer benchmark data is available for this case.")


if __name__ == "__main__":
    main()
