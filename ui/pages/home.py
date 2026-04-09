from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from lib.api import ensure_state, fetch_cases, fetch_health

LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "logo.png"


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


def _inject_page_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Space+Grotesk:wght@400;500;600;700&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,500,0,0');

        :root {
            --cr-ink: #0f2237;
            --cr-navy: #123b61;
            --cr-blue: #1f6aa9;
            --cr-sky: #d9eaf9;
            --cr-gold: #efb44a;
            --cr-surface: #f5f9fd;
            --cr-surface-soft: #eef4fb;
            --cr-muted: #54657b;
            --cr-good-bg: #e7f6ee;
            --cr-good-fg: #16623f;
            --cr-bad-bg: #fdecec;
            --cr-bad-fg: #9f2d2d;
        }

        .home-hero {
            border-radius: 24px;
            padding: 1.7rem 1.8rem;
            color: var(--cr-ink);
            background:
                radial-gradient(circle at 8% 12%, rgba(255, 207, 130, 0.38), transparent 35%),
                radial-gradient(circle at 97% -8%, rgba(124, 182, 232, 0.42), transparent 33%),
                radial-gradient(circle at 72% 88%, rgba(140, 203, 241, 0.2), transparent 42%),
                linear-gradient(125deg, #f8fcff 0%, #e8f4ff 49%, #d3e9fb 100%);
            border: 1px solid #c7d9eb;
            box-shadow: 0 16px 34px rgba(16, 42, 67, 0.16);
            margin-bottom: 1rem;
            position: relative;
            overflow: hidden;
        }
        .home-hero::before {
            content: "";
            position: absolute;
            width: 280px;
            height: 280px;
            top: -135px;
            right: -95px;
            border-radius: 999px;
            background: rgba(142, 188, 231, 0.38);
        }
        .home-hero::after {
            content: "";
            position: absolute;
            inset: 0;
            background:
                radial-gradient(circle, rgba(31, 106, 169, 0.11) 1.05px, transparent 1.2px),
                linear-gradient(90deg, rgba(255, 255, 255, 0.24) 0%, rgba(255, 255, 255, 0) 44%);
            background-size: 18px 18px, 100% 100%;
            background-position: 0 0, 0 0;
            opacity: 0.42;
            pointer-events: none;
            mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.35) 0%, rgba(0, 0, 0, 0) 72%);
        }
        .home-orb-two {
            position: absolute;
            width: 170px;
            height: 170px;
            top: -62px;
            right: 205px;
            border-radius: 999px;
            background: rgba(170, 208, 238, 0.24);
            pointer-events: none;
            z-index: 0;
        }
        .home-hero > :not(.home-orb-two) {
            position: relative;
            z-index: 1;
        }
        .home-kicker {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font: 700 0.74rem "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
            color: #245987;
            margin: 0 0 0.45rem 0;
        }
        .home-kicker-logo-wrap {
            margin: 0 0 0.5rem 0;
        }
        .home-kicker-logo {
            display: block;
            width: clamp(330px, 40vw, 600px);
            height: auto;
            max-width: 95%;
        }
        .home-title {
            margin: 0;
            line-height: 1.04;
            color: #122947;
            font: 700 clamp(2rem, 4vw, 3rem) "Fraunces", Georgia, serif;
        }
        .home-copy {
            margin: 0.75rem 0 0;
            max-width: 44rem;
            color: #304b69;
            font: 500 1.02rem/1.55 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
        }
        .home-tagline {
            margin: 0.52rem 0 0;
            max-width: 44rem;
            color: rgba(222, 237, 255, 0.96);
            font: 700 0.95rem/1.45 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
            letter-spacing: 0.01em;
        }
        .stApp .home-promise {
            margin: 0.7rem 0 1rem;
            color: color-mix(in srgb, var(--text-color, currentColor) 96%, transparent);
            text-align: center;
            font: 700 clamp(1.02rem, 2vw, 1.2rem)/1.4 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
            letter-spacing: 0.01em;
        }
        .stApp .section-kicker {
            margin: 2rem 0 0.25rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            color: color-mix(in srgb, var(--primary-color, #1f6aa9) 68%, var(--text-color, currentColor) 32%);
            font: 700 0.72rem/1.2 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
        }

        .stApp .section-title {
            margin: 0 0 0.45rem;
            color: var(--text-color, inherit) !important;
            font: 700 clamp(1.52rem, 2.4vw, 2rem)/1.18 "Fraunces", Georgia, serif;
        }
        .stApp .section-copy {
            margin: 0 0 1rem;
            max-width: 56rem;
            color: color-mix(in srgb, var(--text-color, currentColor) 76%, transparent);
            font: 500 0.97rem/1.55 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
        }
        .section-divider {
            width: 100%;
            height: 1px;
            margin: 1.4rem 0 0.25rem;
            background: linear-gradient(90deg, rgba(31, 106, 169, 0), rgba(31, 106, 169, 0.32), rgba(31, 106, 169, 0));
        }

        .material-symbols-outlined {
            font-variation-settings: "FILL" 0, "wght" 500, "GRAD" 0, "opsz" 24;
            line-height: 1;
        }

        .panel-card,
        .feature-card,
        .step-card,
        .mission-band,
        .why-card,
        .demo-card {
            position: relative;
            overflow: hidden;
            border: 1px solid #d8e4f2;
            border-radius: 18px;
            box-shadow: 0 12px 22px rgba(15, 34, 55, 0.08);
            transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
            animation: home-rise 0.45s ease both;
        }
        .panel-card:hover,
        .feature-card:hover,
        .step-card:hover,
        .why-card:hover,
        .demo-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 16px 28px rgba(15, 34, 55, 0.12);
            border-color: #b9cfe6;
        }
        @keyframes home-rise {
            from { opacity: 0; transform: translateY(7px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .card-icon {
            width: 2rem;
            height: 2rem;
            border-radius: 12px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 0.62rem;
            color: #1f6aa9;
            background: rgba(31, 106, 169, 0.12);
        }

        .panel-card {
            padding: 1rem 1.05rem 1.08rem;
            background: linear-gradient(180deg, #ffffff 0%, #f6faff 100%);
            height: 100%;
        }
        .panel-card::after {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: linear-gradient(90deg, #1f6aa9 0%, #4ea0d7 100%);
        }
        .panel-label {
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 0.11em;
            color: #65809b;
            font: 700 0.69rem/1.2 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
        }
        .panel-value {
            margin: 0.33rem 0 0;
            color: var(--cr-ink);
            font: 700 1.45rem/1.15 "Fraunces", Georgia, serif;
        }
        .panel-desc {
            margin: 0.45rem 0 0;
            color: var(--cr-muted);
            font: 500 0.91rem/1.48 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
        }

        .feature-card {
            padding: 1rem 1.05rem 1.05rem;
            background: linear-gradient(180deg, #ffffff 0%, #f7fbff 100%);
            height: 100%;
            min-height: 160px;
        }
        .feature-card::before {
            content: "";
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 3px;
            background: linear-gradient(180deg, #1f6aa9 0%, #5db0de 100%);
        }
        .feature-title {
            margin: 0;
            color: var(--cr-ink);
            font: 700 1.03rem/1.25 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
        }
        .feature-copy {
            margin: 0.45rem 0 0;
            color: var(--cr-muted);
            font: 500 0.9rem/1.5 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
        }

        .step-card {
            padding: 1rem 1rem 1.05rem;
            background: linear-gradient(180deg, #ffffff 0%, #eef5fc 100%);
            height: 100%;
            min-height: 170px;
            overflow: visible;
            padding-right: 1.3rem;
        }
        .step-card.has-arrow::before {
            content: "";
            position: absolute;
            top: 50%;
            right: -24px;
            transform: translateY(-50%);
            width: 0;
            height: 0;
            border-top: 35px solid transparent;
            border-bottom: 35px solid transparent;
            border-left: 24px solid #c4d8ec;
            z-index: 2;
        }
        .step-card.has-arrow::after {
            content: "";
            position: absolute;
            top: 50%;
            right: -21px;
            transform: translateY(-50%);
            width: 0;
            height: 0;
            border-top: 32px solid transparent;
            border-bottom: 32px solid transparent;
            border-left: 21px solid #edf4fb;
            z-index: 3;
        }
        .step-head {
            display: flex;
            align-items: center;
            gap: 0.48rem;
            margin-bottom: 0.4rem;
        }
        .step-number {
            width: 2rem;
            height: 2rem;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(180deg, #194a76 0%, #2f78b5 100%);
            color: #f8fbff;
            font: 700 0.88rem/1 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
        }
        .step-icon {
            color: #2e76b3;
            font-size: 1.18rem;
            vertical-align: middle;
        }
        .step-title {
            margin: 0;
            color: var(--cr-ink);
            font: 700 1rem/1.25 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
        }
        .step-copy {
            margin: 0.38rem 0 0;
            color: var(--cr-muted);
            font: 500 0.88rem/1.5 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
        }

        .mission-band {
            background:
                radial-gradient(circle at 15% 16%, rgba(239, 180, 74, 0.24), transparent 37%),
                linear-gradient(170deg, #f2f9ff 0%, #e6f0fb 100%);
            padding: 1.2rem 1.25rem;
        }
        .mission-grid {
            display: grid;
            grid-template-columns: 1.5fr 1fr;
            gap: 1rem;
        }
        .mission-title {
            margin: 0;
            color: #0f3558;
            font: 700 1.25rem/1.2 "Fraunces", Georgia, serif;
        }
        .mission-copy {
            margin: 0.55rem 0 0;
            color: #294864;
            font: 500 0.98rem/1.56 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
        }
        .mission-points {
            display: grid;
            gap: 0.5rem;
            align-content: start;
        }
        .mission-point {
            border: 1px solid #c8daee;
            border-radius: 12px;
            padding: 0.42rem 0.6rem;
            background: rgba(255, 255, 255, 0.7);
            color: #284766;
            font: 600 0.85rem/1.35 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
        }

        .why-card {
            height: 100%;
            padding: 1rem 1.05rem;
            background: linear-gradient(180deg, #ffffff 0%, #f6faff 100%);
        }
        .why-title {
            margin: 0;
            color: #16385a;
            font: 700 1.06rem/1.25 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
        }
        .why-list {
            margin: 0.58rem 0 0;
            padding: 0;
            list-style: none;
            display: grid;
            gap: 0.5rem;
        }
        .why-bullet {
            border: 1px solid #d6e5f4;
            border-radius: 12px;
            padding: 0.48rem 0.6rem;
            background: #ffffff;
            color: #3f5874;
            font: 500 0.9rem/1.42 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
        }
        .why-card-alt {
            background: linear-gradient(180deg, #f6fbff 0%, #eef5fd 100%);
        }
        .why-copy {
            margin: 0.58rem 0 0;
            color: #3f5874;
            font: 500 0.9rem/1.52 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
        }

        .demo-card {
            height: 100%;
            padding: 1rem 1.05rem;
            background: linear-gradient(180deg, #ffffff 0%, #f6faff 100%);
            min-height: 150px;
        }
        .demo-title {
            margin: 0;
            color: #16385a;
            font: 700 1.03rem/1.25 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
        }
        .demo-copy {
            margin: 0.48rem 0 0;
            color: #49627d;
            font: 500 0.89rem/1.48 "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
        }

        .status-badge {
            display: inline-block;
            padding: 0.14rem 0.45rem;
            border-radius: 999px;
            font-size: 0.8rem;
            line-height: 1.2;
            font-weight: 700;
            border: 1px solid transparent;
        }
        .status-badge-good {
            background: var(--cr-good-bg);
            color: var(--cr-good-fg);
            border-color: #9fd5b7;
        }
        .status-badge-bad {
            background: var(--cr-bad-bg);
            color: var(--cr-bad-fg);
            border-color: #efb3b3;
        }

        [data-theme="dark"] .home-promise {
            color: #dce8f8;
        }
        [data-theme="dark"] .section-kicker {
            color: #9eb6cf;
        }
        [data-theme="dark"] .section-title {
            color: #e6eefc;
        }
        [data-theme="dark"] .section-copy {
            color: #b8c8db;
        }
        [data-theme="dark"] .section-divider {
            background: linear-gradient(90deg, rgba(121, 165, 211, 0), rgba(121, 165, 211, 0.42), rgba(121, 165, 211, 0));
        }

        [data-theme="dark"] .panel-card,
        [data-theme="dark"] .feature-card,
        [data-theme="dark"] .step-card,
        [data-theme="dark"] .mission-band,
        [data-theme="dark"] .why-card,
        [data-theme="dark"] .demo-card {
            border-color: #2f4360;
            box-shadow: 0 12px 22px rgba(0, 0, 0, 0.28);
        }
        [data-theme="dark"] .panel-card {
            background: linear-gradient(180deg, #162236 0%, #101b2c 100%);
        }
        [data-theme="dark"] .feature-card {
            background: linear-gradient(180deg, #152236 0%, #101a2b 100%);
        }
        [data-theme="dark"] .step-card {
            background: linear-gradient(180deg, #162437 0%, #111d2f 100%);
        }
        [data-theme="dark"] .step-card.has-arrow::before {
            border-left-color: #2f4360;
        }
        [data-theme="dark"] .step-card.has-arrow::after {
            border-left-color: #111d2f;
        }
        [data-theme="dark"] .mission-band {
            background:
                radial-gradient(circle at 15% 16%, rgba(239, 180, 74, 0.18), transparent 37%),
                linear-gradient(170deg, #16283f 0%, #0f1f35 100%);
        }
        [data-theme="dark"] .why-card {
            background: linear-gradient(180deg, #152236 0%, #101b2d 100%);
        }
        [data-theme="dark"] .why-card-alt {
            background: linear-gradient(180deg, #1a2b44 0%, #13243a 100%);
        }
        [data-theme="dark"] .demo-card {
            background: linear-gradient(180deg, #152236 0%, #101a2c 100%);
        }
        [data-theme="dark"] .panel-label,
        [data-theme="dark"] .step-copy,
        [data-theme="dark"] .feature-copy,
        [data-theme="dark"] .why-copy,
        [data-theme="dark"] .demo-copy,
        [data-theme="dark"] .why-bullet {
            color: #b9cbe0;
        }
        [data-theme="dark"] .panel-value,
        [data-theme="dark"] .feature-title,
        [data-theme="dark"] .step-title,
        [data-theme="dark"] .mission-title,
        [data-theme="dark"] .mission-copy,
        [data-theme="dark"] .why-title,
        [data-theme="dark"] .demo-title {
            color: #e8f0ff;
        }
        [data-theme="dark"] .card-icon {
            color: #8cc3f0;
            background: rgba(98, 157, 205, 0.2);
        }
        [data-theme="dark"] .mission-point,
        [data-theme="dark"] .why-bullet {
            border-color: #344b68;
            background: rgba(19, 35, 56, 0.56);
        }

        @media (max-width: 900px) {
            .home-hero {
                padding: 1.35rem 1.15rem;
            }
            .mission-grid {
                grid-template-columns: 1fr;
            }
            .step-card.has-arrow::before,
            .step-card.has-arrow::after {
                display: none;
            }
            .panel-card,
            .feature-card,
            .step-card,
            .mission-band,
            .why-card,
            .demo-card {
                margin-bottom: 0.3rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar_status_item(label: str, value: str, *, tone: str = "neutral") -> None:
    if tone in {"good", "bad"}:
        badge_class = "status-badge-good" if tone == "good" else "status-badge-bad"
        st.markdown(f'{label}: <span class="status-badge {badge_class}">{value}</span>', unsafe_allow_html=True)
        return
    st.write(f"{label}: `{value}`")


def _render_login_prompt(key_prefix: str) -> None:
    with st.container(border=True):
        st.markdown("### Ready to start?")
        st.markdown("Unlock the appeal workspace.")
        if st.button(
            "Log In",
            icon=":material/login:",
            key=f"{key_prefix}_login_button",
            use_container_width=True,
        ):
            st.session_state["redirect_to_login"] = True
            st.rerun()


def _render_landing_hero(is_authenticated: bool) -> None:
    logo_data_uri = _logo_data_uri(LOGO_PATH)
    kicker_html = '<p class="home-kicker">ClaimRight</p>'
    if logo_data_uri:
        kicker_html = (
            f'<div class="home-kicker-logo-wrap">'
            f'<img class="home-kicker-logo" src="{logo_data_uri}" alt="ClaimRight logo">'
            f"</div>"
        )

    st.markdown(
        f"""
        <div class="home-hero">
            <span class="home-orb-two" aria-hidden="true"></span>
            {kicker_html}
            <h1 class="home-title">AI-powered decision support for health insurance claim appeals</h1>
            <p class="home-copy">
                ClaimRight helps people move from confusion to action. We transform denial documents into a clear,
                evidence-backed appeal strategy so patients, caregivers, and advocates can respond with confidence.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="home-promise">Patient-first appeal intelligence for denied health insurance claims</p>',
        unsafe_allow_html=True,
    )

    _, cta_col1, cta_col2, _ = st.columns([0.9, 1.35, 1.35, 0.9], gap="small")
    if is_authenticated:
        with cta_col1:
            if st.button(
                "Start in My Cases",
                icon=":material/folder_open:",
                key="home_start_cases_btn",
                use_container_width=True,
            ):
                st.switch_page("pages/2_My_Cases.py")
        with cta_col2:
            if st.button(
                "Ask the AI Assistant",
                icon=":material/chat:",
                key="home_ai_assistant_btn",
                use_container_width=True,
            ):
                st.switch_page("pages/1_AI_Chatbox.py")
    else:
        with cta_col1:
            st.button("Explore the Platform", icon=":material/travel_explore:", disabled=True, use_container_width=True)
        with cta_col2:
            st.button("Appeal Workspace Locked", icon=":material/lock:", disabled=True, use_container_width=True)
        _render_login_prompt("hero")


def _render_top_logo() -> None:
    if LOGO_PATH.exists():
        left_col, center_col, right_col = st.columns([1.2, 2.8, 1.2])
        with center_col:
            st.image(str(LOGO_PATH), use_container_width=True)
    st.markdown("")


def _render_problem_and_solution() -> None:
    st.markdown('<p class="section-kicker">Challenge</p><h2 class="section-title">The Problem</h2>', unsafe_allow_html=True)
    st.markdown(
        """
        <p class="section-copy">
            Claim denials are common, but most people do not appeal because the process is confusing, technical,
            and time consuming.
        </p>
        """,
        unsafe_allow_html=True,
    )

    problem_cards = [
        (
            "monitoring",
            "10-20%",
            "ACA claims denied",
            "Many denials stem from medical necessity or administrative issues.",
        ),
        (
            "warning",
            "<1%",
            "patients appeal",
            "Most eligible appeals never happen because people do not know where to start.",
        ),
        (
            "gavel",
            "60-70%",
            "appeals overturned",
            "When people do appeal, a large share of denials can be reversed.",
        ),
    ]
    problem_cols = st.columns(3, gap="large")
    for col, (icon, value, label, desc) in zip(problem_cols, problem_cards):
        with col:
            st.markdown(
                f"""
                <div class="panel-card">
                    <span class="card-icon"><span class="material-symbols-outlined">{icon}</span></span>
                    <p class="panel-label">{label}</p>
                    <p class="panel-value">{value}</p>
                    <p class="panel-desc">{desc}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('<p class="section-kicker">Platform</p><h2 class="section-title">What ClaimRight Delivers</h2>', unsafe_allow_html=True)
    st.markdown(
        """
        <p class="section-copy">
            Built from your project framing, ClaimRight combines decision support, precedent grounding,
            and submission-ready outputs in one workflow.
        </p>
        """,
        unsafe_allow_html=True,
    )

    feature_cards = [
        (
            "query_stats",
            "Appealability Score (A-Score)",
            "A data-driven estimate of appeal success that reduces guesswork.",
        ),
        (
            "menu_book",
            "Cited Precedent",
            "Grounded recommendations based on prior outcomes and evidence patterns.",
        ),
        (
            "draft",
            "Draft Appeal Letter",
            "Structured language you can refine and submit faster.",
        ),
        (
            "alt_route",
            "Routing Guidance",
            "Helps determine the best appeal path for the case.",
        ),
        (
            "inventory_2",
            "Submission Packet Builder",
            "Bundles letter, supporting evidence, and checklist into one PDF packet.",
        ),
        (
            "forum",
            "Ongoing AI Support",
            "Use the assistant to ask case-specific questions at any point.",
        ),
    ]
    for start in range(0, len(feature_cards), 3):
        row_cols = st.columns(3, gap="large")
        for col, (icon, title, copy) in zip(row_cols, feature_cards[start : start + 3]):
            with col:
                st.markdown(
                    f"""
                    <div class="feature-card">
                        <span class="card-icon"><span class="material-symbols-outlined">{icon}</span></span>
                        <p class="feature-title">{title}</p>
                        <p class="feature-copy">{copy}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)


def _render_how_it_works() -> None:
    st.markdown('<p class="section-kicker">Workflow</p><h2 class="section-title">How It Works</h2>', unsafe_allow_html=True)
    st.markdown(
        """
        <p class="section-copy">
            From documents to a submission-ready case packet, ClaimRight keeps the process simple and guided.
        </p>
        """,
        unsafe_allow_html=True,
    )

    steps = [
        ("1", "upload_file", "Upload documents", "Add denial letters and supporting records for the case."),
        ("2", "schema", "Structure the case", "The system reads, extracts, and normalizes case data."),
        ("3", "psychology", "Review strategy", "Get A-Score, evidence-backed recommendations, and route guidance."),
        ("4", "send", "Generate packet", "Export organized appeal materials and continue with AI chat support."),
    ]
    step_cols = st.columns(4, gap="medium")
    for idx, (col, (number, icon, title, copy)) in enumerate(zip(step_cols, steps)):
        card_class = "step-card has-arrow" if idx < len(steps) - 1 else "step-card"
        with col:
            st.markdown(
                f"""
                <div class="{card_class}">
                    <div class="step-head">
                        <span class="step-number">{number}</span>
                        <span class="step-icon material-symbols-outlined">{icon}</span>
                    </div>
                    <p class="step-title">{title}</p>
                    <p class="step-copy">{copy}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)


def _render_mission_section() -> None:
    st.markdown('<p class="section-kicker">Purpose</p><h2 class="section-title">Our Mission</h2>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="mission-band">
            <div class="mission-grid">
                <p class="mission-copy">
                    We exist to close the information gap in health insurance appeals.
                    ClaimRight is designed for patient-first transparency: clear explanations,
                    practical guidance, and action-ready outputs when people need them most.
                </p>
                <div class="mission-points">
                    <div class="mission-point">Plain-language explanations</div>
                    <div class="mission-point">Evidence-backed recommendations</div>
                    <div class="mission-point">Submission-ready outputs</div>
                    <div class="mission-point">Human-centered workflow support</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)


def _render_why_use_section(is_authenticated: bool) -> None:
    st.markdown('<p class="section-kicker">Why ClaimRight</p><h2 class="section-title">Why Use ClaimRight</h2>', unsafe_allow_html=True)
    left_col, right_col = st.columns([1.25, 1], gap="large")
    with left_col:
        st.markdown(
            """
            <div class="why-card">
                <p class="why-title">Built for appeal outcomes, not generic chat</p>
                <ul class="why-list">
                    <li class="why-bullet"><strong>Healthcare-specific support:</strong> tailored for denial and appeal workflows.</li>
                    <li class="why-bullet"><strong>Faster preparation:</strong> reduce manual drafting and checklist friction.</li>
                    <li class="why-bullet"><strong>Better structure:</strong> keep evidence, rationale, and next steps in one place.</li>
                    <li class="why-bullet"><strong>Human-centered design:</strong> clarity for patients, advocates, and caregivers.</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right_col:
        st.markdown(
            """
            <div class="why-card why-card-alt">
                <p class="why-title">Who this helps</p>
                <p class="why-copy">Patients and caregivers who need clear action steps after a denial.</p>
                <p class="why-copy">Advocates and care teams who need faster drafting, evidence packaging, and consistent workflow support.</p>
                <p class="why-copy">Teams preparing class demos with a realistic end-to-end appeal experience.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if is_authenticated:
        center_left, center_link, center_right = st.columns([1.2, 1.6, 1.2], gap="small")
        with center_link:
            st.page_link(
                "pages/2_My_Cases.py",
                label="Go to My Cases",
                icon=":material/arrow_forward:",
                use_container_width=True,
            )
    else:
        _render_login_prompt("whyuse")

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)


def _render_demo_workflow_section() -> None:
    st.markdown('<p class="section-kicker">Demo</p><h2 class="section-title">Built For The Demo Workflow</h2>', unsafe_allow_html=True)
    st.markdown(
        """
        <p class="section-copy">
            Navigate the core workspace modules quickly while keeping one active case context across tools.
        </p>
        """,
        unsafe_allow_html=True,
    )

    workflow_cards = [
        ("folder_open", "My Cases", "Create and organize case workspaces, then monitor active status."),
        ("chat", "AI Chatbox", "Ask natural-language questions with or without selected case context."),
        ("query_stats", "A-Score", "Review appealability signals, confidence level, and recommendations."),
    ]
    workflow_cols = st.columns(3, gap="large")
    for col, (icon, title, copy) in zip(workflow_cols, workflow_cards):
        with col:
            st.markdown(
                f"""
                <div class="demo-card">
                    <span class="card-icon"><span class="material-symbols-outlined">{icon}</span></span>
                    <p class="demo-title">{title}</p>
                    <p class="demo-copy">{copy}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


def main() -> None:
    st.set_page_config(page_title="ClaimRight - Home", page_icon="🏠", layout="wide")
    ensure_state()
    _inject_page_styles()

    health, health_err = fetch_health()
    cases, cases_err = fetch_cases()
    is_authenticated = bool(st.session_state.get("is_authenticated"))

    with st.sidebar:
        st.markdown("### System Status")
        _render_sidebar_status_item(
            "Session",
            "Authenticated" if is_authenticated else "Visitor",
            tone="good" if is_authenticated else "neutral",
        )
        _render_sidebar_status_item("Cases", str(len(cases or [])) if not cases_err and cases is not None else "n/a")
        if health_err:
            st.error("API/Ollama status unavailable")
        else:
            _render_sidebar_status_item("API", "Online", tone="good")
            _render_sidebar_status_item(
                "Ollama",
                "Available" if health.get("ollama_available") else "Unavailable",
                tone="good" if health.get("ollama_available") else "bad",
            )

    _render_landing_hero(is_authenticated)

    _render_mission_section()
    _render_problem_and_solution()
    _render_how_it_works()
    _render_why_use_section(is_authenticated)

    if health_err:
        st.warning(f"API health check failed: {health_err}")

    if is_authenticated:
        st.markdown('<h2 class="section-title">Recent Cases</h2>', unsafe_allow_html=True)
        if cases_err:
            st.warning(f"Could not load cases list: {cases_err}")
        elif cases:
            preview = [
                {
                    "case_id": c.get("case_id"),
                    "title": c.get("title"),
                    "status": c.get("status"),
                    "updated_at": c.get("updated_at"),
                }
                for c in cases[:10]
            ]
            st.dataframe(preview, use_container_width=True)
        else:
            st.info("No cases yet. Start from `My Cases` to create your first appeal workspace.")

    _render_demo_workflow_section()


if __name__ == "__main__":
    main()
