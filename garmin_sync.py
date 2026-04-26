"""Synchronises processed FIT activity files from GCS to Garmin Connect."""

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

from absl import logging
from google.cloud import storage

from config import GCS_BUCKET_NAME
from config import PROJECT_ID
from csv_utils import parse_smartrow_csv
from fit_utils import build_fit_from_csv
from fit_utils import rewrite_fit_file_attributes
from utils import init_garmin_client

GARMIN_SYNC_STATE_FILE = "garmin_sync_state.json"


@dataclass
class ActivityData:
    """Container for activity file names and metadata."""

    base_name: str
    created: datetime  # Derived solely from the filename timestamp

    @property
    def fit_file(self) -> str:
        """Returns the GCS filename for the FIT file."""
        return f"{self.base_name}.fit"

    @property
    def json_file(self) -> str:
        """Returns the GCS filename for the JSON metadata file."""
        return f"{self.base_name}.json"

    @property
    def csv_file(self) -> str:
        """Returns the GCS filename for the per-stroke CSV file."""
        return f"{self.base_name}.csv"


def get_last_garmin_sync_time(bucket: storage.Bucket) -> str:
    """Read the last synced activity creation time from GCS.

    Args:
        bucket: The GCS bucket containing the sync state.

    Returns:
        The ISO timestamp of the last synced activity, or an empty string.
    """
    blob = bucket.blob(GARMIN_SYNC_STATE_FILE)
    if blob.exists():
        try:
            content = blob.download_as_text()
            data = json.loads(content)
            return str(data.get("last_synced_created", ""))
        except Exception as e:
            logging.warning(
                "Failed to parse Garmin sync state file from GCS: %s", e
            )
    return ""


def update_last_garmin_sync_time(
    bucket: storage.Bucket, last_synced_created: str
) -> None:
    """Update the GCS state file with the newest synced activity time.

    Args:
        bucket: The GCS bucket to update.
        last_synced_created: The ISO timestamp of the newest synced activity.
    """
    blob = bucket.blob(GARMIN_SYNC_STATE_FILE)
    blob.upload_from_string(
        json.dumps({"last_synced_created": last_synced_created}, indent=4),
        content_type="application/json",
    )


def parse_date_from_filename(filename: str) -> datetime:
    """Extracts the date and time from the activity filename.

    Args:
        filename: Filename in format YYYYMMDD_HHMMSS_<activity_id>.fit

    Returns:
        A datetime object in UTC.
    """
    try:
        # 20260305_065350_1234.fit -> 20260305_065350
        date_part = filename.split("_", 2)[:2]
        date_str = "_".join(date_part)
        return datetime.strptime(date_str, "%Y%m%d_%H%M%S").replace(
            tzinfo=timezone.utc
        )
    except Exception as e:
        logging.error(
            "Failed to parse date from filename '%s': %s", filename, e
        )
        return datetime.min.replace(tzinfo=timezone.utc)


def check_overlap(
    fit_start_dt: datetime,
    fit_duration_sec: int,
    garmin_activities: list[dict[str, Any]],
) -> bool:
    """Checks if a FIT activity overlaps with existing Garmin activities.

    Args:
        fit_start_dt: Start time of the activity to check.
        fit_duration_sec: Duration in seconds.
        garmin_activities: List of recent Garmin activities to check against.

    Returns:
        True if an overlap is detected, False otherwise.
    """
    # Add a minimum 1 second duration for overlap calculation
    fit_end_dt = fit_start_dt + timedelta(seconds=max(fit_duration_sec, 1))

    for garmin_activity in garmin_activities:
        garmin_start_str = garmin_activity.get("startTimeGMT")
        garmin_duration_sec = garmin_activity.get(
            "duration", garmin_activity.get("elapsedDuration", 0)
        )
        if not garmin_start_str:
            continue

        try:
            # Garmin startTimeGMT is "YYYY-MM-DD HH:MM:SS"
            garmin_start_dt = datetime.strptime(
                garmin_start_str, "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=timezone.utc)
            garmin_end_dt = garmin_start_dt + timedelta(
                seconds=garmin_duration_sec
            )

            # Temporal overlap collision calculation
            if max(fit_start_dt, garmin_start_dt) < min(
                fit_end_dt, garmin_end_dt
            ):
                return True
        except ValueError as e:
            logging.debug(
                "Could not parse garmin start time: %s - %s",
                garmin_start_str,
                e,
            )
            continue

    return False


def filter_recent(
    activities: list[ActivityData], weeks: int = 3
) -> list[ActivityData]:
    """Filters activities within a recent time window.

    Args:
        activities: List of activities to filter.
        weeks: Number of weeks to look back.

    Returns:
        Filtered list of activities.
    """
    threshold = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    return [a for a in activities if a.created >= threshold]


def filter_already_synced(
    activities: list[ActivityData], last_synced_dt: datetime
) -> list[ActivityData]:
    """Filters out activities older than the last synced timestamp.

    Args:
        activities: List of activities to filter.
        last_synced_dt: The timestamp of the last successful sync.

    Returns:
        Filtered list of activities.
    """
    return [a for a in activities if a.created > last_synced_dt]


def filter_duplicates(
    activities: list[ActivityData],
    garmin_activities: list[dict[str, Any]],
    bucket: storage.Bucket,
) -> list[ActivityData]:
    """Filters against Garmin activities to prevent duplicate uploads.

    Args:
        activities: Candidate activities to sync.
        garmin_activities: List of already existing Garmin activities.
        bucket: GCS bucket to download companion JSON files from.

    Returns:
        List of activities that do not overlap with existing Garmin data.
    """
    non_duplicates: list[ActivityData] = []

    for a in activities:
        json_blob = bucket.blob(a.json_file)
        fit_duration_sec = 0
        exact_created = a.created

        if json_blob.exists():
            try:
                json_content = json_blob.download_as_text()
                json_data = json.loads(json_content)
                fit_duration_sec = json_data.get("elapsed_seconds", 0)

                created_str = json_data.get("created")
                if created_str:
                    exact_created = datetime.fromisoformat(
                        created_str.replace("Z", "+00:00")
                    )
            except Exception as e:
                logging.warning(
                    "Failed to parse companion json %s: %s", a.json_file, e
                )

        if not check_overlap(
            exact_created, fit_duration_sec, garmin_activities
        ):
            non_duplicates.append(a)

    return non_duplicates


def sync_to_garmin() -> None:
    """Main execution function to sync .fit activities from GCS to Garmin."""
    logging.info("Starting Garmin synchronization process...")

    # 1. Initialize Garmin Client
    try:
        client = init_garmin_client()
        garmin_activities: list[dict[str, Any]] = client.get_activities(0, 100)
    except Exception as e:
        logging.error("Failed to login to Garmin or fetch activities: %s", e)
        return

    # 2. Access GCS Bucket
    try:
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        if not bucket.exists():
            logging.error("Bucket %s does not exist.", GCS_BUCKET_NAME)
            return
    except Exception as e:
        logging.error("Failed to access GCS bucket: %s", e)
        return

    # 3. Get sync state
    last_synced_created = get_last_garmin_sync_time(bucket)
    last_synced_dt = datetime.min.replace(tzinfo=timezone.utc)
    if last_synced_created:
        try:
            last_synced_dt = datetime.fromisoformat(
                last_synced_created.replace("Z", "+00:00")
            )
        except ValueError:
            logging.warning(
                "Could not parse last synced timestamp '%s'.",
                last_synced_created,
            )

    # 4. List and filter .fit blobs
    all_blobs = list(storage_client.list_blobs(GCS_BUCKET_NAME))
    fit_blob_names = [b.name for b in all_blobs if b.name.endswith(".fit")]

    activities: list[ActivityData] = []
    for fname in fit_blob_names:
        base_name = fname.replace(".fit", "")
        file_dt = parse_date_from_filename(fname)
        activities.append(ActivityData(base_name=base_name, created=file_dt))

    activities.sort(key=lambda x: x.created)
    activities = filter_recent(activities, weeks=3)
    # activities = filter_already_synced(activities, last_synced_dt)
    activities = filter_duplicates(activities, garmin_activities, bucket)

    if not activities:
        logging.info("No new FIT files to sync to Garmin.")
        return

    logging.info("Found %d new FIT files to sync.", len(activities))

    highest_synced_dt = last_synced_dt

    with tempfile.TemporaryDirectory() as tmp_dir:
        for activity in activities:
            logging.info("Syncing activity %s to Garmin...", activity.fit_file)
            try:
                blob = bucket.blob(activity.fit_file)
                if not blob.exists():
                    logging.warning(
                        "File %s not found in GCS.", activity.fit_file
                    )
                    continue

                raw_fit_path = os.path.join(tmp_dir, f"raw_{activity.fit_file}")
                processed_fit_path = os.path.join(tmp_dir, activity.fit_file)

                blob.download_to_filename(raw_fit_path)

                csv_blob = bucket.blob(activity.csv_file)
                if csv_blob.exists():
                    # Build enriched FIT from per-stroke CSV data
                    logging.info(
                        "CSV found for %s — building enriched FIT.",
                        activity.fit_file,
                    )
                    csv_path = os.path.join(tmp_dir, activity.csv_file)
                    csv_blob.download_to_filename(csv_path)
                    with open(csv_path, "rb") as csv_fh:
                        csv_bytes = csv_fh.read()
                    csv_records = parse_smartrow_csv(csv_bytes)
                    build_fit_from_csv(
                        template_path=raw_fit_path,
                        csv_records=csv_records,
                        output_path=processed_fit_path,
                    )
                else:
                    # Fallback: rewrite attributes on the original FIT
                    logging.info(
                        "No CSV for %s — falling back to attribute rewrite.",
                        activity.fit_file,
                    )
                    rewrite_fit_file_attributes(
                        raw_fit_path, processed_fit_path
                    )

                client.upload_activity(processed_fit_path)
                logging.info("Successfully uploaded %s.", activity.fit_file)

                highest_synced_dt = max(highest_synced_dt, activity.created)

            except Exception as e:
                logging.error(
                    "Failed to upload %s to Garmin: %s", activity.fit_file, e
                )

    # Update the state file in GCS
    if highest_synced_dt > last_synced_dt:
        update_last_garmin_sync_time(
            bucket, highest_synced_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        )

    logging.info("Garmin synchronization process completed.")


if __name__ == "__main__":
    sync_to_garmin()
