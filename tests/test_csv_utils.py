import os
import unittest

from csv_utils import CsvStrokeRecord
from csv_utils import parse_smartrow_csv


class TestParseSmarrowCsv(unittest.TestCase):
    def _sample_csv_bytes(self) -> bytes:
        path = os.path.join(
            os.path.dirname(__file__), "test_data", "sample_activity.csv"
        )
        with open(path, "rb") as fh:
            return fh.read()

    def test_parse_returns_correct_count(self) -> None:
        records = parse_smartrow_csv(self._sample_csv_bytes())
        self.assertEqual(len(records), 10)

    def test_first_stroke_values(self) -> None:
        records = parse_smartrow_csv(self._sample_csv_bytes())
        first = records[0]
        self.assertEqual(first.stroke_num, 1)
        self.assertEqual(first.elapsed_seconds, 2)
        self.assertEqual(first.interval_num, 1)
        self.assertAlmostEqual(first.distance_m, 8.0)
        self.assertAlmostEqual(first.actual_power_w, 139.0)
        self.assertEqual(first.heart_rate_bpm, 79)
        self.assertAlmostEqual(first.stroke_rate_spm, 28.9)
        self.assertAlmostEqual(first.actual_split_s, 136.0)

    def test_timestamp_parsed_correctly(self) -> None:
        records = parse_smartrow_csv(self._sample_csv_bytes())
        # 2026-04-24T05:44:58Z = 1777009498000 ms since epoch
        self.assertEqual(records[0].timestamp_ms, 1777009498000)

    def test_force_curve_length(self) -> None:
        records = parse_smartrow_csv(self._sample_csv_bytes())
        self.assertEqual(len(records[0].force_curve_n), 25)

    def test_sorted_ascending(self) -> None:
        records = parse_smartrow_csv(self._sample_csv_bytes())
        timestamps = [r.timestamp_ms for r in records]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_raises_on_empty_bytes(self) -> None:
        with self.assertRaises(ValueError):
            parse_smartrow_csv(b"")

    def test_raises_on_missing_required_column(self) -> None:
        bad_csv = b"Stroke (#),Second (#)\n1,2\n"
        with self.assertRaises(ValueError):
            parse_smartrow_csv(bad_csv)

    def test_skips_unparseable_timestamp_row(self) -> None:
        header = (
            "Stroke (#),Second (#),Interval (#),Timestamp (UTC),"
            "Distance (m),Work (J),Actual power (W),Average power (W),"
            "Actual split (s),Average split (s),Stroke rate (SPM),"
            "Heart rate (bpm),Stroke length (cm)"
        )
        good = (
            "1,2,1,2026-04-24T05:44:58Z,8,288.1,139,139.0,136,136,28.9,79,109"
        )
        bad = "2,5,1,NOT_A_TIMESTAMP,18,263.7,82,104.6,162,151,18.7,82,110"
        csv_bytes = f"{header}\n{good}\n{bad}\n".encode()
        records = parse_smartrow_csv(csv_bytes)
        self.assertEqual(len(records), 1)


class TestCsvStrokeRecordSpeedConversion(unittest.TestCase):
    def _make_record(self, split_s: float | None) -> CsvStrokeRecord:
        return CsvStrokeRecord(
            stroke_num=1,
            elapsed_seconds=5,
            interval_num=1,
            timestamp_ms=1745473498000,
            distance_m=8.0,
            work_j=288.0,
            actual_power_w=139.0,
            avg_power_w=139.0,
            actual_split_s=split_s,
            avg_split_s=split_s,
            stroke_rate_spm=28.9,
            heart_rate_bpm=79,
            stroke_length_cm=109.0,
        )

    def test_speed_mps_correct(self) -> None:
        record = self._make_record(125.0)  # 125 s/500m → 4 m/s
        self.assertAlmostEqual(record.speed_mps(), 4.0)

    def test_speed_mps_none_when_no_split(self) -> None:
        record = self._make_record(None)
        self.assertIsNone(record.speed_mps())


if __name__ == "__main__":
    unittest.main()
