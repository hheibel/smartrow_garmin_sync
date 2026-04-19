import os
import sys
import unittest
import json
from unittest.mock import patch
import subprocess

# Add parent directory to path to import main code
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from smartrow_sync import sync_smartrow_activities
from smartrow_client import SmartRowClient
from fake_gcs import FakeStorageClient

class TestSyncSmartRowActivities(unittest.TestCase):
    def setUp(self) -> None:
        """
        Verify that we have logged in via gcloud first.
        """
        cmd = "gcloud auth print-access-token"
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            self.fail(f"gcloud authentication failed or gcloud not found. Please assure you have logged in via gcloud.\nError output:\n{result.stderr}")

        # Setup local mock directory for GCS
        self.mock_gcs_root = os.path.join(os.path.dirname(__file__), 'mock_gcs_bucket')
        os.makedirs(self.mock_gcs_root, exist_ok=True)

    @patch('smartrow_sync.storage.Client')
    def test_sync_smartrow_activities_limits_to_10(self, mock_storage_client_cls) -> None:
        """
        Test that sync_smartrow_activities processes at most the last 10 workouts.
        We seed the local mock GCS sync_state.json with the timestamp of the 11th from last activity.
        """
        import config
        bucket_name = config.GCS_BUCKET_NAME

        # Instantiate our Fake Storage client
        fake_client = FakeStorageClient(local_root=self.mock_gcs_root)
        mock_storage_client_cls.return_value = fake_client

        # Initialize real SmartRowClient to fetch activities list and determine 11th timestamp
        try:
            client = SmartRowClient()
            activities = client.get_activities()
        except Exception as e:
            self.fail(f"Failed to initialize SmartRowClient or fetch activities: {e}")

        # Sort activities chronologically (oldest first as they do in main script)
        activities.sort(key=lambda x: x.get('created', ''))

        if len(activities) > 10:
            # We want to process only the last 10.
            # So the highest synced activity should be the 11th from the end: activities[-11]
            last_synced_activity = activities[-11]
            last_synced_timestamp = last_synced_activity.get('created', '')
            
            fake_bucket = fake_client.bucket(bucket_name)
            state_blob = fake_bucket.blob("sync_state.json")
            state_blob.upload_from_string(json.dumps({"last_synced_created": last_synced_timestamp}))
            
            print(f"Pre-seeded sync_state.json to exclude all but the last 10 activities (Timestamp cutoff: {last_synced_timestamp})")
        else:
            print("Found 10 or fewer activities on the account, testing without pre-seeding state.")

        # Execute the sync function. This will use the patched GCS client.
        sync_smartrow_activities()

        # Verification
        # Check files inside the mock bucket
        bucket_dir = os.path.join(self.mock_gcs_root, bucket_name)
        self.assertTrue(os.path.exists(bucket_dir), "Bucket directory was not created.")
        
        # Look for sync_state.json
        state_file_path = os.path.join(bucket_dir, "sync_state.json")
        self.assertTrue(os.path.exists(state_file_path), "sync_state.json should exist")
        
        # Verify it downloaded some files (up to 10 activities, meaning up to 30 files if all have TCX/FIT)
        files = os.listdir(bucket_dir)
        fit_files = [f for f in files if f.endswith('.fit')]
        tcx_files = [f for f in files if f.endswith('.tcx')]
        json_files = [f for f in files if f.endswith('.json') and f != "sync_state.json"]

        print(f"Found {len(json_files)} JSON, {len(tcx_files)} TCX, and {len(fit_files)} FIT files in the mocked GCS bucket.")
        
        self.assertLessEqual(len(json_files), 10, "Should have synced at most 10 JSON activities.")

        # Ensure that the latest state was updated
        with open(state_file_path, 'r', encoding='utf-8') as f:
            state_data = json.load(f)
            self.assertIn("last_synced_created", state_data)
            self.assertGreater(state_data["last_synced_created"], activities[-11].get('created', '') if len(activities) > 10 else "")

if __name__ == '__main__':
    unittest.main()
