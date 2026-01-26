import streamlit as st
from logic.style_manager import set_app_theme
from logic.auth_user import login_required

# 1. SETUP
st.set_page_config(page_title="Y4J AiOps Ecosystem", page_icon="🚀", layout="centered")

# Custom CSS for the "Launchpad" look
st.markdown("""
<style>
    .big-btn {
        width: 100%;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 10px;
        text-decoration: none;
        color: white !important;
        font-weight: bold;
        font-size: 20px;
        display: block;
        transition: transform 0.2s;
    }
    .big-btn:hover {
        transform: scale(1.02);
        opacity: 0.9;
    }
    .btn-orange { background-color: #ff4b4b; }
    .btn-green { background-color: #09ab3b; }
    .btn-blue { background-color: #2b7af0; }
    .btn-red { background-color: #e03195; }
</style>
""", unsafe_allow_html=True)

# 2. LOGIN (Central Gatekeeper)
# We re-use your auth logic so the home page is also secure
user = login_required()

st.title("🚀 Y4J AiOps Ecosystem")
st.write(f"Welcome back, **{user['name']}**. Select a module to begin:")
st.divider()

# 3. THE LAUNCHPAD
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <a href="https://y4j-youthscan.streamlit.app" target="_blank" class="big-btn btn-orange">
        🟠 YouthScan<br><span style='font-size:14px; font-weight:normal'>Digitize Candidates</span>
    </a>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <a href="https://y4j-youthprofile.streamlit.app" target="_blank" class="big-btn btn-blue">
        🔵 YouthProfile<br><span style='font-size:14px; font-weight:normal'>Manage Database</span>
    </a>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <a href="https://y4j-youthjobs.streamlit.app" target="_blank" class="big-btn btn-green">
        🟢 YouthJobs<br><span style='font-size:14px; font-weight:normal'>Digitize JDs</span>
    </a>
    """, unsafe_allow_html=True)

    st.markdown("""
    <a href="https://y4j-youthmatch.streamlit.app" target="_blank" class="big-btn btn-red">
        🔴 YouthMatch<br><span style='font-size:14px; font-weight:normal'>AI Recruiter</span>
    </a>
    """, unsafe_allow_html=True)

st.divider()
st.caption("Youth4Jobs Foundation | Powered by Gemini AI & Google Drive")
