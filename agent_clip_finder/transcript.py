"""Parse an SRT transcript and snap times to sentence boundaries.

A clip that starts mid-word feels broken; a clip that starts at a sentence
boundary feels intentional. The plan step snaps every moment's start to the
start of the cue that contains it and its end to the end of the cue that
contains it, so cuts land on pauses between utterances.
"""

import re

# Excitement words that mark a quotable line. English + Persian, kept
# small and explicit — this is a signal, not a classifier.
KEYWORDS_EN = [
    "wow", "oh my god", "oh no", "no way", "insane", "unbelievable",
    "look at this", "watch this", "run", "oh shit",
]
KEYWORDS_FA = [
    "وای", "عجب", "ایول", "باورم نمیشه", "وای خدا", "نگاه کن",
]

TIME_RE = re.compile(
    r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)"
)


def _to_seconds(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_srt(text):
    """Parse SRT text into [{start, end, text}]; skips malformed blocks."""
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        if not lines:
            continue
        match = None
        body_start = 0
        for i, line in enumerate(lines):
            match = TIME_RE.search(line)
            if match:
                body_start = i + 1
                break
        if not match:
            continue
        groups = match.groups()
        start = _to_seconds(*groups[0:4])
        end = _to_seconds(*groups[4:8])
        if end <= start:
            continue
        body = " ".join(lines[body_start:])
        if body:
            cues.append({"start": start, "end": end, "text": body})
    cues.sort(key=lambda c: c["start"])
    return cues


def load_srt(path):
    with open(path, encoding="utf-8") as fh:
        return parse_srt(fh.read())


def cue_at(cues, t):
    """The cue covering time t, or None.

    At a boundary shared by two cues (one ends at 8.0, the next starts at
    8.0) the *later* cue wins: the moment belongs to the sentence that is
    starting, not the one that just ended.
    """
    found = None
    for cue in cues:
        if cue["start"] <= t <= cue["end"]:
            found = cue
    return found


def snap_start(cues, t):
    """Start of the cue containing t (or the next cue); t itself if no cues.

    Strict ``>``: a cue that merely *ends* at t does not contain t — the
    next cue starts there.
    """
    if not cues:
        return t
    for cue in cues:
        if cue["end"] > t:
            return cue["start"]
    return cues[-1]["start"]


def snap_end(cues, t):
    """End of the cue containing t (or the previous cue); t itself if no cues.

    Strict ``<``: a cue that merely *starts* at t does not contain t — the
    previous cue ends there.
    """
    if not cues:
        return t
    for cue in reversed(cues):
        if cue["start"] < t:
            return cue["end"]
    return cues[0]["end"]


def keyword_hits(cues, keywords=None):
    """Return {cue_index: [matched words]} for cues containing a keyword."""
    words = list(keywords) if keywords is not None else KEYWORDS_EN + KEYWORDS_FA
    lowered = [(w, w.lower()) for w in words]
    hits = {}
    for i, cue in enumerate(cues):
        text = cue["text"].lower()
        matched = [w for w, lw in lowered if lw in text]
        if matched:
            hits[i] = matched
    return hits


def first_sentence(text, limit=60):
    """First sentence of a cue, truncated — used as clip title/hook."""
    for mark in (".", "!", "?", "؟", "…"):
        if mark in text:
            text = text.split(mark)[0] + mark
            break
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text
