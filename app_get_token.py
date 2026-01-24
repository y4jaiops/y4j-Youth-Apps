# The Refresh Token (The Access Key) Source: Your Custom Token Generator App

import streamlit as st
from google_auth_oauthlib.flow import Flow

# 1. PASTE YOUR CREDENTIALS HERE DIRECTLY FOR THIS ONE-TIME RUN
CLIENT_ID = "700839813540-v7fmmrufkg3be50vglndo81tjb422kdj.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REDIRECT_URI = "y4j-token-gen.streamlit" # Use the URL of an existing deployed app for simplicity, or the temp one.

# Scopes needed
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]

st.title("🔑 Refresh Token Generator")

if "code" not in st.query_params:
    # 2. Start Auth Flow
    flow = Flow.from_client_config(
        {"web": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token"}},
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
    st.link_button("Login as y4jaiops@gmail.com", auth_url)
else:
    # 3. Exchange Code for Token
    code = st.query_params["code"]
    flow = Flow.from_client_config(
        {"web": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token"}},
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(code=code)
    st.success("✅ Success! Copy this token:")
    st.code(flow.credentials.refresh_token)
