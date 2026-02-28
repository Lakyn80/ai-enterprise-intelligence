"""Shared utility functions."""

from datetime import date
from typing import Any


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def date_range_overlap(
    start1: date, end1: date, start2: date, end2: date
) -> bool:
    """Check if two date ranges overlap."""
    return start1 <= end2 and end1 >= start2
