import datetime
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional, Union

from fit_tool.fit_file_builder import FitFile, FitFileBuilder
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.activity_message import ActivityMessage
from fit_tool.profile.profile_type import Activity, FileType, Manufacturer, Sport, SubSport, Event, EventType


# 1. Namespace Definitions
# 'ns' is the standard TCX namespace (for Trackpoint, Time, etc.)
# 'ax' (Activity Extension) is the namespace for TPX, Watts, Speed
NS = {
    'ns': 'http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2',
    'ax': 'http://www.garmin.com/xmlschemas/ActivityExtension/v2'
}

def extract_time(trackpoint_element: ET.Element) -> int | None:
    """
    Extracts time from a Trackpoint element and returns it as a Garmin timestamp (ms).
    Returns None if no Time element is found.
    """
    time_element = trackpoint_element.find('ns:Time', NS)
    if time_element is not None:
        return parse_iso_time_ms(time_element.text)
    return None

def extract_watts(trackpoint_element: ET.Element) -> int | None:
    """
    Attempts to read watts from a Trackpoint element.
    Returns None if no watt data is available.
    """
    # Look for: Extensions -> TPX -> Watts
    # Since 'Extensions' typically belongs to the standard NS, but 'TPX' and 'Watts' belong to 'ax',
    # the search path looks like this:
    watts_element = trackpoint_element.find('.//ax:Watts', NS)
    
    if watts_element is not None:
        return int(watts_element.text)
    
    return None


def parse_iso_time_ms(iso_str: str) -> int:
    """Converts TCX time (e.g., 2023-10-25T18:00:00Z) into Garmin Timestamp (ms)"""
    # Remove Z because fromisoformat in older Python versions might have issues with it.
    # We assume TCX times are always UTC.
    clean_str = iso_str.replace('Z', '+00:00')
    
    try:
        dt = datetime.datetime.fromisoformat(clean_str)
    except ValueError:
        # Fallback: Sometimes TCX has milliseconds. fromisoformat often doesn't like them
        # if the length isn't exact. We truncate milliseconds for a fix:
        if '.' in clean_str:
            clean_str = clean_str.split('.')[0] + '+00:00'
            dt = datetime.datetime.fromisoformat(clean_str)
        else:
            raise

    # Normalize to UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    return int(dt.timestamp() * 1000)


@dataclass
class ActivityRecord:
    """
    Represents a single data point (e.g., one second) in rowing training.
    """
    time_ms: int                        # Timestamp in milliseconds since Unix Epoch
    heart_rate: Optional[int] = None    # Heart rate (BPM)
    distance: Optional[float] = None    # Total distance covered in meters (e.g., 500.5)

    cadence: Optional[int] = None       # Stroke rate (SPM)
    watts: Optional[int] = None         # Power in Watts

    position_lat: Optional[float] = None  # Latitude position in degrees
    position_long: Optional[float] = None # Longitude position in degrees

    altitude: Optional[float] = None    # Altitude in meters
    
    def to_fit_record(self) -> Optional[RecordMessage]:
        """
        Converts this dataclass directly into a FIT RecordMessage.
        Returns None if the timestamp is invalid.
        """
        msg = RecordMessage()
        msg.timestamp = self.time_ms # conversion to Garmin timestamp happens internally
        
        if self.heart_rate is not None:
            msg.heart_rate = int(self.heart_rate)

        if self.distance is not None:
            msg.distance = float(self.distance)
            
        if self.cadence is not None:
            # For Sport=ROWING, 'cadence' is automatically interpreted as strokes per minute
            msg.cadence = int(self.cadence)
            
        if self.watts is not None:
            msg.power = int(self.watts)

        if self.position_lat is not None and self.position_long is not None:
            msg.position_lat = self.position_lat
            msg.position_long = self.position_long

        if self.altitude is not None:
            msg.altitude = float(self.altitude)
            
        return msg


def convert_to_fit(tcx_string: str) -> FitFile:
    # 1. create TCX xml tree
    root = ET.fromstring(tcx_string)

    # Build a simple builder
    builder = FitFileBuilder(auto_define=True, min_string_size=50)

    # ==========================================
    # STEP 1: The "Spoofing" Header
    # Telling Garmin: "I am an Edge 1040"
    # ==========================================
    file_id_message = FileIdMessage()
    file_id_message.type = FileType.ACTIVITY
    file_id_message.manufacturer = Manufacturer.GARMIN  # IMPORTANT: ID 1
    file_id_message.product = 3843  # ID for Edge 1040 Solar (Example)
    file_id_message.serial_number = 123456789
    file_id_message.time_created = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000) # ms
    builder.add(file_id_message)

    # Searching for all Trackpoints
    # The typical path is: Activities -> Activity -> Lap -> Track -> Trackpoint
    activity_records = []

    for trackpoint in root.findall('.//ns:Trackpoint', NS):

        time_ms = extract_time(trackpoint)
        if time_ms is None:
            continue  # Trackpoint doesn't make sense without time

        activity_record = ActivityRecord(time_ms=time_ms)
        
        # B. Position (Lat/Lon)
        pos_elem = trackpoint.find('ns:Position', NS)
        if pos_elem is not None:
            lat = pos_elem.find('ns:LatitudeDegrees', NS)
            lon = pos_elem.find('ns:LongitudeDegrees', NS)
            if lat is not None and lon is not None:
                activity_record.position_lat = float(lat.text)
                activity_record.position_long = float(lon.text)

        # C. Altitude
        ele_elem = trackpoint.find('ns:AltitudeMeters', NS)
        if ele_elem is not None:
            activity_record.altitude = float(ele_elem.text)

        dist_elem = trackpoint.find('ns:DistanceMeters', NS)
        if dist_elem is not None:
            activity_record.distance = float(dist_elem.text)

        activity_record.watts = extract_watts(trackpoint)

        # D. Heart Rate (Standard in TCX!)
        # Structure: <HeartRateBpm><Value>145</Value></HeartRateBpm>
        hr_elem = trackpoint.find('ns:HeartRateBpm/ns:Value', NS)
        if hr_elem is not None:
            activity_record.heart_rate = int(hr_elem.text)

        # E. Cadence (Optional, often present in TCX)
        cad_elem = trackpoint.find('ns:Cadence', NS)
        if cad_elem is not None:
            activity_record.cadence = round(float(cad_elem.text))

        activity_records.append(activity_record)

    for record_data in activity_records:
        record = record_data.to_fit_record()
        builder.add(record)
    
    # Write Session Message
    session_message = SessionMessage()
    session_message.sport = Sport.ROWING
    session_message.sub_sport = SubSport.INDOOR_ROWING
    # Setting timestamp to now as the completion time
    session_message.timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    session_message.start_time = activity_records[0].time_ms
    session_message.total_elapsed_time = (activity_records[-1].time_ms - activity_records[0].time_ms) / 1000.0  # in seconds
    session_message.total_timer_time = session_message.total_elapsed_time
    session_message.total_distance = activity_records[-1].distance if activity_records[-1].distance is not None else 0.0
    builder.add(session_message)

    # Write Activity Message
    activity_message = ActivityMessage()

    # 1. Timestamp (Required)
    # This is the moment when the file was "closed" (end of training)
    activity_message.timestamp = activity_records[-1].time_ms 

    # 2. Number of sessions (Required)
    # In 99% of cases, this is "1". 
    # (Only more for multi-sport/triathlon)
    activity_message.num_sessions = 1

    # 3. Type (Required)
    # Defaults to MANUAL, though systems often override this based on session data.
    activity_message.type = Activity.MANUAL

    # 4. Event (Optional, but good practice)
    activity_message.event = Event.ACTIVITY
    activity_message.event_type = EventType.STOP
    builder.add(activity_message)

    return builder.build()


def save_fit_file(fit_file: FitFile, output_path: str) -> None:
    with open(output_path, 'wb') as fit_output:
        fit_file.write(fit_output)
    print(f"Done! File saved as: {output_path}")
