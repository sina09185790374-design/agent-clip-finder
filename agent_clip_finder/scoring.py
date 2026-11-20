"""Score windows and pick the moments worth clipping.

Three signals, one weighted sum (defaults mirror the pattern's ranking):
- ``loud`` — window RMS vs the local baseline (sudden jumps score high).
- ``voice`` — 2-4 kHz band energy vs the file median (raised voices).
- ``words`` — an excitement keyword in the transcript cue under the window.

Weights are learned from the user's own 1-5 star ratings
(``feedback.jsonl``): after 8 ratings the weights are refit — pulled
toward the defaults, blended in gradually, exactly like the pattern's
ridge-regression update. Fewer than 8 ratings: defaults, unchanged.
"""

from statistics import median

DEFAULT_WEIGHTS = {"loud": 1.0, "voice": 0.7, "words": 0.8}
MIN_RATINGS_TO_REFIT = 8


def score_windows(rows, baselines, cues, keyword_hits, weights=None):
    """Score every window; returns [{t, loud, voice, words, score}]."""
    weights = weights or DEFAULT_WEIGHTS
    band_median = median([r["band"] for r in rows]) if rows else 0.0
    band_median = band_median or 1e-9
    hit_times = set()
    for idx in keyword_hits:
        hit_times.add((cues[idx]["start"], cues[idx]["end"]))
    scored = []
    for row, base in zip(rows, baselines):
        base = base or 1e-9
        loud = min(row["rms"] / base, 5.0)
        voice = min(row["band"] / band_median, 5.0)
        words = 0.0
        for start, end in hit_times:
            if start <= row["t"] < end:
                words = 1.0
                break
        score = (
            weights["loud"] * loud
            + weights["voice"] * voice
            + weights["words"] * words
        )
        scored.append(
            {"t": row["t"], "loud": loud, "voice": voice,
             "words": words, "score": score}
        )
    return scored


def find_moments(scored, duration, top=10, min_gap=8.0, window_s=0.1):
    """Pick peak windows as moments, best first, at least min_gap apart.

    A moment's span grows from its peak while neighbouring windows keep at
    least half the peak's score (capped at 90 s). Moments are returned
    sorted by start time.
    """
    if not scored:
        return []
    peak_score = max(s["score"] for s in scored)
    median_score = median([s["score"] for s in scored])
    # A moment must clearly beat the ordinary windows: halfway from the
    # median to the peak. Flat audio (peak == median) yields no moments.
    floor = median_score + 0.5 * (peak_score - median_score)
    by_score = sorted(scored, key=lambda s: -s["score"])
    peaks = []
    for cand in by_score:
        if cand["score"] <= floor:
            break
        if all(abs(cand["t"] - p["t"]) >= min_gap for p in peaks):
            peaks.append(cand)
        if len(peaks) >= top:
            break
    by_time = {round(s["t"], 3): s for s in scored}
    moments = []
    for i, peak in enumerate(sorted(peaks, key=lambda p: p["t"])):
        half = 0.5 * peak["score"]
        start = peak["t"]
        while start - window_s >= 0:
            prev = by_time.get(round(start - window_s, 3))
            if prev is None or prev["score"] < half:
                break
            start -= window_s
        end = peak["t"] + window_s
        while end + window_s <= duration and end - peak["t"] < 90.0:
            nxt = by_time.get(round(end, 3))
            if nxt is None or nxt["score"] < half:
                break
            end += window_s
        moments.append({
            "id": f"moment-{i + 1}",
            "start": round(start, 2),
            "end": round(min(end, duration), 2),
            "peak_t": round(peak["t"], 2),
            "score": round(peak["score"], 3),
            "signals": {
                "loud": round(peak["loud"], 3),
                "voice": round(peak["voice"], 3),
                "words": peak["words"],
            },
        })
    return moments


def refit_weights(ratings, weights=None):
    """Refit signal weights from 1-5 star ratings; defaults below 8 ratings.

    ``ratings`` is a list of {"signals": {"loud":..,"voice":..,"words":..},
    "rating": 1..5}. For each signal, take the mean rating of the moments
    where that signal was the *dominant* contributor; rating 3 is neutral
    (factor 1.0), 5 pushes the weight up, 1 pushes it down. The result is
    70% defaults + 30% adjusted, clipped to [0.5x, 1.5x] of the default —
    pulled toward the defaults, blended in gradually.
    """
    weights = dict(weights or DEFAULT_WEIGHTS)
    if len(ratings) < MIN_RATINGS_TO_REFIT:
        return weights
    new_weights = {}
    for signal, default in weights.items():
        dominant = [
            r["rating"] for r in ratings
            if r.get("signals") and max(r["signals"], key=r["signals"].get) == signal
        ]
        if not dominant:
            new_weights[signal] = default
            continue
        mean_rating = sum(dominant) / len(dominant)
        factor = mean_rating / 3.0
        adjusted = default * factor
        blended = 0.7 * default + 0.3 * adjusted
        new_weights[signal] = round(
            min(max(blended, 0.5 * default), 1.5 * default), 3
        )
    return new_weights
