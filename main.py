import os
import requests
from google.cloud import secretmanager

from config import PROJECT_ID

def access_secret_version(project_id, secret_id, version_id="latest"):
    """
    Accesses the payload for the given secret version using GCP Secret Manager.
    """
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    
    try:
        response = client.access_secret_version(request={"name": name})
        # Extract the payload as a string
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error retrieving secret {secret_id}: {e}")
        return None

def main():
    print("Starting automated web task...")

    if not PROJECT_ID:
        print("Error: GCP_PROJECT_ID environment variable not set.")
        return

    # 1. Fetch your credentials from Secret Manager
    # Replace 'MY_WEBSITE_PASSWORD' with the actual name of your secret in GCP
    my_secret_password = access_secret_version(PROJECT_ID, "MY_WEBSITE_PASSWORD")
    
    if not my_secret_password:
        print("Failed to get credentials. Exiting.")
        return

    # 2. Execute your web logic using the fetched secret
    print("Credentials successfully retrieved! (Length: {})".format(len(my_secret_password)))
    print("Connecting to website...")
    
    # --- YOUR WEB SCRAPING / API LOGIC GOES HERE ---
    # Example using requests:
    # response = requests.post("https://example.com/login", data={"user": "admin", "pass": my_secret_password})
    # print(f"Website responded with status code: {response.status_code}")
    
    print("Task completed successfully.")

if __name__ == "__main__":
    main()