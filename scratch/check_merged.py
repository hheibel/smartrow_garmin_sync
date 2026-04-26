import sys
import os
sys.path.append(os.getcwd())
from fit_utils import read_fit_file

path = "tests/test_data/latest_merge.fit"
if not os.path.exists(path):
    print(f"File {path} not found.")
    sys.exit(0)

print(f"Checking {path}")
fit = read_fit_file(path)
sessions = [r.message for r in fit.records if type(r.message).__name__ == "SessionMessage"]
activities = [r.message for r in fit.records if type(r.message).__name__ == "ActivityMessage"]
laps = [r.message for r in fit.records if type(r.message).__name__ == "LapMessage"]

if sessions:
    s = sessions[0]
    print(f"Session: start={s.start_time}, end={s.timestamp}, dur={getattr(s, 'total_elapsed_time', 'N/A')}")

if activities:
    a = activities[0]
    print(f"Activity: end={a.timestamp}, timer={getattr(a, 'total_timer_time', 'N/A')}")

if laps:
    l = laps[0]
    print(f"Lap: start={l.start_time}, dur={getattr(l, 'total_elapsed_time', 'N/A')}")

records = [r.message for r in fit.records if type(r.message).__name__ == "RecordMessage"]
if records:
    print(f"First record: {records[0].timestamp}")
    print(f"Last record:  {records[-1].timestamp}")
    print(f"Record span:  {(records[-1].timestamp - records[0].timestamp)/1000}")
