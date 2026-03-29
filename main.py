import logging
from smartrow_sync import sync_smartrow_activities

def main():
    """
    Main entrypoint for the garmin-syncher application.
    Executes the synchronization of SmartRow activities into Google Cloud Storage.
    """
    logging.info("Starting Garmin Syncher application...")
    
    try:
        sync_smartrow_activities()
        logging.info("Garmin Syncher task completed successfully.")
    except Exception as e:
        logging.error(f"An unexpected error occurred during execution: {e}")
        
if __name__ == "__main__":
    main()