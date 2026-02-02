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
set_app_theme("match") # 🔴 Red/Magenta Vibe
user = login_required()
genai.configure(api_key=st.secrets["gemini"]["api_key"])

st.write(f"👋 Hi **{user['name']}**! Let's match candidates to jobs.")

# 2. LOAD DATABASES (SUPPLY & DEMAND)
@st.cache_data(ttl=60)
def load_data():
    # Load Candidates (Supply)
    scan_fid = st.secrets.get("youthscan", {}).get("folder_id")
    scan_url = get_or_create_spreadsheet("YouthScan_Data", scan_fid)
    df_c = pd.DataFrame(read_data_from_sheet(scan_url)) if scan_url else pd.DataFrame()
    
    # Load Jobs (Demand)
    jobs_fid = st.secrets.get("youthjobs", {}).get("folder_id")
    jobs_url = get_or_create_spreadsheet("YouthJobs_Master_DB", jobs_fid)
    df_j = pd.DataFrame(read_data_from_sheet(jobs_url)) if jobs_url else pd.DataFrame()
    
    return df_c, df_j

with st.spinner("Syncing databases..."):
    df_candidates, df_jobs = load_data()

# 3. CHECK DATA HEALTH
if df_candidates.empty or df_jobs.empty:
    st.warning("⚠️ Waiting for data... Ensure you have scanned at least one Candidate and one Job.")
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
                # We added 'Contact Email' here so the AI can pass it back in the result
                # Make sure the column exists, otherwise create a dummy one
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
                                    body = f"""Hi {profile.get('First Name')},\n\nWe found a match for you!\nRole: {m.get('title')}\nCompany: {m.get('company')}\n\nOur AI matched you because: "{m.get('reason')}"\n\nApply now?\n\n- Youth4Jobs"""
                                    
                                    params = urllib.parse.urlencode({'subject': subject, 'body': body})
                                    st.link_button("👤 Email Candidate", f"mailto:{cand_email}?{params}")
                                else:
                                    st.caption("🚫 No Candidate Email")

                            # --- 2. EMAIL TO EMPLOYER (NEW FEATURE) ---
                            with col_e_mail:
                                emp_email = m.get('email', '')
                                if emp_email and "@" in emp_email:
                                    subject_emp = f"Candidate Profile: {profile.get('First Name')} for {m.get('title')}"
                                    body_emp = f"""Hi {m.get('company')} Hiring Team,\n\nI am writing from Youth4Jobs. We have identified a strong candidate for your {m.get('title')} role.\n\nName: {profile.get('First Name')} {profile.get('Last Name')}\nSkills: {profile.get('Skills')}\nLocation: {profile.get('State')}\n\nWhy they are a fit: {m.get('reason')}\n\nPlease let us know if you would like to interview them.\n\nBest,\nYouth4Jobs Placement Team"""
                                    
                                    params_emp = urllib.parse.urlencode({'subject': subject_emp, 'body': body_emp})
                                    # Use type="primary" to make it pop as the main action
                                    st.link_button("🏢 Email Employer", f"mailto:{emp_email}?{params_emp}", type="primary")
                                else:
                                    st.caption("🚫 No Employer Email")
                            
                except Exception as e:
                    st.error(f"AI Error: {e}")
