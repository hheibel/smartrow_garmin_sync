import base64
from typing import Any

import requests
from absl import logging

from utils import read_credentials


class SmartRowClient:
    """A client for the SmartRow API.
    Handles authentication and data fetching.
    """

    def __init__(self) -> None:
        self.base_url = "https://smartrow.fit"
        self.username, self.password = read_credentials("smartrow-credentials")
        self.session: requests.Session | None = None

    def _login(self) -> None:
        """Logs in to the website using Basic Auth to retrieve a session cookie.

        This method is called automatically when needed. It establishes a
        requests.Session and stores it in self.session.

        Raises:
            requests.exceptions.RequestException: If the login request fails.
        """
        if self.session:
            return

        # 1. Create a session object to persist cookies across requests
        session = requests.Session()

        # 2. Prepare credentials for Basic Authentication
        credentials = f"{self.username}:{self.password}"
        encoded_credentials = base64.b64encode(
            credentials.encode("utf-8")
        ).decode("utf-8")

        # 3. Prepare the Authorization header
        login_headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Connection": "keep-alive",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/142.0.0.0 Safari/537.36"
            ),
        }

        # 4. Send the login request to /api/account/0
        login_url = f"{self.base_url}/api/account/0"

        try:
            # Using a GET request for login as per current implementation
            login_response = session.get(login_url, headers=login_headers)
            login_response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.error(
                "Login failed: %s. Please verify your credentials.", e
            )
            raise

        self.session = session

    def get_activities(self) -> list[dict[str, Any]]:
        """Fetches a list of public activities from SmartRow.

        If not already logged in, it will perform login first.

        Returns:
            A list of dictionaries representing activities. Key fields include:
            - id (int): Internal SmartRow activity ID.
            - created (str): ISO timestamp.
            - public_id (str): ID used for exports.
            - distance (int): Distance in meters.

        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """
        if not self.session:
            self._login()

        activities_url = f"{self.base_url}/api/public-game"

        try:
            if self.session:
                activities_response = self.session.get(activities_url)
                activities_response.raise_for_status()
                return list(activities_response.json())
            return []

        except requests.exceptions.RequestException as e:
            logging.error("Failed to fetch activities: %s", e)
            raise

    def get_activity(self, public_id: str, format: str = "tcx") -> bytes:
        """Fetches raw activity data (FIT/TCX) by its public ID.

        If not already logged in, it will perform login first.

        Args:
            public_id: The public UUID string of the activity.
            format: The format to export ('tcx' or 'fit').

        Returns:
            The raw bytes of the exported file.

        Raises:
            requests.exceptions.RequestException: If the download fails.
        """
        if not self.session:
            self._login()

        activity_details_url = (
            f"{self.base_url}/api/export/{format}/{public_id}"
        )

        try:
            if self.session:
                details_response = self.session.get(activity_details_url)
                details_response.raise_for_status()
                return bytes(details_response.content)
            return b""

        except requests.exceptions.RequestException as e:
            logging.error(
                "Failed to fetch activity details for public ID %s: %s",
                public_id,
                e,
            )
            raise
