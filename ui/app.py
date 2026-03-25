from __future__ import annotations

import streamlit as st


def main() -> None:
    navigation = st.navigation(
        [
            st.Page("pages/home.py", title="Home", icon="🏠", default=True),
            st.Page("pages/1_AI_Chatbox.py", title="AI Chatbox", icon="💬"),
            st.Page("pages/2_My_Cases.py", title="My Cases", icon="📁"),
        ]
    )
    navigation.run()


if __name__ == "__main__":
    main()
