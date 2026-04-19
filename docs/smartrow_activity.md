# SmartRow Activity Data Structure

The SmartRow API returns activities as a list of JSON objects. Based on the provided sample, an activity represents a rowing session with various metrics tracking performance, duration, user biometrics, and sync states.

## Critical Information

The following fields are generally the most crucial for syncing or tracking data:

> [!WARNING]
> When downloading TCX data using `get_activity_tcx`, you MUST use the `public_id`. Trying to use the standard integer `id` is a common mistake and will fail.

| Field | Type | Description | Example |
|---|---|---|---|
| `id` | Integer | The unique internal identifier for the activity within SmartRow. Do NOT use this for `get_activity_tcx`. | `2694175` |
| `public_id`| String (UUID)| The public identifier used for downloading the TCX file. **Required by `get_activity_tcx`**. | `"d8f8a...af38"`|
| `created` | String (ISO 8601) | The timestamp representing when the activity was created/started. | `"2026-03-05T06:53:50.807Z"` |
| `strava_id` | String | The corresponding ID of the activity if it has been synced to Strava. | `"18707734213"` |
| `distance` | Integer | The total distance rowed in meters. | `8500` |
| `elapsed_seconds` | Integer | The total time of the activity in seconds. | `2491` |

## Full Field Reference

Below is a breakdown of all fields available in a SmartRow activity object:

*   **`id`** (Integer): Unique activity ID.
*   **`calories`** (Float): Estimated calories burned (e.g., `314.302`).
*   **`distance`** (Integer): Distance covered in meters (e.g., `8500`).
*   **`elapsed_seconds`** (Integer): Total time in seconds (e.g., `2491`).
*   **`extra_millies`** (Integer): Additional milliseconds to add to the total duration.
*   **`time`** (Nullable String): Time string. Often `null` depending on activity type.
*   **`p_ave`** (Integer): Average power in Watts (e.g., `125`).
*   **`stroke_count`** (Integer): Total number of strokes taken during the session (e.g., `932`).
*   **`option`** (String): The type of target set for the session. E.g., `"Distance"`.
*   **`option_distance`** (Integer): The target distance for the session (if `option` is "Distance").
*   **`option_time`** (Integer): The target time for the session.
*   **`created`** (String): Creation date of the activity in UTC.
*   **`account`** (Integer): User account ID.
*   **`mod`** (String): Last modified timestamp in UTC.
*   **`device_mac`** (String): The MAC address of the device used.
*   **`accessory_mac`** (String): The MAC address of connected accessories (e.g., HR monitor).
*   **`ave_bpm`** (Integer): Average heart rate in beats per minute (e.g., `158`).
*   **`watt_per_beat`** (Float): Efficiency metric, Watts generated per heartbeat.
*   **`ave_power`** (Nullable Float): Average power, though `p_ave` is often used instead.
*   **`watt_kg`** (Float): Power-to-weight ratio (Watts per kilogram).
*   **`strava_id`** (String): The synced Strava activity ID.
*   **`curve`** (String): A semicolon-separated string representing the force curve shape.
*   **`confirmed`** (Boolean): Whether the activity has been confirmed/validated.
*   **`race`** (Nullable String): Information about the race, if applicable.
*   **`public_id`** (String): A UUID for sharing the activity publicly.
*   **`user_age`** (Integer): The user's age at the time of the activity.
*   **`user_weight`** (Integer): The user's weight in kilograms at the time of the activity.
*   **`user_max_hr`** (Integer): The user's configured max heart rate.
*   **`protocol_version`** (Integer): The version of the smartrow protocol used.
*   **`is_interval`** (Boolean): Indicates whether the session was an interval workout.
*   **`calc_ave_split`** (Integer): Calculated average split time (typically in seconds per 500m).
*   **`calc_avg_stroke_work`** (Integer): Calculated average work per stroke in Joules.
*   **`calc_avg_stroke_rate`** (Float): Calculated average stroke rate (strokes per minute).
