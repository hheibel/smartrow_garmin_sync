import os
import sys
from collections.abc import Sequence
from typing import Any

from absl import app
from absl import flags
from absl import logging

# Add parent directory to path to import fit_utils from the root directory
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
)
from fit_utils import read_fit_file

FLAGS = flags.FLAGS

flags.DEFINE_string("input_fit", None, "Path to the FIT file to check.")
flags.mark_flag_as_required("input_fit")


def check_file_id_message(messages: list[Any]) -> bool:
    """Validates the FileIdMessage against guidelines.

    Args:
        messages: List of messages extracted from the FIT file.

    Returns:
        True if the FileIdMessage is present and valid, False otherwise.
    """
    file_id_msgs = [m for m in messages if type(m).__name__ == "FileIdMessage"]
    if not file_id_msgs:
        logging.error("Missing FileIdMessage. Every FIT file must have one.")
        return False

    msg = file_id_msgs[0]
    required_fields = [
        "type",
        "manufacturer",
        "product",
        "serial_number",
        "time_created",
    ]
    has_error = False

    for field in required_fields:
        val = getattr(msg, field, None)
        if val is None:
            logging.error(
                "FileIdMessage is missing required field: '%s'", field
            )
            has_error = True

    if not has_error:
        logging.info("FileIdMessage OK.")
    return not has_error


def check_activity_message(messages: list[Any]) -> bool:
    """Validates the ActivityMessage against guidelines.

    Args:
        messages: List of messages extracted from the FIT file.

    Returns:
        True if the ActivityMessage is present and valid, False otherwise.
    """
    activity_msgs = [
        m for m in messages if type(m).__name__ == "ActivityMessage"
    ]
    if not activity_msgs:
        logging.error(
            "Missing ActivityMessage. The file is not a valid Activity file."
        )
        return False

    msg = activity_msgs[0]
    required_fields = [
        "timestamp",
        "num_sessions",
        "type",
        "event",
        "event_type",
        "total_timer_time",
    ]
    has_error = False

    for field in required_fields:
        val = getattr(msg, field, None)
        if val is None:
            logging.error(
                "ActivityMessage is missing required field: '%s'", field
            )
            has_error = True

    # Check wall clock time in Activity
    session_msgs = [m for m in messages if type(m).__name__ == "SessionMessage"]
    if session_msgs and getattr(msg, "total_timer_time", None) is not None:
        actual_timer = getattr(msg, "total_timer_time", 0)
        expected_timer = sum(
            getattr(s, "total_timer_time", 0) for s in session_msgs
        )
        if abs(actual_timer - expected_timer) > 0.1:
            logging.error(
                "Activity total_timer_time mismatch. Expected %f, found %f",
                expected_timer,
                actual_timer,
            )
            has_error = True

    if not has_error:
        logging.info("ActivityMessage OK.")
    return not has_error


def check_session_message(messages: list[Any]) -> bool:
    """Validates the SessionMessage against guidelines.

    Args:
        messages: List of messages extracted from the FIT file.

    Returns:
        True if SessionMessages are present and valid, False otherwise.
    """
    session_msgs = [m for m in messages if type(m).__name__ == "SessionMessage"]
    if not session_msgs:
        logging.error(
            "Missing SessionMessage. Activity file should have one session."
        )
        return False

    has_error = False
    required_fields = [
        "timestamp",
        "start_time",
        "total_elapsed_time",
        "total_timer_time",
        "sport",
        "sub_sport",
        "total_distance",
    ]

    for i, msg in enumerate(session_msgs):
        for field in required_fields:
            val = getattr(msg, field, None)
            if val is None:
                logging.error(
                    "SessionMessage %d is missing required field: '%s'",
                    i,
                    field,
                )
                has_error = True

        # Check wall clock time consistency
        if getattr(msg, "timestamp", None) and getattr(msg, "start_time", None):
            duration_s = (msg.timestamp - msg.start_time) / 1000.0
            elapsed = getattr(msg, "total_elapsed_time", 0)
            timer = getattr(msg, "total_timer_time", 0)

            if abs(elapsed - duration_s) > 0.1:
                logging.error(
                    "Session %d total_elapsed_time mismatch. Wall: %f, Field: %f",
                    i,
                    duration_s,
                    elapsed,
                )
                has_error = True
            if abs(timer - duration_s) > 0.1:
                logging.error(
                    "Session %d total_timer_time mismatch. Wall: %f, Field: %f",
                    i,
                    duration_s,
                    timer,
                )
                has_error = True

    if not has_error:
        logging.info("SessionMessage(s) OK.")
    return not has_error


def check_record_messages(messages: list[Any]) -> bool:
    """Validates RecordMessages against guidelines.

    Args:
        messages: List of messages extracted from the FIT file.

    Returns:
        True if RecordMessages are valid, False otherwise.
    """
    record_msgs = [m for m in messages if type(m).__name__ == "RecordMessage"]
    if not record_msgs:
        logging.warning(
            "No RecordMessages found. Activity file might be empty."
        )
        return True

    has_error = False
    for i, msg in enumerate(record_msgs):
        if getattr(msg, "timestamp", None) is None:
            logging.error("RecordMessage %d is missing 'timestamp' field.", i)
            has_error = True

    if not has_error:
        logging.info("RecordMessage(s) OK (%d points).", len(record_msgs))
    return not has_error


def check_session_summary_vs_records(messages: list[Any]) -> bool:
    """Checks SessionMessage summaries against aggregated RecordMessage data.

    This check identifies potential discrepancies between session-level
    averages and the underlying per-stroke data. Note that SmartRow uses
    time-averaging over the full session duration, so simple stroke-averages
    may differ by 10-15%.

    Args:
        messages: List of messages extracted from the FIT file.

    Returns:
        True if the discrepancies are within acceptable bounds, False otherwise.
    """
    session_msgs = [m for m in messages if type(m).__name__ == "SessionMessage"]
    record_msgs = [m for m in messages if type(m).__name__ == "RecordMessage"]

    if not session_msgs or not record_msgs:
        return True

    msg = session_msgs[0]
    has_warning = False

    # 1. Aggregate Record metrics
    def _avg(vals: list[float | int]) -> float | None:
        return sum(vals) / len(vals) if vals else None

    powers = [getattr(r, "power", None) for r in record_msgs if getattr(r, "power", None) is not None]
    hrs = [getattr(r, "heart_rate", None) for r in record_msgs if getattr(r, "heart_rate", None) is not None]
    cadences = [getattr(r, "cadence", None) for r in record_msgs if getattr(r, "cadence", None) is not None]
    
    stroke_avg_pwr = _avg(powers)
    stroke_avg_hr = _avg(hrs)
    stroke_avg_cad = _avg(cadences)

    # 2. Compare against Session Message
    session_avg_pwr = getattr(msg, "avg_power", None)
    session_avg_hr = getattr(msg, "avg_heart_rate", None)
    session_avg_cad = getattr(msg, "avg_cadence", None)
    timer_time = getattr(msg, "total_timer_time", 0)

    logging.info("--- Session Summary vs Records ---")
    
    if session_avg_pwr and stroke_avg_pwr:
        diff_pct = abs(session_avg_pwr - stroke_avg_pwr) / session_avg_pwr
        logging.info("Power: Session Avg=%d W, Stroke Avg=%.1f W (diff=%.1f%%)", 
                     session_avg_pwr, stroke_avg_pwr, diff_pct * 100)
        if diff_pct > 0.25: # Large discrepancy
            logging.error("Large Power discrepancy detected (> 25%).")
            has_warning = True

    if session_avg_hr and stroke_avg_hr:
        diff = abs(session_avg_hr - stroke_avg_hr)
        logging.info("HR: Session Avg=%d bpm, Stroke Avg=%.1f bpm (diff=%.1f bpm)", 
                     session_avg_hr, stroke_avg_hr, diff)

    if session_avg_cad and stroke_avg_cad:
        diff_pct = abs(session_avg_cad - stroke_avg_cad) / session_avg_cad
        logging.info("Cadence: Session Avg=%d spm, Stroke Avg=%.1f spm (diff=%.1f%%)", 
                     session_avg_cad, stroke_avg_cad, diff_pct * 100)

    # 3. Check Total Work consistency
    total_work = getattr(msg, "total_work", None)
    if total_work and session_avg_pwr and timer_time:
        # P = W / t => W = P * t
        expected_work = session_avg_pwr * timer_time
        diff_pct = abs(total_work - expected_work) / total_work
        logging.info("Work: Session Total=%d J, Calc (AvgPwr * Time)=%.1f J (diff=%.1f%%)",
                     total_work, expected_work, diff_pct * 100)
        if diff_pct > 0.1:
            logging.warning("Total work inconsistent with average power and time.")

    return not has_warning


def main(argv: Sequence[str]) -> None:
    """Main integrity check execution loop."""
    del argv  # Unused
    input_path = FLAGS.input_fit
    if not input_path or not os.path.exists(input_path):
        logging.fatal("Provided FIT file does not exist: %s", input_path)
        return

    logging.info("Reading FIT file: %s", input_path)
    try:
        fit_file = read_fit_file(input_path)
    except Exception as e:
        logging.fatal("Failed to read FIT file via fit_tools: %s", e)
        return

    # Extract all messages
    messages = [
        record.message
        for record in fit_file.records
        if hasattr(record, "message")
    ]
    logging.info("Loaded %d total messages.", len(messages))

    valid = True
    valid &= check_file_id_message(messages)
    valid &= check_activity_message(messages)
    valid &= check_session_message(messages)
    valid &= check_record_messages(messages)
    valid &= check_session_summary_vs_records(messages)

    if valid:
        logging.info("FIT file integrity is SUCCESSFUL.")
    else:
        logging.error("FIT file integrity check FAILED due to missing fields.")
        sys.exit(1)


if __name__ == "__main__":
    app.run(main)
