# Handles Login/Logout common to all apps.

import streamlit as st
import os
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# Allow OAuth over Http for Cloud environments
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

def _get_auth_flow():
    if "auth" not in st.secrets:
        st.error("❌ Missing [auth] section in secrets.")
        st.stop()
    
    auth_specs = st.secrets["auth"]
    
    return Flow.from_client_config(
        {
            "web": {
                "client_id": auth_specs["client_id"],
                "client_secret": auth_specs["client_secret"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [auth_specs["redirect_uri"]],
            }
        },
        scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile"
        ],
        redirect_uri=auth_specs["redirect_uri"]
    )

def login_required():
    """Returns user dict if logged in; Stops app if not."""
    if "credentials" in st.session_state:
        with st.sidebar:
            st.divider()
            user = st.session_state.get("user_info", {"name": "User", "email": "..."})
            st.caption(f"Logged in as: {user.get('email')}")
            if st.button("🚪 Logout"):
                for key in list(st.session_state.keys()): del st.session_state[key]
                st.rerun()
        return user

    if "code" in st.query_params:
        try:
            code = st.query_params["code"]
            flow = _get_auth_flow()
            flow.fetch_token(code=code)
            st.session_state["credentials"] = flow.credentials
            service = build('oauth2', 'v2', credentials=flow.credentials)
            st.session_state["user_info"] = service.userinfo().get().execute()
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Login failed: {e}")
            st.stop()

    st.info("🔒 Please log in to access Y4J Tools.")
    flow = _get_auth_flow()
    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
    st.link_button("Login with Google", auth_url, type="primary")
    st.stop()
