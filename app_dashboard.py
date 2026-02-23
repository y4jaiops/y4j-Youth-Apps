import streamlit as st
import pandas as pd

# 1. Custom Module Imports & Setup
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_sheets import init_google_sheet_client

# Initialize Theme and User Auth
set_app_theme("admin")
user = login_required()

# 2. Admin Authorization
ADMIN_EMAILS = ["shivasawant@gmail.com"]

if user.get("email") not in ADMIN_EMAILS:
    st.error("Access Denied")
    st.warning("You do not have administrator privileges to view the Y4J Admin Dashboard.")
    st.stop()

# 3. Data Syncing Function
def sync_volunteer_data(file_prefix, secret_key):
    """
    Scans the specified Google Drive folder for files matching the prefix,
    extracts records, and appends the volunteer's email to a new column.
    """
    client = init_google_sheet_client()
    
    # Dynamically fetch the correct folder ID based on the passed secret_key
    folder_id = st.secrets.get(secret_key, {}).get("folder_id")
    
    if not folder_id:
        st.error(f"Drive folder ID is missing from st.secrets for [{secret_key}].")
        return pd.DataFrame()

    all_records = []
    
    with st.spinner(f"Scanning Drive for {file_prefix} files..."):
        try:
            query = f"'{folder_id}' in parents and name contains '{file_prefix}' and trashed=false"
            files = client.list_files_by_query(query) 
        except AttributeError:
            st.warning("Using fallback file listing. Ensure your client supports Drive queries.")
            files = client.list_spreadsheet_files(title=file_prefix)

        total_files = len(files)
        if total_files == 0:
            st.info(f"No files found starting with '{file_prefix}'.")
            return pd.DataFrame()

        progress_bar = st.progress(0)
        
        for i, file_meta in enumerate(files):
            file_name = file_meta.get("name", "")
            file_id = file_meta.get("id")
            
            if file_name.startswith(file_prefix):
                try:
                    sheet = client.open_by_key(file_id).sheet1
                    records = sheet.get_all_records()
                    
                    volunteer_email = file_name.replace(file_prefix, "").strip()
                    
                    for row in records:
                        row["Scanned By"] = volunteer_email
                        
                    all_records.extend(records)
                except Exception as e:
                    st.error(f"Failed to read {file_name}: {e}")
            
            progress_bar.progress((i + 1) / total_files)
            
        progress_bar.empty()
        
    return pd.DataFrame(all_records)


# 4. Dashboard UI Layout & State Management
if "youthscan_df" not in st.session_state:
    st.session_state["youthscan_df"] = pd.DataFrame()
if "jobscan_df" not in st.session_state:
    st.session_state["jobscan_df"] = pd.DataFrame()

# Combine unique volunteers from both datasets to populate the dynamic filter
youth_vols = set(st.session_state["youthscan_df"].get("Scanned By", [])) if not st.session_state["youthscan_df"].empty else set()
job_vols = set(st.session_state["jobscan_df"].get("Scanned By", [])) if not st.session_state["jobscan_df"].empty else set()
all_volunteers = sorted(list(youth_vols.union(job_vols)))

# Sidebar
st.sidebar.header("Filter Options")
selected_volunteers = st.sidebar.multiselect(
    "Filter by Volunteer (Scanned By)",
    options=all_volunteers
)

def apply_volunteer_filter(df):
    """Filters the dataframe based on sidebar multiselect."""
    if df.empty:
        return df
    if selected_volunteers:
        return df[df["Scanned By"].isin(selected_volunteers)]
    return df

# Create Tabs
tab_youth, tab_job = st.tabs(["📋 YouthScan Roster", "💼 JobScan Roster"])

# 5. Tab Contents

# --- YOUTHSCAN TAB ---
with tab_youth:
    col_sync, _ = st.columns([1, 4])
    with col_sync:
        if st.button("Sync YouthScan Data", key="sync_youthscan", use_container_width=True):
            st.session_state["youthscan_df"] = sync_volunteer_data("YouthScan_")
            st.rerun()

    df_youth = st.session_state["youthscan_df"]
    
    if not df_youth.empty:
        filtered_youth = apply_volunteer_filter(df_youth)
        
        # Calculate Metrics
        total_candidates = len(filtered_youth)
        active_volunteers = filtered_youth["Scanned By"].nunique() if "Scanned By" in filtered_youth.columns else 0
        
        if "Disability Type" in filtered_youth.columns:
            disability_count = len(filtered_youth[filtered_youth["Disability Type"] != "N/A"])
        else:
            disability_count = 0

        # Display Metrics
        st.markdown("### YouthScan Metrics")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Candidates", total_candidates)
        m2.metric("Active Volunteers", active_volunteers)
        m3.metric("Profiles w/ Disability Data", disability_count)
        
        # Dataframe & Download
        st.dataframe(filtered_youth, use_container_width=True)
        
        csv_youth = filtered_youth.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download YouthScan CSV",
            data=csv_youth,
            file_name="YouthScan_Filtered_Roster.csv",
            mime="text/csv",
            key="dl_youthscan_csv"
        )
    else:
        st.info("No YouthScan data loaded. Click 'Sync YouthScan Data' to fetch from Drive.")

# --- JOBSCAN TAB ---
with tab_job:
    col_sync_job, _ = st.columns([1, 4])
    with col_sync_job:
        if st.button("Sync JobScan Data", key="sync_jobscan", use_container_width=True):
            st.session_state["jobscan_df"] = sync_volunteer_data("JobScan_")
            st.rerun()

    df_job = st.session_state["jobscan_df"]
    
    if not df_job.empty:
        filtered_job = apply_volunteer_filter(df_job)
        
        # Calculate Metrics
        total_jobs = len(filtered_job)
        active_job_volunteers = filtered_job["Scanned By"].nunique() if "Scanned By" in filtered_job.columns else 0

        # Display Metrics
        st.markdown("### JobScan Metrics")
        m1, m2 = st.columns(2)
        m1.metric("Total Jobs", total_jobs)
        m2.metric("Active Volunteers", active_job_volunteers)
        
        # Dataframe & Download
        st.dataframe(filtered_job, use_container_width=True)
        
        csv_job = filtered_job.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download JobScan CSV",
            data=csv_job,
            file_name="JobScan_Filtered_Roster.csv",
            mime="text/csv",
            key="dl_jobscan_csv"
        )
    else:
        st.info("No JobScan data loaded. Click 'Sync JobScan Data' to fetch from Drive.")
