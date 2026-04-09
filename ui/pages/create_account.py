from __future__ import annotations

import streamlit as st


def main() -> None:
    st.set_page_config(page_title="Create Account", page_icon=":material/person_add:", layout="wide")

    st.title("Create an Account")
    st.caption("Demo placeholder page")

    st.markdown(
        """
        This page is intentionally a **faux account creation flow** for demo purposes.
        Real self-service signup is not enabled in this prototype yet.
        """
    )

    with st.form("create_account_form"):
        st.text_input("Full Name")
        st.text_input("Email")
        st.text_input("Password", type="password")
        st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Create Account", use_container_width=True)

    if submitted:
        st.warning(
            "Account creation is not available in this demo build. "
            "Please use the demo credentials provided by the presenter."
        )

    nav_col1, nav_col2 = st.columns(2, gap="small")
    with nav_col1:
        if st.button("Back to Log In", icon=":material/login:", use_container_width=True):
            st.session_state["redirect_to_login"] = True
            st.rerun()
    with nav_col2:
        if st.button("Back to Home", icon=":material/home:", use_container_width=True):
            st.session_state["redirect_to_home"] = True
            st.rerun()


if __name__ == "__main__":
    main()
