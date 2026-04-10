from __future__ import annotations

from datetime import datetime, timezone
from html import escape

import pandas as pd
import streamlit as st

from lib.api import (
    api_patch,
    ensure_state,
    fetch_case_payload,
    fetch_cases,
    open_case_workspace_create_flow,
    safe_call,
    select_case,
)


def _inject_page_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --dash-accent: #2f74b6;
            --dash-accent-soft: #79b9ea;
            --dash-accent-deep: #17497d;
            --dash-ink: #132c4a;
            --dash-ink-soft: #365373;
            --dash-surface: #eef6ff;
            --dash-surface-soft: #e2f0fd;
            --dash-border: #bfd7ee;
            --dash-shadow: rgba(18, 44, 74, 0.14);
        }
        .mycases-hero {
            padding: 1.45rem 1.55rem;
            border-radius: 24px;
            background:
                radial-gradient(circle at 8% 12%, rgba(255, 206, 133, 0.34), transparent 35%),
                radial-gradient(circle at 97% -8%, rgba(132, 183, 231, 0.38), transparent 33%),
                radial-gradient(circle at 14% 86%, rgba(147, 226, 255, 0.24), transparent 36%),
                radial-gradient(circle at 72% 88%, rgba(145, 203, 243, 0.18), transparent 42%),
                linear-gradient(126deg, #f8fcff 0%, #e7f2fc 52%, #d4e7fa 100%);
            color: var(--dash-ink);
            margin-bottom: 1rem;
            border: 1px solid #c6d9ed;
            box-shadow: 0 16px 34px rgba(16, 42, 67, 0.16);
            position: relative;
            overflow: hidden;
        }
        .mycases-hero::before {
            content: "";
            position: absolute;
            width: 262px;
            height: 262px;
            top: -130px;
            right: -96px;
            border-radius: 999px;
            background: rgba(134, 183, 230, 0.36);
        }
        .mycases-hero::after {
            content: "";
            position: absolute;
            inset: 0;
            background:
                radial-gradient(circle, rgba(31, 106, 169, 0.1) 1.05px, transparent 1.2px),
                linear-gradient(90deg, rgba(255, 255, 255, 0.22) 0%, rgba(255, 255, 255, 0) 46%);
            background-size: 18px 18px, 100% 100%;
            opacity: 0.36;
            pointer-events: none;
            mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.35) 0%, rgba(0, 0, 0, 0) 72%);
        }
        .mycases-hero-orb {
            position: absolute;
            width: 156px;
            height: 156px;
            top: -58px;
            right: 198px;
            border-radius: 999px;
            background: rgba(172, 214, 251, 0.3);
            pointer-events: none;
        }
        .mycases-hero > * {
            position: relative;
            z-index: 1;
        }
        .mycases-kicker {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.75rem;
            color: #245987;
            margin-bottom: 0.35rem;
            font-weight: 700;
        }
        .mycases-hero h2 {
            margin: 0;
            font-size: 2rem;
            line-height: 1.08;
            color: var(--dash-ink);
        }
        .mycases-hero p {
            margin: 0.55rem 0 0;
            max-width: 54rem;
            color: var(--dash-ink-soft);
            line-height: 1.55;
        }
        .dash-glance-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.82rem;
            margin: 0 0 1rem;
        }
        .dash-glance-card {
            border: 1px solid var(--dash-border);
            border-radius: 16px;
            padding: 0.8rem 0.88rem;
            background: linear-gradient(180deg,
                color-mix(in srgb, var(--dash-surface) 82%, #ffffff 18%) 0%,
                color-mix(in srgb, var(--dash-surface-soft) 84%, #ffffff 16%) 100%);
            box-shadow: 0 10px 18px color-mix(in srgb, var(--dash-shadow) 68%, transparent);
            position: relative;
            overflow: hidden;
        }
        .dash-glance-card::after {
            content: "";
            position: absolute;
            inset: 0;
            background: radial-gradient(circle at 108% -22%, rgba(121, 185, 234, 0.26), transparent 45%);
            pointer-events: none;
        }
        .dash-glance-card > * {
            position: relative;
            z-index: 1;
        }
        .dash-glance-kicker {
            margin: 0;
            font-size: 0.68rem;
            letter-spacing: 0.11em;
            text-transform: uppercase;
            font-weight: 800;
            color: color-mix(in srgb, var(--dash-accent) 74%, var(--dash-ink) 26%);
        }
        .dash-glance-value {
            margin: 0.32rem 0 0;
            font-size: 1.55rem;
            line-height: 1;
            font-weight: 800;
            color: var(--dash-ink);
        }
        .dash-glance-note {
            margin: 0.35rem 0 0;
            font-size: 0.83rem;
            line-height: 1.3;
            color: var(--dash-ink-soft);
        }
        .dashboard-gap-lg {
            height: 0.85rem;
        }
        .tracker-bottom-gap {
            height: 0.7rem;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 18px;
            border: 1px solid var(--dash-border);
            background: linear-gradient(180deg,
                color-mix(in srgb, var(--dash-surface) 70%, #ffffff 30%) 0%,
                color-mix(in srgb, var(--dash-surface-soft) 76%, #ffffff 24%) 100%);
            box-shadow: 0 10px 18px color-mix(in srgb, var(--dash-shadow) 58%, transparent);
        }
        .section-label {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.72rem;
            font-weight: 700;
            color: color-mix(in srgb, var(--dash-accent) 78%, var(--dash-ink) 22%);
            margin-bottom: 0.45rem;
        }
        .section-title {
            margin: 0.1rem 0 0.2rem;
            color: var(--dash-ink);
            font-size: 1.58rem;
            line-height: 1.12;
        }
        .section-subtext {
            margin: 0.16rem 0 0.54rem;
            color: var(--dash-ink-soft);
            font-size: 0.92rem;
            line-height: 1.5;
        }
        .stage-card {
            border: 1px solid var(--dash-border);
            border-radius: 14px;
            padding: 0.76rem 0.72rem;
            min-height: 8.3rem;
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.68), rgba(231, 243, 255, 0.56));
            box-shadow: 0 8px 14px color-mix(in srgb, var(--dash-shadow) 44%, transparent);
        }
        .stage-name {
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.73rem;
            font-weight: 800;
            color: color-mix(in srgb, var(--dash-accent-deep) 80%, var(--dash-ink) 20%);
        }
        .stage-pct {
            margin: 0.32rem 0 0.45rem;
            font-size: 1.45rem;
            font-weight: 800;
            line-height: 1;
            color: var(--dash-ink);
        }
        .stage-chip {
            display: inline-block;
            border-radius: 999px;
            padding: 0.18rem 0.52rem;
            font-size: 0.75rem;
            font-weight: 700;
            border: 1px solid transparent;
            margin-bottom: 0.45rem;
        }
        .stage-progress-rail {
            width: 100%;
            height: 0.38rem;
            border-radius: 999px;
            overflow: hidden;
            background: rgba(47, 116, 182, 0.14);
        }
        .stage-progress-fill {
            display: block;
            height: 100%;
            border-radius: inherit;
        }
        .stage-complete {
            background: #e7f6ee;
            color: #16623f;
            border-color: #9fd5b7;
        }
        .stage-progress {
            background: #eaf4ff;
            color: #0f4e8a;
            border-color: #a8caef;
        }
        .stage-waiting {
            background: #fff3d6;
            color: #8a5a00;
            border-color: #f1c56d;
        }
        .stage-progress-fill.stage-complete {
            background: linear-gradient(90deg, #63c891 0%, #3da975 100%);
        }
        .stage-progress-fill.stage-progress {
            background: linear-gradient(90deg, #6aa8dd 0%, #367bc3 100%);
        }
        .stage-progress-fill.stage-waiting {
            background: linear-gradient(90deg, #f3cf80 0%, #d3a451 100%);
        }
        .case-signal-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.8rem;
            margin: 0.08rem 0 1rem;
        }
        .case-signal-card {
            border: 1px solid var(--dash-border);
            border-radius: 14px;
            padding: 0.78rem 0.8rem;
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.76), rgba(226, 240, 253, 0.62));
            box-shadow: 0 8px 14px color-mix(in srgb, var(--dash-shadow) 44%, transparent);
        }
        .case-signal-kicker {
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            font-size: 0.66rem;
            font-weight: 800;
            color: color-mix(in srgb, var(--dash-accent) 76%, var(--dash-ink) 24%);
        }
        .case-signal-value {
            margin: 0.32rem 0 0;
            font-size: 1.02rem;
            line-height: 1.35;
            font-weight: 700;
            color: var(--dash-ink);
        }
        .case-signal-note {
            margin: 0.36rem 0 0;
            font-size: 0.82rem;
            line-height: 1.3;
            color: var(--dash-ink-soft);
        }
        .action-callout {
            border: 1px solid var(--dash-border);
            border-radius: 14px;
            padding: 0.78rem 0.84rem;
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.78), rgba(226, 240, 253, 0.6));
            box-shadow: 0 8px 14px color-mix(in srgb, var(--dash-shadow) 38%, transparent);
            margin-bottom: 0.75rem;
        }
        .action-callout-kicker {
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 0.09em;
            font-size: 0.68rem;
            font-weight: 800;
            color: color-mix(in srgb, var(--dash-accent) 76%, var(--dash-ink) 24%);
        }
        .action-callout-title {
            margin: 0.28rem 0 0;
            font-size: 1.1rem;
            line-height: 1.25;
            font-weight: 800;
            color: var(--dash-ink);
        }
        .action-callout-copy {
            margin: 0.34rem 0 0;
            font-size: 0.9rem;
            line-height: 1.5;
            color: var(--dash-ink-soft);
        }
        .action-list-title {
            margin: 0.2rem 0 0.24rem;
            font-size: 0.82rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            font-weight: 800;
            color: color-mix(in srgb, var(--dash-accent) 74%, var(--dash-ink) 26%);
        }
        .action-list {
            margin: 0;
            padding-left: 1rem;
            color: var(--dash-ink-soft);
            font-size: 0.9rem;
            line-height: 1.45;
        }
        .action-list li {
            margin: 0.24rem 0;
        }
        .activity-feed {
            display: flex;
            flex-direction: column;
            gap: 0.58rem;
            margin-top: 0.15rem;
            padding-bottom: 0.38rem;
        }
        .activity-bottom-gap {
            height: 0.7rem;
        }
        .activity-item {
            border: 1px solid var(--dash-border);
            border-radius: 12px;
            padding: 0.62rem 0.72rem;
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.74), rgba(230, 242, 254, 0.55));
            box-shadow: 0 6px 12px color-mix(in srgb, var(--dash-shadow) 34%, transparent);
        }
        .activity-head {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 0.6rem;
        }
        .activity-title {
            margin: 0;
            font-size: 0.92rem;
            line-height: 1.32;
            font-weight: 700;
            color: var(--dash-ink);
        }
        .activity-time {
            margin: 0;
            font-size: 0.77rem;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            font-weight: 700;
            color: color-mix(in srgb, var(--dash-accent) 68%, var(--dash-ink) 32%);
            flex-shrink: 0;
        }
        .activity-note {
            margin: 0.36rem 0 0;
            font-size: 0.86rem;
            line-height: 1.42;
            color: var(--dash-ink-soft);
        }
        div[data-testid="stMetric"] {
            border: 1px solid var(--dash-border);
            border-radius: 14px;
            padding: 0.58rem 0.62rem;
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(228, 241, 253, 0.56));
            box-shadow: 0 6px 12px color-mix(in srgb, var(--dash-shadow) 40%, transparent);
        }
        div[data-testid="stMetricLabel"] p {
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.69rem;
            font-weight: 700;
            color: color-mix(in srgb, var(--dash-accent) 72%, var(--dash-ink) 28%);
        }
        div[data-testid="stMetricValue"] {
            color: var(--dash-ink);
            font-weight: 700;
        }
        div[data-testid="stDataFrame"] {
            border-radius: 14px;
            overflow: hidden;
            border: 1px solid var(--dash-border);
            box-shadow: 0 8px 14px color-mix(in srgb, var(--dash-shadow) 38%, transparent);
        }
        div.stButton > button,
        div[data-testid="stPageLink"] a {
            border-radius: 12px;
        }
        [data-theme="dark"] .mycases-hero {
            border-color: rgba(121, 176, 225, 0.46);
            background:
                radial-gradient(circle at 8% 12%, rgba(220, 153, 67, 0.28), transparent 34%),
                radial-gradient(circle at 98% -8%, rgba(77, 138, 204, 0.34), transparent 35%),
                radial-gradient(circle at 16% 84%, rgba(68, 147, 205, 0.2), transparent 34%),
                linear-gradient(126deg, #11355b 0%, #1f5f95 52%, #3b84ba 100%);
            color: #eef6ff;
            box-shadow: 0 16px 34px rgba(4, 13, 23, 0.46);
        }
        [data-theme="dark"] .mycases-hero p,
        [data-theme="dark"] .dash-glance-note,
        [data-theme="dark"] .section-subtext,
        [data-theme="dark"] .case-signal-note {
            color: #d8e9fb;
        }
        [data-theme="dark"] .mycases-kicker,
        [data-theme="dark"] .dash-glance-kicker,
        [data-theme="dark"] .section-label,
        [data-theme="dark"] .case-signal-kicker,
        [data-theme="dark"] .stage-name,
        [data-theme="dark"] div[data-testid="stMetricLabel"] p {
            color: #9fd1ff;
        }
        [data-theme="dark"] .mycases-hero h2,
        [data-theme="dark"] .dash-glance-value,
        [data-theme="dark"] .section-title,
        [data-theme="dark"] .case-signal-value,
        [data-theme="dark"] .stage-pct,
        [data-theme="dark"] div[data-testid="stMetricValue"],
        [data-theme="dark"] div[data-testid="stMetricLabel"] {
            color: #f0f6ff;
        }
        [data-theme="dark"] .dash-glance-card,
        [data-theme="dark"] .stage-card,
        [data-theme="dark"] .case-signal-card,
        [data-theme="dark"] .action-callout,
        [data-theme="dark"] .activity-item,
        [data-theme="dark"] div[data-testid="stMetric"],
        [data-theme="dark"] [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: rgba(121, 176, 225, 0.45);
            background: linear-gradient(180deg, rgba(20, 48, 77, 0.86), rgba(14, 37, 62, 0.9));
            box-shadow: 0 10px 18px rgba(0, 0, 0, 0.34);
        }
        [data-theme="dark"] .action-callout-kicker,
        [data-theme="dark"] .action-list-title {
            color: #9fd1ff;
        }
        [data-theme="dark"] .action-callout-title {
            color: #f0f6ff;
        }
        [data-theme="dark"] .action-callout-copy,
        [data-theme="dark"] .action-list,
        [data-theme="dark"] .activity-note {
            color: #d8e9fb;
        }
        [data-theme="dark"] .activity-title {
            color: #f0f6ff;
        }
        [data-theme="dark"] .activity-time {
            color: #9fd1ff;
        }
        [data-theme="dark"] .stage-progress-rail {
            background: rgba(121, 176, 225, 0.24);
        }
        [data-theme="dark"] div[data-testid="stDataFrame"] {
            border-color: rgba(121, 176, 225, 0.44);
            box-shadow: 0 8px 14px rgba(0, 0, 0, 0.34);
        }
        @media (max-width: 1080px) {
            .dash-glance-grid,
            .case-signal-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 760px) {
            .dash-glance-grid,
            .case-signal-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _normalize_status(status: str | None) -> str:
    return (status or "draft").strip().lower()


def _is_active_case_status(status: str | None) -> bool:
    return _normalize_status(status) not in {"done", "completed", "closed", "resolved"}


def _status_buckets(cases: list[dict]) -> tuple[int, int, int]:
    open_count = 0
    pending_count = 0
    done_count = 0
    for case in cases:
        status = _normalize_status(case.get("status"))
        if status in {"done", "completed", "closed", "resolved"}:
            done_count += 1
        elif status in {"waiting", "pending", "in review", "submitted"}:
            pending_count += 1
        else:
            open_count += 1
    return open_count, pending_count, done_count


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _days_since(value: str | None) -> str:
    dt = _parse_iso(value)
    if dt is None:
        return "n/a"
    now = datetime.now(timezone.utc)
    delta = now - dt.astimezone(timezone.utc)
    days = max(delta.days, 0)
    if days == 0:
        return "Today"
    if days == 1:
        return "1 day ago"
    return f"{days} days ago"


def _time_since(value: str | None) -> str:
    dt = _parse_iso(value)
    if dt is None:
        return "Unknown time"
    now = datetime.now(timezone.utc)
    seconds = max(int((now - dt.astimezone(timezone.utc)).total_seconds()), 0)
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        minutes = max(seconds // 60, 1)
        return f"{minutes}m ago"
    if seconds < 86400:
        hours = max(seconds // 3600, 1)
        return f"{hours}h ago"
    days = max(seconds // 86400, 1)
    return f"{days}d ago"


def _humanize_event_type(value: str | None) -> str:
    text = str(value or "case_update").strip().replace("-", "_")
    if not text:
        text = "case_update"
    return " ".join(part.capitalize() for part in text.split("_") if part)


def _count_recent_updates(cases: list[dict], hours: int = 24) -> int:
    now = datetime.now(timezone.utc)
    threshold_seconds = max(hours, 1) * 3600
    count = 0
    for case in cases:
        dt = _parse_iso(case.get("updated_at"))
        if not dt:
            continue
        delta_seconds = (now - dt.astimezone(timezone.utc)).total_seconds()
        if 0 <= delta_seconds <= threshold_seconds:
            count += 1
    return count


def _stage_chip_class(state: str) -> str:
    state_l = state.lower()
    if "complete" in state_l:
        return "stage-complete"
    if "progress" in state_l or "ready" in state_l or "generate" in state_l:
        return "stage-progress"
    return "stage-waiting"


def _build_stage_progress(case_payload: dict | None) -> tuple[int, list[tuple[str, int, str]]]:
    if not case_payload:
        stages = [
            ("Documents", 0, "Waiting"),
            ("Extraction", 0, "Waiting"),
            ("Tasks", 0, "Waiting"),
            ("Packet", 0, "Waiting"),
            ("Tracking", 0, "Waiting"),
        ]
        return 0, stages

    documents = case_payload.get("documents") or []
    extraction = case_payload.get("extraction")
    tasks = case_payload.get("tasks") or []
    artifacts = case_payload.get("artifacts") or []
    events = case_payload.get("events") or []

    docs_pct = 100 if documents else 0

    if extraction:
        extraction_pct = 100
        extraction_state = "Complete"
    elif documents:
        extraction_pct = 35
        extraction_state = "Ready to run"
    else:
        extraction_pct = 0
        extraction_state = "Waiting"

    done_tasks = sum(1 for task in tasks if _normalize_status(task.get("status")) == "done")
    if tasks:
        tasks_pct = int(round((done_tasks / len(tasks)) * 100))
        if tasks_pct == 100:
            tasks_state = "Complete"
        else:
            tasks_state = f"In progress ({done_tasks}/{len(tasks)})"
    elif extraction:
        tasks_pct = 20
        tasks_state = "Generate tasks"
    else:
        tasks_pct = 0
        tasks_state = "Waiting"

    has_packet = any((artifact.get("type") == "packet_pdf") for artifact in artifacts)
    has_letter = any((artifact.get("type") == "letter") for artifact in artifacts)
    if has_packet:
        packet_pct = 100
        packet_state = "Complete"
    elif has_letter:
        packet_pct = 55
        packet_state = "In progress"
    else:
        packet_pct = 0
        packet_state = "Waiting"

    if events:
        tracking_pct = 100
        tracking_state = "Complete"
    elif tasks or has_packet or has_letter:
        tracking_pct = 25
        tracking_state = "Ready to log"
    else:
        tracking_pct = 0
        tracking_state = "Waiting"

    stages = [
        ("Documents", docs_pct, "Complete" if docs_pct == 100 else "Waiting"),
        ("Extraction", extraction_pct, extraction_state),
        ("Tasks", tasks_pct, tasks_state),
        ("Packet", packet_pct, packet_state),
        ("Tracking", tracking_pct, tracking_state),
    ]
    overall = int(round(sum(stage[1] for stage in stages) / len(stages)))
    return overall, stages


def _render_stage_card(name: str, pct: int, state: str) -> None:
    safe_pct = max(0, min(int(pct), 100))
    chip_class = _stage_chip_class(state)
    st.markdown(
        f"""
        <div class="stage-card">
            <p class="stage-name">{name}</p>
            <p class="stage-pct">{safe_pct}%</p>
            <span class="stage-chip {chip_class}">{state}</span>
            <div class="stage-progress-rail">
                <span class="stage-progress-fill {chip_class}" style="width: {safe_pct}%;"></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_dashboard_glance(cases: list[dict], open_count: int, pending_count: int, done_count: int) -> None:
    total_cases = len(cases)
    active_cases = open_count + pending_count
    ready_like = sum(1 for case in cases if _normalize_status(case.get("status")) in {"ready", "in review", "submitted"})
    updated_recent = _count_recent_updates(cases, hours=24)
    completion_rate = int(round((done_count / total_cases) * 100)) if total_cases else 0

    cards = [
        ("Portfolio", str(total_cases), f"{active_cases} active in workspace"),
        ("In Motion", str(active_cases), f"{ready_like} ready/in-review"),
        ("Completed", str(done_count), f"{completion_rate}% closure rate"),
        ("Fresh Activity", str(updated_recent), "Updated in last 24h"),
    ]
    cols = st.columns(4, gap="small")
    for col, (label, value, note) in zip(cols, cards):
        with col:
            st.markdown(
                f"""
                <div class="dash-glance-card">
                    <p class="dash-glance-kicker">{escape(label)}</p>
                    <p class="dash-glance-value">{escape(str(value))}</p>
                    <p class="dash-glance-note">{escape(str(note))}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_case_signal_strip(case_payload: dict | None) -> None:
    if not case_payload:
        return

    case = case_payload.get("case") or {}
    extraction = case_payload.get("extraction") or {}
    case_json = extraction.get("case_json") or {}
    tasks = case_payload.get("tasks") or []
    artifacts = case_payload.get("artifacts") or []
    docs = case_payload.get("documents") or []
    reasons = case_json.get("denial_reasons") or []

    done_tasks = sum(1 for task in tasks if _normalize_status(task.get("status")) == "done")
    pending_tasks = max(len(tasks) - done_tasks, 0)

    cards = [
        ("Active Case", str(case.get("title") or "Untitled case"), str(case.get("status") or "draft").title()),
        ("Payer", str(case_json.get("payer") or "Unknown").title(), f"{len(reasons)} denial reasons extracted"),
        ("Documents", str(len(docs)), "Upload and extraction activity"),
        ("Execution", f"{done_tasks}/{len(tasks)} tasks", f"{len(artifacts)} outputs · {pending_tasks} pending"),
    ]
    cols = st.columns(4, gap="small")
    for col, (label, value, note) in zip(cols, cards):
        with col:
            st.markdown(
                f"""
                <div class="case-signal-card">
                    <p class="case-signal-kicker">{escape(label)}</p>
                    <p class="case-signal-value">{escape(str(value))}</p>
                    <p class="case-signal-note">{escape(str(note))}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _derive_action_center(case_payload: dict | None) -> tuple[str, str, list[str], list[str]]:
    if not case_payload:
        return (
            "Pick an active case",
            "Select a case in the progress tracker so we can recommend the best next step.",
            [],
            [],
        )

    documents = case_payload.get("documents") or []
    extraction = case_payload.get("extraction")
    tasks = case_payload.get("tasks") or []
    artifacts = case_payload.get("artifacts") or []
    events = case_payload.get("events") or []

    done_tasks = sum(1 for task in tasks if _normalize_status(task.get("status")) == "done")
    pending_tasks = max(len(tasks) - done_tasks, 0)
    has_packet = any((artifact.get("type") == "packet_pdf") for artifact in artifacts)
    has_letter = any((artifact.get("type") == "letter") for artifact in artifacts)

    blockers: list[str] = []
    wins: list[str] = []

    if not documents:
        blockers.append("No intake documents uploaded yet.")
    else:
        wins.append(f"{len(documents)} document(s) uploaded.")

    if extraction:
        wins.append("Extraction completed.")
    elif documents:
        blockers.append("Extraction is ready to run.")

    if tasks:
        if pending_tasks == 0:
            wins.append("All tasks are complete.")
        else:
            blockers.append(f"{pending_tasks} task(s) still need completion.")
    elif extraction:
        blockers.append("Tasks not generated yet.")

    if has_packet:
        wins.append("Appeal packet generated.")
    elif has_letter:
        blockers.append("Letter exists, but packet PDF is not generated yet.")
    elif extraction:
        blockers.append("Packet has not been generated yet.")

    if events:
        wins.append(f"{len(events)} tracking event(s) logged.")

    if not documents:
        return (
            "Start intake in Case Workspace",
            "Upload at least one denial/supporting document or complete manual intake to initialize the workflow.",
            blockers,
            wins,
        )
    if not extraction:
        return (
            "Run extraction",
            "Documents are ready. Run extraction to structure denial details, payer data, and key context.",
            blockers,
            wins,
        )
    if not tasks:
        return (
            "Generate tasks",
            "Create an actionable checklist so the team can execute the appeal step by step.",
            blockers,
            wins,
        )
    if pending_tasks > 0:
        return (
            "Finish outstanding tasks",
            "Close remaining tasks to improve readiness before generating final packet artifacts.",
            blockers,
            wins,
        )
    if not has_packet:
        return (
            "Generate appeal packet",
            "You are nearly ready. Create the final packet PDF for submission and handoff.",
            blockers,
            wins,
        )
    return (
        "Review strategy and submit",
        "Core workflow items are complete. Validate final details, then continue tracking outcomes.",
        blockers,
        wins,
    )


def _render_action_center_box(case_payload: dict | None, payload_err: str | None = None) -> None:
    with st.container(border=True):
        st.markdown('<p class="section-label">Action Center</p>', unsafe_allow_html=True)
        st.markdown('<p class="section-title">What To Do Next</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="section-subtext">A focused checklist to keep the appeal workflow moving.</p>',
            unsafe_allow_html=True,
        )

        if payload_err:
            st.error(f"Could not load selected case: {payload_err}")
            st.page_link(
                "pages/4_Case_Library.py",
                label="Open Case Library",
                icon=":material/library_books:",
                use_container_width=True,
            )
            return

        title, copy, blockers, wins = _derive_action_center(case_payload)
        st.markdown(
            f"""
            <div class="action-callout">
                <p class="action-callout-kicker">Recommended Next Step</p>
                <p class="action-callout-title">{escape(title)}</p>
                <p class="action-callout-copy">{escape(copy)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if blockers:
            st.markdown('<p class="action-list-title">Current Blockers</p>', unsafe_allow_html=True)
            blocker_list = "".join(f"<li>{escape(item)}</li>" for item in blockers[:4])
            st.markdown(f'<ul class="action-list">{blocker_list}</ul>', unsafe_allow_html=True)

        if wins:
            st.markdown('<p class="action-list-title">Progress Signals</p>', unsafe_allow_html=True)
            wins_list = "".join(f"<li>{escape(item)}</li>" for item in wins[:3])
            st.markdown(f'<ul class="action-list">{wins_list}</ul>', unsafe_allow_html=True)

        st.page_link(
            "pages/5_Case_Workspace.py",
            label="Continue In Case Workspace",
            icon=":material/lab_profile:",
            use_container_width=True,
        )
        action_col1, action_col2 = st.columns(2, gap="small")
        with action_col1:
            st.page_link(
                "pages/1_AI_Chatbox.py",
                label="AI Chat",
                icon=":material/chat:",
                use_container_width=True,
            )
        with action_col2:
            st.page_link(
                "pages/3_A_Score.py",
                label="A-Score",
                icon=":material/analytics:",
                use_container_width=True,
            )


def _render_case_overview_box(case_payload: dict | None) -> None:
    with st.container(border=True):
        st.markdown('<p class="section-label">Case Snapshot</p>', unsafe_allow_html=True)
        st.markdown('<p class="section-title">High-Level Case Details</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="section-subtext">Quick summary of case health, payer context, and recent activity.</p>',
            unsafe_allow_html=True,
        )

        if not case_payload:
            st.info("Select an active case in the tracker above.")
            return

        case = case_payload.get("case") or {}
        extraction = case_payload.get("extraction") or {}
        case_json = extraction.get("case_json") or {}
        tasks = case_payload.get("tasks") or []
        artifacts = case_payload.get("artifacts") or []
        events = case_payload.get("events") or []

        reasons = case_json.get("denial_reasons") or []
        deadlines = case_json.get("deadlines") or []
        done_tasks = sum(1 for task in tasks if _normalize_status(task.get("status")) == "done")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Status", str(case.get("status") or "draft").title())
        m2.metric("Documents", str(len(case_payload.get("documents") or [])))
        m3.metric("Tasks", f"{done_tasks}/{len(tasks)} done" if tasks else "0")
        m4.metric("Outputs", str(len(artifacts)))

        c1, c2, c3 = st.columns(3)
        c1.metric("Payer", str(case_json.get("payer") or "unknown").title())
        c2.metric("Denial Reasons", str(len(reasons)))
        c3.metric("Deadlines", str(len(deadlines)))

        st.caption(
            f"Case ID: {case.get('case_id', 'n/a')} · Updated: {case.get('updated_at', 'n/a')} · "
            f"Last active: {_days_since(case.get('updated_at'))}"
        )
        if events:
            st.caption(f"Latest event: {events[0].get('type', 'unknown')} at {events[0].get('timestamp', 'n/a')}")


def _render_task_summary_box(case_payload: dict | None) -> None:
    with st.container(border=True):
        st.markdown('<p class="section-label">Task Tracker</p>', unsafe_allow_html=True)
        st.markdown('<p class="section-title">Current Task Progress</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="section-subtext">Monitor execution pace and keep outstanding items visible.</p>',
            unsafe_allow_html=True,
        )

        if not case_payload:
            st.info("Select an active case to view task progress.")
            return

        tasks = case_payload.get("tasks") or []
        if not tasks:
            st.info("No generated tasks yet. Run `Generate Tasks` in Case Workspace.")
            return

        todo = sum(1 for t in tasks if _normalize_status(t.get("status")) == "todo")
        waiting = sum(1 for t in tasks if _normalize_status(t.get("status")) in {"waiting", "pending"})
        done = sum(1 for t in tasks if _normalize_status(t.get("status")) == "done")
        completion = int(round((done / len(tasks)) * 100)) if tasks else 0

        st.progress(completion / 100, text=f"{completion}% tasks complete")

        col1, col2, col3 = st.columns(3)
        col1.metric("To Do", str(todo))
        col2.metric("Waiting", str(waiting))
        col3.metric("Done", str(done))

        case = case_payload.get("case") or {}
        case_id = str(case.get("case_id") or "")
        if not case_id:
            st.info("Task check-off is unavailable until the case is loaded.")
            return

        st.caption("Use the status dropdown to update tasks directly from this table.")

        task_rows: list[dict[str, str]] = []
        status_by_task_id: dict[str, str] = {}
        for task in tasks:
            task_id = str(task.get("task_id") or "").strip()
            if not task_id:
                continue

            status = _normalize_status(task.get("status"))
            if status not in {"todo", "waiting", "done"}:
                status = "todo"

            status_by_task_id[task_id] = status
            task_rows.append(
                {
                    "task_id": task_id,
                    "title": str(task.get("title") or "Untitled task"),
                    "status": status,
                    "owner": str(task.get("owner") or "unassigned"),
                    "due_date": str(task.get("due_date") or "n/a"),
                }
            )

        if not task_rows:
            st.info("No editable tasks found for this case.")
            return

        task_df = pd.DataFrame(task_rows)
        edited_df = st.data_editor(
            task_df,
            use_container_width=True,
            hide_index=True,
            key=f"mycases_task_editor_{case_id}",
            column_config={
                "task_id": None,
                "title": st.column_config.TextColumn("title", width="large"),
                "status": st.column_config.SelectboxColumn(
                    "status",
                    options=["todo", "waiting", "done"],
                    required=True,
                    help="Update task status from the dashboard.",
                ),
                "owner": st.column_config.TextColumn("owner", width="medium"),
                "due_date": st.column_config.TextColumn("due_date", width="small"),
            },
            disabled=["title", "owner", "due_date"],
        )

        if isinstance(edited_df, pd.DataFrame):
            changes: list[tuple[str, str, str]] = []
            for row in edited_df.to_dict(orient="records"):
                task_id = str(row.get("task_id") or "").strip()
                if not task_id:
                    continue
                old_status = status_by_task_id.get(task_id)
                new_status = _normalize_status(row.get("status"))
                if old_status and new_status in {"todo", "waiting", "done"} and new_status != old_status:
                    changes.append((task_id, str(row.get("title") or "task"), new_status))

            if changes:
                failures: list[str] = []
                for task_id, task_title, new_status in changes:
                    _, update_err = safe_call(
                        api_patch,
                        f"/cases/{case_id}/tasks/{task_id}",
                        json_body={"status": new_status},
                    )
                    if update_err:
                        failures.append(f"{task_title}: {update_err}")

                if failures:
                    st.error("Could not update one or more tasks.")
                    for failure in failures[:3]:
                        st.caption(failure)
                    return

                st.success(f"Updated {len(changes)} task status{'es' if len(changes) != 1 else ''}.")
                st.rerun()


def _render_workspace_shortcuts_box(*, compact: bool = False) -> None:
    with st.container(border=True):
        st.markdown('<p class="section-label">Workspace Shortcuts</p>', unsafe_allow_html=True)
        if compact:
            st.markdown('<p class="section-title">Jump To Tools</p>', unsafe_allow_html=True)
            st.markdown(
                '<p class="section-subtext">Open key pages quickly while reviewing progress.</p>',
                unsafe_allow_html=True,
            )
            st.page_link(
                "pages/5_Case_Workspace.py",
                label="Case Workspace",
                icon=":material/lab_profile:",
                use_container_width=True,
            )
            st.page_link(
                "pages/4_Case_Library.py",
                label="Case Library",
                icon=":material/library_books:",
                use_container_width=True,
            )
            st.page_link(
                "pages/1_AI_Chatbox.py",
                label="AI Chatbox",
                icon=":material/chat:",
                use_container_width=True,
            )
            st.page_link(
                "pages/3_A_Score.py",
                label="A-Score",
                icon=":material/analytics:",
                use_container_width=True,
            )
            return

        st.markdown('<p class="section-title">Navigate Fast</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="section-subtext">Jump directly into core tools for the selected case workflow.</p>',
            unsafe_allow_html=True,
        )

        left, right = st.columns(2, gap="small")
        with left:
            st.page_link(
                "pages/5_Case_Workspace.py",
                label="Open Case Workspace",
                icon=":material/lab_profile:",
                use_container_width=True,
            )
            st.page_link(
                "pages/1_AI_Chatbox.py",
                label="Open AI Chatbox",
                icon=":material/chat:",
                use_container_width=True,
            )
        with right:
            st.page_link(
                "pages/4_Case_Library.py",
                label="Open Case Library",
                icon=":material/library_books:",
                use_container_width=True,
            )
            st.page_link(
                "pages/3_A_Score.py",
                label="Open A-Score",
                icon=":material/analytics:",
                use_container_width=True,
            )


def _render_recent_activity_feed_box(cases: list[dict], case_payload: dict | None) -> None:
    with st.container(border=True):
        st.markdown('<p class="section-label">Recent Activity</p>', unsafe_allow_html=True)
        st.markdown('<p class="section-title">Activity Feed</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="section-subtext">Latest workflow events from your selected case and recent portfolio updates.</p>',
            unsafe_allow_html=True,
        )

        if not cases:
            st.info("No cases yet.")
            return

        items: list[dict[str, str]] = []
        selected_case = (case_payload or {}).get("case") or {}
        selected_case_id = str(selected_case.get("case_id") or "")
        selected_case_title = str(selected_case.get("title") or "Selected case")
        selected_events = (case_payload or {}).get("events") or []
        selected_docs = (case_payload or {}).get("documents") or []
        selected_extraction = (case_payload or {}).get("extraction") or {}
        selected_tasks = (case_payload or {}).get("tasks") or []
        selected_artifacts = (case_payload or {}).get("artifacts") or []

        def _sort_key(ts_value: str | None) -> float:
            dt = _parse_iso(ts_value)
            return dt.timestamp() if dt else 0.0

        selected_items: list[dict[str, str]] = []

        for event in sorted(selected_events, key=lambda item: _sort_key(item.get("timestamp")), reverse=True)[:5]:
            event_type = _humanize_event_type(event.get("type"))
            event_ts = str(event.get("timestamp") or "")
            detail = event.get("detail")
            if detail is None:
                detail = event.get("summary")
            note = str(detail or f"{selected_case_title} · {selected_case_id or 'case selected'}")
            selected_items.append(
                {
                    "title": event_type,
                    "time": event_ts,
                    "note": note,
                }
            )

        if selected_case_id:
            selected_items.append(
                {
                    "title": "Case Updated",
                    "time": str(selected_case.get("updated_at") or ""),
                    "note": f"{selected_case_title} · {str(selected_case.get('status') or 'draft').title()}",
                }
            )

        if selected_docs:
            latest_doc = max(selected_docs, key=lambda doc: _sort_key(doc.get("uploaded_at")))
            selected_items.append(
                {
                    "title": "Document Uploaded",
                    "time": str(latest_doc.get("uploaded_at") or ""),
                    "note": f"{len(selected_docs)} document(s) attached to this case.",
                }
            )

        if selected_extraction:
            mode = str(selected_extraction.get("mode") or "structured").replace("_", " ")
            selected_items.append(
                {
                    "title": "Extraction Completed",
                    "time": str(selected_extraction.get("created_at") or ""),
                    "note": f"Extraction mode: {mode}.",
                }
            )

        if selected_tasks:
            latest_task = max(selected_tasks, key=lambda task: _sort_key(task.get("created_at")))
            done_tasks = sum(1 for task in selected_tasks if _normalize_status(task.get("status")) == "done")
            selected_items.append(
                {
                    "title": "Task Plan Updated",
                    "time": str(latest_task.get("created_at") or ""),
                    "note": f"{done_tasks}/{len(selected_tasks)} tasks complete.",
                }
            )

        if selected_artifacts:
            latest_artifact = max(selected_artifacts, key=lambda artifact: _sort_key(artifact.get("created_at")))
            latest_type = str(latest_artifact.get("type") or "artifact").replace("_", " ").title()
            selected_items.append(
                {
                    "title": "Artifact Generated",
                    "time": str(latest_artifact.get("created_at") or ""),
                    "note": f"Latest output: {latest_type} ({len(selected_artifacts)} total).",
                }
            )

        for entry in sorted(selected_items, key=lambda entry: _sort_key(entry.get("time")), reverse=True)[:5]:
            items.append(
                {
                    "title": entry["title"],
                    "time": _time_since(entry.get("time")),
                    "note": entry["note"],
                }
            )

        other_cases = sorted(cases, key=lambda case: _sort_key(case.get("updated_at")), reverse=True)
        for case in other_cases:
            case_id = str(case.get("case_id") or "")
            if selected_case_id and case_id == selected_case_id:
                continue
            items.append(
                {
                    "title": "Case Updated",
                    "time": _time_since(case.get("updated_at")),
                    "note": f"{case.get('title') or 'Untitled case'} · {str(case.get('status') or 'draft').title()}",
                }
            )
            if len(items) >= 8:
                break

        if not items:
            st.info("No activity yet. Start by selecting a case and running a workflow step.")
            return

        for entry in items[:8]:
            st.markdown(
                f"""
                <div class="activity-item">
                    <div class="activity-head">
                        <p class="activity-title">{escape(entry['title'])}</p>
                        <p class="activity-time">{escape(entry['time'])}</p>
                    </div>
                    <p class="activity-note">{escape(entry['note'])}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown('<div class="activity-bottom-gap"></div>', unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="My Cases", page_icon="📁", layout="wide")
    ensure_state()
    _inject_page_styles()

    cases, cases_err = fetch_cases()
    cases = cases or []

    st.markdown(
        """
        <div class="mycases-hero">
            <span class="mycases-hero-orb" aria-hidden="true"></span>
            <div class="mycases-kicker">My Cases</div>
            <h2>Claims Dashboard</h2>
            <p>
                Track workflow progress across your most recent active cases, switch case focus,
                and jump quickly into workspace tools from one dashboard.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if cases_err:
        st.error(f"Could not load cases: {cases_err}")

    open_count, pending_count, done_count = _status_buckets(cases)
    _render_dashboard_glance(cases, open_count, pending_count, done_count)
    st.markdown('<div class="dashboard-gap-lg"></div>', unsafe_allow_html=True)

    active_cases = [case for case in cases if _is_active_case_status(case.get("status"))]
    tracker_cases = active_cases or cases

    selected_case_id = st.session_state.get("selected_case_id")
    if tracker_cases:
        if not selected_case_id or not any(case.get("case_id") == selected_case_id for case in tracker_cases):
            st.session_state.selected_case_id = tracker_cases[0].get("case_id")
            selected_case_id = st.session_state.selected_case_id
    else:
        st.session_state.selected_case_id = None
        selected_case_id = None

    case_payload = None
    payload_err = None

    tracker_col, focus_col = st.columns([4, 1.2], gap="large")

    with tracker_col:
        with st.container(border=True):
            st.markdown('<p class="section-label">Progress Tracker</p>', unsafe_allow_html=True)
            st.markdown('<p class="section-title">Recent Active Case Progress</p>', unsafe_allow_html=True)
            st.markdown(
                '<p class="section-subtext">Choose a case to track stage completion and workflow readiness.</p>',
                unsafe_allow_html=True,
            )

            if not tracker_cases:
                st.info("No cases yet. Create one below to start tracking.")
            else:
                selected_case_id = select_case(tracker_cases, key_prefix="mycases_tracker", label="Track case")
                if selected_case_id:
                    case_payload, payload_err = fetch_case_payload(selected_case_id)

                if payload_err:
                    st.error(f"Could not load selected case: {payload_err}")
                else:
                    overall, stages = _build_stage_progress(case_payload)
                    st.progress(overall / 100, text=f"Workflow completion: {overall}%")

                    stage_cols = st.columns(len(stages), gap="small")
                    for col, (name, pct, state) in zip(stage_cols, stages):
                        with col:
                            _render_stage_card(name, pct, state)
                    st.markdown('<div class="tracker-bottom-gap"></div>', unsafe_allow_html=True)

    with focus_col:
        _render_workspace_shortcuts_box(compact=True)

    if case_payload and not payload_err:
        _render_case_signal_strip(case_payload)
        st.markdown('<div class="dashboard-gap-lg"></div>', unsafe_allow_html=True)

    left_stack, right_stack = st.columns(2, gap="large")
    with left_stack:
        _render_case_overview_box(case_payload if not payload_err else None)
        st.markdown('<div class="dashboard-gap-lg"></div>', unsafe_allow_html=True)
        _render_recent_activity_feed_box(cases, case_payload if not payload_err else None)
    with right_stack:
        _render_action_center_box(case_payload if not payload_err else None, payload_err if payload_err else None)
        st.markdown('<div class="dashboard-gap-lg"></div>', unsafe_allow_html=True)
        _render_task_summary_box(case_payload if not payload_err else None)

    with st.container(border=True):
        st.markdown('<p class="section-label">Create Case</p>', unsafe_allow_html=True)
        st.markdown('<p class="section-title">Start a New Appeal Workspace</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="section-subtext">Use guided intake so every new case follows the same setup and validation.</p>',
            unsafe_allow_html=True,
        )
        if st.button(
            "Create New Case",
            icon=":material/add_circle:",
            use_container_width=True,
            key="mycases_dashboard_create_case_btn",
        ):
            open_case_workspace_create_flow()


if __name__ == "__main__":
    main()
