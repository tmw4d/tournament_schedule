"""Optional Google sign-in and email-based admin access."""

import streamlit as st


def _get_email_lists():
    try:
        secrets = st.secrets
        allowed_domain = str(secrets.get("ALLOWED_DOMAIN", "")).strip().lower()
        admin_emails = secrets.get("ADMIN_EMAILS", [])
        allowed_emails = secrets.get("ALLOWED_EMAILS", [])
    except Exception:
        return "", [], []

    def normalize_list(values):
        if isinstance(values, str):
            values = values.split(",")
        return [str(value).strip().lower() for value in values if str(value).strip()]

    return allowed_domain, normalize_list(admin_emails), normalize_list(allowed_emails)


def resolve_optional_auth():
    """Set the current role without blocking public access."""
    user = getattr(st, "user", None)
    if user is None:
        user = getattr(st, "experimental_user", None)

    is_logged_in = bool(user and getattr(user, "is_logged_in", False))
    email = ""
    if is_logged_in:
        email = str(getattr(user, "email", "") or user.get("email", "")).strip().lower()

    allowed_domain, admin_emails, allowed_emails = _get_email_lists()
    is_admin = is_logged_in and email in admin_emails
    is_allowed = (
        is_logged_in
        and (
            is_admin
            or email in allowed_emails
            or bool(allowed_domain and email.endswith(f"@{allowed_domain}"))
        )
    )

    role = "Admin" if is_admin else "Viewer" if is_allowed else "Public"
    st.session_state["user_email"] = email
    st.session_state["user_role"] = role
    st.session_state["read_only_mode"] = role != "Admin"
    return role


def is_admin():
    return st.session_state.get("user_role") == "Admin"


def render_account_sidebar():
    """Offer sign-in without preventing visitors from using public pages."""
    role = st.session_state.get("user_role", "Public")
    email = st.session_state.get("user_email", "")

    if email:
        st.sidebar.caption(f"Signed in: {email}")
    if role == "Admin":
        st.sidebar.info("Administrator access")
        st.sidebar.button("Log out", on_click=st.logout, icon=":material/logout:")
    elif email:
        st.sidebar.caption("Public schedule access")
        st.sidebar.button("Log out", on_click=st.logout, icon=":material/logout:")
    else:
        try:
            has_google_provider = "google" in st.secrets.get("auth", {})
        except Exception:
            has_google_provider = False

        if has_google_provider:
            st.sidebar.button(
                "Log in with Google",
                on_click=st.login,
                args=("google",),
                icon=":material/login:",
            )
        else:
            st.sidebar.button(
                "Log in with Google",
                on_click=st.login,
                icon=":material/login:",
            )
