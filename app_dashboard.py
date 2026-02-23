import streamlit as st
import pandas as pd
import time

# 1. Custom Module Imports & Setup
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_sheets import (
    init_google_sheet_client, 
    get_or_create_spreadsheet, 
    overwrite_sheet_with_df,
    with_exponential_backoff
)

# Initialize Theme and User Auth
set_app_theme("admin")
user = login_required()

# 2. Admin Authorization
ADMIN_EMAILS = ["shivasawant@gmail.com"]

if user.get("email") not in ADMIN_EMAILS:
    st.error("Access Denied")
    st.warning("You do not have administrator privileges to view the Y4J Admin Dashboard.")
    st.stop()

# Helper Function for Visual and Audio Feedback
def trigger_success_feedback():
    """Triggers the balloons animation and plays the success chime."""
    st.balloons()
    try:
        st.audio("koiroylers-awesome-notification-351720.mp3", autoplay=True)
    except Exception:
        pass

# 3. Data Syncing Function
@with_exponential_backoff(max_retries=5)
def sync_volunteer_data(file_prefix, secret_key):
    """
    Scans the specified Google Drive folder for files matching the prefix,
    extracts records, and appends the volunteer's email to a new column.
    """
    client = init_google_sheet_client()
    
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
                sheet = client.open_by_key(file_id).sheet1
                records = sheet.get_all_records()
                
                volunteer_email = file_name.replace(file_prefix, "").strip()
                
                for row in records:
                    row["Scanned By"] = volunteer_email
                    
                all_records.extend(records)
            
            progress_bar.progress((i + 1) / total_files)
            
        progress_bar.empty()
        
    return pd.DataFrame(all_records)

# 4. Dashboard UI Layout & State Management
if "youthscan_df" not in st.session_state:
    st.session_state["youthscan_df"] = pd.DataFrame()
if "jobscan_df" not in st.session_state:
    st.session_state["jobscan_df"] = pd.DataFrame()

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
            try:
                st.session_state["youthscan_df"] = sync_volunteer_data("YouthScan_", "youthscan")
                st.rerun()
            except Exception as e:
                st.error(f"Sync failed after retries: {e}")

    df_youth = st.session_state["youthscan_df"]
    
    if not df_youth.empty:
        filtered_youth = apply_volunteer_filter(df_youth)
        
        total_candidates = len(filtered_youth)
        active_volunteers = filtered_youth["Scanned By"].nunique() if "Scanned By" in filtered_youth.columns else 0
        disability_count = len(filtered_youth[filtered_youth["Disability Type"] != "N/A"]) if "Disability Type" in filtered_youth.columns else 0

        st.markdown("### YouthScan Metrics")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Candidates", total_candidates)
        m2.metric("Active Volunteers", active_volunteers)
        m3.metric("Profiles w/ Disability Data", disability_count)
        
        st.dataframe(filtered_youth, use_container_width=True)
        
        current_date = time.strftime("%Y-%m-%d")
        csv_youth = filtered_youth.to_csv(index=False).encode('utf-8')
        
        col_dl_youth, col_save_youth = st.columns(2)
        
        with col_dl_youth:
            youth_dl_clicked = st.download_button(
                label="Download YouthScan CSV",
                data=csv_youth,
                file_name=f"YouthScan_Filtered_Roster_{current_date}.csv",
                mime="text/csv",
                key="dl_youthscan_csv",
                use_container_width=True
            )
            if youth_dl_clicked:
                trigger_success_feedback()
            
        with col_save_youth:
            if st.button("💾 Save to Google Drive", key="save_drive_youth", use_container_width=True):
                roster_fid = st.secrets.get("youthscan", {}).get("roster_folder_id")
                if not roster_fid:
                    st.error("Roster folder ID missing in st.secrets for 'youthscan'.")
                else:
                    with st.spinner("Saving YouthScan Master Roster to Google Drive..."):
                        try:
                            sheet_name = f"YouthScan_Master_Roster_{current_date}"
                            url = get_or_create_spreadsheet(sheet_name, roster_fid)
                            overwrite_sheet_with_df(url, filtered_youth)
                            st.success(f"Successfully saved **{sheet_name}** to Google Drive!")
                            trigger_success_feedback()
                            time.sleep(2.5)
                        except Exception as e:
                            st.error(f"Failed to save to Drive after retries: {e}")
    else:
        st.info("No YouthScan data loaded. Click 'Sync YouthScan Data' to fetch from Drive.")

# --- JOBSCAN TAB ---
with tab_job:
    col_sync_job, _ = st.columns([1, 4])
    with col_sync_job:
        if st.button("Sync JobScan Data", key="sync_jobscan", use_container_width=True):
            try:
                st.session_state["jobscan_df"] = sync_volunteer_data("JobScan_", "jobscan")
                st.rerun()
            except Exception as e:
                st.error(f"Sync failed after retries: {e}")

    df_job = st.session_state["jobscan_df"]
    
    if not df_job.empty:
        filtered_job = apply_volunteer_filter(df_job)
        
        total_jobs = len(filtered_job)
        active_job_volunteers = filtered_job["Scanned By"].nunique() if "Scanned By" in filtered_job.columns else 0

        st.markdown("### JobScan Metrics")
        m1, m2 = st.columns(2)
        m1.metric("Total Jobs", total_jobs)
        m2.metric("Active Volunteers", active_job_volunteers)
        
        st.dataframe(filtered_job, use_container_width=True)
        
        current_date = time.strftime("%Y-%m-%d")
        csv_job = filtered_job.to_csv(index=False).encode('utf-8')
        
        col_dl_job, col_save_job = st.columns(2)
        
        with col_dl_job:
            job_dl_clicked = st.download_button(
                label="Download JobScan CSV",
                data=csv_job,
                file_name=f"JobScan_Filtered_Roster_{current_date}.csv",
                mime="text/csv",
                key="dl_jobscan_csv",
                use_container_width=True
            )
            if job_dl_clicked:
                trigger_success_feedback()
            
        with col_save_job:
            if st.button("💾 Save to Google Drive", key="save_drive_job", use_container_width=True):
                roster_fid = st.secrets.get("jobscan", {}).get("roster_folder_id")
                if not roster_fid:
                    st.error("Roster folder ID missing in st.secrets for 'jobscan'.")
                else:
                    with st.spinner("Saving JobScan Master Roster to Google Drive..."):
                        try:
                            sheet_name = f"JobScan_Master_Roster_{current_date}"
                            url = get_or_create_spreadsheet(sheet_name, roster_fid)
                            overwrite_sheet_with_df(url, filtered_job)
                            st.success(f"Successfully saved **{sheet_name}** to Google Drive!")
                            trigger_success_feedback()
                            time.sleep(2.5)
                        except Exception as e:
                            st.error(f"Failed to save to Drive after retries: {e}")
    else:
        st.info("No JobScan data loaded. Click 'Sync JobScan Data' to fetch from Drive.")
