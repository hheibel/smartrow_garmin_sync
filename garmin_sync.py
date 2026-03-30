import json
import logging
import io
from datetime import datetime, timedelta, timezone
from google.cloud import storage
from garminconnect import Garmin

from config import PROJECT_ID, GCS_BUCKET_NAME
from utils import read_credentials

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

GARMIN_SYNC_STATE_FILE = "garmin_sync_state.json"

def get_last_garmin_sync_time(bucket) -> str:
    """Read the last synced activity creation time from the GCS state file for Garmin."""
    blob = bucket.blob(GARMIN_SYNC_STATE_FILE)
    if blob.exists():
        try:
            content = blob.download_as_text()
            data = json.loads(content)
            return data.get("last_synced_created", "")
        except Exception as e:
            logging.warning(f"Failed to parse Garmin sync state file from GCS: {e}. Treating as empty.")
    return ""

def update_last_garmin_sync_time(bucket, last_synced_created: str):
    """Update the GCS state file with the newest synced activity time for Garmin."""
    blob = bucket.blob(GARMIN_SYNC_STATE_FILE)
    blob.upload_from_string(
        json.dumps({"last_synced_created": last_synced_created}, indent=4), 
        content_type="application/json"
    )

def parse_date_from_filename(filename: str) -> datetime:
    """
    Extracts the date and time from the filename.
    Filename expected: YYYYMMDD_HHMMSS_<activity_id>.fit
    """
    try:
        # 20260305_065350_1234.fit -> 20260305_065350
        date_part = filename.split('_', 2)[:2]
        date_str = "_".join(date_part)
        return datetime.strptime(date_str, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
    except Exception as e:
        logging.error(f"Failed to parse date from filename '{filename}': {e}")
        return datetime.min.replace(tzinfo=timezone.utc)

def sync_to_garmin():
    """Main execution function to sync .fit activities from GCS to Garmin Connect."""
    logging.info("Starting Garmin synchronization process...")
    
    # 1. Initialize Garmin Client
    try:
        username, password = read_credentials("garmin-credentials")
        client = Garmin(username, password)
        client.login()
        logging.info("Successfully logged into Garmin Connect.")
    except Exception as e:
        logging.error(f"Failed to login to Garmin Connect: {e}")
        return

    # 2. Access GCS Bucket
    try:
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        if not bucket.exists():
            logging.error(f"Bucket {GCS_BUCKET_NAME} does not exist.")
            return
    except Exception as e:
        logging.error(f"Failed to access GCS bucket: {e}")
        return

    # 3. Get sync state
    last_synced_created = get_last_garmin_sync_time(bucket)
    
    # Threshold for the 3-week failsafe
    three_weeks_ago = datetime.now(timezone.utc) - timedelta(days=21)
    
    # 4. List and filter .fit blobs
    all_blobs = list(storage_client.list_blobs(GCS_BUCKET_NAME))
    fit_blobs = [b for b in all_blobs if b.name.endswith(".fit")]
    
    # Determine the ISO timestamp from the filename for comparison logic if available
    # We want to match the "created" timestamp from the original SmartRow JSON 
    # to maintain consistency in timestamps.
    # We use the filename components for filtering since they mirror the 'created' date.
    
    # Convert ISO string from state to UTC datetime for accurate comparison
    last_synced_dt = datetime.min.replace(tzinfo=timezone.utc)
    if last_synced_created:
        try:
            # We expect YYYY-MM-DDTHH:MM:SS.mmmZ
            last_synced_dt = datetime.fromisoformat(last_synced_created.replace("Z", "+00:00"))
        except ValueError:
             logging.warning(f"Could not parse last synced timestamp '{last_synced_created}'.")

    new_uploads = []
    
    # To properly update the state, we need to map filename back to the ISO 'created' format
    # The filename prefix YYYYMMDD_HHMMSS is derived from 'created'.
    
    for blob in fit_blobs:
        file_dt = parse_date_from_filename(blob.name)
        
        # Failsafe check (3 weeks)
        if file_dt < three_weeks_ago:
            # logging.debug(f"Skipping {blob.name} (failsafe): activity is older than 3 weeks.")
            continue
            
        # Already synced check
        if file_dt <= last_synced_dt:
             continue
             
        new_uploads.append(blob)

    if not new_uploads:
        logging.info("No new FIT files to sync to Garmin.")
        return

    # Sort new uploads by name (which is chronological)
    new_uploads.sort(key=lambda x: x.name)
    
    logging.info(f"Found {len(new_uploads)} new FIT files to sync.")
    
    highest_synced_dt = last_synced_dt
    
    for blob in new_uploads:
        logging.info(f"Syncing activity file {blob.name} to Garmin...")
        try:
            # Download FIT file content
            fit_content = blob.download_as_bytes()
            
            # Use io.BytesIO to send as a file-like object to garminconnect
            file_stream = io.BytesIO(fit_content)
            
            # Garmin doesn't strictly need a filename, but the stream is necessary
            # We can't easily check for duplicates in Garmin based on ID here, 
            # so we rely on our state tracking.
            client.upload_activity(file_stream)
            logging.info(f"Successfully uploaded {blob.name} to Garmin.")
            
            # Update local highest synced tracking
            file_dt = parse_date_from_filename(blob.name)
            highest_synced_dt = max(highest_synced_dt, file_dt)
            
        except Exception as e:
            logging.error(f"Failed to upload {blob.name} to Garmin: {e}")
            # We continue with next files even if one fails
            
    # Update the state file in GCS
    if highest_synced_dt > last_synced_dt:
        # Convert back to a standardized ISO format for consistency
        update_last_garmin_sync_time(bucket, highest_synced_dt.strftime("%Y-%m-%dT%H:%M:%SZ"))

    logging.info("Garmin synchronization process completed.")

if __name__ == "__main__":
    sync_to_garmin()
