"""Utility functions for converting TCX to FIT and modifying FIT attributes."""

import datetime
import xml.etree.ElementTree as ET
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from absl import logging
from fit_tool.fit_file_builder import FitFile
from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.activity_message import ActivityMessage
from fit_tool.profile.messages.device_info_message import DeviceInfoMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.profile_type import Activity
from fit_tool.profile.profile_type import Event
from fit_tool.profile.profile_type import EventType
from fit_tool.profile.profile_type import FileType
from fit_tool.profile.profile_type import Manufacturer
from fit_tool.profile.profile_type import Sport
from fit_tool.profile.profile_type import SubSport

from csv_utils import CsvStrokeRecord

# 1. Namespace Definitions
# 'ns' is the standard TCX namespace (for Trackpoint, Time, etc.)
# 'ax' (Activity Extension) is the namespace for TPX, Watts, Speed
NS = {
    "ns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
    "ax": "http://www.garmin.com/xmlschemas/ActivityExtension/v2",
}

# Garmin Device Constants (Edge 1040 Solar)
GARMIN_MANUFACTURER = Manufacturer.GARMIN
GARMIN_PRODUCT = 3843
GARMIN_SERIAL_NUMBER = 3442358385
GARMIN_SOFTWARE_VERSION = 30.18


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _avg(values: list[float | int]) -> float | None:
    """Returns the mean of *values*, or None if the list is empty."""
    return sum(values) / len(values) if values else None


def _rebuild_message(source: Any, msg_type: Any) -> Any:
    """Copies all non-None fields from *source* into a fresh *msg_type*.

    Args:
        source: The original FIT message to copy from.
        msg_type: The message class to instantiate.

    Returns:
        A new message instance with all readable fields copied.
    """
    new_msg = msg_type()
    for field in source.fields:
        if (val := field.get_value()) is not None:
            with suppress(AttributeError, ValueError):
                setattr(new_msg, field.name, val)
    return new_msg


def _make_garmin_header(builder: FitFileBuilder, time_created: int) -> None:
    """Adds a spoofed Garmin Edge 1040 Solar FileId + DeviceInfo to *builder*.

    Args:
        builder: The FitFileBuilder to populate.
        time_created: Creation timestamp in milliseconds.
    """
    file_id = FileIdMessage()
    file_id.type = FileType.ACTIVITY
    file_id.manufacturer = GARMIN_MANUFACTURER
    file_id.product = GARMIN_PRODUCT
    file_id.serial_number = GARMIN_SERIAL_NUMBER
    file_id.time_created = time_created
    builder.add(file_id)

    device_info = DeviceInfoMessage()
    device_info.device_index = 0
    device_info.manufacturer = GARMIN_MANUFACTURER
    device_info.product = GARMIN_PRODUCT
    device_info.serial_number = GARMIN_SERIAL_NUMBER
    device_info.software_version = GARMIN_SOFTWARE_VERSION
    device_info.timestamp = time_created
    builder.add(device_info)


def _insert_csv_records(
    builder: FitFileBuilder,
    csv_records: list[CsvStrokeRecord],
    start_ms: int,
    end_ms: int,
) -> None:
    """Adds all CSV stroke records to *builder*, bracketed by session bounds.

    Inserts a zeroed anchor record at *start_ms* if the first CSV record does
    not already coincide with the session start, and adjusts the final record's
    timestamp to *end_ms* when needed to preserve the full session duration.

    Args:
        builder: The FitFileBuilder to populate.
        csv_records: Per-stroke records parsed from the SmartRow CSV.
        start_ms: Session start timestamp in milliseconds.
        end_ms: Session end timestamp in milliseconds.
    """
    # Anchor record at session start (distance = 0)
    if csv_records[0].timestamp_ms > start_ms:
        start_rec = RecordMessage()
        start_rec.timestamp = start_ms
        start_rec.distance = 0.0
        if csv_records[0].heart_rate_bpm:
            start_rec.heart_rate = csv_records[0].heart_rate_bpm
        start_rec.power = 0
        start_rec.cadence = 0
        start_rec.speed = 0.0
        builder.add(start_rec)

    for i, stroke in enumerate(csv_records):
        fit_rec = stroke_to_fit_record(stroke)
        # Align last record with session end to preserve total duration
        if i == len(csv_records) - 1 and fit_rec.timestamp < end_ms:
            fit_rec.timestamp = end_ms
        builder.add(fit_rec)


# ---------------------------------------------------------------------------
# Public helpers: TCX / timestamp parsing
# ---------------------------------------------------------------------------


def extract_time(trackpoint_element: ET.Element) -> int | None:
    """Extracts time from a Trackpoint element and returns Garmin timestamp.

    Args:
        trackpoint_element: The XML element for a TCX Trackpoint.

    Returns:
        The timestamp in milliseconds since the Garmin Epoch, or None.
    """
    time_element = trackpoint_element.find("ns:Time", NS)
    if time_element is not None and time_element.text:
        return parse_iso_time_ms(time_element.text)
    return None


def extract_watts(trackpoint_element: ET.Element) -> int | None:
    """Attempts to read watts from a Trackpoint element.

    Args:
        trackpoint_element: The XML element for a TCX Trackpoint.

    Returns:
        The power in Watts, or None if unavailable.
    """
    watts_element = trackpoint_element.find(".//ax:Watts", NS)
    if watts_element is not None and watts_element.text:
        return int(watts_element.text)
    return None


def parse_iso_time_ms(iso_str: str) -> int:
    """Converts TCX time (ISO 8601) into Garmin Timestamp (ms).

    Args:
        iso_str: The ISO 8601 timestamp string.

    Returns:
        The timestamp in milliseconds.

    Raises:
        ValueError: If the timestamp cannot be parsed.
    """
    clean_str = iso_str.replace("Z", "+00:00")

    try:
        dt = datetime.datetime.fromisoformat(clean_str)
    except ValueError:
        if "." in clean_str:
            clean_str = clean_str.split(".")[0] + "+00:00"
            dt = datetime.datetime.fromisoformat(clean_str)
        else:
            raise

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    return int(dt.timestamp() * 1000)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ActivityRecord:
    """Represents a single data point in rowing training."""

    time_ms: int
    heart_rate: int | None = None
    distance: float | None = None
    cadence: int | None = None
    watts: int | None = None
    position_lat: float | None = None
    position_long: float | None = None
    altitude: float | None = None

    def to_fit_record(self) -> RecordMessage:
        """Converts this dataclass into a FIT RecordMessage.

        Returns:
            A RecordMessage object populated with the record data.
        """
        msg = RecordMessage()
        msg.timestamp = self.time_ms

        if self.heart_rate is not None:
            msg.heart_rate = int(self.heart_rate)

        if self.distance is not None:
            msg.distance = float(self.distance)

        if self.cadence is not None:
            msg.cadence = int(self.cadence)

        if self.watts is not None:
            msg.power = int(self.watts)

        if self.position_lat is not None and self.position_long is not None:
            msg.position_lat = self.position_lat
            msg.position_long = self.position_long

        if self.altitude is not None:
            msg.altitude = float(self.altitude)

        return msg


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def stroke_to_fit_record(stroke: CsvStrokeRecord) -> RecordMessage:
    """Converts a CsvStrokeRecord into a FIT RecordMessage.

    Args:
        stroke: The per-stroke record from CSV.

    Returns:
        A RecordMessage populated with available stroke metrics.
    """
    msg = RecordMessage()
    msg.timestamp = stroke.timestamp_ms
    msg.distance = stroke.distance_m

    if stroke.actual_power_w is not None:
        msg.power = round(stroke.actual_power_w)

    if stroke.heart_rate_bpm is not None:
        msg.heart_rate = stroke.heart_rate_bpm

    if stroke.stroke_rate_spm is not None:
        msg.cadence = round(stroke.stroke_rate_spm)

    speed = stroke.speed_mps()
    if speed is not None:
        msg.speed = speed
        msg.enhanced_speed = speed

    return msg


def convert_to_fit(tcx_string: str) -> FitFile:
    """Converts a TCX XML string into a Garmin-compatible FitFile object.

    Args:
        tcx_string: The raw TCX XML data.

    Returns:
        A FitFile object containing the activity data and Garmin metadata.
    """
    root = ET.fromstring(tcx_string)
    builder = FitFileBuilder(auto_define=True, min_string_size=50)

    now_ms = int(
        datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000
    )
    _make_garmin_header(builder, now_ms)

    activity_records: list[ActivityRecord] = []

    for trackpoint in root.findall(".//ns:Trackpoint", NS):
        time_ms = extract_time(trackpoint)
        if time_ms is None:
            continue

        activity_record = ActivityRecord(time_ms=time_ms)

        pos_elem = trackpoint.find("ns:Position", NS)
        if pos_elem is not None:
            lat = pos_elem.find("ns:LatitudeDegrees", NS)
            lon = pos_elem.find("ns:LongitudeDegrees", NS)
            if lat is not None and lon is not None and lat.text and lon.text:
                activity_record.position_lat = float(lat.text)
                activity_record.position_long = float(lon.text)

        ele_elem = trackpoint.find("ns:AltitudeMeters", NS)
        if ele_elem is not None and ele_elem.text:
            activity_record.altitude = float(ele_elem.text)

        dist_elem = trackpoint.find("ns:DistanceMeters", NS)
        if dist_elem is not None and dist_elem.text:
            activity_record.distance = float(dist_elem.text)

        activity_record.watts = extract_watts(trackpoint)

        hr_elem = trackpoint.find("ns:HeartRateBpm/ns:Value", NS)
        if hr_elem is not None and hr_elem.text:
            activity_record.heart_rate = int(hr_elem.text)

        cad_elem = trackpoint.find("ns:Cadence", NS)
        if cad_elem is not None and cad_elem.text:
            activity_record.cadence = round(float(cad_elem.text))

        activity_records.append(activity_record)

    for record_data in activity_records:
        builder.add(record_data.to_fit_record())

    # Write Session Message
    session_message = SessionMessage()
    session_message.sport = Sport.ROWING
    session_message.sub_sport = SubSport.INDOOR_ROWING
    session_message.timestamp = int(
        datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000
    )
    session_message.start_time = activity_records[0].time_ms
    session_message.total_elapsed_time = (
        activity_records[-1].time_ms - activity_records[0].time_ms
    ) / 1000.0
    session_message.total_timer_time = session_message.total_elapsed_time
    session_message.total_distance = (
        activity_records[-1].distance
        if activity_records[-1].distance is not None
        else 0.0
    )

    # Populate summary metrics
    powers = [r.watts for r in activity_records if r.watts is not None]
    hrs = [r.heart_rate for r in activity_records if r.heart_rate is not None]
    cadences = [r.cadence for r in activity_records if r.cadence is not None]

    if powers:
        session_message.avg_power = round(sum(powers) / len(powers))
        session_message.max_power = max(powers)
    if hrs:
        session_message.avg_heart_rate = round(sum(hrs) / len(hrs))
        session_message.max_heart_rate = max(hrs)
    if cadences:
        session_message.avg_cadence = round(sum(cadences) / len(cadences))
        session_message.max_cadence = max(cadences)

    builder.add(session_message)

    # Write Activity Message
    activity_message = ActivityMessage()
    activity_message.timestamp = activity_records[-1].time_ms
    activity_message.num_sessions = 1
    activity_message.type = Activity.MANUAL
    activity_message.event = Event.ACTIVITY
    activity_message.event_type = EventType.STOP
    builder.add(activity_message)

    return builder.build()


def save_fit_file(fit_file: FitFile, output_path: str) -> None:
    """Saves a FitFile object to disk.

    Args:
        fit_file: The FitFile to save.
        output_path: The filesystem path to save to.
    """
    fit_file.to_file(output_path)
    logging.info("Done! File saved as: %s", output_path)


def read_fit_file(input_path: str) -> FitFile:
    """Reads a FIT file from disk and returns a FitFile object.

    Args:
        input_path: The path to the FIT file.

    Returns:
        A FitFile object.
    """
    return FitFile.from_file(input_path)


def extract_session_metadata(input_path: str) -> dict[str, Any]:
    """Extracts session anchoring metadata from a FIT file.

    Reads the first SessionMessage found in the FIT file and returns its
    start time, total distance, and total elapsed time. These values are used
    to anchor a CSV-based FIT rebuild to the correct absolute timestamp and
    distance totals from the original SmartRow FIT file.

    Args:
        input_path: Path to the FIT file to inspect.

    Returns:
        A dict with the following keys:

        - ``start_time_ms`` (int): Session start time in ms since epoch.
        - ``total_distance_m`` (float): Total distance in metres.
        - ``total_elapsed_time_s`` (float): Total elapsed time in seconds.

    Raises:
        ValueError: If no SessionMessage is found in the FIT file.
    """
    for record in read_fit_file(input_path).records:
        if isinstance(record.message, SessionMessage):
            msg = record.message
            start_time_ms = getattr(msg, "start_time", None)
            if start_time_ms is not None:
                return {
                    "start_time_ms": int(start_time_ms),
                    "total_distance_m": float(
                        getattr(msg, "total_distance", 0.0) or 0.0
                    ),
                    "total_elapsed_time_s": float(
                        getattr(msg, "total_elapsed_time", 0.0) or 0.0
                    ),
                }
    raise ValueError(
        f"No SessionMessage with a start_time found in FIT file: {input_path}"
    )


def rewrite_fit_file_attributes(input_path: str, output_path: str) -> None:
    """Rewrites attributes of a FIT file to fix durations and add metadata.

    Args:
        input_path: Path to the original FIT file.
        output_path: Path where the rewritten FIT file will be saved.
    """
    fit_file = read_fit_file(input_path)

    # Analysis pass: aggregate max speed from Lap messages and locate Session
    max_ems: float | None = None
    max_ms: float | None = None
    target_session: SessionMessage | None = None

    for record in fit_file.records:
        msg = record.message
        if isinstance(msg, SessionMessage) and target_session is None:
            if (
                getattr(msg, "total_elapsed_time", None)
                == getattr(msg, "total_timer_time", None)
                is not None
            ):
                target_session = msg
        elif type(msg).__name__ == "LapMessage":
            if (l_ems := getattr(msg, "enhanced_max_speed", None)) is not None:
                max_ems = max(max_ems or 0, l_ems)
            if (l_ms := getattr(msg, "max_speed", None)) is not None:
                max_ms = max(max_ms or 0, l_ms)

    builder = FitFileBuilder(auto_define=True, min_string_size=50)
    device_info_added = False

    for record in fit_file.records:
        msg = record.message

        if isinstance(msg, FileIdMessage):
            time_created = getattr(
                msg,
                "time_created",
                int(
                    datetime.datetime.now(datetime.timezone.utc).timestamp()
                    * 1000
                ),
            )
            if not device_info_added:
                _make_garmin_header(builder, time_created)
                device_info_added = True
            else:
                new_id = FileIdMessage()
                new_id.type = getattr(msg, "type", FileType.ACTIVITY)
                new_id.time_created = time_created
                new_id.manufacturer = GARMIN_MANUFACTURER
                new_id.product = GARMIN_PRODUCT
                new_id.serial_number = GARMIN_SERIAL_NUMBER
                builder.add(new_id)

        elif isinstance(msg, DeviceInfoMessage):
            # Skip primary device; we already spoofed it via _make_garmin_header
            if getattr(msg, "device_index", None) == 0:
                continue
            builder.add(msg)

        elif isinstance(msg, SessionMessage) and msg is target_session:
            new_s = _rebuild_message(msg, SessionMessage)
            if new_s.timestamp and new_s.start_time:
                dur = (new_s.timestamp - new_s.start_time) / 1000.0
                new_s.total_elapsed_time = dur
                new_s.total_timer_time = dur
            if max_ems is not None:
                new_s.enhanced_max_speed = max_ems
            if max_ms is not None:
                new_s.max_speed = max_ms
            new_s.message_index = 0
            builder.add(new_s)

        elif isinstance(msg, ActivityMessage):
            new_a = _rebuild_message(msg, ActivityMessage)
            new_a.num_sessions = 1
            if (
                target_session
                and target_session.timestamp
                and target_session.start_time
            ):
                new_a.total_timer_time = (
                    target_session.timestamp - target_session.start_time
                ) / 1000.0
            builder.add(new_a)

        else:
            builder.add(msg)

    builder.build().to_file(output_path)


def build_fit_from_csv(
    template_path: str, csv_records: list[CsvStrokeRecord], output_path: str
) -> None:
    """Builds an enriched FIT file using a template and CSV stroke data.

    This function uses an original FIT file as a structural template. It
    preserves metadata messages (laps, events) while replacing all
    RecordMessages with those derived from the CSV data. Session and Activity
    messages are updated with aggregated CSV metrics.

    Args:
        template_path: Path to the original SmartRow FIT file.
        csv_records: List of per-stroke records parsed from the CSV.
        output_path: Path where the enriched FIT file will be saved.

    Raises:
        ValueError: If csv_records is empty.
    """
    if not csv_records:
        raise ValueError("Cannot build FIT file from empty CSV records.")

    fit_file = read_fit_file(template_path)
    builder = FitFileBuilder(auto_define=True, min_string_size=50)

    # Aggregate metrics from CSV records
    powers = [r.actual_power_w for r in csv_records if r.actual_power_w]
    hrs = [r.heart_rate_bpm for r in csv_records if r.heart_rate_bpm]
    cadences = [r.stroke_rate_spm for r in csv_records if r.stroke_rate_spm]
    speeds = [s for r in csv_records if (s := r.speed_mps())]

    avg_pwr = _avg(powers)
    avg_hr = _avg(hrs)
    avg_cad = _avg(cadences)
    avg_spd = _avg(speeds)

    # Locate the first session in the template to inherit timing bounds
    target_session: SessionMessage | None = None
    for record in fit_file.records:
        if isinstance(record.message, SessionMessage):
            target_session = record.message
            break

    if target_session:
        start_ms = target_session.start_time
        end_ms = target_session.timestamp
    else:
        start_ms = csv_records[0].timestamp_ms
        end_ms = csv_records[-1].timestamp_ms

    duration_s = (end_ms - start_ms) / 1000.0

    records_inserted = False
    device_info_added = False

    for record in fit_file.records:
        msg = record.message

        if isinstance(msg, RecordMessage):
            if not records_inserted:
                _insert_csv_records(builder, csv_records, start_ms, end_ms)
                records_inserted = True
            # Discard original record messages; replaced by CSV data
            continue

        # Safety: insert CSV records before any summary message if not yet done
        if (
            isinstance(msg, (SessionMessage, ActivityMessage))
            or type(msg).__name__ == "LapMessage"
        ) and not records_inserted:
            _insert_csv_records(builder, csv_records, start_ms, end_ms)
            records_inserted = True

        if isinstance(msg, FileIdMessage):
            time_created = getattr(
                msg,
                "time_created",
                int(
                    datetime.datetime.now(datetime.timezone.utc).timestamp()
                    * 1000
                ),
            )
            if not device_info_added:
                _make_garmin_header(builder, time_created)
                device_info_added = True

        elif isinstance(msg, DeviceInfoMessage):
            if getattr(msg, "device_index", None) == 0:
                continue
            builder.add(msg)

        elif isinstance(msg, SessionMessage) and msg is target_session:
            new_s = _rebuild_message(msg, SessionMessage)
            new_s.start_time = start_ms
            new_s.timestamp = end_ms
            new_s.total_elapsed_time = duration_s
            new_s.total_timer_time = duration_s
            new_s.sport = Sport.ROWING
            new_s.sub_sport = SubSport.INDOOR_ROWING

            if avg_pwr is not None:
                new_s.avg_power = round(avg_pwr)
            if powers:
                new_s.max_power = max(powers)
            if avg_hr is not None:
                new_s.avg_heart_rate = round(avg_hr)
            if hrs:
                new_s.max_heart_rate = max(hrs)
            if avg_cad is not None:
                new_s.avg_cadence = round(avg_cad)
            if cadences:
                new_s.max_cadence = max(cadences)
            if avg_spd is not None:
                new_s.enhanced_avg_speed = avg_spd
            if speeds:
                new_s.enhanced_max_speed = max(speeds)
                new_s.max_speed = max(speeds)

            new_s.message_index = 0
            builder.add(new_s)

        elif isinstance(msg, ActivityMessage):
            new_a = _rebuild_message(msg, ActivityMessage)
            new_a.timestamp = end_ms
            new_a.num_sessions = 1
            new_a.total_timer_time = duration_s
            builder.add(new_a)

        elif type(msg).__name__ in ("WorkoutMessage", "WorkoutStepMessage"):
            continue  # Workout metadata doesn't align with stroke-level records

        else:
            builder.add(msg)

    # Final safety: file had no records, sessions, or laps at all
    if not records_inserted:
        _insert_csv_records(builder, csv_records, start_ms, end_ms)

    builder.build().to_file(output_path)
