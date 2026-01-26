import streamlit as st
import pandas as pd
import time
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_sheets import get_or_create_spreadsheet, read_data_from_sheet, overwrite_sheet_with_df

# 1. SETUP
set_app_theme("profile") # 🔵 Blue Vibe
user = login_required()

st.title("🔵 YouthProfile Manager")
st.write(f"Logged in as: **{user['name']}**")

# 2. LOAD DATA
@st.cache_data(ttl=60) # Cache for speed, expire every 60s
def load_candidates():
    fid = st.secrets.get("youthscan", {}).get("folder_id")
    url = get_or_create_spreadsheet("YouthScan_Data", fid)
    
    if url:
        data = read_data_from_sheet(url)
        if data:
            return pd.DataFrame(data), url
            
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
    
    # Count unique locations if 'State' exists
    if 'State' in df_candidates.columns:
        col2.metric("Locations covered", df_candidates['State'].nunique())
    
    # Count specific disability types if exists
    if 'Disability Type' in df_candidates.columns:
        col3.metric("Disability Types", df_candidates['Disability Type'].nunique())

    st.divider()

    # B. SEARCH & FILTER
    search_term = st.text_input("🔍 Search Candidates (Name, Location, Skills...)", "")

    # C. EDITABLE GRID
    st.subheader("📝 Edit Database")
    st.caption("Double-click any cell to edit. Click 'Save Changes' when done.")

    # Apply Search Filter (Visual only - we edit the full DF usually, but here we edit the view)
    # NOTE: For simple editing, we edit the FULL dataframe to ensure row indexes match.
    # If search is active, we just highlight; or we can filter. 
    # To keep it safe: We display the DATA EDITOR.
    
    if search_term:
        # Simple string matching across all columns
        mask = df_candidates.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
        df_display = df_candidates[mask]
    else:
        df_display = df_candidates

    # THE MAGIC WIDGET: Data Editor
    # num_rows="dynamic" allows you to ADD or DELETE rows!
    edited_df = st.data_editor(
        df_display, 
        num_rows="dynamic", 
        use_container_width=True,
        key="profile_editor"
    )

    # 4. SAVE LOGIC
    st.write("")
    col_l, col_r = st.columns([4, 1])
    
    with col_r:
        if st.button("💾 Save Changes", type="primary"):
            if sheet_url:
                with st.spinner("Syncing to Google Drive..."):
                    # We need to be careful: If we filtered the view, we shouldn't overwrite the whole DB 
                    # with just the filtered view.
                    
                    if search_term:
                        st.error("⚠️ Safety Lock: Please clear the Search Box before Saving to prevent data loss.")
                    else:
                        # Save the FULL edited dataframe
                        if overwrite_sheet_with_df(sheet_url, edited_df):
                            st.success("✅ Database Updated!")
                            st.cache_data.clear() # Clear cache so next reload gets fresh data
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Save Failed.")
            else:
                st.error("Database URL not found.")
