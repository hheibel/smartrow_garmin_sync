"""Downloads SmartRow activities and stores FIT and CSV files in GCS."""

import json
from datetime import datetime

from absl import logging
from google.cloud import storage

from config import GCS_BUCKET_NAME
from config import PROJECT_ID
from smartrow_client import SmartRowClient

SYNC_STATE_FILE = "sync_state.json"


def get_last_synced_time(bucket: storage.Bucket) -> str:
    """Read the last synced activity creation time from the GCS state file.

    Args:
        bucket: The GCS bucket containing the sync state.

    Returns:
        The ISO timestamp of the last synced activity, or an empty
        string if not found.
    """
    blob = bucket.blob(SYNC_STATE_FILE)
    if blob.exists():
        try:
            content = blob.download_as_text()
            data = json.loads(content)
            return str(data.get("last_synced_created", ""))
        except Exception as e:
            logging.warning(
                "Failed to parse sync state file from GCS: %s."
                " Treating as empty.",
                e,
            )
    return ""


def update_last_synced_time(
    bucket: storage.Bucket, last_synced_created: str
) -> None:
    """Update the GCS state file with the newest synced activity time.

    Args:
        bucket: The GCS bucket to update.
        last_synced_created: The ISO timestamp of the newest synced activity.
    """
    blob = bucket.blob(SYNC_STATE_FILE)
    blob.upload_from_string(
        json.dumps({"last_synced_created": last_synced_created}, indent=4),
        content_type="application/json",
    )


def format_filename(created_str: str, activity_id: int, extension: str) -> str:
    """Format the filename as YYYYMMDD_HHMMSS_<activity_id>.<extension>.

    Args:
        created_str: The ISO timestamp string.
        activity_id: The unique ID of the activity.
        extension: The file extension (e.g., 'json', 'fit').

    Returns:
        A formatted filename string.
    """
    try:
        # Expected format: 2026-03-05T06:53:50.807Z
        # Some timestamps might not have milliseconds, so we handle both
        if "." in created_str:
            dt = datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        else:
            dt = datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%SZ")
        prefix = dt.strftime("%Y%m%d_%H%M%S")
    except ValueError as e:
        logging.warning(
            "Could not parse timestamp '%s' for activity %d: %s",
            created_str,
            activity_id,
            e,
        )
        # Fallback to sanitized string
        prefix = (
            created_str.replace(":", "")
            .replace("-", "")
            .replace("T", "_")
            .split(".")[0]
        )

    return f"{prefix}_{activity_id}.{extension}"


def upload_to_gcs(
    bucket: storage.Bucket,
    filename: str,
    content: bytes | str,
    content_type: str,
) -> None:
    """Uploads string or binary content to a GCS bucket.

    Args:
        bucket: The GCS bucket to upload to.
        filename: The target filename in the bucket.
        content: The content to upload (bytes or string).
        content_type: The MIME type of the content.

    Examples:
        # JSON (string)
        upload_to_gcs(bucket, "data.json", json.dumps(data), "application/json")

        # Binary (bytes)
        upload_to_gcs(
            bucket, "activity.fit", fit_bytes, "application/octet-stream"
        )
    """
    blob = bucket.blob(filename)
    blob.upload_from_string(content, content_type=content_type)
    logging.info("Uploaded %s to gs://%s/", filename, bucket.name)


def sync_smartrow_activities() -> None:
    """Main execution function to sync SmartRow activities to GCS."""
    logging.info("Starting SmartRow sync process...")

    try:
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        # Verify bucket exists
        if not bucket.exists():
            logging.error(
                "Bucket %s does not exist in project %s.",
                GCS_BUCKET_NAME,
                PROJECT_ID,
            )
            return
    except Exception as e:
        logging.error(
            "Failed to initialize GCP Storage client or access bucket: %s", e
        )
        return

    last_synced: str = get_last_synced_time(bucket)
    if last_synced:
        logging.info("Last synced activity timestamp: %s", last_synced)
    else:
        logging.info(
            "No prior sync state found. Will sync all available activities."
        )

    client = SmartRowClient()

    try:
        activities = client.get_activities()
    except Exception as e:
        logging.error("Failed to retrieve activities from SmartRow: %s", e)
        return

    # Sort activities chronologically by 'created' timestamp (oldest first)
    activities.sort(key=lambda x: x.get("created", ""))

    new_activities = [
        a for a in activities if str(a.get("created", "")) > last_synced
    ]

    if not new_activities:
        logging.info("No new activities to sync.")
        return

    logging.info("Found %d new activities to sync.", len(new_activities))

    highest_synced: str = last_synced

    for activity in new_activities:
        activity_id = activity.get("id")
        public_id = activity.get("public_id")
        created_str = str(activity.get("created", ""))

        if not activity_id or not created_str or not public_id:
            logging.warning(
                "Skipping activity due to missing id, public_id"
                " or created timestamp: %s",
                activity,
            )
            continue

        json_filename = format_filename(created_str, int(activity_id), "json")
        fit_filename = format_filename(created_str, int(activity_id), "fit")

        # Upload JSON
        upload_to_gcs(
            bucket,
            json_filename,
            json.dumps(activity, indent=2),
            "application/json",
        )

        # Fetch and Upload original FIT from SmartRow
        try:
            fit_data = client.get_activity(str(public_id), format="fit")
            if fit_data:
                upload_to_gcs(
                    bucket, fit_filename, fit_data, "application/octet-stream"
                )
            else:
                logging.warning(
                    "No activity FIT data available for activity %s.",
                    activity_id,
                )

        except Exception as e:
            logging.error(
                "Unexpected error processing FIT for activity %s"
                " (created date: %s): %s",
                activity_id,
                created_str,
                e,
            )
            # Continue processing next activities even if one fails

        # Fetch and upload per-stroke CSV from SmartRow
        csv_filename = format_filename(created_str, int(activity_id), "csv")
        try:
            csv_data = client.get_activity_csv(str(public_id))
            if csv_data:
                upload_to_gcs(bucket, csv_filename, csv_data, "text/csv")
            else:
                logging.warning(
                    "No CSV data returned for activity %s.", activity_id
                )
        except Exception as e:
            logging.error(
                "Unexpected error fetching CSV for activity %s: %s",
                activity_id,
                e,
            )
            # Continue — a missing CSV only affects FIT enrichment quality

        highest_synced = max(highest_synced, created_str)

    # Update the sync state file exactly once at the end.
    if highest_synced and highest_synced != last_synced:
        update_last_synced_time(bucket, highest_synced)

    logging.info("Sync process completed successfully.")
