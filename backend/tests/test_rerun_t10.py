"""Clock-change coverage labels must distinguish separate recorded hours."""

from datetime import datetime

import numpy as np

from app.model import Segments
from tools.rerun_t10 import _runs_by_hour


def segments_at(*instants: str) -> Segments:
    origins = np.array(
        sorted(int(datetime.fromisoformat(t).timestamp()) for t in instants),
        dtype=np.int64,
    )
    ids = np.array([str(i) for i in range(len(origins))])
    return Segments(ids, ids, origins, origins + 600)


def test_repeated_london_hour_keeps_bst_and_gmt_counts_separate():
    report = _runs_by_hour(segments_at(
        "2026-10-25T00:10:00+00:00",
        "2026-10-25T00:40:00+00:00",
        "2026-10-25T01:20:00+00:00",
    ))
    assert report == (
        "2026-10-25 01:00 BST (+0100): 2, "
        "2026-10-25 01:00 GMT (+0000): 1"
    )


def test_same_weekday_and_hour_on_different_dates_stay_separate():
    report = _runs_by_hour(segments_at(
        "2026-10-24T15:30:00+00:00",
        "2026-10-31T16:30:00+00:00",
    ))
    assert report == (
        "2026-10-24 16:00 BST (+0100): 1, "
        "2026-10-31 16:00 GMT (+0000): 1"
    )
