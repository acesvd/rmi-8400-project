from __future__ import annotations

import streamlit as st

from lib.api import (
    create_case_form,
    ensure_state,
    fetch_case_payload,
    fetch_cases,
    fetch_health,
    safe_call,
    api_post,
    select_case,
)
from lib.components import render_sources


def main() -> None:
    st.set_page_config(page_title="AI Chatbox", page_icon="💬", layout="wide")
    ensure_state()

    st.title("AI Chatbox")
    st.caption("Ask questions about your selected case. Ollama is primary; fallback logic is automatic.")

    cases, cases_err = fetch_cases()

    with st.sidebar:
        st.subheader("Case Selection")
        create_case_form(key_prefix="chat")

        st.divider()
        if cases_err:
            st.error(f"Could not load cases: {cases_err}")
        elif not cases:
            st.info("No cases found. Create one above.")
        else:
            select_case(cases, key_prefix="chat", label="Active case")

        st.divider()
        health, health_err = fetch_health()
        if health_err:
            st.caption("API/Ollama status unavailable")
        else:
            st.caption(f"Ollama available: {health.get('ollama_available')}")

    case_id = st.session_state.get("selected_case_id")
    if not case_id:
        st.info("Select or create a case from the sidebar.")
        st.stop()

    case_payload, payload_err = fetch_case_payload(case_id)
    if payload_err or not case_payload:
        st.error(f"Could not load selected case: {payload_err}")
        st.stop()

    case = case_payload["case"]
    st.markdown(f"**Active Case:** {case['title']} (`{case['case_id']}`) | Status: `{case['status']}`")

    extraction = case_payload.get("extraction")
    with st.expander("Case Context", expanded=False):
        if extraction:
            st.json(extraction.get("case_json", {}))
        else:
            st.caption("No extraction yet. Go to `My Cases` and run extraction for better responses.")

    chat_key = f"assistant_messages_{case_id}"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    col1, col2 = st.columns([3, 1])
    col1.caption("Examples: `Why was my claim denied?` or `Explain this denial in simple terms.`")
    if col2.button("Clear Chat", key=f"chat_clear_{case_id}"):
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
