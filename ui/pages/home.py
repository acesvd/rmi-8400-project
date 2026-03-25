from __future__ import annotations

import streamlit as st

from lib.api import ensure_state, fetch_cases, fetch_health


def _inject_page_styles() -> None:
    st.markdown(
        """
        <style>
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


def _render_sidebar_status_item(label: str, value: str, *, tone: str = "neutral") -> None:
    if tone in {"good", "bad"}:
        badge_class = "status-badge-good" if tone == "good" else "status-badge-bad"
        st.markdown(f'{label}: <span class="status-badge {badge_class}">{value}</span>', unsafe_allow_html=True)
        return
    st.write(f"{label}: `{value}`")


def main() -> None:
    st.set_page_config(page_title="Claims Appeal OS - Home", page_icon="🏠", layout="wide")
    ensure_state()
    _inject_page_styles()

    st.title("Claims Appeal OS")
    st.caption("Home page for the class prototype. Use the pages in the left sidebar to access AI Chatbox and My Cases.")

    health, health_err = fetch_health()
    cases, cases_err = fetch_cases()

    with st.sidebar:
        st.markdown("### Status")
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
