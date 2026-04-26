# FIT Format Analysis Guide

This document provides guidance for analyzing FIT files in this repository, particularly for ensuring compatibility with Garmin Connect after synchronization.

## Analysis Tool: `fit_analyzer.py`

The primary tool for analysis is located at `tools/fit_analyzer.py`. It consolidates several previous diagnostic scripts.

### Basic Usage

#### 1. Summary of Messages
Get a count of all message types in a file and high-level session info.
```bash
python tools/fit_analyzer.py summary path/to/file.fit
```

#### 2. Detailed Inspection
View all fields for specific message types (e.g., `SessionMessage`, `RecordMessage`).
```bash
python tools/fit_analyzer.py inspect path/to/file.fit -t SessionMessage ActivityMessage -n 1
```

#### 3. Field Comparison
Compare which fields are present/absent in all message types between two files. This is useful for identifying missing metadata.
```bash
python tools/fit_analyzer.py compare-fields reference.fit merged.fit
```

#### 4. Consistency Check
Check if durations and timestamps align across `RecordMessage`, `LapMessage`, and `SessionMessage`. This is crucial for fixing the "Double Duration" issue on Garmin.
```bash
python tools/fit_analyzer.py consistency path/to/file.fit
```

#### 5. Value Comparison
Compare values for key metadata messages (`FileIdMessage`, `SessionMessage`, `ActivityMessage`) between two files.
```bash
python tools/fit_analyzer.py compare original.fit modified.fit
```

---

## Key FIT Concepts for this Project

### Session vs. Activity
- **`SessionMessage`**: Contains the bulk of the summary data (average heart rate, total distance, sport type). This is what Garmin uses for most of its display.
- **`ActivityMessage`**: Usually a single message at the end of the file. Its `timestamp` should match the session's `timestamp`.

### Critical Fields for Garmin Compatibility

| Message | Field | Importance |
| :--- | :--- | :--- |
| `FileIdMessage` | `manufacturer` | Must be `GARMIN` (1) for many features to work. |
| `FileIdMessage` | `product` | Spoofed to a real Garmin device (e.g., Edge 1040) to enable Training Effect. |
| `SessionMessage` | `sport` | Set to `ROWING` (15). |
| `SessionMessage` | `sub_sport` | Set to `INDOOR_ROWING` (14). |
| `SessionMessage` | `total_elapsed_time` | Total time including pauses. Must match `timestamp - start_time`. |
| `SessionMessage` | `total_timer_time` | Moving time. Usually set equal to elapsed time for indoor rowing. |

### The "Double Duration" Bug
Garmin sometimes displays double the actual duration if the `SessionMessage` duration fields don't exactly match the span of the `RecordMessage` timestamps.
- **Fix**: Ensure `SessionMessage.total_elapsed_time == (last_record.timestamp - first_record.timestamp) / 1000.0`.
- **Validation**: Use `python tools/fit_analyzer.py consistency <file>`.

### Heart Rate and Power
SmartRow provides high-quality power and stroke data.
- **Power**: Stored in `RecordMessage.power`.
- **Cadence**: Stored in `RecordMessage.cadence` (SPM).
- **Speed**: Stored in `RecordMessage.enhanced_speed` (m/s).

## Common Troubleshooting Steps

1. **Activity not showing Training Effect**:
   - Check if `manufacturer` is Garmin.
   - Check if `product` ID is set to a valid Garmin device.
   - Ensure `heart_rate` data is present in `RecordMessage`s.

2. **Distance or Speed Mismatches**:
   - Verify `SessionMessage.total_distance` vs the last `RecordMessage.distance`.
   - Ensure units are correct (meters for distance, m/s for speed).

3. **Missing Map on Garmin**:
   - Indoor rowing doesn't typically have a map, but Garmin expects `position_lat` and `position_long` to be absent or consistent.
   - If `position_lat/long` are present, Garmin might try to render a map.
