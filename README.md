# smartrow_garmin_sync

This project automates the synchronization of workout activities from [SmartRow](https://smartrow.fit/) to [Garmin Connect](https://connect.garmin.com/).

## Core Application: `main.py`

`main.py` serves as the primary entry point for the `garmin-syncher` application. It acts as an automated pipeline to securely fetch new workouts from your SmartRow profile, safely archive them in Google Cloud Storage (GCS), and subsequently upload the relevant track data to your Garmin Connect account.

## Built Phases

The synchronization pipeline consists of two distinct phases executed sequentially:

### Phase 1: SmartRow to GCS Synchronization (`sync_smartrow_activities`)
- Connects to the SmartRow API and retrieves all user activity records.
- Compares the activities against a remote sync state stored in GCS to identify newly recorded workouts.
- Downloads the summary data (JSON) and exact track data (TCX) from SmartRow.
- Converts the TCX files locally into Garmin's proprietary `.fit` format.
- Archives the JSON, TCX, and converted FIT files in a Google Cloud Storage bucket.
- Updates the remote sync state (`sync_state.json`) once complete to ensure idempotent runs.

### Phase 2: GCS to Garmin Connect Synchronization (`sync_to_garmin`)
- Scans the Google Cloud Storage bucket for unprocessed `.fit` files.
- Uses a separate state file (`garmin_sync_state.json`) to track which files have already been pushed to Garmin Connect.
- Authenticates securely with Garmin Connect.
- Excludes files that are older than 3 weeks as an automatic failsafe.
- Pushes the new `.fit` activity tracks directly to Garmin Connect.
- Updates the Garmin remote sync state (`garmin_sync_state.json`) upon completion.

## Google Cloud Storage (GCS) Structure

The output and state management files are structured in a flat configuration at the root level of your configured GCS Bucket. 

```text
gs://[YOUR_GCS_BUCKET_NAME]/
│
├── sync_state.json                        # Tracks the timestamp of the last activity pulled from SmartRow
├── garmin_sync_state.json                 # Tracks the timestamp of the last activity pushed to Garmin Connect
│
├── YYYYMMDD_HHMMSS_<activity_id>.json     # Raw JSON summary response from the SmartRow API
├── YYYYMMDD_HHMMSS_<activity_id>.tcx      # Exported raw track data from SmartRow
└── YYYYMMDD_HHMMSS_<activity_id>.fit      # Converted Garmin-compatible track data
```

*(For example: `20260305_065350_1234.fit`)*

This flat structure allows for straightforward chronological sorting via filename conventions, while neatly grouping records belonging to the same workout by sharing the `YYYYMMDD_HHMMSS_<activity_id>` prefix.

## Local Setup

```bash
# Authenticate with Google Cloud
gcloud auth application-default login

# Activate environment
conda activate smartrow_sync

# Install dependencies
python -m pip install -r requirements.txt
```