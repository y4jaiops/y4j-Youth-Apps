# (The Vibe Manager) Handles the colors and icons for the 5 apps.
import streamlit as st

THEMES = {
    "youthscan": {"color": "#FFA500", "icon": "📸", "title": "YouthScan"},  # Orange
    "youthcomm": {"color": "#800080", "icon": "🎓", "title": "YouthComm"},  # Purple
    "jobscan": {"color": "#228B22", "icon": "💼", "title": "JobScan"},      # Green
    "jobcomm": {"color": "#1E90FF", "icon": "🗂️", "title": "JobComm"},      # Blue
    "y4jmatch": {"color": "#FF00FF", "icon": "🤝", "title": "Y4J-Match"},      # Magenta
}

def set_app_theme(app_code):
    """Applies the specific vibe (Icon, Title, Color) for the app."""
    theme = THEMES.get(app_code)
    if not theme: return

    st.set_page_config(page_title=f"Y4J {theme['title']}", page_icon=theme['icon'], layout="wide")
    
    # Custom CSS for the colored header line
    st.markdown(f"""
        <style>
        .stAppHeader {{ background-color: {theme['color']}; }}
        h1 {{ color: {theme['color']}; }}
        </style>
        """, unsafe_allow_html=True)
    
    st.title(f"{theme['icon']} {theme['title']}")
