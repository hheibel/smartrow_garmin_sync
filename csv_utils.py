"""Utilities for parsing SmartRow CSV exports and building FIT files.

The SmartRow CSV export (csv-us format) contains one row per rowing stroke
with per-stroke metrics. This module parses that data and builds a complete
Garmin-compatible FIT file using the stroke data as the primary source.
"""

import csv
import datetime
import io
from dataclasses import dataclass
from dataclasses import field
from typing import Any

from absl import logging

# Number of force-curve sample columns in the SmartRow CSV export.
_FORCE_CURVE_SAMPLES = 25


@dataclass
class CsvStrokeRecord:
    """Represents one rowing stroke from a SmartRow CSV export.

    Attributes:
        stroke_num: Sequential stroke number within the session.
        elapsed_seconds: Elapsed seconds from session start at this stroke.
        interval_num: Interval index (1-based).
        timestamp_ms: Absolute UTC timestamp in milliseconds since epoch.
        distance_m: Cumulative distance in metres.
        work_j: Work performed on this stroke in Joules.
        actual_power_w: Instantaneous power in Watts, or None.
        avg_power_w: Running average power in Watts, or None.
        actual_split_s: Actual split time (s per 500 m), or None.
        avg_split_s: Running average split time (s per 500 m), or None.
        stroke_rate_spm: Stroke rate in strokes per minute, or None.
        heart_rate_bpm: Heart rate in BPM, or None.
        stroke_length_cm: Stroke length in centimetres, or None.
        force_curve_n: List of 25 force samples in Newtons.
    """

    stroke_num: int
    elapsed_seconds: int
    interval_num: int
    timestamp_ms: int
    distance_m: float
    work_j: float
    actual_power_w: float | None
    avg_power_w: float | None
    actual_split_s: float | None
    avg_split_s: float | None
    stroke_rate_spm: float | None
    heart_rate_bpm: int | None
    stroke_length_cm: float | None
    force_curve_n: list[int] = field(default_factory=list)

    def speed_mps(self) -> float | None:
        """Returns speed in m/s derived from the actual split time.

        Returns:
            Speed in metres per second, or None if split is unavailable.
        """
        if self.actual_split_s and self.actual_split_s > 0:
            return 500.0 / self.actual_split_s
        return None


def _parse_float(value: str) -> float | None:
    """Parses a string to float, returning None on failure.

    Args:
        value: The string to parse.

    Returns:
        A float, or None if the string is empty or unparseable.
    """
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError:
        return None


def _parse_int(value: str) -> int | None:
    """Parses a string to int via float, returning None on failure.

    Args:
        value: The string to parse.

    Returns:
        An integer, or None if the string is empty or unparseable.
    """
    f = _parse_float(value)
    return round(f) if f is not None else None


def _parse_timestamp_ms(iso_str: str) -> int:
    """Converts an ISO 8601 UTC timestamp string to milliseconds since epoch.

    Args:
        iso_str: An ISO 8601 timestamp string (e.g. '2026-04-24T05:44:58Z').

    Returns:
        Milliseconds since the Unix epoch.

    Raises:
        ValueError: If the timestamp cannot be parsed.
    """
    clean = iso_str.strip().replace("Z", "+00:00")
    dt = datetime.datetime.fromisoformat(clean)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return int(dt.timestamp() * 1000)


def parse_smartrow_csv(csv_bytes: bytes) -> list[CsvStrokeRecord]:
    """Parses raw SmartRow CSV bytes into a list of per-stroke records.

    The CSV must be in the SmartRow 'csv-us' export format with one row per
    rowing stroke. Force-curve columns (#0-#24 N) are parsed but are not
    mapped to FIT fields since no standard FIT field exists for them.

    Args:
        csv_bytes: Raw bytes of the SmartRow CSV export.

    Returns:
        A list of CsvStrokeRecord objects sorted by ascending timestamp.

    Raises:
        ValueError: If the CSV is empty, missing required columns, or contains
            no parseable stroke data.
    """
    text = csv_bytes.decode("utf-8-sig")  # strips optional BOM
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise ValueError("CSV has no header row.")

    required_cols = {
        "Stroke (#)",
        "Second (#)",
        "Interval (#)",
        "Timestamp (UTC)",
        "Distance (m)",
        "Work (J)",
    }
    missing = required_cols - set(reader.fieldnames)
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")

    records: list[CsvStrokeRecord] = []
    for row_num, row in enumerate(reader, start=2):  # row 2 = first data row
        ts_raw = row.get("Timestamp (UTC)", "")
        try:
            timestamp_ms = _parse_timestamp_ms(ts_raw)
        except ValueError as e:
            logging.warning(
                "Skipping CSV row %d: cannot parse timestamp '%s': %s",
                row_num,
                ts_raw,
                e,
            )
            continue

        force_curve: list[int] = []
        for i in range(_FORCE_CURVE_SAMPLES):
            col = f"#{i} (N)"
            val = _parse_int(row.get(col, ""))
            force_curve.append(val if val is not None else 0)

        records.append(
            CsvStrokeRecord(
                stroke_num=_parse_int(row.get("Stroke (#)", "")) or 0,
                elapsed_seconds=_parse_int(row.get("Second (#)", "")) or 0,
                interval_num=_parse_int(row.get("Interval (#)", "")) or 1,
                timestamp_ms=timestamp_ms,
                distance_m=_parse_float(row.get("Distance (m)", "")) or 0.0,
                work_j=_parse_float(row.get("Work (J)", "")) or 0.0,
                actual_power_w=_parse_float(row.get("Actual power (W)", "")),
                avg_power_w=_parse_float(row.get("Average power (W)", "")),
                actual_split_s=_parse_float(row.get("Actual split (s)", "")),
                avg_split_s=_parse_float(row.get("Average split (s)", "")),
                stroke_rate_spm=_parse_float(row.get("Stroke rate (SPM)", "")),
                heart_rate_bpm=_parse_int(row.get("Heart rate (bpm)", "")),
                stroke_length_cm=_parse_float(
                    row.get("Stroke length (cm)", "")
                ),
                force_curve_n=force_curve,
            )
        )

    if not records:
        raise ValueError("CSV parsed successfully but contains no stroke data.")

    records.sort(key=lambda r: r.timestamp_ms)
    logging.info("Parsed %d stroke records from SmartRow CSV.", len(records))
    return records
