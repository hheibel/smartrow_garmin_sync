import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from fit_utils import (
    parse_iso_time_ms,
    ActivityRecord,
    extract_time,
    extract_watts,
    convert_to_fit,
    NS
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

if __name__ == '__main__':
    unittest.main()
