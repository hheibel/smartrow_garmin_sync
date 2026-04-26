import sys
import os
sys.path.append(os.getcwd())
from fit_utils import read_fit_file

path = "tests/test_data/latest_merge.fit"
fit = read_fit_file(path)
msg_types = [type(r.message).__name__ for r in fit.records]
from collections import Counter
print(Counter(msg_types))
