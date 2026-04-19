import os
import unittest
from unittest.mock import patch, MagicMock
from google.cloud import storage
from config import PROJECT_ID, GCS_BUCKET_NAME
from utils import init_garmin_client

class TestGarminTokenstoreIntegration(unittest.TestCase):
    def setUp(self):
        self.storage_client = storage.Client(project=PROJECT_ID)
        self.bucket = self.storage_client.bucket(GCS_BUCKET_NAME)
        self.test_blob_name = "testing_garmin_tokenstore/garmin_tokens.json"
        
        blob = self.bucket.blob(self.test_blob_name)
        if blob.exists():
            blob.delete()
            
    def tearDown(self):
        blob = self.bucket.blob(self.test_blob_name)
        if blob.exists():
            blob.delete()

    @patch('utils.read_credentials')
    @patch('garminconnect.Garmin.login')
    @patch('garminconnect.client.Client.dump')
    def test_init_garmin_client_no_existing_token_uploads_to_gcs(self, mock_dump, mock_login, mock_read_credentials):
        mock_read_credentials.return_value = ("testuser", "testpass")
        
        def mock_login_impl(tokenstore=None, *args, **kwargs):
            if tokenstore:
                if not os.path.exists(tokenstore) or os.path.getsize(tokenstore) == 0:
                    raise Exception("Mock cached login failure")
            return (None, None)
        mock_login.side_effect = mock_login_impl
        
        def mock_dump_impl(path):
            with open(path, "w") as f:
                f.write('{"mock": "generated_token"}')
        mock_dump.side_effect = mock_dump_impl
        
        original_blob = storage.Bucket.blob
        
        # We track how many times upload and download were natively called
        upload_mock = MagicMock()
        download_mock = MagicMock()
        exists_mock = MagicMock(return_value=False)
        
        def side_effect_blob(bucket_instance, name, *args, **kwargs):
            if name == "garmin_tokenstore/garmin_tokens.json":
                # We return an entirely mocked blob that intercepts calls to test the counts!
                # Since we don't actually need to hit GCS to verify logic execution.
                # BUT the user said "We can read and write test blobs in a texting folder on GCS"!
                name = self.test_blob_name
            return original_blob(bucket_instance, name, *args, **kwargs)
            
        with patch('google.cloud.storage.Bucket.blob', side_effect=side_effect_blob, autospec=True):
            _ = init_garmin_client()
            
            blob = self.bucket.blob(self.test_blob_name)
            self.assertTrue(blob.exists(), "The fallback logic did not upload the token to GCS")
            
            self.assertEqual(mock_login.call_count, 2)

    @patch('utils.read_credentials')
    @patch('garminconnect.Garmin.login')
    @patch('garminconnect.client.Client.dump')
    def test_init_garmin_client_downloads_existing_token_from_gcs(self, mock_dump, mock_login, mock_read_credentials):
        mock_read_credentials.return_value = ("testuser", "testpass")
        
        def mock_login_impl(tokenstore=None, *args, **kwargs):
            if tokenstore:
                if not os.path.exists(tokenstore) or os.path.getsize(tokenstore) == 0:
                    raise Exception("Mock cached login failure")
            return (None, None)
        mock_login.side_effect = mock_login_impl
        
        blob = self.bucket.blob(self.test_blob_name)
        blob.upload_from_string('{"validated": "gcs_token"}')
        
        original_blob = storage.Bucket.blob
        def side_effect_blob(bucket_instance, name, *args, **kwargs):
            if name == "garmin_tokenstore/garmin_tokens.json":
                name = self.test_blob_name
            return original_blob(bucket_instance, name, *args, **kwargs)
            
        with patch('google.cloud.storage.Bucket.blob', side_effect=side_effect_blob, autospec=True):
            _ = init_garmin_client()
            
            self.assertEqual(mock_login.call_count, 1)
            mock_dump.assert_not_called()

