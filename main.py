import json
import logging as std_logging
import os
import sys
from collections.abc import Sequence
from datetime import datetime
from datetime import timezone

from absl import app
from absl import logging

from garmin_sync import sync_to_garmin
from smartrow_sync import sync_smartrow_activities


class CloudRunJsonFormatter(std_logging.Formatter):
    """Formats logs as JSON for Google Cloud Logging."""

    def format(self, record: std_logging.LogRecord) -> str:
        # Map python log levels to Cloud Logging severities
        severity_map = {
            "DEBUG": "DEBUG",
            "INFO": "INFO",
            "WARNING": "WARNING",
            "ERROR": "ERROR",
            "CRITICAL": "CRITICAL",
            "FATAL": "CRITICAL",
        }
        severity = severity_map.get(record.levelname, "DEFAULT")
        message = super().format(record)

        log_entry = {
            "severity": severity,
            "message": message,
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "logging.googleapis.com/sourceLocation": {
                "file": record.pathname,
                "line": str(record.lineno),
                "function": record.funcName,
            },
        }

        # Include exception info if present
        if record.exc_info:
            log_entry["message"] += f"\n{self.formatException(record.exc_info)}"

        return json.dumps(log_entry)


def setup_logging() -> None:
    """Configures absl logging based on the environment."""
    # Set the output log level of the absl logging system to debug
    logging.set_verbosity(logging.DEBUG)

    # Detect if running in Cloud Run
    if os.environ.get("K_SERVICE") or os.environ.get("CLOUD_RUN_JOB"):
        handler = logging.get_absl_handler()
        handler.setFormatter(CloudRunJsonFormatter())


def main(argv: Sequence[str]) -> None:
    """Main entrypoint for the garmin-syncher application.

    - Synchronizes SmartRow activities into Google Cloud Storage.
    - Synchronizes newly received .fit files from GCS to Garmin Connect.

    Args:
        argv: Command-line arguments.
    """
    del argv  # Unused
    setup_logging()
    logging.info("Starting Garmin Syncher application...")

    try:
        # Sync SmartRow to GCS
        sync_smartrow_activities()

        # Sync GCS to Garmin Connect
        sync_to_garmin()

        logging.info("Garmin Syncher task completed successfully.")
    except Exception as e:
        logging.exception(
            "An unexpected error occurred during execution: %s", e
        )
        sys.exit(1)


if __name__ == "__main__":
    app.run(main)
