import streamlit as st
import pandas as pd
import json
import urllib.parse
import google.generativeai as genai

# --- IMPORTS FROM YOUR LOGIC MODULES ---
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_sheets import get_or_create_spreadsheet, read_data_from_sheet
from logic.logic_gemini import GEMINI_MODEL_NAME

# 1. SETUP
set_app_theme("y4jmatch") # 🔴 Red/Magenta Vibe
user = login_required()
genai.configure(api_key=st.secrets["gemini"]["api_key"])

st.write(f"👋 Hi **{user['name']}**! Let's match candidates to jobs.")

# Initialize session state variables to hold our data
if 'df_candidates' not in st.session_state:
    st.session_state.df_candidates = pd.DataFrame()
if 'df_jobs' not in st.session_state:
    st.session_state.df_jobs = pd.DataFrame()

# 2. CONFIGURE & LOAD DATABASES (SUPPLY & DEMAND)
st.subheader("📂 Data Sources")
st.write("Confirm or edit the Google Sheets names to load data from:")

# Generate the default sheet names based on the volunteer's email
v_email = user.get("email", "volunteer")
default_cand_sheet = f"YouthScan_{v_email}"
default_job_sheet = f"JobScan_{v_email}"

@st.cache_data(ttl=60, show_spinner=False)
def load_data(c_sheet, j_sheet):
    # Load Candidates (Supply)
    scan_fid = st.secrets.get("youthscan", {}).get("folder_id")
    scan_url = get_or_create_spreadsheet(c_sheet, scan_fid)
    df_c = pd.DataFrame(read_data_from_sheet(scan_url)) if scan_url else pd.DataFrame()
    
    # Load Jobs (Demand) - Updated to use "jobscan" secret
    jobs_fid = st.secrets.get("jobscan", {}).get("folder_id")
    jobs_url = get_or_create_spreadsheet(j_sheet, jobs_fid)
    df_j = pd.DataFrame(read_data_from_sheet(jobs_url)) if jobs_url else pd.DataFrame()
    
    return df_c, df_j

# Use a form so the app doesn't reload on every single keystroke while editing
with st.form("sheet_names_form"):
    col_src1, col_src2 = st.columns(2)
    with col_src1:
        cand_sheet_name = st.text_input("Candidate Sheet Name", value=default_cand_sheet)
    with col_src2:
        job_sheet_name = st.text_input("Job Sheet Name", value=default_job_sheet)
    
    submit_sheets = st.form_submit_button("Fetch Data")

# Only fetch the data when the user explicitly clicks the button
if submit_sheets:
    with st.spinner(f"Syncing databases from '{cand_sheet_name}' & '{job_sheet_name}'..."):
        # Fetch the data
        fetched_c, fetched_j = load_data(cand_sheet_name, job_sheet_name)
        
        # Save to session state so it persists
        st.session_state.df_candidates = fetched_c
        st.session_state.df_jobs = fetched_j
        
        # Display the counts immediately below the form
        st.success(f"✅ Loaded **{len(fetched_c)}** candidates and **{len(fetched_j)}** jobs.")

# Assign session state data back to local variables for the rest of the app to use
df_candidates = st.session_state.df_candidates
df_jobs = st.session_state.df_jobs

# 3. CHECK DATA HEALTH
if df_candidates.empty or df_jobs.empty:
    st.info("👆 Please verify the sheet names above and click 'Fetch Data' to begin.")
    st.stop()

# 4. MATCHING INTERFACE
col_left, col_right = st.columns([1, 2])

# --- LEFT COLUMN: CANDIDATE SELECTION ---
with col_left:
    st.subheader("👤 Candidate")
    # Dropdown label creation
    c_list = df_candidates.apply(lambda x: f"{x.get('First Name','')} {x.get('Last Name','')}", axis=1)
    selected_name = st.selectbox("Select Youth", c_list)
    
    # Fetch full profile data
    idx = c_list[c_list == selected_name].index[0]
    profile = df_candidates.iloc[idx]
    
    # Display Profile Card
    st.info(f"""
    **🎓 Edu:** {profile.get('Education')}  
    **📍 Loc:** {profile.get('State')}  
    **♿ Type:** {profile.get('Disability Type')}  
    **🛠 Skills:** {profile.get('Skills', 'N/A')}
    """)
    
    # Show email if available (visual confirmation)
    cand_email = profile.get('Email', '')
    if cand_email:
        st.caption(f"📧 Candidate: {cand_email}")
    else:
        st.caption("⚠️ No candidate email")

# --- RIGHT COLUMN: JOB MATCHING ---
with col_right:
    st.subheader("🎯 Job Recommendations")
    
    # Optional Filter: Only show jobs in the candidate's state
    filter_loc = st.checkbox("Filter by Location Match?", value=True)
    
    if filter_loc:
        loc = str(profile.get('State', '')).strip()
        # Fuzzy match: checks if Candidate State is inside Job Location string
        jobs_pool = df_jobs[df_jobs['Location'].astype(str).str.contains(loc, case=False, na=False)]
    else:
        jobs_pool = df_jobs
        
    st.write(f"**Available Pool:** {len(jobs_pool)} Jobs")

    if st.button("🚀 Run AI Matcher", type="primary"):
        if jobs_pool.empty:
            st.error("No jobs found in this location.")
        else:
            with st.spinner(f"Gemini ({GEMINI_MODEL_NAME}) is interviewing {selected_name}..."):
                
                # A. PREPARE DATA FOR AI
                if 'Contact Email' not in jobs_pool.columns:
                    jobs_pool['Contact Email'] = ''

                jobs_json = jobs_pool[['Job Title', 'Company Name', 'Required Skills', 'Min Experience', 'Contact Email']].to_json(orient='records')
                profile_str = json.dumps(profile.to_dict())
                
                # B. INITIALIZE MODEL
                model = genai.GenerativeModel(GEMINI_MODEL_NAME)
                
                # C. THE PROMPT
                prompt = f"""
                Act as a Disability Placement Officer.
                CANDIDATE: {profile_str}
                OPEN JOBS: {jobs_json}
                
                TASK:
                Rank the Top 3 most suitable jobs based on skills, education, and disability accommodation needs.
                
                Output ONLY a JSON list (no markdown, just raw JSON):
                [{{"title": "...", "company": "...", "email": "...", "score": 90, "reason": "..."}}]
                """
                
                try:
                    # D. CALL GEMINI
                    response = model.generate_content(prompt)
                    clean_json = response.text.replace("```json", "").replace("```", "").strip()
                    matches = json.loads(clean_json)
                    
                    # E. RENDER RESULTS
                    for m in matches:
                        score = m.get('score', 0)
                        # Determine Color Code
                        if score >= 80: color_emoji = "🟢"
                        elif score >= 50: color_emoji = "🟠"
                        else: color_emoji = "🔴"
                        
                        with st.expander(f"{color_emoji} {m.get('title')} @ {m.get('company')} ({score}%)", expanded=True):
                            st.write(f"_{m.get('reason')}_")
                            st.progress(score / 100)
                            
                            col_c_mail, col_e_mail = st.columns(2)

                            # --- 1. EMAIL TO CANDIDATE ---
                            with col_c_mail:
                                if cand_email:
                                    subject = f"Job Opportunity: {m.get('title')} at {m.get('company')}"
                                    body = f"""Hi {profile.get('First Name')},

We found a match for you!
Role: {m.get('title')}
Company: {m.get('company')}

Our AI matched you because: "{m.get('reason')}"

Apply now?

- Youth4Jobs"""
                                    
                                    params = urllib.parse.urlencode({'subject': subject, 'body': body})
                                    st.link_button("👤 Email Candidate", f"mailto:{cand_email}?{params}")
                                else:
                                    st.caption("🚫 No Candidate Email")

                            # --- 2. EMAIL TO EMPLOYER (NEW FEATURE) ---
                            with col_e_mail:
                                emp_email = m.get('email', '')
                                if emp_email and "@" in emp_email:
                                    subject_emp = f"Candidate Profile: {profile.get('First Name')} for {m.get('title')}"
                                    body_emp = f"""Hi {m.get('company')} Hiring Team,

I am writing from Youth4Jobs. We have identified a strong candidate for your {m.get('title')} role.

Name: {profile.get('First Name')} {profile.get('Last Name')}
Skills: {profile.get('Skills')}
Location: {profile.get('State')}

Why they are a fit: {m.get('reason')}

Please let us know if you would like to interview them.

Best,
Youth4Jobs Placement Team"""
                                    
                                    params_emp = urllib.parse.urlencode({'subject': subject_emp, 'body': body_emp})
                                    st.link_button("🏢 Email Employer", f"mailto:{emp_email}?{params_emp}", type="primary")
                                else:
                                    st.caption("🚫 No Employer Email")
                            
                except Exception as e:
                    st.error(f"AI Error: {e}")
