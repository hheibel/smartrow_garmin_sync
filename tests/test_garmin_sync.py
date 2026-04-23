import unittest
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from unittest.mock import MagicMock
from unittest.mock import patch

from absl import logging

from garmin_sync import GARMIN_SYNC_STATE_FILE
from garmin_sync import ActivityData
from garmin_sync import filter_already_synced
from garmin_sync import filter_duplicates
from garmin_sync import filter_recent

# Mock google.cloud before importing garmin_sync
from garmin_sync import get_last_garmin_sync_time
from garmin_sync import parse_date_from_filename
from garmin_sync import sync_to_garmin
from garmin_sync import update_last_garmin_sync_time


class TestGarminSync(unittest.TestCase):
    def setUp(self) -> None:
        # Disable logging output during tests
        logging.set_verbosity(logging.FATAL)

    def tearDown(self) -> None:
        logging.set_verbosity(logging.INFO)

    def test_get_last_garmin_sync_time_exists(self) -> None:
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = True
        mock_blob.download_as_text.return_value = (
            '{"last_synced_created": "2026-03-05T06:53:50Z"}'
        )

        result = get_last_garmin_sync_time(mock_bucket)
        self.assertEqual(result, "2026-03-05T06:53:50Z")

    def test_update_last_garmin_sync_time(self) -> None:
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        update_last_garmin_sync_time(mock_bucket, "2026-03-06T12:00:00Z")
        mock_blob.upload_from_string.assert_called_once()

        args, _ = mock_blob.upload_from_string.call_args
        self.assertIn('"last_synced_created": "2026-03-06T12:00:00Z"', args[0])

    def test_parse_date_from_filename_valid(self) -> None:
        filename = "20260305_065350_1234.fit"
        dt = parse_date_from_filename(filename)
        expected = datetime(2026, 3, 5, 6, 53, 50, tzinfo=timezone.utc)
        self.assertEqual(dt, expected)

    def test_parse_date_from_filename_invalid(self) -> None:
        filename = "invalid_filename.fit"
        dt = parse_date_from_filename(filename)
        self.assertEqual(dt, datetime.min.replace(tzinfo=timezone.utc))

    def test_activity_data_properties(self) -> None:
        a = ActivityData(
            "20260305_065350", datetime(2026, 3, 5, 0, 0, tzinfo=timezone.utc)
        )
        self.assertEqual(a.fit_file, "20260305_065350.fit")
        self.assertEqual(a.json_file, "20260305_065350.json")

    def test_filter_recent(self) -> None:
        now = datetime.now(timezone.utc)
        a1 = ActivityData("recent", now - timedelta(days=5))
        a2 = ActivityData("old", now - timedelta(days=25))
        activities = [a1, a2]

        filtered = filter_recent(activities, weeks=3)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].base_name, "recent")

    def test_filter_already_synced(self) -> None:
        dt = datetime(2026, 3, 20, tzinfo=timezone.utc)
        a1 = ActivityData("new", dt + timedelta(days=1))
        a2 = ActivityData("old", dt - timedelta(days=1))

        filtered = filter_already_synced([a1, a2], dt)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].base_name, "new")

    @patch("garmin_sync.check_overlap")
    def test_filter_duplicates(self, mock_check_overlap) -> None:
        a1 = ActivityData("unique", datetime.now(timezone.utc))
        a2 = ActivityData("dup", datetime.now(timezone.utc))

        mock_bucket = MagicMock()

        def mock_blob(name):
            b = MagicMock()
            b.exists.return_value = True
            if name == "dup.json":
                b.download_as_text.return_value = '{"elapsed_seconds": 99}'
            else:
                b.download_as_text.return_value = '{"elapsed_seconds": 0}'
            return b

        mock_bucket.blob.side_effect = mock_blob

        # mock returns True if sec == 99
        mock_check_overlap.side_effect = lambda dt, sec, garmin: (
            True if sec == 99 else False
        )

        filtered = filter_duplicates([a1, a2], [], mock_bucket)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].base_name, "unique")

    @patch("garmin_sync.rewrite_fit_file_attributes")
    @patch("garmin_sync.update_last_garmin_sync_time")
    @patch("garmin_sync.storage.Client")
    @patch("garmin_sync.get_last_garmin_sync_time")
    @patch("garmin_sync.init_garmin_client")
    def test_sync_to_garmin_filtering(
        self,
        mock_init_garmin_client,
        mock_get_last_sync,
        mock_storage_client_class,
        mock_update_last_sync,
        mock_rewrite,
    ) -> None:
        # Setup today for consistent testing (let's say 2026-03-30)
        today = datetime(2026, 3, 30, 12, 0, 0, tzinfo=timezone.utc)

        with patch("garmin_sync.datetime") as mock_datetime:
            mock_datetime.now.return_value = today
            mock_datetime.strptime = datetime.strptime
            mock_datetime.fromisoformat = datetime.fromisoformat
            mock_datetime.min = datetime.min

            # Setup: State is 2 weeks before today (2026-03-16)
            mock_get_last_sync.return_value = "2026-03-16T12:00:00Z"

            # Setup Garmin mock
            mock_garmin = MagicMock()
            mock_init_garmin_client.return_value = mock_garmin

            # Setup GCS mock with multiple blobs
            mock_storage_client = MagicMock()
            mock_storage_client_class.return_value = mock_storage_client
            mock_bucket = MagicMock()
            mock_storage_client.bucket.return_value = mock_bucket
            mock_bucket.exists.return_value = True

            def mock_bucket_blob(name):
                b = MagicMock()
                if name == GARMIN_SYNC_STATE_FILE:
                    b.exists.return_value = True
                    b.download_as_text.return_value = (
                        '{"last_synced_created": "2026-03-16T12:00:00Z"}'
                    )
                else:
                    b.exists.return_value = True
                    b.download_as_bytes.return_value = b"data"
                    b.download_as_text.return_value = "{}"  # empty json
                return b

            mock_bucket.blob.side_effect = mock_bucket_blob

            # Create blobs for list_blobs:
            # 1. 2026-03-01 (4 weeks ago) -> failsafe should skip
            # 2. 2026-03-10 (older than state) -> should skip
            # 3. 2026-03-20 (newer than state, within 3 weeks) -> should sync
            # 4. 2026-03-25 (newer than state, within 3 weeks) -> should sync
            blob1 = MagicMock()
            blob1.name = "20260301_100000_1.fit"
            blob2 = MagicMock()
            blob2.name = "20260310_100000_2.fit"
            blob3 = MagicMock()
            blob3.name = "20260320_100000_3.fit"
            blob4 = MagicMock()
            blob4.name = "20260325_100000_4.fit"

            mock_storage_client.list_blobs.return_value = [
                blob1,
                blob2,
                blob3,
                blob4,
            ]

            sync_to_garmin()

            # Should have uploaded exactly two files
            self.assertEqual(mock_garmin.upload_activity.call_count, 2)

            # Verify latest state was updated to 2026-03-25
            mock_update_last_sync.assert_called_with(
                mock_bucket, "2026-03-25T10:00:00Z"
            )


if __name__ == "__main__":
    unittest.main()
