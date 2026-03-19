"""Tests for the overlap resolver."""
from datetime import datetime, timezone
from src.scheduling.overlap_resolver import find_overlaps, describe_no_overlap


def utc(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def test_basic_two_participant_overlap():
    slots = {
        "alice@example.com": [(utc(2025, 4, 1, 10), utc(2025, 4, 1, 12))],
        "bob@example.com":   [(utc(2025, 4, 1, 11), utc(2025, 4, 1, 13))],
    }
    result = find_overlaps(slots)
    assert len(result) == 1
    assert result[0][0] == utc(2025, 4, 1, 11)
    assert result[0][1] == utc(2025, 4, 1, 12)


def test_no_overlap():
    slots = {
        "alice@example.com": [(utc(2025, 4, 1, 9), utc(2025, 4, 1, 10))],
        "bob@example.com":   [(utc(2025, 4, 1, 11), utc(2025, 4, 1, 12))],
    }
    assert find_overlaps(slots) == []


def test_three_participant_overlap():
    slots = {
        "a@x.com": [(utc(2025, 4, 1, 9), utc(2025, 4, 1, 17))],
        "b@x.com": [(utc(2025, 4, 1, 10), utc(2025, 4, 1, 15))],
        "c@x.com": [(utc(2025, 4, 1, 11), utc(2025, 4, 1, 13))],
    }
    result = find_overlaps(slots)
    assert len(result) == 1
    assert result[0][0] == utc(2025, 4, 1, 11)
    assert result[0][1] == utc(2025, 4, 1, 13)


def test_multiple_overlapping_windows():
    slots = {
        "a@x.com": [
            (utc(2025, 4, 1, 9), utc(2025, 4, 1, 11)),
            (utc(2025, 4, 1, 14), utc(2025, 4, 1, 16)),
        ],
        "b@x.com": [
            (utc(2025, 4, 1, 10), utc(2025, 4, 1, 12)),
            (utc(2025, 4, 1, 14, 30), utc(2025, 4, 1, 17)),
        ],
    }
    result = find_overlaps(slots)
    assert len(result) == 2


def test_empty_availability():
    assert find_overlaps({}) == []


def test_single_participant():
    """Single participant — returns their own slots (filtered for future)."""
    far_future = utc(2099, 1, 1, 10)
    far_future_end = utc(2099, 1, 1, 11)
    slots = {"a@x.com": [(far_future, far_future_end)]}
    result = find_overlaps(slots)
    assert len(result) == 1


def test_minimum_duration_filter():
    """Overlaps shorter than 30 min should be excluded."""
    slots = {
        "a@x.com": [(utc(2099, 4, 1, 10, 0), utc(2099, 4, 1, 10, 20))],
        "b@x.com": [(utc(2099, 4, 1, 9, 50), utc(2099, 4, 1, 10, 20))],
    }
    result = find_overlaps(slots, min_duration_minutes=30)
    assert result == []


def test_describe_no_overlap():
    slots = {"a@x.com": [], "b@x.com": []}
    msg = describe_no_overlap(slots)
    assert "2 participant" in msg
