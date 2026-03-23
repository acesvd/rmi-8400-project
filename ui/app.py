from __future__ import annotations

import streamlit as st

from lib.api import ensure_state, fetch_cases, fetch_health


def main() -> None:
    st.set_page_config(page_title="Claims Appeal OS - Home", page_icon="🏠", layout="wide")
    ensure_state()

    st.title("Claims Appeal OS")
    st.caption("Home page for the class prototype. Use the pages in the left sidebar to access AI Chatbox and My Cases.")

    health, health_err = fetch_health()
    cases, cases_err = fetch_cases()

    col1, col2, col3 = st.columns(3)

    if health_err:
        col1.metric("API Status", "Unavailable")
        col2.metric("Ollama", "Unknown")
    else:
        col1.metric("API Status", "Online")
        col2.metric("Ollama", "Available" if health.get("ollama_available") else "Unavailable")

    if cases_err or cases is None:
        col3.metric("Cases", "n/a")
    else:
        col3.metric("Cases", len(cases))

    if health_err:
        st.error(f"API health check failed: {health_err}")

    st.subheader("Navigation")
    st.markdown("- Open `My Cases` to create/select cases and manage documents/tasks/artifacts.")
    st.markdown("- Open `AI Chatbox` to ask natural language questions about a selected case.")

    st.subheader("Demo Flow")
    st.markdown("1. Go to `My Cases` and create a new case.")
    st.markdown("2. Upload denial and supporting docs, then run extraction.")
    st.markdown("3. Generate tasks, letter, and packet PDF.")
    st.markdown("4. Go to `AI Chatbox` and ask: `Why was my claim denied?`")

    if cases_err:
        st.warning(f"Could not load cases list: {cases_err}")
    elif cases:
        st.subheader("Recent Cases")
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
        st.info("No cases yet. Create one from the `My Cases` page.")


if __name__ == "__main__":
    main()
