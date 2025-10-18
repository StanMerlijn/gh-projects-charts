"""Utility helpers for file I/O and date conversion.

This module contains small helpers used throughout the project, such as
reading files from disk and converting GitHub ISO8601 timestamps to the
project's preferred date string format.
"""
from datetime import datetime
from pathlib import Path


def load_file(filename: Path) -> str:
    """Read the entire contents of a text file and return it as a string.

    Args:
        filename: Path to the file to read.

    Returns:
        The full contents of the file as a string.
    """
    with open(filename, "r") as file:
        file_content = file.read()
        
    return file_content


def utc_to_date(ts: str) -> str:
    """Convert an ISO8601 UTC timestamp into DD-MM-YYYY string format.

    The GitHub API commonly returns timestamps like "2024-01-31T12:34:56Z".
    This function parses such strings and returns a human-friendly
    "DD-MM-YYYY" representation.

    Args:
        ts: ISO8601 timestamp string, e.g. "2024-01-31T12:34:56Z".

    Returns:
        A date string formatted as "DD-MM-YYYY" in UTC.
    """
    # Parse ISO8601 (replace Z with +00:00 for Python's parser)
    dt_utc = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    # Return the date in DD-MM-YYYY format
    return dt_utc.strftime("%d-%m-%Y")
       
    