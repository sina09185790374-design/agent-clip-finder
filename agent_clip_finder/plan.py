"""Turn scored moments into a 9:16 clip plan (JSON + ffmpeg commands).

Rules, in order:
1. Snap start/end to sentence boundaries from the SRT cues.
2. Enforce min/max clip length (extend symmetrically to min, trim to max
   around the peak).
3. Drop lower-scored clips that overlap a kept clip.
4. Every clip gets a title + hook from the transcript under its peak.
"""

from .transcript import cue_at, first_sentence, snap_end, snap_start

DEFAULT_MIN_S = 30.0
DEFAULT_MAX_S = 80.0


def make_plan(moments, audio_path, duration, cues=None, min_s=DEFAULT_MIN_S,
              max_s=DEFAULT_MAX_S, count=3):
    """Build the plan dict for the top ``count`` moments."""
    cues = cues or []
    clips = []
    for moment in sorted(moments, key=lambda m: -m["score"]):
        start, end = moment["start"], moment["end"]
        if cues:
            start = snap_start(cues, start)
            end = snap_end(cues, end)
        peak = moment["peak_t"]
        # Enforce length bounds around the peak.
        if end - start < min_s:
            need = min_s - (end - start)
            start = max(0.0, start - need / 2)
            end = min(duration, end + need / 2)
            if end - start < min_s:  # hit a file edge; extend the other side
                end = min(duration, start + min_s)
                start = max(0.0, end - min_s)
        if end - start > max_s:
            half = max_s / 2
            start = max(0.0, peak - half)
            end = min(duration, start + max_s)
            start = max(0.0, end - max_s)
        if end - start < 1.0:
            continue
        if any(not (end <= c["start"] or start >= c["end"]) for c in clips):
            continue  # overlaps a better clip; drop it
        cue = cue_at(cues, peak) if cues else None
        title = first_sentence(cue["text"]) if cue else f"Moment {len(clips) + 1}"
        clips.append({
            "id": moment["id"],
            "start": round(start, 2),
            "end": round(end, 2),
            "length": round(end - start, 2),
            "score": moment["score"],
            "title": title,
            "hook": title,
            "ffmpeg": (
                f'ffmpeg -ss {start:.2f} -to {end:.2f} -i "{audio_path}" '
                f'-vf "scale=1080:1920:force_original_aspect_ratio=increase,'
                f'crop=1080:1920" -c:v libx264 -crf 18 -c:a aac '
                f'"{moment["id"]}.mp4"'
            ),
        })
        if len(clips) >= count:
            break
    clips.sort(key=lambda c: c["start"])
    return {
        "source": audio_path,
        "duration": round(duration, 2),
        "min_s": min_s,
        "max_s": max_s,
        "clips": clips,
    }


def check_plan(plan, duration=None):
    """CI gate for a plan dict; returns a list of problem strings (empty = pass)."""
    problems = []
    clips = plan.get("clips", [])
    if not clips:
        problems.append("plan has no clips")
    if duration is None:
        duration = plan.get("duration", 0)
    prev_end = None
    for clip in clips:
        start, end = clip.get("start", 0), clip.get("end", 0)
        if start < 0:
            problems.append(f"{clip.get('id')}: starts before 0")
        if duration and end > duration + 0.01:
            problems.append(f"{clip.get('id')}: ends after the audio")
        if end <= start:
            problems.append(f"{clip.get('id')}: empty or reversed range")
            continue
        length = end - start
        if length < plan.get("min_s", 0) - 0.01:
            problems.append(
                f"{clip.get('id')}: {length:.1f}s shorter than min_s "
                f"{plan.get('min_s')}s"
            )
        if length > plan.get("max_s", 10 ** 9) + 0.01:
            problems.append(
                f"{clip.get('id')}: {length:.1f}s longer than max_s "
                f"{plan.get('max_s')}s"
            )
        if not clip.get("title"):
            problems.append(f"{clip.get('id')}: missing title")
        if prev_end is not None and start < prev_end - 0.01:
            problems.append(f"{clip.get('id')}: overlaps the previous clip")
        prev_end = end if prev_end is None else max(prev_end, end)
    return problems
