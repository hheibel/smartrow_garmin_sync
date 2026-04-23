"""Centralized configuration for the smartrow_garmin_sync project."""

import os

try:
    from dotenv import load_dotenv

    # Load environment variables from a .env file locally (if it exists)
    load_dotenv()
except ImportError:
    pass  # python-dotenv isn't guaranteed to be installed everywhere

# Centralized Configuration Variables
PROJECT_ID: str = os.environ.get("PROJECT_ID", "garmin-syncher-491619")
GCS_BUCKET_NAME: str = os.environ.get(
    "GCS_BUCKET_NAME", "smartrow-activities-sync"
)
