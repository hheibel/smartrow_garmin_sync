import logging
from smartrow_sync import sync_smartrow_activities
from garmin_sync import sync_to_garmin

def main():
    """
    Main entrypoint for the garmin-syncher application.
    - Synchronizes SmartRow activities into Google Cloud Storage.
    - Synchronizes newly received .fit files from GCS to Garmin Connect.
    """
    logging.info("Starting Garmin Syncher application...")
    
    try:
        # Sync SmartRow to GCS
        sync_smartrow_activities()
        
        # Sync GCS to Garmin Connect
        sync_to_garmin()
        
        logging.info("Garmin Syncher task completed successfully.")
    except Exception as e:
        logging.error(f"An unexpected error occurred during execution: {e}")
        
if __name__ == "__main__":
    main()