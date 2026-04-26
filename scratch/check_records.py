import sys
import os
sys.path.append(os.getcwd())
from fit_utils import read_fit_file

path = "tests/integration_tests/mock_gcs_bucket/smartrow-activities-sync/20260424_054456_2750185.fit"
if not os.path.exists(path):
    # fallback to the one I know exists
    path = "tests/test_data/20251211_065506_2578614.fit"

print(f"Checking {path}")
fit = read_fit_file(path)
records = [r.message for r in fit.records if type(r.message).__name__ == "RecordMessage"]
sessions = [r.message for r in fit.records if type(r.message).__name__ == "SessionMessage"]

if sessions:
    s = sessions[0]
    print(f"Session: start={s.start_time}, end={s.timestamp}, dur={(s.timestamp-s.start_time)/1000}")

if records:
    print(f"First record: {records[0].timestamp}")
    print(f"Last record:  {records[-1].timestamp}")
    print(f"Record span:  {(records[-1].timestamp - records[0].timestamp)/1000}")
