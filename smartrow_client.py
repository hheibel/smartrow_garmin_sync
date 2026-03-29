from typing import Any
import requests
import base64
from utils import read_credentials

class SmartRowClient:
    """
    A client for the SmartRow API.
    Handles authentication and data fetching.
    """
    def __init__(self):
        self.base_url = "https://smartrow.fit"
        self.username, self.password = read_credentials("smartrow-credentials")
        self.session = None 
    
    def _login(self):
        """
        Logs in to the website, retrieves a session cookie, and stores the session.
        This method is called automatically when needed.
        """

        if self.session:
            return
        
        """
        Logs in to the website using a GET request, retrieves a session cookie, and stores the session.
        This method is called automatically when needed.
        """
        if self.session:
            return

        # 1. Create a session object to persist cookies across requests
        session = requests.Session()

        # 2. Prepare credentials for Basic Authentication
        credentials = f"{self.username}:{self.password}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

        # 3. Prepare the Authorization header
        login_headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
        }

        # 4. Send the login request to /api/account/0
        login_url = f"{self.base_url}/api/account/0"

        try:
            # Using a GET request for login as per current implementation
            login_response = session.get(login_url, headers=login_headers)
            login_response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Login failed: {e}")
            if e.response is not None:
                print(f"Response Body: {e.response.text}")
            raise  # Re-raise the exception

        self.session = session
    

    def get_activities(self) -> Any:
        """
        Fetches a list of public games.
        If not already logged in, it will perform login first.
        
        Returns a list of dictionaries. Some exemplary fields for each activity are:
        - `id` (int): Internal SmartRow activity ID.
        - `created` (str): Activity timestamp (e.g., "2026-03-05T06:53:50.807Z").
        - `strava_id` (str): Linked Strava activity ID, if synced.
        - `distance` (int): Total distance covered in meters.

        For details, see github.com/hheibel/smartrow_garmin_sync/blob/main/docs/smartrow_activity.md
        """
        if not self.session:
            self._login()

        activities_url = f"{self.base_url}/api/public-game"

        try:
            activities_response = self.session.get(activities_url)
            activities_response.raise_for_status()
            return activities_response.json()

        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch activities: {e}")
            if e.response is not None:
                print(f"Response Body: {e.response.text}")
            raise


    def get_activity_tcx(self, activity_id: int) -> str:
        """
        Fetches detailed information about a specific activity by its ID.
        If not already logged in, it will perform login first.
        """
        if not self.session:
            self._login()

        activity_details_url = f"{self.base_url}/api/export/tcx/{activity_id}"

        try:
            details_response = self.session.get(activity_details_url)
            details_response.raise_for_status()
            return details_response.text  # Return the TCX data as a string

        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch activity details for ID {activity_id}: {e}")
            if e.response is not None:
                print(f"Response Body: {e.response.text}")
            raise
