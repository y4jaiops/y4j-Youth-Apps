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
SURVEY_LINK = "https://forms.gle/YOUR_ACTUAL_FORM_ID" 

# 2. LOAD DATA
@st.cache_data(ttl=60)
def load_candidates():
    fid = st.secrets.get("youthscan", {}).get("folder_id")
    url = get_or_create_spreadsheet("YouthScan_Data", fid)
    
    if url:
        data = read_data_from_sheet(url)
        if data:
            df = pd.DataFrame(data)
            # Ensure phone is string in the dataframe
            if 'Phone Number' in df.columns:
                df['Phone Number'] = df['Phone Number'].astype(str).replace('nan', '')
            return df, url
            
    return pd.DataFrame(), url

# Load initial data
df_candidates, sheet_url = load_candidates()

# 3. DASHBOARD INTERFACE
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
        
        # --- THE FIX IS HERE ---
        # We explicitly tell Streamlit: "Render 'Phone Number' as a Text Column, not a Number."
        edited_df = st.data_editor(
            df_display, 
            num_rows="dynamic", 
            use_container_width=True,
            key="profile_editor",
            column_config={
                "Phone Number": st.column_config.TextColumn(
                    "Phone Number",
                    help="Enter phone number (Text allowed)",
                    validate=None # Allows any character
                )
            }
        )

        st.write("")
        if st.button("💾 Save Changes", type="primary"):
            if sheet_url:
                with st.spinner("Syncing to Google Drive..."):
                    if search_term:
                        st.error("⚠️ Safety Lock: Please clear the Search Box before Saving.")
                    else:
                        if overwrite_sheet_with_df(sheet_url, edited_df):
                            st.success("✅ Database Updated!")
                            st.cache_data.clear()
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Save Failed.")
    
    # --- MODE 2: SEND SURVEY ---
    elif action_mode == "Send Survey":
        st.caption("📧 **Survey Mode:** Select a candidate to draft an email with the survey link.")
        
        # We use a dataframe with a selection checkbox
        display_cols = ['First Name', 'Last Name', 'Email', 'Phone Number']
        display_cols = [c for c in display_cols if c in df_display.columns]
        
        event = st.dataframe(
            df_display[display_cols],
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # Logic to handle selection
        if event.selection.rows:
            idx = event.selection.rows[0]
            selected_row = df_display.iloc[idx]
            
            cand_name = selected_row.get('First Name', 'Candidate')
            cand_email = selected_row.get('Email', '')
            
            st.divider()
            st.subheader(f"📨 Contact: {cand_name}")
            
            if not cand_email or "@" not in str(cand_email):
                st.error(f"❌ No valid email found for {cand_name}.")
            else:
                subject = f"Feedback Request: Youth4Jobs Survey"
                body = f"""Hi {cand_name},

We are updating our records at Youth4Jobs and would love your input.
Please take 2 minutes to fill out this survey:

{SURVEY_LINK}

Thank you!
Youth4Jobs Team"""
                
                params = urllib.parse.urlencode({'subject': subject, 'body': body})
                mailto_link = f"mailto:{cand_email}?{params}"
                
                st.markdown(f"**To:** `{cand_email}`")
                st.info("Click the button below to open your email app.")
                st.link_button("📤 Open Draft Email", mailto_link, type="primary")
