# Travel Planner Agent with ADK

## Prerequisites

### IAM Roles
Grant the following IAM Roles to the User or Service Account running the ADK Agent:
*   Vertex AI User
*   Cloud Trace Agent (to write Trace Logs)
*   Service Usage Consumer 

### Enable APIs
1.  Enable Vertex AI recommended APIs:
    *   In the Google Cloud console, navigate to Vertex AI by searching for it at the top of the console.
    *   Click **Enable all recommended APIs**.

### Authenticate
Authenticate using the command below:
```bash
gcloud auth application-default login
```

## Setup Instructions

1.  **Set up a virtual environment:**
    ```bash
    python -m venv .venv
    ```

2.  **Activate the Virtual Environment:**
    ```bash
    source .venv/bin/activate
    ```

3.  **Install ADK library along with other required libraries:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Clone this directory within a new directory called adk-multiagent-systems (if you haven't already):**
    ```bash
    git clone https://github.com/googlecloudplatform/adk-multiagent-systems.git
    ```

5.  **Service Account Setup:**
    *   Create a new service account in Google Cloud with access to Google Sheets API, Google Drive API, and Google Docs API.
    *   Download the JSON key file.
    *   Rename it to `sa_sheets.json`.
    *   Place this file in the `travel_planner` directory (i.e., at the same level as your `agent.py` and `tools.py`).

6.  **Create `.env` file:**
    Create a `.env` file in the `travel_planner` directory and add the following environment variables, replacing placeholders with your actual values:
    ```env
    # If using Gemini via Vertex AI on Google Cloud
    GOOGLE_CLOUD_PROJECT=<your_google_cloud_project_id>
    GOOGLE_CLOUD_LOCATION=<your_google_cloud_location>
    GOOGLE_GENAI_USE_VERTEXAI="True"
    AGENT_NAME="travel_planner"
    MODEL_ID="gemini-2.0-flash" # Or your preferred model, e.g., gemini-1.5-flash
    SHEETS_SERVICE_ACCOUNT_KEY_PATH="sa_sheets.json"
    USER_EMAIL_TO_SHARE_WITH="<your_email_address_to_share_files_with>"
    ```
7. cd adk-multiagent-systems/
run adk web --> this will take you to the ADK UI. You can then run the agent from the UI.

8. Select traveller_planner from the dropdown

9. Start asking for flights / hotels / itinerary / food recommendations

10. Ask the agent to export your detailed recommendations to the Google Doc

11. Ask the agent to create a financial planner and export it to Google Sheets

12. Provide a sheet / Doc ID to the agent if you want to delete a document
