import unittest
import os
import json
from absl import logging
from unittest.mock import patch, MagicMock

import sys
# Mock google.cloud before importing smartrow_sync
sys.modules['google.cloud'] = MagicMock()
sys.modules['google.cloud.storage'] = MagicMock()

from smartrow_sync import (
    get_last_synced_time,
    update_last_synced_time,
    format_filename,
    sync_smartrow_activities,
    SYNC_STATE_FILE
)

class TestSmartRowSync(unittest.TestCase):
    """
    Test suite for the SmartRow synchronization logic.
    Validates fetching states from Google Cloud Storage, formatting filenames,
    and accurately tracking and uploading new activities.
    """
    
    def setUp(self) -> None:
        # Disable logging output during tests
        logging.set_verbosity(logging.FATAL)

    def tearDown(self) -> None:
        logging.set_verbosity(logging.INFO)

    def test_get_last_synced_time_exists(self) -> None:
        """
        Test retrieving the last synced time when the state file exists in GCS.
        Verifies that it reads the JSON content and extracts the timestamp correctly.
        """
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = True
        mock_blob.download_as_text.return_value = '{"last_synced_created": "2026-03-05T06:53:50.807Z"}'
        
        result = get_last_synced_time(mock_bucket)
        self.assertEqual(result, "2026-03-05T06:53:50.807Z")
        mock_bucket.blob.assert_called_once_with(SYNC_STATE_FILE)

    def test_get_last_synced_time_not_exists(self) -> None:
        """
        Test retrieving the last synced time when the state file is missing from GCS.
        Verifies that it correctly defaults to an empty string.
        """
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = False
        
        result = get_last_synced_time(mock_bucket)
        self.assertEqual(result, "")

    def test_update_last_synced_time(self) -> None:
        """
        Test updating the synced time state.
        Verifies that a valid JSON payload is constructed and uploaded to the GCS blob.
        """
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        
        update_last_synced_time(mock_bucket, "2026-03-06T12:00:00Z")
        mock_bucket.blob.assert_called_once_with(SYNC_STATE_FILE)
        mock_blob.upload_from_string.assert_called_once()
        
        args, kwargs = mock_blob.upload_from_string.call_args
        self.assertIn('"last_synced_created": "2026-03-06T12:00:00Z"', args[0])
        self.assertEqual(kwargs['content_type'], "application/json")

    def test_format_filename_with_millis(self) -> None:
        """
        Test formatting filenames for timestamps that include milliseconds.
        Verifies that ISO 8601 strings are correctly parsed into the concise chronological format.
        """
        filename = format_filename("2026-03-05T06:53:50.807Z", 1234, "json")
        self.assertEqual(filename, "20260305_065350_1234.json")

    def test_format_filename_without_millis(self) -> None:
        """
        Test formatting filenames for strict ISO timestamps lacking milliseconds.
        Verifies fallback timestamp formatting works properly.
        """
        filename = format_filename("2026-03-05T06:53:50Z", 5678, "tcx")
        self.assertEqual(filename, "20260305_065350_5678.tcx")

    def test_timestamp_ordering_and_sorting(self) -> None:
        """
        Verify that string comparison accurately reflects chronological ordering
        for ISO 8601 timestamps.
        """
        old = "2026-03-05T06:53:50.807Z"
        newer_millis = "2026-03-05T06:53:50.808Z" # Later by 1 millisecond
        newer_sec = "2026-03-05T06:53:51.000Z"    # Later by 1 second
        newer_month = "2026-04-01T00:00:00.000Z"  # Later by almost a month
        
        # Verify > operator logic used for new_activities filtering
        self.assertTrue(newer_millis > old)
        self.assertTrue(newer_sec > newer_millis)
        self.assertTrue(newer_month > newer_sec)
        
        # Verify chronological sorting logic
        activities = [
            {"created": newer_sec},
            {"created": old},
            {"created": newer_month},
            {"created": newer_millis}
        ]
        
        # This is exactly how the script sorts:
        activities.sort(key=lambda x: x.get('created', ''))
        
        self.assertEqual(activities[0]["created"], old)
        self.assertEqual(activities[1]["created"], newer_millis)
        self.assertEqual(activities[2]["created"], newer_sec)
        self.assertEqual(activities[3]["created"], newer_month)

    @patch('smartrow_sync.convert_to_fit')
    @patch('smartrow_sync.update_last_synced_time')
    @patch('smartrow_sync.upload_to_gcs')
    @patch('smartrow_sync.storage.Client')
    @patch('smartrow_sync.SmartRowClient')
    @patch('smartrow_sync.get_last_synced_time')
    def test_sync_smartrow_activities(self, mock_get_last_synced, mock_client_class, mock_storage_client_class, mock_upload_to_gcs, mock_update_last_synced, mock_convert_to_fit) -> None:
        """
        Test the main synchronization loop for SmartRow activities.
        
        Verifies that:
        - Only activities newer than the 'last_synced' threshold are processed.
        - The TCX detail string is explicitly fetched for the filtered activities.
        - Two upload events (JSON + TCX) trigger for each new activity.
        - The last synced marker is properly updated with the absolute newest timestamp.
        """
        mock_get_last_synced.return_value = "2026-03-01T00:00:00Z"
        
        mock_smartrow_client = MagicMock()
        mock_client_class.return_value = mock_smartrow_client
        mock_smartrow_client.get_activities.return_value = [
            {"id": 1, "public_id": "uuid-1", "created": "2026-02-01T00:00:00Z"}, # Old, should be skipped
            {"id": 2, "public_id": "uuid-2", "created": "2026-03-02T10:00:00Z"}, # New
            {"id": 3, "public_id": "uuid-3", "created": "2026-03-05T06:53:50.807Z"}  # Newest
        ]
        mock_smartrow_client.get_activity_tcx.return_value = "<tcx>data</tcx>"
        
        mock_storage_client = MagicMock()
        mock_storage_client_class.return_value = mock_storage_client
        mock_bucket = MagicMock()
        mock_storage_client.bucket.return_value = mock_bucket
        mock_bucket.exists.return_value = True

        # Mock the FIT conversion return value
        mock_fit_file = MagicMock()
        mock_fit_file.to_bytes.return_value = b"fit_data"
        mock_convert_to_fit.return_value = mock_fit_file

        sync_smartrow_activities()
        
        # Should only process activities newer than 2026-03-01T00:00:00Z
        # So it should upload id 2 and id 3. JSON + TCX + FIT for each -> 6 uploads
        self.assertEqual(mock_upload_to_gcs.call_count, 6)
        
        # Verify it fetched TCX for id 2 and id 3 using their public_ids
        mock_smartrow_client.get_activity_tcx.assert_any_call("uuid-2")
        mock_smartrow_client.get_activity_tcx.assert_any_call("uuid-3")
        self.assertEqual(mock_smartrow_client.get_activity_tcx.call_count, 2)
        
        # Verify FIT conversion was called twice
        self.assertEqual(mock_convert_to_fit.call_count, 2)
        
        # Verify last synced time was updated with the newest item's timestamp
        mock_update_last_synced.assert_called_with(mock_bucket, "2026-03-05T06:53:50.807Z")

if __name__ == '__main__':
    unittest.main()
