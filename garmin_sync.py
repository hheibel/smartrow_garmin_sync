import json
from absl import logging
import io
import os
import tempfile
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Any
from google.cloud import storage
from garminconnect import Garmin

from config import PROJECT_ID, GCS_BUCKET_NAME
from utils import init_garmin_client
from fit_utils import rewrite_fit_file_attributes



GARMIN_SYNC_STATE_FILE = "garmin_sync_state.json"

@dataclass
class ActivityData:
    base_name: str
    created: datetime  # Derived solely from the filename timestamp
    
    @property
    def fit_file(self) -> str:
        return f"{self.base_name}.fit"
        
    @property
    def json_file(self) -> str:
        return f"{self.base_name}.json"

def get_last_garmin_sync_time(bucket: storage.Bucket) -> str:
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

def update_last_garmin_sync_time(bucket: storage.Bucket, last_synced_created: str) -> None:
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

def check_overlap(fit_start_dt: datetime, fit_duration_sec: int, garmin_activities: list[dict[str, Any]]) -> bool:
    """Checks if the fit_interval overlaps with any garmin activity interval."""
    # Add a minimum 1 second duration to ensure max() < min() works properly for instantaneous acts
    fit_end_dt = fit_start_dt + timedelta(seconds=max(fit_duration_sec, 1))
    
    for garmin_activity in garmin_activities:
        garmin_start_str = garmin_activity.get('startTimeGMT')
        # Some Garmin types use duration, some might have elapsedDuration (fallbacks)
        garmin_duration_sec = garmin_activity.get('duration', garmin_activity.get('elapsedDuration', 0))
        if not garmin_start_str:
            continue
            
        try:
            # Garmin startTimeGMT is string like "2023-10-25 16:00:00" natively without timezone
            garmin_start_dt = datetime.strptime(garmin_start_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            garmin_end_dt = garmin_start_dt + timedelta(seconds=garmin_duration_sec)
            
            # temporal overlap collision calculation
            if max(fit_start_dt, garmin_start_dt) < min(fit_end_dt, garmin_end_dt):
                return True
        except ValueError as e:
            logging.debug(f"Could not parse garmin start time: {garmin_start_str} - {e}")
            continue
            
    return False

def filter_recent(activities: list[ActivityData], weeks: int = 3) -> list[ActivityData]:
    """Filters items from the last three weeks."""
    threshold = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    return [a for a in activities if a.created >= threshold]

def filter_already_synced(activities: list[ActivityData], last_synced_dt: datetime) -> list[ActivityData]:
    """Filters out any activity that is older than or equal to the highest synced timestamp."""
    return [a for a in activities if a.created > last_synced_dt]

def filter_duplicates(activities: list[ActivityData], garmin_activities: list[dict[str, Any]], bucket: storage.Bucket) -> list[ActivityData]:
    """Filters against duplicates by downloading exact duration metrics from GCS."""
    non_duplicates = []
    
    for a in activities:
        json_blob = bucket.blob(a.json_file)
        fit_duration_sec = 0
        exact_created = a.created
        
        if json_blob.exists():
            try:
                json_content = json_blob.download_as_text()
                json_data = json.loads(json_content)
                fit_duration_sec = json_data.get('elapsed_seconds', 0)
                
                created_str = json_data.get('created')
                if created_str:
                    exact_created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except Exception as e:
                logging.warning(f"Failed to parse companion json {a.json_file}: {e}")
                
        if not check_overlap(exact_created, fit_duration_sec, garmin_activities):
            non_duplicates.append(a)
            
    return non_duplicates

def sync_to_garmin() -> None:
    """Main execution function to sync .fit activities from GCS to Garmin Connect."""
    logging.info("Starting Garmin synchronization process...")
    
    # 1. Initialize Garmin Client
    try:
        client = init_garmin_client()
        
        # Pre-fetch the latest 100 workouts to use for duplication checking
        garmin_activities: list[dict[str, Any]] = client.get_activities(0, 100)
    except Exception as e:
        logging.error(f"Failed to login to Garmin Connect or fetch baseline activities. Are you authenticated via gcloud? Error: {e}")
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
    
    # Determine the ISO timestamp from the state for comparison logic
    last_synced_dt = datetime.min.replace(tzinfo=timezone.utc)
    if last_synced_created:
        try:
            last_synced_dt = datetime.fromisoformat(last_synced_created.replace("Z", "+00:00"))
        except ValueError:
             logging.warning(f"Could not parse last synced timestamp '{last_synced_created}'.")

    # 4. List and filter .fit blobs
    all_blobs = list(storage_client.list_blobs(GCS_BUCKET_NAME))
    fit_blob_names = [b.name for b in all_blobs if b.name.endswith(".fit")]

    # Create initial ActivityData using filename data to prevent expensive GCS calls
    activities = []
    for fname in fit_blob_names:
        base_name = fname.replace(".fit", "")
        file_dt = parse_date_from_filename(fname)
        activities.append(ActivityData(base_name=base_name, created=file_dt))
        
    activities.sort(key=lambda x: x.created)
    activities = filter_recent(activities, weeks=3)
    activities = filter_already_synced(activities, last_synced_dt)
    activities = filter_duplicates(activities, garmin_activities, bucket)
    
    if not activities:
        logging.info("No new FIT files to sync to Garmin.")
        return
        
    logging.info(f"Found {len(activities)} new FIT files to sync.")
    
    highest_synced_dt = last_synced_dt
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        for activity in activities:
            logging.info(f"Syncing activity file {activity.fit_file} to Garmin...")
            try:
                blob = bucket.blob(activity.fit_file)
                if not blob.exists():
                    logging.warning(f"File {activity.fit_file} not found in GCS.")
                    continue
                    
                # Download and Translate on-the-fly
                raw_fit_path = os.path.join(tmp_dir, f"raw_{activity.fit_file}")
                processed_fit_path = os.path.join(tmp_dir, activity.fit_file)
                
                blob.download_to_filename(raw_fit_path)
                rewrite_fit_file_attributes(raw_fit_path, processed_fit_path)
                
                client.upload_activity(processed_fit_path)
                logging.info(f"Successfully uploaded {activity.fit_file} to Garmin.")
                
                highest_synced_dt = max(highest_synced_dt, activity.created)
                
            except Exception as e:
                logging.error(f"Failed to upload {activity.fit_file} to Garmin: {e}")
            
    # Update the state file in GCS
    if highest_synced_dt > last_synced_dt:
        update_last_garmin_sync_time(bucket, highest_synced_dt.strftime("%Y-%m-%dT%H:%M:%SZ"))

    logging.info("Garmin synchronization process completed.")

if __name__ == "__main__":
    sync_to_garmin()
