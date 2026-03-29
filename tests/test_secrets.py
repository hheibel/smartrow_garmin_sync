import unittest
import os
from google.cloud import secretmanager

class TestSecretManager(unittest.TestCase):
    def test_access_test_password(self):
        """
        Verifies that the Google Cloud Secret Manager client can successfully
        authenticate and retrieve the 'test-password' secret.
        """
        # We use the environment variable if available, otherwise default to the project ID
        project_id = os.environ.get("PROJECT_ID", "garmin-syncher-491619")
        
        try:
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{project_id}/secrets/test-credentials/versions/latest"
            
            response = client.access_secret_version(request={"name": name})
            payload = response.payload.data.decode("UTF-8")
            
            # Assert that we actually retrieved a non-empty string
            self.assertTrue(len(payload) > 0, "The retrieved test password payload is empty.")
            
        except Exception as e:
            self.fail(f"Failed to access the test-password secret. Error: {e}")

if __name__ == '__main__':
    unittest.main()
