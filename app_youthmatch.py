import streamlit as st
import pandas as pd
import json
import google.generativeai as genai
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_sheets import get_or_create_spreadsheet, read_data_from_sheet

# 1. SETUP
set_app_theme("match") # 🔴 Red/Magenta Vibe
user = login_required()
genai.configure(api_key=st.secrets["gemini"]["api_key"])

st.write(f"👋 Hi **{user['name']}**! Let's match candidates to jobs.")

# 2. LOAD DATABASES (SUPPLY & DEMAND)
@st.cache_data(ttl=60)
def load_data():
    # Load Candidates (From Orange App Folder)
    scan_fid = st.secrets.get("youthscan", {}).get("folder_id")
    scan_url = get_or_create_spreadsheet("YouthScan_Data", scan_fid)
    df_c = pd.DataFrame(read_data_from_sheet(scan_url)) if scan_url else pd.DataFrame()
    
    # Load Jobs (From Green App Folder)
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

with col_left:
    st.subheader("👤 Candidate")
    # Create a simple label for the dropdown
    c_list = df_candidates.apply(lambda x: f"{x.get('First Name','')} {x.get('Last Name','')}", axis=1)
    selected_name = st.selectbox("Select Youth", c_list)
    
    # Fetch full profile
    idx = c_list[c_list == selected_name].index[0]
    profile = df_candidates.iloc[idx]
    
    # Display Card
    st.info(f"""
    **🎓 Edu:** {profile.get('Education')}  
    **📍 Loc:** {profile.get('State')}  
    **♿ Type:** {profile.get('Disability Type')}  
    **🛠 Skills:** {profile.get('Skills', 'N/A')}
    """)

with col_right:
    st.subheader("🎯 Job Recommendations")
    
    # Optional Filter
    filter_loc = st.checkbox("Filter by Location Match?", value=True)
    
    if filter_loc:
        # Simple fuzzy match for state/city
        loc = str(profile.get('State', '')).strip()
        jobs_pool = df_jobs[df_jobs['Location'].astype(str).str.contains(loc, case=False, na=False)]
    else:
        jobs_pool = df_jobs
        
    st.write(f"**Available Pool:** {len(jobs_pool)} Jobs")

    if st.button("🚀 Run AI Matcher", type="primary"):
        if jobs_pool.empty:
            st.error("No jobs found in this location.")
        else:
            with st.spinner(f"Gemini is interviewing {selected_name} for these roles..."):
                
                # PREPARE DATA FOR AI
                # We limit the columns to save tokens and improve accuracy
                jobs_json = jobs_pool[['Job Title', 'Company Name', 'Required Skills', 'Min Experience', 'Salary Range']].to_json(orient='records')
                profile_str = json.dumps(profile.to_dict())
                
                # THE RECRUITER PROMPT
                model = genai.GenerativeModel('gemini-1.5-flash')
                prompt = f"""
                Act as a Disability Placement Officer.
                
                CANDIDATE:
                {profile_str}
                
                OPEN JOBS:
                {jobs_json}
                
                TASK:
                Rank the Top 3 most suitable jobs.
                You must calculate a "Match Score" (0-100%) based on:
                1. Skills Match (Critical)
                2. Education Level
                3. Disability Friendliness (Implied)
                
                OUTPUT:
                Return ONLY a JSON list:
                [{{"title": "...", "company": "...", "score": 90, "reason": "Short explanation why..."}}]
                """
                
                try:
                    response = model.generate_content(prompt)
                    # Clean markdown
                    clean_json = response.text.replace("```json", "").replace("```", "").strip()
                    matches = json.loads(clean_json)
                    
                    # RENDER CARDS
                    for m in matches:
                        score = m['score']
                        color = "green" if score >= 80 else "orange" if score >= 50 else "red"
                        
                        with st.expander(f"**{score}% Match** | {m['title']} @ {m['company']}", expanded=True):
                            st.write(m['reason'])
                            st.progress(score / 100)
                            
                except Exception as e:
                    st.error(f"AI Error: {e}")
