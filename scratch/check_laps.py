import sys
import os
sys.path.append(os.getcwd())
from fit_utils import read_fit_file

path = "tests/integration_tests/mock_gcs_bucket/smartrow-activities-sync/20260424_054456_2750185.fit"
fit = read_fit_file(path)
msg_types = [type(r.message).__name__ for r in fit.records]
print(f"Message types in template: {set(msg_types)}")
print(f"Count of LapMessage: {msg_types.count('LapMessage')}")
