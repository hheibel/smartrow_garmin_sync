import os
import json
from absl import logging
from datetime import datetime
from google.cloud import storage

from config import PROJECT_ID, GCS_BUCKET_NAME
from smartrow_client import SmartRowClient
from fit_utils import read_fit_file



SYNC_STATE_FILE = "sync_state.json"

def get_last_synced_time(bucket: storage.Bucket) -> str:
    """Read the last synced activity creation time from the GCS state file."""
    blob = bucket.blob(SYNC_STATE_FILE)
    if blob.exists():
        try:
            content = blob.download_as_text()
            data = json.loads(content)
            return data.get("last_synced_created", "")
        except Exception as e:
            logging.warning(f"Failed to parse sync state file from GCS: {e}. Treating as empty.")
    return ""

def update_last_synced_time(bucket: storage.Bucket, last_synced_created: str) -> None:
    """Update the GCS state file with the newest synced activity time."""
    blob = bucket.blob(SYNC_STATE_FILE)
    blob.upload_from_string(
        json.dumps({"last_synced_created": last_synced_created}, indent=4), 
        content_type="application/json"
    )

def format_filename(created_str: str, activity_id: int, extension: str) -> str:
    """Format the filename as YYYYMMDD_HHMMSS_<activity_id>.<extension>"""
    try:
        # Expected format: 2026-03-05T06:53:50.807Z
        # Some timestamps might not have milliseconds, so we handle both
        if '.' in created_str:
            dt = datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        else:
            dt = datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%SZ")
        prefix = dt.strftime("%Y%m%d_%H%M%S")
    except ValueError as e:
        logging.warning(f"Could not parse timestamp '{created_str}' for activity {activity_id}: {e}")
        # Fallback to sanitized string
        prefix = created_str.replace(":", "").replace("-", "").replace("T", "_").split(".")[0]
        
    return f"{prefix}_{activity_id}.{extension}"

def upload_to_gcs(bucket: storage.Bucket, filename: str, content: bytes | str, content_type: str) -> None:
    """
    Uploads string or binary content to a GCS bucket.

    Examples:
        # JSON (string)
        upload_to_gcs(bucket, "data.json", json.dumps(data), "application/json")

        # Binary (bytes)
        upload_to_gcs(bucket, "activity.fit", fit_bytes, "application/octet-stream")
    """
    blob = bucket.blob(filename)
    blob.upload_from_string(content, content_type=content_type)
    logging.info(f"Uploaded {filename} to gs://{bucket.name}/")

def sync_smartrow_activities() -> None:
    """Main execution function to sync SmartRow activities to GCS."""
    logging.info("Starting SmartRow sync process...")
    
    try:
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        # Verify bucket exists
        if not bucket.exists():
            logging.error(f"Bucket {GCS_BUCKET_NAME} does not exist in project {PROJECT_ID}.")
            return
    except Exception as e:
        logging.error(f"Failed to initialize GCP Storage client or access bucket: {e}")
        return

    last_synced = get_last_synced_time(bucket)
    if last_synced:
        logging.info(f"Last synced activity timestamp: {last_synced}")
    else:
        logging.info("No prior sync state found. Will sync all available activities.")
        
    client = SmartRowClient()
    
    try:
        activities = client.get_activities()
    except Exception as e:
        logging.error(f"Failed to retrieve activities from SmartRow: {e}")
        return

    # Sort activities chronologically by 'created' timestamp (oldest first)
    activities.sort(key=lambda x: x.get('created', ''))
    
    new_activities = [a for a in activities if a.get('created', '') > last_synced]
    
    if not new_activities:
        logging.info("No new activities to sync.")
        return
        
    logging.info(f"Found {len(new_activities)} new activities to sync.")

    highest_synced = last_synced

    for activity in new_activities:
        activity_id = activity.get('id')
        public_id = activity.get('public_id')
        created_str = activity.get('created', '')
        
        if not activity_id or not created_str or not public_id:
            logging.warning(f"Skipping activity due to missing id, public_id or created timestamp: {activity}")
            continue
            
        json_filename = format_filename(created_str, activity_id, "json")
        fit_filename = format_filename(created_str, activity_id, "fit")
        
        # Upload JSON
        upload_to_gcs(bucket, json_filename, json.dumps(activity, indent=2), "application/json")
        
        # Fetch and Upload original FIT from SmartRow
        try:
            fit_data = client.get_activity(public_id, format="fit")
            if fit_data:
                upload_to_gcs(bucket, fit_filename, fit_data, "application/octet-stream")
            else:
                logging.warning(f"No activity FIT data available for activity {activity_id}.")

        except Exception as e:
            logging.error(f"Unexpected error processing FIT for activity {activity_id} (created date: {created_str}): {e}")
            # Continue processing next activities even if one fails
            
        highest_synced = max(highest_synced, created_str)
        
    # Update the sync state file exactly once at the end.
    # This prevents the GCS 1 object mutation per second rate limit issue on sync_state.json,
    # and significantly reduces the number of Class A (write) operations, keeping you comfortably in the GCP Free Tier.
    if highest_synced and highest_synced != last_synced:
        update_last_synced_time(bucket, highest_synced)

    logging.info("Sync process completed successfully.")
