r"""Standalone binary to merge a SmartRow .fit and .csv into an enriched .fit.

Reads session metadata (start time, total distance) from the original SmartRow
FIT file, parses per-stroke data from the SmartRow CSV export, and writes a
new enriched Garmin FIT file containing one RecordMessage per rowing stroke.

Usage:
    python tools/merge_fit_csv.py \
        --fit_file=path/to/activity.fit \
        --csv_file=path/to/activity.csv \
        --out_file=path/to/output.fit
"""

import sys

from absl import app
from absl import flags
from absl import logging

# Allow importing from the project root regardless of cwd
sys.path.insert(0, ".")

from csv_utils import parse_smartrow_csv
from fit_utils import build_fit_from_csv

FLAGS = flags.FLAGS

flags.DEFINE_string(
    "fit_file",
    None,
    "Path to the original SmartRow .fit file (used for session metadata).",
)
flags.DEFINE_string(
    "csv_file",
    None,
    "Path to the SmartRow CSV export file (csv-us format, per-stroke data).",
)
flags.DEFINE_string(
    "out_file",
    None,
    "Output path where the enriched .fit file will be written.",
)
flags.mark_flag_as_required("fit_file")
flags.mark_flag_as_required("csv_file")
flags.mark_flag_as_required("out_file")


def main(argv: list[str]) -> None:
    """Merges SmartRow FIT metadata with per-stroke CSV data.

    Args:
        argv: Unused remaining command-line arguments after flag parsing.
    """
    del argv  # unused

    logging.info("Reading CSV from: %s", FLAGS.csv_file)
    with open(FLAGS.csv_file, "rb") as fh:
        csv_bytes = fh.read()

    csv_records = parse_smartrow_csv(csv_bytes)
    logging.info("Parsed %d stroke records from CSV.", len(csv_records))

    logging.info("Building enriched FIT file...")
    build_fit_from_csv(
        template_path=FLAGS.fit_file,
        csv_records=csv_records,
        output_path=FLAGS.out_file,
    )

    logging.info("Enriched FIT file written to: %s", FLAGS.out_file)


if __name__ == "__main__":
    app.run(main)
