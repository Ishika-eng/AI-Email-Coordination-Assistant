"""
Overlap Resolver.

Given a dict mapping participant email → list of (start_utc, end_utc) TimeSlot tuples,
compute all time windows where EVERY participant is available simultaneously.

Returns slots ranked by start time (soonest first).
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

TimeSlot = Tuple[datetime, datetime]


def find_overlaps(
    availability: Dict[str, List[TimeSlot]],
    min_duration_minutes: int = 30,
) -> List[TimeSlot]:
    """
    Compute time windows where all participants are available.

    Args:
        availability: {email: [(start_utc, end_utc), ...], ...}
        min_duration_minutes: Minimum overlap duration to be considered valid.

    Returns:
        Sorted list of (start_utc, end_utc) tuples representing common free windows.
    """
    if not availability:
        return []

    participants = list(availability.keys())
    if len(participants) == 0:
        return []

    logger.info(f"Computing overlaps for {len(participants)} participant(s).")

    # Start with the first participant's slots
    common: List[TimeSlot] = list(availability[participants[0]])

    # Intersect with each subsequent participant
    for participant in participants[1:]:
        their_slots = availability[participant]
        new_common: List[TimeSlot] = []
        for (s1_start, s1_end) in common:
            for (s2_start, s2_end) in their_slots:
                overlap_start = max(s1_start, s2_start)
                overlap_end = min(s1_end, s2_end)
                if overlap_end > overlap_start:
                    new_common.append((overlap_start, overlap_end))
        common = new_common
        if not common:
            logger.info(f"No overlap after intersecting with {participant}.")
            return []

    # Filter out slots shorter than min_duration
    min_delta = timedelta(minutes=min_duration_minutes)
    valid = [(s, e) for s, e in common if (e - s) >= min_delta]

    # Filter out slots in the past
    now = datetime.now(timezone.utc)
    future = [(s, e) for s, e in valid if s > now]

    result = sorted(future, key=lambda x: x[0])
    logger.info(f"Found {len(result)} common slot(s).")
    return result


def describe_no_overlap(availability: Dict[str, List[TimeSlot]]) -> str:
    """
    Returns a human-readable message about who has slots but no common time.
    Used to craft the clarification reply.
    """
    if not availability:
        return "No availability has been received yet."
    responded = list(availability.keys())
    return (
        f"I received availability from {len(responded)} participant(s) "
        f"({', '.join(responded)}), but could not find a common time slot. "
        "Please provide additional time windows."
    )
