import os
import sys
import unittest
import subprocess
from datetime import datetime, timezone

# Add parent directory to path to import main code
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from smartrow_client import SmartRowClient
from garminconnect import Garmin
from utils import init_garmin_client
from garmin_sync import check_overlap

class TestGarminDuplication(unittest.TestCase):
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

    def test_verify_duplications(self) -> None:
        """
        Downloads 30 recent activities from SmartRow and 100 from Garmin.
        Prints exactly which ones overlap/already exist.
        """
        print("\n--- Verifying Garmin Duplications ---")
        
        # 1. Fetch Garmin Activities
        try:
            garmin_client = init_garmin_client()
            garmin_activities = garmin_client.get_activities(0, 100)
            print(f"Fetched {len(garmin_activities)} recent workouts from Garmin Connect.")
        except Exception as e:
            self.fail(f"Failed to fetch Garmin workouts securely: {e}")
            
        # 2. Fetch SmartRow Activities from Fake GCS Mock Bucket
        from tests.integration_tests.fake_gcs import FakeStorageClient
        import json
        
        mock_gcs_root = os.path.join(os.path.dirname(__file__), 'mock_gcs_bucket')
        fake_client = FakeStorageClient(local_root=mock_gcs_root)
        import config
        fake_bucket = fake_client.bucket(config.GCS_BUCKET_NAME)
        
        # Manually browse the local mock bucket directory for .json files
        bucket_dir = os.path.join(mock_gcs_root, config.GCS_BUCKET_NAME)
        smartrow_activities = []
        
        if os.path.exists(bucket_dir):
            for fname in os.listdir(bucket_dir):
                if fname.endswith(".json") and fname != "sync_state.json":
                    with open(os.path.join(bucket_dir, fname), 'r', encoding='utf-8') as f:
                        smartrow_activities.append(json.load(f))
        
        # Sort chronologically, then pick the last 30
        smartrow_activities.sort(key=lambda x: x.get('created', ''))
        last_30_smartrow = smartrow_activities[-30:] if len(smartrow_activities) > 30 else smartrow_activities
        print(f"Evaluating {len(last_30_smartrow)} recent workouts from Mocked GCS...\n")
        
        # 3. Check for Intersections
        duplication_count = 0
        
        for sr_activity in last_30_smartrow:
            created_str = sr_activity.get('created')
            sr_id = sr_activity.get('id', 'Unknown')
            duration_sec = sr_activity.get('elapsed_seconds', 0)
            
            if not created_str:
                continue
                
            try:
                sr_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except ValueError:
                print(f"Could not parse date {created_str} for SR Activity {sr_id}")
                continue
                
            # Perform Evaluation
            is_dup = check_overlap(sr_dt, duration_sec, garmin_activities)
            
            if is_dup:
                print(f"[DUPLICATE DETECTED] SmartRow Activity {sr_id} on {created_str} overlaps directly with an existing Garmin workout.")
                duplication_count += 1
                
        print(f"\nCompleted verification. {duplication_count} out of {len(last_30_smartrow)} analyzed SmartRow workouts explicitly exist in the recent Garmin 100.")

if __name__ == '__main__':
    unittest.main()
