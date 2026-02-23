import streamlit as st
import pandas as pd
import json
import urllib.parse
import google.generativeai as genai
import re

# --- IMPORTS FROM YOUR LOGIC MODULES ---
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_sheets import get_or_create_spreadsheet, read_data_from_sheet
from logic.logic_gemini import GEMINI_MODEL_NAME

# 1. SETUP
set_app_theme("y4jmatch") # 🔴 Red/Magenta Vibe
user = login_required()
genai.configure(api_key=st.secrets["gemini"]["api_key"])

st.write(f"👋 Hi **{user['name']}**! Let's match candidates and jobs.")

# Initialize session state variables to hold our data
if 'df_candidates' not in st.session_state:
    st.session_state.df_candidates = pd.DataFrame()
if 'df_jobs' not in st.session_state:
    st.session_state.df_jobs = pd.DataFrame()

# 2. CONFIGURE & LOAD DATABASES (SUPPLY & DEMAND)
st.subheader("📂 Data Sources")
st.write("Confirm or edit the Google Sheets names to load data from:")

v_email = user.get("email", "volunteer")
default_cand_sheet = f"YouthScan_{v_email}"
default_job_sheet = f"JobScan_{v_email}"

@st.cache_data(ttl=60, show_spinner=False)
def load_data(c_sheet, j_sheet):
    scan_fid = st.secrets.get("youthscan", {}).get("folder_id")
    scan_url = get_or_create_spreadsheet(c_sheet, scan_fid)
    df_c = pd.DataFrame(read_data_from_sheet(scan_url)) if scan_url else pd.DataFrame()
    
    jobs_fid = st.secrets.get("jobscan", {}).get("folder_id")
    jobs_url = get_or_create_spreadsheet(j_sheet, jobs_fid)
    df_j = pd.DataFrame(read_data_from_sheet(jobs_url)) if jobs_url else pd.DataFrame()
    
    return df_c, df_j

with st.form("sheet_names_form"):
    col_src1, col_src2 = st.columns(2)
    with col_src1:
        cand_sheet_name = st.text_input("Candidate Sheet Name", value=default_cand_sheet)
    with col_src2:
        job_sheet_name = st.text_input("Job Sheet Name", value=default_job_sheet)
    
    submit_sheets = st.form_submit_button("Fetch Data")

if submit_sheets:
    with st.spinner(f"Syncing databases from '{cand_sheet_name}' & '{job_sheet_name}'..."):
        fetched_c, fetched_j = load_data(cand_sheet_name, job_sheet_name)
        st.session_state.df_candidates = fetched_c
        st.session_state.df_jobs = fetched_j
        st.success(f"✅ Loaded **{len(fetched_c)}** candidates and **{len(fetched_j)}** jobs.")

df_candidates = st.session_state.df_candidates
df_jobs = st.session_state.df_jobs

if df_candidates.empty or df_jobs.empty:
    st.info("👆 Please verify the sheet names above and click 'Fetch Data' to begin.")
    st.stop()

# Helper function to clean phone numbers for WhatsApp
def clean_phone(phone_str):
    if not phone_str or pd.isna(phone_str):
        return ""
    # Strip everything except digits
    digits = re.sub(r'\D', '', str(phone_str))
    # Prepend India country code if it looks like a standard 10-digit number without one
    if len(digits) == 10:
        return f"91{digits}"
    return digits

# 3. SELECT MATCHING CRITERIA
st.markdown("---")
st.subheader("⚙️ Matching Criteria")
match_mode = st.radio(
    "How would you like to run the matching?",
    options=["Match per Candidate (Find Jobs)", "Match per Job (Find Candidates)"],
    horizontal=True
)
st.markdown("---")

# 4. MATCHING INTERFACE
col_left, col_right = st.columns([1, 2])

# ==========================================
# MODE 1: MATCH PER CANDIDATE
# ==========================================
if match_mode == "Match per Candidate (Find Jobs)":
    with col_left:
        st.subheader("👤 Candidate")
        c_list = df_candidates.apply(lambda x: f"{x.get('First Name','')} {x.get('Last Name','')}", axis=1)
        selected_name = st.selectbox("Select Youth", c_list)
        
        idx = c_list[c_list == selected_name].index[0]
        profile = df_candidates.iloc[idx]
        
        st.info(f"""
        **🎓 Edu:** {profile.get('Education')}  
        **📍 Loc:** {profile.get('State')}  
        **♿ Type:** {profile.get('Disability Type')}  
        **🛠 Skills:** {profile.get('Skills', 'N/A')}
        """)
        
        cand_email = profile.get('Email', '')
        cand_phone = clean_phone(profile.get('Phone', profile.get('Phone Number', '')))
        
        st.caption(f"📧 {cand_email if cand_email else 'No email'}")
        st.caption(f"📱 {cand_phone if cand_phone else 'No phone'}")

    with col_right:
        st.subheader("🎯 Job Recommendations")
        filter_loc = st.checkbox("Filter by Location Match?", value=True)
        
        if filter_loc:
            loc = str(profile.get('State', '')).strip()
            jobs_pool = df_jobs[df_jobs['Location'].astype(str).str.contains(loc, case=False, na=False)]
        else:
            jobs_pool = df_jobs
            
        st.write(f"**Available Pool:** {len(jobs_pool)} Jobs")

        if st.button("🚀 Run AI Matcher", type="primary"):
            if jobs_pool.empty:
                st.error("No jobs found in this location.")
            else:
                with st.spinner(f"Gemini ({GEMINI_MODEL_NAME}) is looking for jobs for {selected_name}..."):
                   # jobs_json = jobs_pool[['Job Title', 'Company Name', 'Required Skills', 'Min Experience']].to_json(orient='records')
                    # Safely filter only the columns that actually exist in the job sheet
                    desired_job_cols = ['Job Title', 'Company Name', 'Required Skills', 'Min Experience']
                    available_job_cols = [col for col in desired_job_cols if col in jobs_pool.columns]
                    jobs_json = jobs_pool[available_job_cols].to_json(orient='records')
                    profile_str = json.dumps(profile.to_dict())
                    
                    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
                    prompt = f"""
                    Act as a Disability Placement Officer.
                    CANDIDATE: {profile_str}
                    OPEN JOBS: {jobs_json}
                    
                    TASK: Rank the Top 3 most suitable jobs based on skills, education, and disability accommodation needs.
                    Output ONLY a JSON list: [{{"title": "...", "company": "...", "score": 90, "reason": "..."}}]
                    """
                    
                    try:
                        response = model.generate_content(prompt)
                        clean_json = response.text.replace("```json", "").replace("```", "").strip()
                        matches = json.loads(clean_json)
                        
                        # Build aggregated message
                        msg_subject = "New Job Matches from Youth4Jobs!"
                        msg_body = f"Hi {profile.get('First Name')},\n\nWe found some exciting job matches for you based on your profile!\n\n"
                        
                        for m in matches:
                            score = m.get('score', 0)
                            color_emoji = "🟢" if score >= 80 else "🟠" if score >= 50 else "🔴"
                            with st.expander(f"{color_emoji} {m.get('title')} @ {m.get('company')} ({score}%)", expanded=True):
                                st.write(f"_{m.get('reason')}_")
                                st.progress(score / 100)
                            
                            msg_body += f"🔹 Role: {m.get('title')} at {m.get('company')}\n"
                            msg_body += f"   Why it fits: {m.get('reason')}\n\n"
                            
                        msg_body += "Would you like to apply to any of these?\n\nBest,\nYouth4Jobs Placement Team"
                        
                        st.markdown("### 📤 Send Matches to Candidate")
                        col_btn1, col_btn2 = st.columns(2)
                        
                        with col_btn1:
                            if cand_email:
                                params = urllib.parse.urlencode({'subject': msg_subject, 'body': msg_body})
                                st.link_button("📧 Email Candidate", f"mailto:{cand_email}?{params}", use_container_width=True)
                            else:
                                st.button("📧 Email Candidate (No Email)", disabled=True, use_container_width=True)
                                
                        with col_btn2:
                            if cand_phone:
                                wa_text = urllib.parse.quote(msg_body)
                                st.link_button("💬 WhatsApp Candidate", f"https://wa.me/{cand_phone}?text={wa_text}", type="primary", use_container_width=True)
                            else:
                                st.button("💬 WhatsApp Candidate (No Phone)", disabled=True, use_container_width=True)

                    except Exception as e:
                        st.error(f"AI Error: {e}")

# ==========================================
# MODE 2: MATCH PER JOB
# ==========================================
else:
    with col_left:
        st.subheader("🏢 Job")
        j_list = df_jobs.apply(lambda x: f"{x.get('Job Title','')} @ {x.get('Company Name','')}", axis=1)
        selected_job = st.selectbox("Select Job Vacancy", j_list)
        
        idx = j_list[j_list == selected_job].index[0]
        job_profile = df_jobs.iloc[idx]
        
        st.info(f"""
        **🏢 Company:** {job_profile.get('Company Name')}  
        **📍 Loc:** {job_profile.get('Location')}  
        **🛠 Req Skills:** {job_profile.get('Required Skills')}  
        **⏳ Min Exp:** {job_profile.get('Min Experience', '0')}
        """)
        
        emp_email = job_profile.get('Contact Email', '')
        emp_phone = clean_phone(job_profile.get('Contact Phone', ''))
        
        st.caption(f"📧 {emp_email if emp_email else 'No email'}")
        st.caption(f"📱 {emp_phone if emp_phone else 'No phone'}")

    with col_right:
        st.subheader("🎯 Candidate Recommendations")
        filter_loc_job = st.checkbox("Filter by Location Match?", value=True)
        
        if filter_loc_job:
            loc = str(job_profile.get('Location', '')).strip()
            cands_pool = df_candidates[df_candidates['State'].astype(str).str.contains(loc, case=False, na=False)]
        else:
            cands_pool = df_candidates
            
        st.write(f"**Available Pool:** {len(cands_pool)} Candidates")

        if st.button("🚀 Run AI Matcher", type="primary"):
            if cands_pool.empty:
                st.error("No candidates found in this location.")
            else:
                with st.spinner(f"Gemini ({GEMINI_MODEL_NAME}) is sourcing candidates for {job_profile.get('Company Name')}..."):
                  #  cands_json = cands_pool[['First Name', 'Last Name', 'Skills', 'State', 'Education', 'Disability Type']].to_json(orient='records')
                    # Safely filter only the columns that actually exist in the candidate sheet
                    # (Added 'Qualification' in case 'Education' is missing)
                    desired_cand_cols = ['First Name', 'Last Name', 'Skills', 'State', 'Education', 'Qualification', 'Disability Type']
                    available_cand_cols = [col for col in desired_cand_cols if col in cands_pool.columns]
                    cands_json = cands_pool[available_cand_cols].to_json(orient='records')      
                    job_str = json.dumps(job_profile.to_dict())
                    
                    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
                    prompt = f"""
                    Act as a Disability Placement Officer.
                    JOB: {job_str}
                    CANDIDATES: {cands_json}
                    
                    TASK: Rank the Top 3 most suitable candidates based on skills, education, and job requirements.
                    Output ONLY a JSON list: [{{"name": "...", "skills": "...", "score": 90, "reason": "..."}}]
                    """
                    
                    try:
                        response = model.generate_content(prompt)
                        clean_json = response.text.replace("```json", "").replace("```", "").strip()
                        matches = json.loads(clean_json)
                        
                        # Build aggregated message
                        msg_subject = f"Candidate Matches for {job_profile.get('Job Title')} from Youth4Jobs"
                        msg_body = f"Hi {job_profile.get('Company Name')} Hiring Team,\n\nWe have identified some strong candidates for your {job_profile.get('Job Title')} role:\n\n"
                        
                        for m in matches:
                            score = m.get('score', 0)
                            color_emoji = "🟢" if score >= 80 else "🟠" if score >= 50 else "🔴"
                            with st.expander(f"{color_emoji} {m.get('name')} ({score}%)", expanded=True):
                                st.write(f"**Skills:** {m.get('skills')}")
                                st.write(f"_{m.get('reason')}_")
                                st.progress(score / 100)
                            
                            msg_body += f"🔹 Name: {m.get('name')}\n"
                            msg_body += f"   Skills: {m.get('skills')}\n"
                            msg_body += f"   Why they fit: {m.get('reason')}\n\n"
                            
                        msg_body += "Please let us know if you would like to proceed with interviews.\n\nBest,\nYouth4Jobs Placement Team"
                        
                        st.markdown("### 📤 Send Matches to Employer")
                        col_btn1, col_btn2 = st.columns(2)
                        
                        with col_btn1:
                            if emp_email:
                                params = urllib.parse.urlencode({'subject': msg_subject, 'body': msg_body})
                                st.link_button("🏢 Email Employer", f"mailto:{emp_email}?{params}", use_container_width=True)
                            else:
                                st.button("🏢 Email Employer (No Email)", disabled=True, use_container_width=True)
                                
                        with col_btn2:
                            if emp_phone:
                                wa_text = urllib.parse.quote(msg_body)
                                st.link_button("💬 WhatsApp Employer", f"https://wa.me/{emp_phone}?text={wa_text}", type="primary", use_container_width=True)
                            else:
                                st.button("💬 WhatsApp Employer (No Phone)", disabled=True, use_container_width=True)

                    except Exception as e:
                        st.error(f"AI Error: {e}")
