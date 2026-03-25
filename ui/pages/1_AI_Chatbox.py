from __future__ import annotations

import streamlit as st

from lib.api import (
    api_post,
    create_case_form,
    ensure_state,
    fetch_case_payload,
    fetch_cases,
    fetch_health,
    safe_call,
    select_case,
)
from lib.components import render_sources


def _inject_page_styles() -> None:
    st.markdown(
        """
        <style>
        .chat-hero {
            padding: 1.35rem 1.5rem;
            border-radius: 24px;
            background:
                radial-gradient(circle at top right, rgba(161, 211, 199, 0.25), transparent 32%),
                linear-gradient(135deg, #1a2833 0%, #23566a 55%, #6db8a6 100%);
            color: #f5f7f2;
            margin-bottom: 1rem;
            box-shadow: 0 18px 38px rgba(26, 40, 51, 0.2);
        }
        .chat-kicker {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.75rem;
            opacity: 0.82;
            margin-bottom: 0.35rem;
        }
        .chat-hero h2 {
            margin: 0;
            font-size: 2rem;
            line-height: 1.1;
        }
        .chat-hero p {
            margin: 0.55rem 0 0;
            max-width: 48rem;
            color: rgba(245, 247, 242, 0.9);
        }
        .section-label {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.72rem;
            font-weight: 700;
            color: #6f7c73;
            margin-bottom: 0.45rem;
        }
        .chat-shell {
            padding: 1rem 1.1rem;
            border-radius: 22px;
            background: linear-gradient(180deg, rgba(255,255,255,0.97) 0%, rgba(243,247,244,0.9) 100%);
            border: 1px solid rgba(26, 40, 51, 0.08);
        }
        .chat-title {
            font-size: 1.25rem;
            font-weight: 800;
            color: #1a2833;
            margin: 0.1rem 0 0.35rem;
        }
        .chat-copy {
            color: #5a6662;
            margin-bottom: 0.25rem;
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
            background: #e7f2ff;
            color: #0f4e8a;
            border-color: #a6caef;
        }
        .status-done {
            background: #e7f6ee;
            color: #16623f;
            border-color: #9fd5b7;
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
            background: #e7f6ee;
            color: #16623f;
            border-color: #9fd5b7;
        }
        .status-badge-bad {
            background: #fdecec;
            color: #9f2d2d;
            border-color: #efb3b3;
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


def _render_active_case_header(case_payload: dict | None, case_id: str | None) -> None:
    if not case_id:
        st.markdown('<p class="section-label">Active Case</p>', unsafe_allow_html=True)
        st.info("Create or select a case above to start chatting.")
        return

    case = (case_payload or {}).get("case", {})
    status = case.get("status", "open")
    pill = _status_class(status)
    extraction = (case_payload or {}).get("extraction")
    extraction_state = extraction.get("mode", "not run") if extraction else "not run"
    docs = len((case_payload or {}).get("documents", []))

    st.markdown(
        f"""
        <div class="chat-shell">
            <div class="section-label">Active Case</div>
            <div class="chat-title">{case.get('title', 'Untitled Case')}</div>
            <div class="chat-copy">
                <span class="status-pill {pill}">{status}</span>
                &nbsp;&nbsp;Case ID: <strong>{case_id}</strong>
            </div>
            <div class="chat-copy">Documents: <strong>{docs}</strong> | Extraction: <strong>{extraction_state}</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar_status_item(label: str, value: str, *, tone: str = "neutral") -> None:
    if tone in {"good", "bad"}:
        badge_class = "status-badge-good" if tone == "good" else "status-badge-bad"
        st.markdown(f'{label}: <span class="status-badge {badge_class}">{value}</span>', unsafe_allow_html=True)
        return
    st.write(f"{label}: `{value}`")


def main() -> None:
    st.set_page_config(page_title="AI Chatbox", page_icon="💬", layout="wide")
    ensure_state()
    _inject_page_styles()

    st.markdown(
        """
        <div class="chat-hero">
            <div class="chat-kicker">Case Assistant</div>
            <h2>AI Chatbox</h2>
            <p>Ask focused questions about a claim, understand denial reasoning, and get grounded next-step guidance without losing sight of the case context.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cases, cases_err = fetch_cases()
    health, health_err = fetch_health()

    top_col1, top_col2 = st.columns([1, 1], gap="large")
    with top_col1:
        with st.container(border=True):
            st.markdown('<p class="section-label">Start Here</p>', unsafe_allow_html=True)
            st.subheader("Create Case")
            st.caption("Start a new case if you want to open a fresh chat workspace.")
            create_case_form(key_prefix="chat")

    with top_col2:
        with st.container(border=True):
            st.markdown('<p class="section-label">Pick Context</p>', unsafe_allow_html=True)
            st.subheader("Select Case")
            st.caption("Choose the case the assistant should use for answers.")
            if cases_err:
                st.error(f"Could not load cases: {cases_err}")
            elif not cases:
                st.info("No cases found. Create one to begin.")
            else:
                select_case(cases, key_prefix="chat", label="Active case")

    if cases_err:
        st.error(f"Cannot continue without cases API: {cases_err}")
        st.stop()

    case_id = st.session_state.get("selected_case_id")
    case_payload = None
    payload_err = None
    if case_id:
        case_payload, payload_err = fetch_case_payload(case_id)

    with st.sidebar:
        st.markdown("### Status")
        _render_sidebar_status_item("Available Cases", str(len(cases or [])))
        _render_sidebar_status_item(
            "Chat Ready",
            "Yes" if case_id and not payload_err else "No",
            tone="good" if case_id and not payload_err else "bad",
        )
        if health_err:
            st.error("API/Ollama status unavailable")
        else:
            _render_sidebar_status_item("API", "Online", tone="good")
            _render_sidebar_status_item(
                "Ollama",
                "Available" if health.get("ollama_available") else "Unavailable",
                tone="good" if health.get("ollama_available") else "bad",
            )

    _render_active_case_header(case_payload, case_id)
    if not case_id:
        st.stop()
    if payload_err or not case_payload:
        st.error(f"Could not load selected case: {payload_err}")
        st.stop()

    with st.container(border=True):
        st.markdown('<p class="section-label">Context</p>', unsafe_allow_html=True)
        st.subheader("Case Context")
        extraction = case_payload.get("extraction")
        if extraction:
            st.caption(f"Extraction mode: {extraction.get('mode', 'unknown')}")
            st.json(extraction.get("case_json", {}))
        else:
            st.info("No extraction yet. Run extraction from `My Cases` for more grounded responses.")

    chat_key = f"assistant_messages_{case_id}"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    with st.container(border=True):
        header_col1, header_col2 = st.columns([3, 1])
        header_col1.markdown("### Conversation")
        header_col1.caption("Examples: `Why was my claim denied?` or `Explain this denial in simple terms.`")
        if header_col2.button("Clear Chat", key=f"chat_clear_{case_id}", use_container_width=True):
            st.session_state[chat_key] = []
            st.rerun()

        for msg in st.session_state[chat_key]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg["role"] == "assistant":
                    st.caption(f"Mode: {msg.get('mode', 'unknown')}")
                    if msg.get("warning"):
                        st.warning(msg["warning"])
                    with st.expander("Sources", expanded=False):
                        render_sources(msg.get("sources", []))

        question = st.chat_input("Ask about denial reasons, evidence, policy context, and next steps...")
        if question:
            st.session_state[chat_key].append({"role": "user", "content": question})
            body, chat_err = safe_call(
                api_post,
                f"/cases/{case_id}/chat",
                json_body={"question": question},
            )
            if chat_err:
                st.session_state[chat_key].append(
                    {
                        "role": "assistant",
                        "content": f"Chat request failed: {chat_err}",
                        "sources": [],
                        "mode": "error",
                    }
                )
            else:
                st.session_state[chat_key].append(
                    {
                        "role": "assistant",
                        "content": str(body.get("answer", "")),
                        "sources": body.get("sources", []),
                        "mode": body.get("mode", "unknown"),
                        "warning": body.get("warning"),
                    }
                )
            st.rerun()


if __name__ == "__main__":
    main()
