import streamlit as st
import pandas as pd
import time
import urllib.parse
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_sheets import get_or_create_spreadsheet, read_data_from_sheet, overwrite_sheet_with_df

# 1. SETUP
set_app_theme("profile") # 🔵 Blue Vibe
user = login_required()

st.title("🔵 YouthProfile Manager")
st.write(f"Logged in as: **{user['name']}**")

# --- CONFIGURATION ---
# Replace this with your actual Google Form link
SURVEY_LINK = "https://forms.gle/YOUR_ACTUAL_FORM_ID" 

# 2. HELPER FUNCTIONS
def clean_phone_number(phone_raw):
    """
    Cleans phone number for WhatsApp URL.
    Removes dashes, spaces, brackets. Ensures country code (defaults to India +91).
    """
    if pd.isna(phone_raw): return None
    
    # Remove non-digit characters
    clean = ''.join(filter(str.isdigit, str(phone_raw)))
    
    if not clean: return None
    
    # Append country code if it looks like a 10-digit Indian number
    if len(clean) == 10:
        return "91" + clean
        
    return clean

# 3. LOAD DATA
@st.cache_data(ttl=60)
def load_candidates():
    fid = st.secrets.get("youthscan", {}).get("folder_id")
    url = get_or_create_spreadsheet("YouthScan_Data", fid)
    
    if url:
        data = read_data_from_sheet(url)
        if data:
            df = pd.DataFrame(data)
            
            # --- THE FIX: FORCE PHONE NUMBER TO STRING ---
            if 'Phone Number' in df.columns:
                df['Phone Number'] = df['Phone Number'].astype(str).replace('nan', '')
                
            return df, url
            
    return pd.DataFrame(), url

# Load initial data
df_candidates, sheet_url = load_candidates()

# 4. DASHBOARD INTERFACE
if df_candidates.empty:
    st.warning("⚠️ No candidates found. Use 'YouthScan' to add people.")
else:
    # A. METRICS
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Candidates", len(df_candidates))
    if 'State' in df_candidates.columns:
        col2.metric("Locations", df_candidates['State'].nunique())
    if 'Disability Type' in df_candidates.columns:
        col3.metric("Disability Types", df_candidates['Disability Type'].nunique())

    st.divider()

    # B. SEARCH & ACTION
    col_search, col_action = st.columns([3, 1])
    with col_search:
        search_term = st.text_input("🔍 Search Candidates", "")
    with col_action:
        # Action Mode Toggle
        action_mode = st.radio("Mode:", ["Edit Data", "Send Survey"], horizontal=True)

    # C. DATA DISPLAY
    if search_term:
        mask = df_candidates.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
        df_display = df_candidates[mask].copy()
    else:
        df_display = df_candidates.copy()

    # --- MODE 1: EDIT DATA ---
    if action_mode == "Edit Data":
        st.caption("📝 **Edit Mode:** Double-click cells to fix typos. Click Save below.")
        
        edited_df = st.data_editor(
            df_display, 
            num_rows="dynamic", 
            use_container_width=True,
            key="profile_editor"
        )

        st.write("")
        if st.button("💾 Save Changes", type="primary"):
            if sheet_url:
                with st.spinner("Syncing to Google Drive..."):
                    # THIS IS WHERE THE ERROR WAS (Fixed variable name)
                    if search_term:
                        st.error("⚠️ Safety Lock: Please clear the Search Box before Saving.")
                    else
