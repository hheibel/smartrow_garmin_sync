import os
import subprocess
import unittest
import sys

# Add parent directory to path to import SmartRowClient
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from smartrow_client import SmartRowClient

class TestSmartRowIntegration(unittest.TestCase):
    """
    Integration tests for SmartRow Client.
    These tests require a valid gcloud login and access to GCP secrets.
    """

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

    def test_smartrow_download_last_5_tcx(self) -> None:
        """
        Test that we can authenticate, fetch activities, and download the last 5 TCX files.
        """
        # 1. Initialize client (this also tests secret retrieval from GCP Secret Manager)
        try:
            client = SmartRowClient()
        except Exception as e:
            self.fail(f"Failed to initialize SmartRowClient (ensure GCP secrets are accessible): {e}")

        # 2. Get activities
        try:
            activities = client.get_activities()
        except Exception as e:
            self.fail(f"Failed to get activities from SmartRow: {e}")
            
        self.assertIsInstance(activities, list)
        self.assertGreaterEqual(len(activities), 0)

        if not activities:
            print("No activities found in SmartRow to download.")
            return

        # Sort activities by created date descending to get the most recent ones
        activities_sorted = sorted(activities, key=lambda x: x.get('created', ''), reverse=True)
        
        # 3. Extract the last 5 ones (or fewer if there are less than 5)
        last_5_activities = activities_sorted[:5]
        
        # 4. Retrieve TCX files and store them locally
        output_dir = os.path.join(os.path.dirname(__file__), 'downloaded_tcx')
        os.makedirs(output_dir, exist_ok=True)
        
        download_count = 0
        for i, activity in enumerate(last_5_activities):
            activity_id = activity.get('id')
            public_id = activity.get('public_id')
            
            self.assertIsNotNone(activity_id, "Activity is missing 'id'")
            self.assertIsNotNone(public_id, "Activity is missing 'public_id'. TCX download requires public_id.")
            
            try:
                tcx_data = client.get_activity(str(public_id), format="tcx")
            except Exception as e:
                # Some activities might not have a TCX file, we can continue to the next
                print(f"Failed to fetch TCX for activity {activity_id}: {e}")
                continue
                
            self.assertTrue(isinstance(tcx_data, str) and len(tcx_data) > 0, "TCX data should be a non-empty string")
            
            # Save locally
            # Clean up timestamp for filename on Windows
            timestamp = activity.get('created', f'activity_{i}').replace(':', '-').replace('.', '-')
            filename = f"smartrow_{activity_id}_{timestamp}.tcx"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(tcx_data)
                
            self.assertTrue(os.path.exists(filepath))
            download_count += 1
            
        print(f"Successfully downloaded {download_count} TCX files to {output_dir}")
        if len(last_5_activities) > 0:
            self.assertGreater(download_count, 0, "Failed to download any TCX files out of the last 5 activities, perhaps they have no TCX data.")

if __name__ == '__main__':
    unittest.main()
