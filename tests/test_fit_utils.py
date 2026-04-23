import os
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from fit_utils import (
    parse_iso_time_ms,
    ActivityRecord,
    extract_time,
    extract_watts,
    convert_to_fit,
    NS,
    rewrite_fit_file_attributes,
    read_fit_file
)

class TestFitUtils(unittest.TestCase):

    def test_parse_iso_time_ms(self) -> None:
        # Basic UTC time
        self.assertEqual(parse_iso_time_ms("2023-10-25T18:00:00Z"), 1698256800000)
        # Time with milliseconds - should reflect 500ms
        self.assertEqual(parse_iso_time_ms("2023-10-25T18:00:00.500Z"), 1698256800500)
        # Time with +00:00
        self.assertEqual(parse_iso_time_ms("2023-10-25T18:00:00+00:00"), 1698256800000)

    def test_activity_record_to_fit_record(self) -> None:
        record = ActivityRecord(
            time_ms=1698256800000,
            heart_rate=150,
            distance=1000.5,
            cadence=25,
            watts=200,
            position_lat=52.52,
            position_long=13.40,
            altitude=10.0
        )
        msg = record.to_fit_record()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.timestamp, 1698256800000)
        self.assertEqual(msg.heart_rate, 150)
        self.assertEqual(msg.distance, 1000.5)
        self.assertEqual(msg.cadence, 25)
        self.assertEqual(msg.power, 200)
        # fit-tool returns a double which might have tiny float precision differences
        self.assertAlmostEqual(msg.position_lat, 52.52, places=6)
        self.assertAlmostEqual(msg.position_long, 13.40, places=6)
        self.assertEqual(msg.altitude, 10.0)

    def test_extract_time(self) -> None:
        xml = '<Trackpoint xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"><Time>2023-10-25T18:00:00Z</Time></Trackpoint>'
        elem = ET.fromstring(xml)
        # Note: We need to register namespace prefix for find if we don't use the full URL in the tag,
        # but here the xmlns is already there. However, ET.fromstring doesn't automatically know prefixes like 'ns'.
        # We use the NS dict from fit_utils.
        self.assertEqual(extract_time(elem), 1698256800000)

    def test_extract_watts(self) -> None:
        xml = """
        <Trackpoint xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
                    xmlns:ax="http://www.garmin.com/xmlschemas/ActivityExtension/v2">
            <Extensions>
                <ax:TPX>
                    <ax:Watts>200</ax:Watts>
                </ax:TPX>
            </Extensions>
        </Trackpoint>
        """
        elem = ET.fromstring(xml)
        self.assertEqual(extract_watts(elem), 200)

    def test_convert_to_fit(self) -> None:
        tcx_content = """<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
                        xmlns:ax="http://www.garmin.com/xmlschemas/ActivityExtension/v2">
    <Activities>
        <Activity Sport="Rowing">
            <Id>2023-10-25T18:00:00Z</Id>
            <Lap StartTime="2023-10-25T18:00:00Z">
                <Track>
                    <Trackpoint>
                        <Time>2023-10-25T18:00:00Z</Time>
                        <DistanceMeters>0.0</DistanceMeters>
                        <HeartRateBpm><Value>100</Value></HeartRateBpm>
                        <Cadence>0</Cadence>
                        <Extensions>
                            <ax:TPX><ax:Watts>0</ax:Watts></ax:TPX>
                        </Extensions>
                    </Trackpoint>
                    <Trackpoint>
                        <Time>2023-10-25T18:00:01Z</Time>
                        <DistanceMeters>5.0</DistanceMeters>
                        <HeartRateBpm><Value>105</Value></HeartRateBpm>
                        <Cadence>20</Cadence>
                        <Extensions>
                            <ax:TPX><ax:Watts>150</ax:Watts></ax:TPX>
                        </Extensions>
                    </Trackpoint>
                </Track>
            </Lap>
        </Activity>
    </Activities>
</TrainingCenterDatabase>
"""
        fit_file = convert_to_fit(tcx_content)
        self.assertIsNotNone(fit_file)
        # Basic check: should have multiple records (messages) in the fit file
        self.assertTrue(len(fit_file.records) > 0)

    def test_rewrite_fit_file_attributes(self) -> None:
        input_path = os.path.join(os.path.dirname(__file__), 'test_data', '20251211_065506_2578614.fit')
        output_path = os.path.join(os.path.dirname(__file__), 'test_data', 'rewritten_test.fit')
        
        # Ensure we don't accidentally use a stale output file
        if os.path.exists(output_path):
            os.remove(output_path)
            
        try:
            rewrite_fit_file_attributes(input_path, output_path)
            
            # Read rewritten file and validate
            rewritten_fit = read_fit_file(output_path)
            
            file_id_msg = None
            session_msgs = []
            activity_msg = None
            for record in rewritten_fit.records:
                if type(record.message).__name__ == 'FileIdMessage':
                    file_id_msg = record.message
                if type(record.message).__name__ == 'SessionMessage':
                    session_msgs.append(record.message)
                if type(record.message).__name__ == 'ActivityMessage':
                    activity_msg = record.message
                    
            self.assertIsNotNone(file_id_msg)
            self.assertEqual(getattr(file_id_msg, 'manufacturer', None), 1)
            self.assertEqual(getattr(file_id_msg, 'product', None), 3843)
            self.assertEqual(getattr(file_id_msg, 'serial_number', None), 123456789)
            
            # Verify deduplication: exactly one session should remain (source only had one anyway)
            self.assertEqual(len(session_msgs), 1)
            session_msg = session_msgs[0]
            
            # Verify the max_speed was correctly aggregated from LapMessages
            self.assertAlmostEqual(getattr(session_msg, 'max_speed', None), 4.425, places=3)
            
            # Verify the duration was recalculated correctly based on wall-clock time
            # Timestamp (End): 1765438420000, Start Time: 1765436106000
            # Diff: 2314000ms = 2314.0s (38:34.000)
            self.assertEqual(getattr(session_msg, 'total_elapsed_time', None), 2314.0)
            self.assertEqual(getattr(session_msg, 'total_timer_time', None), 2314.0)
            
            # Verify correct indexing and activity header
            self.assertEqual(getattr(session_msg, 'message_index', None), 0)
            self.assertIsNotNone(activity_msg)
            self.assertEqual(getattr(activity_msg, 'num_sessions', None), 1)
            self.assertEqual(getattr(activity_msg, 'total_timer_time', None), 2314.0)
        finally:
            # Clean up
            # if os.path.exists(output_path):
            #     os.remove(output_path)
            print(f"Cleaned up {output_path}")

if __name__ == '__main__':
    unittest.main()
