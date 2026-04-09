from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "logo.png"
ABOUT_STORY_IMAGE_PATH = Path(__file__).resolve().parents[1] / "assets" / "about us hands.jpg"


def _logo_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    suffix = path.suffix.lower()
    if suffix == ".png":
        mime = "image/png"
    elif suffix == ".jpg" or suffix == ".jpeg":
        mime = "image/jpeg"
    elif suffix == ".webp":
        mime = "image/webp"
    elif suffix == ".svg":
        mime = "image/svg+xml"
    else:
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Manrope:wght@400;500;600;700;800&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,500,0,0');

        :root {
            --cr-ink: var(--text-color, #0f2237);
            --cr-ink-soft: color-mix(in srgb, var(--text-color, #0f2237) 82%, transparent);
            --cr-accent: #2f8f84;
            --cr-accent-soft: #7dd0bf;
            --cr-accent-deep: #266f67;
            --cr-surface: #eef8f5;
            --cr-surface-soft: #e2f4ee;
            --cr-border: color-mix(in srgb, var(--cr-accent-soft) 54%, #9ecdc2 46%);
            --cr-kicker: color-mix(in srgb, var(--cr-accent) 72%, var(--text-color, #0f2237) 28%);
            --cr-card-shadow: rgba(15, 34, 55, 0.14);
        }

        .intro-band {
            border-radius: 22px;
            padding: 1.6rem 1.65rem;
            margin-bottom: 1.15rem;
            background:
                radial-gradient(circle at 8% 12%, rgba(255, 221, 160, 0.3), transparent 35%),
                radial-gradient(circle at 97% -8%, rgba(138, 216, 199, 0.36), transparent 33%),
                radial-gradient(circle at 72% 88%, rgba(133, 195, 225, 0.2), transparent 42%),
                linear-gradient(126deg, #f9fdfc 0%, #e9f7f3 52%, #d9eef0 100%);
            border: 1px solid var(--cr-border);
            box-shadow: 0 16px 32px color-mix(in srgb, var(--cr-card-shadow) 62%, transparent);
            position: relative;
            overflow: hidden;
        }
        .intro-band::before {
            content: "";
            position: absolute;
            width: 270px;
            height: 270px;
            top: -132px;
            right: -98px;
            border-radius: 999px;
            background: rgba(149, 219, 201, 0.35);
            z-index: 0;
        }
        .intro-band::after {
            content: "";
            position: absolute;
            inset: 0;
            background:
                radial-gradient(circle, rgba(40, 126, 114, 0.1) 1.05px, transparent 1.2px),
                linear-gradient(90deg, rgba(255, 255, 255, 0.22) 0%, rgba(255, 255, 255, 0) 46%);
            background-size: 18px 18px, 100% 100%;
            opacity: 0.38;
            pointer-events: none;
            mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.35) 0%, rgba(0, 0, 0, 0) 72%);
        }
        .intro-orb-two {
            position: absolute;
            width: 170px;
            height: 170px;
            top: -62px;
            right: 205px;
            border-radius: 999px;
            background: rgba(177, 224, 211, 0.24);
            pointer-events: none;
            z-index: 0;
        }
        .kicker {
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: #2d6f67;
            font: 800 0.76rem/1.2 "Manrope", "Avenir Next", "Segoe UI", sans-serif;
        }
        .intro-logo-wrap {
            margin: 0 0 0.45rem 0;
            position: relative;
            z-index: 1;
        }
        .intro-logo {
            display: block;
            width: clamp(300px, 38vw, 560px);
            max-width: 94%;
            height: auto;
        }
        .about-title {
            margin: 0.32rem 0 0;
            color: var(--cr-ink) !important;
            font: 700 clamp(2rem, 4vw, 2.8rem) "Fraunces", Georgia, serif;
            line-height: 1.08;
            position: relative;
            z-index: 1;
        }
        .about-subtitle {
            margin: 0.74rem 0 0;
            color: color-mix(in srgb, var(--text-color, currentColor) 78%, transparent);
            max-width: 52rem;
            font: 500 1rem/1.6 "Manrope", "Avenir Next", "Segoe UI", sans-serif;
            position: relative;
            z-index: 1;
        }
        .intro-band > :not(.intro-orb-two) {
            position: relative;
            z-index: 1;
        }
        .about-glance-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.85rem;
            margin: 0 0 1.15rem;
        }
        .about-story-image-shell {
            border-radius: 18px;
            overflow: hidden;
            border: 1px solid var(--cr-border);
            margin: 0 0 1.15rem;
            box-shadow: 0 12px 24px color-mix(in srgb, var(--cr-card-shadow) 52%, transparent);
            background: color-mix(in srgb, var(--cr-surface) 85%, white 15%);
            height: clamp(140px, 23vw, 240px);
        }
        .about-story-image-shell img {
            display: block;
            width: 100%;
            height: 100%;
            object-fit: cover;
            object-position: center 35%;
        }
        .about-glance-card {
            border: 1px solid var(--cr-border);
            border-radius: 14px;
            padding: 0.8rem 0.88rem;
            background: linear-gradient(180deg,
                color-mix(in srgb, var(--cr-surface) 82%, white 18%) 0%,
                color-mix(in srgb, var(--cr-surface-soft) 78%, white 22%) 100%);
            box-shadow: 0 8px 16px color-mix(in srgb, var(--cr-card-shadow) 45%, transparent);
        }
        .about-glance-label {
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: color-mix(in srgb, var(--cr-accent) 74%, var(--text-color, #0f2237) 26%);
            font: 800 0.67rem/1.25 "Manrope", "Avenir Next", "Segoe UI", sans-serif;
        }
        .about-glance-value {
            margin: 0.32rem 0 0;
            color: var(--cr-ink);
            font: 700 1.16rem/1.2 "Fraunces", Georgia, serif;
        }
        .section-kicker {
            margin: 1.9rem 0 0.22rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            color: color-mix(in srgb, var(--cr-accent) 72%, var(--text-color, #0f2237) 28%);
            font: 800 0.72rem/1.2 "Manrope", "Avenir Next", "Segoe UI", sans-serif;
        }
        .section-title {
            margin: 0 0 0.45rem;
            color: inherit !important;
            font: 700 clamp(1.52rem, 2.25vw, 1.9rem)/1.2 "Fraunces", Georgia, serif;
        }
        .section-lead {
            margin: 0 0 0.92rem;
            max-width: 58rem;
            color: color-mix(in srgb, var(--text-color, currentColor) 76%, transparent) !important;
            font: 500 0.96rem/1.6 "Manrope", "Avenir Next", "Segoe UI", sans-serif;
        }
        .section-divider {
            width: 100%;
            height: 1px;
            margin: 1.35rem 0 0.35rem;
            background: linear-gradient(90deg,
                color-mix(in srgb, var(--cr-accent) 0%, transparent),
                color-mix(in srgb, var(--cr-accent) 36%, transparent),
                color-mix(in srgb, var(--cr-accent) 0%, transparent));
        }
        .body-copy {
            margin: 0 0 0.8rem;
            color: inherit;
            font: 500 0.97rem/1.64 "Manrope", "Avenir Next", "Segoe UI", sans-serif;
        }
        .material-symbols-outlined {
            font-variation-settings: "FILL" 0, "wght" 500, "GRAD" 0, "opsz" 24;
            line-height: 1;
        }
        .card-top {
            display: flex;
            align-items: center;
            gap: 0.55rem;
        }
        .icon-chip {
            width: 1.95rem;
            height: 1.95rem;
            border-radius: 12px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            color: var(--cr-accent-deep);
            background: color-mix(in srgb, var(--cr-accent) 18%, transparent);
            flex-shrink: 0;
        }
        .about-card {
            border: 1px solid var(--cr-border);
            border-radius: 16px;
            padding: 1.08rem 1.12rem;
            background: linear-gradient(180deg,
                color-mix(in srgb, var(--cr-surface) 80%, white 20%) 0%,
                color-mix(in srgb, var(--cr-surface) 92%, var(--cr-surface-soft) 8%) 100%);
            height: 100%;
            box-shadow: 0 12px 22px color-mix(in srgb, var(--cr-card-shadow) 64%, transparent);
            position: relative;
            overflow: hidden;
            transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
            animation: about-rise 0.4s ease both;
        }
        .about-card::before {
            content: "";
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 3px;
            background: linear-gradient(180deg, var(--cr-accent-deep) 0%, var(--cr-accent-soft) 100%);
        }
        .about-card:hover {
            transform: translateY(-3px);
            border-color: color-mix(in srgb, var(--cr-accent) 36%, var(--cr-border) 64%);
            box-shadow: 0 16px 28px color-mix(in srgb, var(--cr-card-shadow) 82%, transparent);
        }
        .about-card-title {
            margin: 0;
            color: var(--cr-ink);
            font: 700 1.03rem/1.28 "Manrope", "Avenir Next", "Segoe UI", sans-serif;
        }
        .about-card-copy {
            margin: 0.45rem 0 0;
            color: var(--cr-ink-soft);
            font: 500 0.9rem/1.55 "Manrope", "Avenir Next", "Segoe UI", sans-serif;
        }
        .snapshot-shell {
            border: 1px solid var(--cr-border);
            border-radius: 16px;
            padding: 1rem 1.05rem;
            background: linear-gradient(180deg,
                color-mix(in srgb, var(--cr-surface-soft) 80%, white 20%) 0%,
                var(--cr-surface-soft) 100%);
            height: 100%;
            box-shadow: 0 10px 18px color-mix(in srgb, var(--cr-card-shadow) 56%, transparent);
        }
        .snapshot-title {
            margin: 0;
            color: var(--cr-ink);
            font: 700 1rem/1.25 "Manrope", "Avenir Next", "Segoe UI", sans-serif;
        }
        .snapshot-list {
            margin: 0.55rem 0 0;
            padding-left: 1rem;
            color: var(--cr-ink-soft);
            font: 500 0.9rem/1.52 "Manrope", "Avenir Next", "Segoe UI", sans-serif;
        }
        .snapshot-list li {
            margin: 0.33rem 0;
        }
        .roadmap-pill {
            margin: 0 0 0.38rem;
            display: inline-block;
            border-radius: 999px;
            padding: 0.12rem 0.5rem;
            background: color-mix(in srgb, var(--cr-accent) 22%, white 78%);
            color: color-mix(in srgb, var(--cr-accent) 80%, var(--text-color, #0f2237) 20%);
            font: 800 0.69rem/1.2 "Manrope", "Avenir Next", "Segoe UI", sans-serif;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }
        .trust-note {
            border-left: 3px solid color-mix(in srgb, var(--cr-accent) 86%, transparent);
            padding: 0.2rem 0 0.2rem 0.8rem;
            margin: 0.46rem 0 0;
            color: inherit;
            font: 600 0.9rem/1.5 "Manrope", "Avenir Next", "Segoe UI", sans-serif;
        }
        .team-role {
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--cr-kicker);
            font: 800 0.69rem/1.2 "Manrope", "Avenir Next", "Segoe UI", sans-serif;
        }
        .team-name {
            margin: 0.35rem 0 0;
            color: var(--cr-ink);
            font: 700 1.06rem/1.28 "Fraunces", Georgia, serif;
        }
        .team-copy {
            margin: 0.42rem 0 0;
            color: var(--cr-ink-soft);
            font: 500 0.9rem/1.55 "Manrope", "Avenir Next", "Segoe UI", sans-serif;
        }
        .block-gap {
            height: 1rem;
        }
        @keyframes about-rise {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }
        [data-theme="dark"] .about-glance-card,
        [data-theme="dark"] .about-card,
        [data-theme="dark"] .snapshot-shell {
            border-color: rgba(91, 181, 164, 0.52);
            background: linear-gradient(180deg, rgba(23, 60, 56, 0.82) 0%, rgba(16, 48, 44, 0.86) 100%);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.28);
        }
        [data-theme="dark"] .about-subtitle,
        [data-theme="dark"] .section-lead,
        [data-theme="dark"] .body-copy,
        [data-theme="dark"] .trust-note {
            color: #d8ece6 !important;
        }
        [data-theme="dark"] .icon-chip {
            color: #9fe3d6;
            background: rgba(59, 132, 118, 0.28);
        }
        [data-theme="dark"] .about-card-title,
        [data-theme="dark"] .about-glance-value,
        [data-theme="dark"] .snapshot-title,
        [data-theme="dark"] .team-name,
        [data-theme="dark"] .team-role,
        [data-theme="dark"] .about-card-copy,
        [data-theme="dark"] .snapshot-list,
        [data-theme="dark"] .team-copy {
            color: #e8f5f2;
        }
        [data-theme="dark"] .about-glance-label {
            color: #9fe3d6;
        }
        [data-theme="dark"] .roadmap-pill {
            background: rgba(47, 143, 132, 0.32);
            color: #d6f2eb;
        }
        [data-theme="dark"] .section-divider {
            background: linear-gradient(90deg,
                rgba(82, 170, 154, 0),
                rgba(82, 170, 154, 0.48),
                rgba(82, 170, 154, 0));
        }
        @media (max-width: 900px) {
            .intro-band {
                padding: 1.2rem 1.15rem;
            }
            .about-glance-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .block-gap {
                height: 0.35rem;
            }
        }
        @media (max-width: 640px) {
            .about-glance-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_login_cta() -> None:
    st.markdown("### Ready to start?")
    st.markdown("Unlock the appeal workspace.")
    if st.button("Log In", icon=":material/login:", key="about_login_button", use_container_width=True):
        st.session_state["redirect_to_login"] = True
        st.rerun()


def _render_info_card(title: str, copy: str, icon: str = "info") -> None:
    st.markdown(
        f"""
        <div class="about-card">
            <div class="card-top">
                <span class="icon-chip"><span class="material-symbols-outlined">{icon}</span></span>
                <p class="about-card-title">{title}</p>
            </div>
            <p class="about-card-copy">{copy}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_team_card(role: str, name: str, copy: str, icon: str = "groups") -> None:
    st.markdown(
        f"""
        <div class="about-card">
            <div class="card-top">
                <span class="icon-chip"><span class="material-symbols-outlined">{icon}</span></span>
                <p class="team-role">{role}</p>
            </div>
            <p class="team-name">{name}</p>
            <p class="team-copy">{copy}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _section_header(kicker: str, title: str, lead: str | None = None) -> None:
    st.markdown(
        f'<p class="section-kicker">{kicker}</p><h2 class="section-title">{title}</h2>',
        unsafe_allow_html=True,
    )
    if lead:
        st.markdown(f'<p class="section-lead">{lead}</p>', unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="About Us", page_icon="ℹ️", layout="wide")
    _inject_styles()
    logo_data_uri = _logo_data_uri(LOGO_PATH)
    intro_logo_html = ""
    if logo_data_uri:
        intro_logo_html = (
            f'<div class="intro-logo-wrap">'
            f'<img class="intro-logo" src="{logo_data_uri}" alt="ClaimRight logo">'
            f"</div>"
        )

    st.markdown(
        f"""
        <div class="intro-band">
            <span class="intro-orb-two" aria-hidden="true"></span>
            {intro_logo_html}
            <p class="kicker">About Us</p>
            <h1 class="about-title">Built to make appeals less overwhelming and more winnable</h1>
            <p class="about-subtitle">
                We are building ClaimRight as a patient-centered appeals platform that combines policy understanding,
                clinical context, and practical workflow support. Our focus is simple: help people turn a denial into
                a clear plan of action.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="about-glance-grid">
            <div class="about-glance-card">
                <p class="about-glance-label">Team Members</p>
                <p class="about-glance-value">7</p>
            </div>
            <div class="about-glance-card">
                <p class="about-glance-label">Core Modules</p>
                <p class="about-glance-value">5</p>
            </div>
            <div class="about-glance-card">
                <p class="about-glance-label">Workflow Stage</p>
                <p class="about-glance-value">Intake to Packet</p>
            </div>
            <div class="about-glance-card">
                <p class="about-glance-label">Design Focus</p>
                <p class="about-glance-value">Patient-First</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    story_image_data_uri = _logo_data_uri(ABOUT_STORY_IMAGE_PATH)
    if story_image_data_uri:
        st.markdown(
            f"""
            <div class="about-story-image-shell">
                <img src="{story_image_data_uri}" alt="ClaimRight team collaboration image">
            </div>
            """,
            unsafe_allow_html=True,
        )

    _section_header(
        "Story",
        "Our Story",
        "Why we built ClaimRight and how we think about impact in the appeals process.",
    )
    story_col, snapshot_col = st.columns([1.7, 1], gap="large")
    with story_col:
        st.markdown(
            """
            <p class="body-copy">
                Most patients are asked to become appeals experts overnight, right after a stressful denial notice.
                They are expected to decode policy language, gather evidence, and write persuasive letters while also
                managing care decisions. That gap between what people need and what the system asks of them is why
                ClaimRight exists.
            </p>
            <p class="body-copy">
                The product direction was inspired by mission-driven claims startups that combine healthcare expertise
                with modern technology. We took that model and shaped it for this project: practical workflow support,
                plain-language guidance, and tools that move users from uncertainty to action.
            </p>
            <p class="body-copy">
                We are not trying to replace clinicians, case managers, or legal advocates. We are building software
                that helps those humans do better work faster and gives patients a stronger voice in the process.
            </p>
            """,
            unsafe_allow_html=True,
        )
    with snapshot_col:
        st.markdown(
            """
            <div class="snapshot-shell">
                <p class="snapshot-title">What Defines ClaimRight</p>
                <ul class="snapshot-list">
                    <li>Patient-first language over payer jargon</li>
                    <li>Evidence-backed recommendations over guesswork</li>
                    <li>Actionable outputs, not just analysis</li>
                    <li>Workflow support from intake to submission</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    _section_header(
        "Leadership",
        "Leadership Team",
        "A cross-functional team spanning product, technology, data, and healthcare workflow design.",
    )
    ceo = (
        "CEO",
        "Ha Tuan Long Nguyen",
        "Originated the initial vision for ClaimRight and leads product direction, strategy, and execution.",
        "badge",
    )
    ceo_left, ceo_center, ceo_right = st.columns([1.2, 2.2, 1.2], gap="large")
    with ceo_center:
        _render_team_card(*ceo)
    st.markdown('<div class="block-gap"></div>', unsafe_allow_html=True)

    leaders = [
        (
            "COO",
            'Heejeong "Faith" Kim',
            "Leads operations and delivery across workstreams so the platform remains coordinated, reliable, and user-ready.",
            "settings_suggest",
        ),
        (
            "CFO",
            "Quang Vo",
            "Oversees financial planning and sustainable growth decisions for the platform and its future rollout.",
            "account_balance",
        ),
        (
            "CMO",
            "Ama Boateng",
            "Shapes narrative, user outreach, and positioning so the platform connects clearly with patients and advocates.",
            "campaign",
        ),
        (
            "CIO",
            "Tawonga Muyila",
            "Owns information architecture, governance, and the structure that keeps appeal data organized and actionable.",
            "hub",
        ),
        (
            "CTO",
            "Mi Le",
            "Leads core technical architecture and engineering quality for a dependable, scalable appeals workflow.",
            "code",
        ),
        (
            "CDO",
            "Nguyen Dang",
            "Directs data strategy and analytics quality to ensure recommendations stay evidence-backed and explainable.",
            "database",
        ),
    ]
    for start in range(0, len(leaders), 3):
        row_cols = st.columns(3, gap="large")
        for col, (role, name, copy, icon) in zip(row_cols, leaders[start : start + 3]):
            with col:
                _render_team_card(role, name, copy, icon)
        st.markdown('<div class="block-gap"></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    _section_header(
        "Audience",
        "Who We Serve",
        "We design for the people and teams doing the real appeals work day to day.",
    )
    audiences = [
        (
            "Patients and Families",
            "People navigating denied care who need a clear path forward without spending days decoding policy documents.",
            "family_restroom",
        ),
        (
            "Care Advocates",
            "Caregivers and patient advocates who coordinate records, timelines, and communication on behalf of others.",
            "volunteer_activism",
        ),
        (
            "Clinical and Admin Teams",
            "Provider-side teams that need a repeatable, structured appeal workflow for high-volume denial management.",
            "local_hospital",
        ),
    ]
    audience_cols = st.columns(3, gap="large")
    for col, (title, copy, icon) in zip(audience_cols, audiences):
        with col:
            _render_info_card(title, copy, icon)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    _section_header(
        "Principles",
        "How We Work",
        "Our product choices are guided by practical user outcomes, not just feature output.",
    )
    principles = [
        (
            "Empower Action",
            "Each screen should answer: what can the user do next right now? We prioritize practical next steps over abstract dashboards.",
            "bolt",
        ),
        (
            "Do The Right Thing",
            "We optimize for clarity, fairness, and patient dignity, especially in moments where the system feels adversarial.",
            "balance",
        ),
        (
            "Build What Is Missing",
            "ClaimRight fills the handoff gaps between denial letters, evidence review, draft writing, and final packet assembly.",
            "build",
        ),
        (
            "Own The Outcome",
            "Success is not just activity inside the app. Success is better-prepared appeals and stronger confidence for users.",
            "target",
        ),
    ]
    for start in range(0, len(principles), 2):
        row_cols = st.columns(2, gap="large")
        for col, (title, copy, icon) in zip(row_cols, principles[start : start + 2]):
            with col:
                _render_info_card(title, copy, icon)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    _section_header(
        "Trust",
        "Trust and Responsibility",
        "Sensitive health and financial details require transparent guidance and careful defaults.",
    )
    trust_col, checklist_col = st.columns([1.4, 1], gap="large")
    with trust_col:
        st.markdown(
            """
            <p class="body-copy">
                Appeals involve sensitive health and financial information, so trust is not optional. We design our
                workflows to be transparent about how recommendations are produced and what users should verify before
                submission.
            </p>
            <p class="body-copy">
                ClaimRight is a decision-support platform, not a substitute for medical or legal judgment. Our role is
                to surface structure, evidence, and drafting support so users can make informed decisions with their
                care team or advocate.
            </p>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <p class="trust-note">
                We treat explainability, user control, and privacy safeguards as product requirements, not optional add-ons.
            </p>
            """,
            unsafe_allow_html=True,
        )
    with checklist_col:
        st.markdown(
            """
            <div class="snapshot-shell">
                <p class="snapshot-title">Our Trust Checklist</p>
                <ul class="snapshot-list">
                    <li>Plain-language rationale behind suggestions</li>
                    <li>Clear review points before export/submission</li>
                    <li>Role-aware workflows for collaborative teams</li>
                    <li>Data minimization and privacy-minded defaults</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    _section_header(
        "Roadmap",
        "Where We Are Going",
        "How the platform evolves from demo workflow into broader operational support.",
    )
    roadmap = [
        (
            "Now",
            "Demoing a complete denial-to-appeal workflow that helps users organize records, evaluate appeal strength, and generate action-ready outputs.",
        ),
        (
            "Next",
            "Expanding policy intelligence, role-based collaboration, and stronger audit trails so teams can scale beyond one-off cases.",
        ),
        (
            "Later",
            "Measuring longitudinal outcomes and building feedback loops that improve recommendations across conditions and payer rules.",
        ),
    ]
    roadmap_cols = st.columns(3, gap="large")
    for col, (phase, copy) in zip(roadmap_cols, roadmap):
        with col:
            st.markdown(
                f"""
                <div class="about-card">
                    <p class="roadmap-pill">{phase}</p>
                    <p class="about-card-copy">{copy}</p>
                </div>
                """,
            unsafe_allow_html=True,
        )

    is_authenticated = bool(st.session_state.get("is_authenticated"))
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    _section_header("Action", "Next Step")
    with st.container(border=True):
        if is_authenticated:
            st.markdown("Continue your workflow in the appeal workspace.")
            st.page_link(
                "pages/2_My_Cases.py",
                label="Go to My Cases",
                icon=":material/arrow_forward:",
                use_container_width=True,
            )
        else:
            _render_login_cta()


if __name__ == "__main__":
    main()
