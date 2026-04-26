import sys
import os
sys.path.append(os.getcwd())
from fit_utils import read_fit_file

path = "tests/test_data/20251211_065506_2578614.fit"
fit = read_fit_file(path)
for record in fit.records:
    m = record.message
    if type(m).__name__ == "SessionMessage":
        print(f"Session: start_time={m.start_time}, timestamp={m.timestamp}")
    if type(m).__name__ == "RecordMessage":
        pass # print(f"Record: timestamp={m.timestamp}")
