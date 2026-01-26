# y4j
Common repository for all y4j-AiOps apps
# 🚀 Youth4Jobs AiOps Ecosystem

A federated suite of AI-powered applications designed to digitize, manage, and connect Persons with Disabilities (PwDs) to employment opportunities. Powered by **Google Gemini 3.0** and **Streamlit**.

## 🏗️ Architecture
The ecosystem consists of 5 interconnected applications that share a common data backend (Google Drive & Sheets).

| App Color | Name | Function | Role |
| :--- | :--- | :--- | :--- |
| 🟠 **Orange** | **YouthScan** | Scanning Resumes & IDs | **Supply Side** (Input) |
| 🟢 **Green** | **YouthJobs** | Scanning Job Descriptions | **Demand Side** (Input) |
| 🔵 **Blue** | **YouthProfile**| Candidate Database View | **Management** (Admin) |
| 🔴 **Red** | **YouthMatch** | AI Recruiter & Matching | **Intelligence** (Output) |
| ⚪ **White** | **Y4J-Hub** | Single Sign-On Launchpad | **Central Access** |

## ⚙️ Setup & Installation

### 1. Prerequisites
* Python 3.9+
* A Google Cloud Project with OAuth 2.0 Credentials.
* Two Google Drive Folders:
    1.  `YouthScan_Data` (for candidates)
    2.  `YouthJobs_Data` (for job descriptions)

### 2. Secrets Configuration (`secrets.toml`)
All apps share the same `[auth]` credentials but require specific folder IDs.

```toml
[auth]
client_id = "YOUR_GOOGLE_CLIENT_ID"
client_secret = "YOUR_GOOGLE_CLIENT_SECRET"
redirect_uri = "[https://YOUR-APP-URL.streamlit.app](https://YOUR-APP-URL.streamlit.app)" # Unique for each app!

[gemini]
api_key = "YOUR_AI_STUDIO_KEY"

[youthscan]
folder_id = "FOLDER_ID_FOR_CANDIDATES"

[youthjobs]
folder_id = "FOLDER_ID_FOR_JOBS"
