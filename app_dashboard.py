import streamlit as st
import pandas as pd
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_sheets import init_google_sheet_client

# 1. SETUP
set_app_theme("admin")
user = login_required()

st.title("📊 Y4J Admin Dashboard")
st.write(f"Welcome back, **{user['name']}**. Here is your master view of all volunteer data.")

# --- SESSION STATE ---
if "master_df" not in st.session_state:
    st.session_state["master_df"] = None

# 2. DATA AGGREGATION LOGIC
def sync_all_volunteer_data():
    client = init_google_sheet_client()
    if not client:
        st.error("❌ Failed to connect to Google Sheets.")
        return None
        
    fid = st.secrets.get("youthscan", {}).get("folder_id")
    
    with st.spinner("Scanning Drive for volunteer sheets..."):
        try:
            # Fetch all spreadsheets in the target folder
            all_files = client.list_spreadsheet_files(folder_id=fid)
            
            # Filter to only grab the YouthScan files we dynamically named
            y4j_files = [f for f in all_files if f.get('name', '').startswith("YouthScan_")]
            
            if not y4j_files:
                st.warning("No volunteer sheets found in the Y4J folder.")
                return None
                
            all_records = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Loop through each volunteer's sheet and pull the data
            for i, file_meta in enumerate(y4j_files):
                status_text.text(f"Syncing: {file_meta['name']}...")
                try:
                    # Open the specific sheet by its ID for safety
                    sh = client.open_by_key(file_meta['id'])
                    # Assuming data is on the first sheet
                    worksheet = sh.sheet1
                    
                    # get_all_records() automatically handles headers and converts to dicts
                    records = worksheet.get_all_records()
                    
                    # Inject the volunteer email into the record so you know who scanned it!
                    volunteer_email = file_meta['name'].replace("YouthScan_", "")
                    for r in records:
                        r["Scanned By"] = volunteer_email
                        all_records.append(r)
                        
                except Exception as e:
                    st.error(f"Could not read {file_meta['name']}: {e}")
                    
                progress_bar.progress((i + 1) / len(y4j_files))
                
            status_text.text("✅ Sync complete!")
            progress_bar.empty()
            
            if all_records:
                return pd.DataFrame(all_records)
            else:
                return None
                
        except Exception as e:
            st.error(f"❌ Error communicating with Google Drive: {e}")
            return None

# 3. DASHBOARD UI
col1, col2 = st.columns([3, 1])

with col1:
    st.markdown("Click the button to pull the latest candidate data from all volunteer sheets.")
with col2:
    if st.button("🔄 Sync Master Data", type="primary"):
        st.session_state["master_df"] = sync_all_volunteer_data()

# 4. METRICS & DISPLAY
if st.session_state["master_df"] is not None:
    df = st.session_state["master_df"]
    
    st.divider()
    
    # Calculate top-level metrics
    total_candidates = len(df)
    unique_volunteers = df["Scanned By"].nunique() if "Scanned By" in df.columns else 0
    
    # Accessible Metric Cards
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Candidates Scanned", total_candidates)
    m2.metric("Active Volunteers", unique_volunteers)
    
    # A dynamic metric if the column exists
    if "Disability Type" in df.columns:
        reported_disabilities = len(df[df["Disability Type"].str.strip() != "N/A"])
        m3.metric("Profiles w/ Disability Data", reported_disabilities)
    else:
        m3.metric("Status", "Up to Date")

    st.divider()
    st.subheader("Master Candidate Roster")
    
    # Display the interactive dataframe
    st.dataframe(df, use_container_width=True)
    
    # 5. EXPORT FUNCTIONALITY
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Master CSV",
        data=csv,
        file_name='Y4J_Master_Roster.csv',
        mime='text/csv',
    )
