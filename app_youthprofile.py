import streamlit as st
import pandas as pd
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_sheets import get_or_create_spreadsheet, read_data_from_sheet

# 1. SETUP
set_app_theme("profile") # 🔵 Blue Vibe
user = login_required()

st.write(f"👋 Hi **{user['name']}**! Here is your Candidate Database.")

# 2. LOAD DATA
# We use the Folder ID from YouthScan because that's where the data lives.
folder_id = st.secrets.get("youthscan", {}).get("folder_id")
sheet_name = "YouthScan_Data" # Default name we used in the Orange App

# Helper to load data (Cached for performance)
@st.cache_data(ttl=60) # Refresh every 60 seconds
def load_data():
    url = get_or_create_spreadsheet(sheet_name, folder_id)
    if url:
        data = read_data_from_sheet(url)
        return pd.DataFrame(data)
    return pd.DataFrame()

with st.spinner("Fetching database..."):
    df = load_data()

# 3. METRICS TOP BAR
if not df.empty:
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Candidates", len(df))
    # Count unique locations if column exists
    if "State" in df.columns:
        col2.metric("Locations Covered", df["State"].nunique())
    # Count specific disability types if column exists
    if "Disability Type" in df.columns:
        top_disability = df["Disability Type"].mode()[0] if not df["Disability Type"].empty else "N/A"
        col3.metric("Most Common Profile", top_disability)

    st.divider()

    # 4. SEARCH & FILTER
    st.subheader("🔍 Search Database")
    
    search_term = st.text_input("Search by Name, Skill, or Location", placeholder="e.g., Mumbai, Java, Rohit...")
    
    # Filter Logic
    if search_term:
        # Case-insensitive search across all columns
        mask = df.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
        filtered_df = df[mask]
    else:
        filtered_df = df

    # 5. DATA GRID
    st.dataframe(
        filtered_df, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Email": st.column_config.LinkColumn("Email"), # Make emails clickable
        }
    )
    
    # 6. DOWNLOAD OPTION
    st.download_button(
        "📥 Download as CSV",
        filtered_df.to_csv(index=False).encode('utf-8'),
        "youth_profiles.csv",
        "text/csv"
    )

else:
    st.info("📭 Database is empty. Go to the Orange App (YouthScan) to add candidates!")
