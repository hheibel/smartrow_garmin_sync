import unittest
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

# Mock google.cloud before importing garmin_sync
sys.modules['google.cloud'] = MagicMock()
sys.modules['google.cloud.storage'] = MagicMock()
sys.modules['garminconnect'] = MagicMock()

from garmin_sync import (
    get_last_garmin_sync_time,
    update_last_garmin_sync_time,
    parse_date_from_filename,
    sync_to_garmin,
    GARMIN_SYNC_STATE_FILE
)

class TestGarminSync(unittest.TestCase):
    
    def setUp(self):
        # Disable logging output during tests
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_get_last_garmin_sync_time_exists(self):
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = True
        mock_blob.download_as_text.return_value = '{"last_synced_created": "2026-03-05T06:53:50Z"}'
        
        result = get_last_garmin_sync_time(mock_bucket)
        self.assertEqual(result, "2026-03-05T06:53:50Z")

    def test_update_last_garmin_sync_time(self):
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        
        update_last_garmin_sync_time(mock_bucket, "2026-03-06T12:00:00Z")
        mock_blob.upload_from_string.assert_called_once()
        
        args, _ = mock_blob.upload_from_string.call_args
        self.assertIn('"last_synced_created": "2026-03-06T12:00:00Z"', args[0])

    def test_parse_date_from_filename_valid(self):
        filename = "20260305_065350_1234.fit"
        dt = parse_date_from_filename(filename)
        expected = datetime(2026, 3, 5, 6, 53, 50, tzinfo=timezone.utc)
        self.assertEqual(dt, expected)

    def test_parse_date_from_filename_invalid(self):
        filename = "invalid_filename.fit"
        dt = parse_date_from_filename(filename)
        self.assertEqual(dt, datetime.min.replace(tzinfo=timezone.utc))

    @patch('garmin_sync.update_last_garmin_sync_time')
    @patch('garmin_sync.storage.Client')
    @patch('garmin_sync.Garmin')
    @patch('garmin_sync.get_last_garmin_sync_time')
    @patch('garmin_sync.read_credentials')
    def test_sync_to_garmin_filtering(self, mock_read_credentials, mock_get_last_sync, mock_garmin_class, mock_storage_client_class, mock_update_last_sync):
        # Setup today for consistent testing (let's say 2026-03-30)
        today = datetime(2026, 3, 30, 12, 0, 0, tzinfo=timezone.utc)
        
        with patch('garmin_sync.datetime') as mock_datetime:
            mock_datetime.now.return_value = today
            mock_datetime.strptime = datetime.strptime
            mock_datetime.fromisoformat = datetime.fromisoformat
            mock_datetime.min = datetime.min
            
            # Setup: State is 2 weeks before today (2026-03-16)
            mock_get_last_sync.return_value = "2026-03-16T12:00:00Z"
            mock_read_credentials.return_value = ("user", "pass")
            
            # Setup Garmin mock
            mock_garmin = MagicMock()
            mock_garmin_class.return_value = mock_garmin
            
            # Setup GCS mock with multiple blobs
            mock_storage_client = MagicMock()
            mock_storage_client_class.return_value = mock_storage_client
            mock_bucket = MagicMock()
            mock_storage_client.bucket.return_value = mock_bucket
            mock_bucket.exists.return_value = True
            
            # Create blobs:
            # 1. 2026-03-01 (4 weeks ago) -> failsafe should skip
            # 2. 2026-03-10 (older than state) -> should skip
            # 3. 2026-03-20 (newer than state, within 3 weeks) -> should sync
            # 4. 2026-03-25 (newer than state, within 3 weeks) -> should sync
            blob1 = MagicMock(); blob1.name = "20260301_100000_1.fit"; blob1.download_as_bytes.return_value = b"data1"
            blob2 = MagicMock(); blob2.name = "20260310_100000_2.fit"; blob2.download_as_bytes.return_value = b"data2"
            blob3 = MagicMock(); blob3.name = "20260320_100000_3.fit"; blob3.download_as_bytes.return_value = b"data3"
            blob4 = MagicMock(); blob4.name = "20260325_100000_4.fit"; blob4.download_as_bytes.return_value = b"data4"
            
            mock_storage_client.list_blobs.return_value = [blob1, blob2, blob3, blob4]
            
            sync_to_garmin()
            
            # Should have uploaded exactly two files
            self.assertEqual(mock_garmin.upload_activity.call_count, 2)
            
            # Verify latest state was updated to 2026-03-25
            mock_update_last_sync.assert_called_with(mock_bucket, "2026-03-25T10:00:00Z")

if __name__ == '__main__':
    unittest.main()
