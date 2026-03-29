import os
try:
    from dotenv import load_dotenv
    # Load environment variables from a .env file locally (if it exists)
    load_dotenv()
except ImportError:
    pass # python-dotenv isn't guaranteed to be installed in all deployment environments

# Centralized Configuration Variables
PROJECT_ID = os.environ.get("PROJECT_ID", "garmin-syncher-491619")
