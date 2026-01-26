import streamlit as st
import pandas as pd
import json
import urllib.parse
import google.generativeai as genai

# --- IMPORTS FROM YOUR LOGIC MODULES ---
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_sheets import get_or_create_spreadsheet, read_data_from_sheet
from logic.logic_gemini import GEMINI_MODEL_NAME  # <--- The Central Config Upgrade

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
        st.caption(f"📧 {cand_email}")
    else:
        st.caption("⚠️ No email on file")

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
                # Filter columns to save tokens
                jobs_json = jobs_pool[['Job Title', 'Company Name', 'Required Skills', 'Min Experience']].to_json(orient='records')
                profile_str = json.dumps(profile.to_dict())
                
                # B. INITIALIZE MODEL (Using Central Config)
                model = genai.GenerativeModel(GEMINI_MODEL_NAME)
                
                # C. THE PROMPT
                prompt = f"""
                Act as a Disability Placement Officer.
                CANDIDATE: {profile_str}
                OPEN JOBS: {jobs_json}
                
                TASK:
                Rank the Top 3 most suitable jobs.
                Output ONLY a JSON list:
                [{{"title": "...", "company": "...", "score": 90, "reason": "..."}}]
                """
                
                try:
                    # D. CALL GEMINI
                    response = model.generate_content(prompt)
                    clean_json = response.text.replace("```json", "").replace("```", "").strip()
                    matches = json.loads(clean_json)
                    
                    # E. RENDER RESULTS
                    for m in matches:
                        score = m['score']
                        # Determine Color Code
                        if score >= 80: color_emoji = "🟢"
                        elif score >= 50: color_emoji = "🟠"
                        else: color_emoji = "🔴"
                        
                        with st.expander(f"{color_emoji} {m['title']} @ {m['company']} ({score}%)", expanded=True):
                            st.write(f"_{m['reason']}_")
                            st.progress(score / 100)
                            
                            # --- EMAIL GENERATOR ---
                            if cand_email:
                                subject = f"Job Opportunity: {m['title']} at {m['company']}"
                                body = f"""Hi {profile.get('First Name')},

We found a job matching your skills in {profile.get('Skills', 'your field')}!

Role: {m['title']}
Company: {m['company']}
Location: {profile.get('State')}

Our AI recruiter matched you because:
"{m['reason']}"

Are you interested in applying?

Best,
Youth4Jobs Team"""
                                
                                # Encode specifically for mailto links
                                params = urllib.parse.urlencode({'subject': subject, 'body': body})
                                mailto_link = f"mailto:{cand_email}?{params}"
                                
                                # The Action Button
                                st.link_button("✉️ Draft Email to Candidate", mailto_link)
                            else:
                                st.warning("🚫 Cannot draft email: No email address found for this candidate.")
                            
                except Exception as e:
                    st.error(f"AI Error: {e}")
