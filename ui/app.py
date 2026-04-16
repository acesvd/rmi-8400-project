from __future__ import annotations

import hmac
import importlib.util
import os
from pathlib import Path

import streamlit as st

from lib.feature_flags import is_chat_ui_enabled, is_demo_mode, is_demo_user_mode

UI_DIR = Path(__file__).parent.resolve()

APP_USERNAME_ENV = "CLAIMRIGHT_UI_USERNAME"
APP_PASSWORD_ENV = "CLAIMRIGHT_UI_PASSWORD"
ADMIN_USERNAME_ENV = "CLAIMRIGHT_UI_ADMIN_USERNAME"
ADMIN_PASSWORD_ENV = "CLAIMRIGHT_UI_ADMIN_PASSWORD"
DEMO_USERNAME_ENV = "CLAIMRIGHT_UI_DEMO_USERNAME"
DEMO_PASSWORD_ENV = "CLAIMRIGHT_UI_DEMO_PASSWORD"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "claimright-admin"
DEFAULT_DEMO_USERNAME = "demo"
DEFAULT_DEMO_PASSWORD = "claimright"
HOME_PAGE = ("Home", ":material/home:")
ABOUT_PAGE = ("About Us", ":material/info:")
CREATE_ACCOUNT_PAGE = ("Create Account", ":material/person_add:")
DEMO_DISCLAIMER_SEEN_KEY = "demo_mode_disclaimer_seen"

PROTECTED_PAGES = [
    (str(UI_DIR / "pages" / "2_My_Cases.py"), "My Cases", ":material/dashboard:"),
    (str(UI_DIR / "pages" / "4_Case_Library.py"), "Case Library", ":material/library_books:"),
    (str(UI_DIR / "pages" / "5_Case_Workspace.py"), "Case Workspace", ":material/lab_profile:"),
    (str(UI_DIR / "pages" / "1_AI_Chatbox.py"), "AI Chatbox", ":material/chat:"),
    (str(UI_DIR / "pages" / "3_A_Score.py"), "A-Score", ":material/analytics:"),
]


def _ensure_auth_state() -> None:
    st.session_state.setdefault("is_authenticated", False)
    st.session_state.setdefault("auth_username", "")
    st.session_state.setdefault("auth_role", "")
    st.session_state.setdefault("redirect_to_cases_after_login", False)
    st.session_state.setdefault("redirect_to_login", False)
    st.session_state.setdefault("show_create_account_form", False)
    st.session_state.setdefault("redirect_to_home", False)
    st.session_state.setdefault(DEMO_DISCLAIMER_SEEN_KEY, False)


@st.dialog("Live Demo Mode Notice", width="large", dismissible=False)
def _render_demo_mode_disclaimer_dialog() -> None:
    st.markdown(
        """
        This prototype is currently configured for a **classroom live demo** on free-tier resources.

        **Temporarily disabled features**
        - New Case creation
        - Document uploads
        - Workflow actions (Process, Extract, Tasks, Letter, Packet)
        - A-Score recomputation

        **AI chat remains available, with limits**
        - Up to 6 messages/questions per session
        - Cooldown between messages

        Two demo cases have been preloaded for viewing.

        Full workflow behavior remains available outside demo mode.
        """
    )
    if st.button("I Understand", type="primary", use_container_width=True, key="demo_mode_disclaimer_ack_btn"):
        st.session_state[DEMO_DISCLAIMER_SEEN_KEY] = True
        st.rerun()


def _run_page_main(page_filename: str) -> None:
    page_path = UI_DIR / "pages" / page_filename
    spec = importlib.util.spec_from_file_location(f"ui_page_{page_path.stem}", page_path)
    if spec is None or spec.loader is None:
        st.error(f"Could not load page module: {page_filename}")
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    main_fn = getattr(module, "main", None)
    if callable(main_fn):
        main_fn()
    else:
        st.error(f"Page module `{page_filename}` is missing a `main()` function.")


def _run_home_page() -> None:
    _run_page_main("home.py")


def _run_about_page() -> None:
    _run_page_main("about.py")


def _configured_credentials() -> dict[str, tuple[str, str]]:
    legacy_username = os.getenv(APP_USERNAME_ENV)
    legacy_password = os.getenv(APP_PASSWORD_ENV)

    admin_username = os.getenv(ADMIN_USERNAME_ENV, DEFAULT_ADMIN_USERNAME)
    admin_password = os.getenv(ADMIN_PASSWORD_ENV, DEFAULT_ADMIN_PASSWORD)
    demo_username = os.getenv(DEMO_USERNAME_ENV, legacy_username or DEFAULT_DEMO_USERNAME)
    demo_password = os.getenv(DEMO_PASSWORD_ENV, legacy_password or DEFAULT_DEMO_PASSWORD)

    return {
        "admin": (admin_username, admin_password),
        "demo": (demo_username, demo_password),
    }


def _render_login_page() -> None:
    show_create_account = bool(st.session_state.get("show_create_account_form"))
    if show_create_account:
        st.title("Create an Account")
        st.caption("Demo placeholder page")
        st.markdown(
            """
            This is intentionally a **faux account creation flow** for demo purposes.
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
                st.session_state["show_create_account_form"] = False
                st.rerun()
        with nav_col2:
            if st.button("Back to Home", icon=":material/home:", use_container_width=True):
                st.session_state["show_create_account_form"] = False
                st.session_state["redirect_to_home"] = True
                st.rerun()
        return

    st.title("Log In")
    st.caption("Sign in to access My Cases, AI Chatbox, and A-Score.")
    credentials = _configured_credentials()
    admin_username, admin_password = credentials["admin"]
    demo_username, demo_password = credentials["demo"]

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In", use_container_width=True)

    if submitted:
        clean_username = username.strip()
        role: str | None = None
        if hmac.compare_digest(clean_username, admin_username) and hmac.compare_digest(password, admin_password):
            role = "admin"
        elif hmac.compare_digest(clean_username, demo_username) and hmac.compare_digest(password, demo_password):
            role = "demo"

        if role:
            st.session_state["is_authenticated"] = True
            st.session_state["auth_username"] = clean_username
            st.session_state["auth_role"] = role
            st.session_state["redirect_to_cases_after_login"] = True
            st.session_state["redirect_to_login"] = False
            st.session_state[DEMO_DISCLAIMER_SEEN_KEY] = False
            st.rerun()
        else:
            st.error("Invalid username or password.")

    if is_demo_mode():
        st.info("Demo login credentials: `demo` / `claimright`.")
    else:
        st.info(
            "Demo login credentials: `demo` / `claimright`.\n\n"
            "Admin login credentials: `admin` / `claimright-admin`."
        )
        st.caption("Note: Admin role is fully unlocked and has access to all features.")

    st.divider()
    st.caption("Don't have an account yet?")
    if st.button("Create an account", icon=CREATE_ACCOUNT_PAGE[1], use_container_width=True, key="login_create_btn"):
        st.session_state["show_create_account_form"] = True
        st.rerun()


def _run_logout_page() -> None:
    st.session_state["is_authenticated"] = False
    st.session_state["auth_username"] = ""
    st.session_state["auth_role"] = ""
    st.session_state["show_create_account_form"] = False
    st.session_state["redirect_to_home"] = True
    st.session_state[DEMO_DISCLAIMER_SEEN_KEY] = False
    st.rerun()


def main() -> None:
    _ensure_auth_state()
    ui_dir = Path(__file__).parent
    demo_user_mode = is_demo_user_mode()
    chat_ui_enabled = is_chat_ui_enabled()

    st.logo(
        str(ui_dir / "assets" / "logo.png"),
        size="large",
    )

    st.markdown(
        """
        <style>
        [data-testid="stHeader"] .stLogo,
        [data-testid="stAppHeader"] .stLogo {
            width: 10.75rem !important;
            max-width: 10.75rem !important;
            height: auto !important;
        }
        [data-testid="stHeader"] .stLogo img,
        [data-testid="stAppHeader"] .stLogo img {
            width: 100% !important;
            height: auto !important;
            max-height: 2.35rem !important;
        }

        /* Sidebar logo (expanded) */
        [data-testid="stSidebarHeader"] .stLogo {
            width: calc(100% - 2rem) !important;
            max-width: calc(100% - 2rem) !important;
            height: auto !important;
            margin: 0 !important;
        }
        [data-testid="stSidebarHeader"] .stLogo img {
            width: 100% !important;
            height: auto !important;
        }

        /* Sidebar logo (collapsed icon) */
        [data-testid="stSidebarCollapsedControl"] .stLogo {
            width: 2.25rem !important;
            max-width: 2.25rem !important;
            height: 2.25rem !important;
        }

        /* Keep enough top spacing so content clears the enlarged header logo */
        div[data-testid="stAppViewBlockContainer"],
        div[data-testid="stMainBlockContainer"] {
            padding-top: 3rem !important;
            padding-bottom: 0.55rem !important;
        }

        .cr-global-footer {
            text-align: center;
            font-size: 0.68rem;
            letter-spacing: 0.06em;
            line-height: 1.2;
            margin-top: 0.8rem;
            padding: 0.45rem 0.75rem 0.35rem;
            color: color-mix(in srgb, var(--text-color, #334155) 68%, transparent);
            border-top: 1px solid color-mix(in srgb, var(--text-color, #334155) 18%, transparent);
            background: transparent;
        }
        .cr-global-footer-note {
            display: block;
            margin-top: 0.2rem;
            font-size: 0.62rem;
            letter-spacing: 0.04em;
            color: color-mix(in srgb, var(--text-color, #334155) 56%, transparent);
        }
        [data-theme="dark"] .cr-global-footer {
            color: rgba(202, 219, 237, 0.86);
            border-top-color: rgba(148, 181, 214, 0.34);
            background: transparent;
        }
        [data-theme="dark"] .cr-global-footer-note {
            color: rgba(185, 207, 229, 0.72);
        }

        @media (max-width: 768px) {
            [data-testid="stHeader"] .stLogo,
            [data-testid="stAppHeader"] .stLogo {
                width: 7.75rem !important;
                max-width: 7.75rem !important;
            }
            [data-testid="stHeader"] .stLogo img,
            [data-testid="stAppHeader"] .stLogo img {
                max-height: 1.95rem !important;
            }

            [data-testid="stSidebarHeader"] .stLogo {
                width: calc(100% - 1.5rem) !important;
                max-width: calc(100% - 1.5rem) !important;
            }

            div[data-testid="stAppViewBlockContainer"],
            div[data-testid="stMainBlockContainer"] {
                padding-top: 2rem !important;
                padding-bottom: 0.45rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    is_authenticated = bool(st.session_state.get("is_authenticated"))
    if demo_user_mode and is_authenticated and not bool(st.session_state.get(DEMO_DISCLAIMER_SEEN_KEY)):
        _render_demo_mode_disclaimer_dialog()
        return

    home_page = st.Page(_run_home_page, title=HOME_PAGE[0], icon=HOME_PAGE[1], default=not is_authenticated)
    about_page = st.Page(_run_about_page, title=ABOUT_PAGE[0], icon=ABOUT_PAGE[1], default=False)
    my_cases_page: st.Page | None = None
    login_page: st.Page | None = None
    nav_pages: list[st.Page] | dict[str, list[st.Page]]

    if is_authenticated:
        protected_page_defs = list(PROTECTED_PAGES)
        if not chat_ui_enabled:
            protected_page_defs = [item for item in protected_page_defs if item[1] != "AI Chatbox"]

        protected_pages = [
            st.Page(protected_page_defs[0][0], title="Dashboard", icon=protected_page_defs[0][2], default=True),
            *[
                st.Page(page_path, title=page_title, icon=page_icon, default=False)
                for page_path, page_title, page_icon in protected_page_defs[1:]
            ],
        ]
        logout_page = st.Page(_run_logout_page, title="Log Out", icon=":material/logout:", default=False)
        my_cases_page = protected_pages[0]
        nav_pages = {
            "Explore": [home_page, about_page],
            "My Cases": protected_pages,
            "Account": [logout_page],
        }
    else:
        login_page = st.Page(_render_login_page, title="Log In", icon=":material/login:", default=False)
        nav_pages = {
            "Explore": [home_page, about_page],
            "Account": [login_page],
        }

    should_redirect_to_cases = bool(st.session_state.get("redirect_to_cases_after_login"))
    if is_authenticated and should_redirect_to_cases and my_cases_page is not None:
        st.session_state["redirect_to_cases_after_login"] = False
        st.switch_page(my_cases_page)

    should_redirect_to_login = bool(st.session_state.get("redirect_to_login"))
    if not is_authenticated and should_redirect_to_login and login_page is not None:
        st.session_state["redirect_to_login"] = False
        st.switch_page(login_page)

    should_redirect_to_home = bool(st.session_state.get("redirect_to_home"))
    if should_redirect_to_home:
        st.session_state["redirect_to_home"] = False
        st.switch_page(home_page)

    navigation = st.navigation(
        nav_pages,
        position="top",
    )
    navigation.run()
    st.markdown(
        """
        <div class="cr-global-footer">
            RMI 8400 - Spring 2026 - Group 4
            <span class="cr-global-footer-note">Developed for Educational Purposes Only. Not a Real Service.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
