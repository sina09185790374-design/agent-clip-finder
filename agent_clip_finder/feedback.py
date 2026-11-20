"""Star ratings for moments, stored locally as JSONL.

One line per rating: {"moment_id": ..., "rating": 1..5, "signals": {...}}.
Nothing leaves the machine. After 8 ratings, ``refit_weights`` uses them
to re-weight the three signals toward the rater's taste.
"""

import json

MIN_RATING = 1
MAX_RATING = 5


def append_rating(path, moment_id, rating, signals=None):
    """Append one rating; raises ValueError on a bad rating."""
    rating = int(rating)
    if not MIN_RATING <= rating <= MAX_RATING:
        raise ValueError(f"rating must be {MIN_RATING}-{MAX_RATING}, got {rating}")
    record = {"moment_id": moment_id, "rating": rating}
    if signals:
        record["signals"] = signals
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def load_ratings(path):
    """Load all ratings from a JSONL file (missing file -> [])."""
    ratings = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    ratings.append(json.loads(line))
    except FileNotFoundError:
        pass
    return ratings
