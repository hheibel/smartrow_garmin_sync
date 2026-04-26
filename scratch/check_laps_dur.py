import sys
import os
sys.path.append(os.getcwd())
from fit_utils import read_fit_file

path = "tests/test_data/latest_merge.fit"
fit = read_fit_file(path)
laps = [r.message for r in fit.records if type(r.message).__name__ == "LapMessage"]
for i, l in enumerate(laps):
    print(f"Lap {i}: start={l.start_time}, elapsed={getattr(l, 'total_elapsed_time', 'N/A')}")
