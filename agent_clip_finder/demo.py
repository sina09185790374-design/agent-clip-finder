"""Deterministic demo: synthesize a WAV + SRT, find the moments, plan clips.

The synthetic recording is 24 s at 16 kHz mono:
- 0-8 s quiet talk (220 Hz sine, amplitude 0.08)
- 8-11 s a shout: loud, noisy, with a 3 kHz tone ("Wow, oh my god!")
- 11-18 s quiet talk again
- 18-20.5 s a second burst ("No way, that was insane!")
- 20.5-24 s quiet outro

The pipeline must find both bursts and snap the clips to the SRT cues.
"""

import math
import os
import random
import struct
import wave

from .audio import duration_s, local_baselines, measure, read_wav
from .plan import make_plan
from .scoring import find_moments, score_windows
from .transcript import keyword_hits, load_srt

SAMPLE_RATE = 16000
DEMO_SRT = """1
00:00:00,000 --> 00:00:08,000
Welcome back. Today we are going to look at a quiet level.

2
00:00:08,000 --> 00:00:11,000
Wow, oh my god, look at this! Did you see that?

3
00:00:11,000 --> 00:00:18,000
Okay, back to the plan. Nothing special happens here.

4
00:00:18,000 --> 00:00:20,500
No way, that was insane! Unbelievable play!

5
00:00:20,500 --> 00:00:24,000
And that is the end of the video. Thanks for watching.
"""


def _segment(rng, duration, kind):
    """Generate one segment of mono samples."""
    n = int(duration * SAMPLE_RATE)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        if kind == "quiet":
            out.append(0.08 * math.sin(2 * math.pi * 220 * t))
        elif kind == "shout":
            # Loud + noisy (high zero-crossing rate) + 3 kHz raised voice.
            out.append(
                0.45 * math.sin(2 * math.pi * 300 * t)
                + 0.15 * math.sin(2 * math.pi * 3000 * t)
                + 0.20 * (rng.random() * 2 - 1)
            )
        else:
            out.append(0.0)
    return out


def write_demo_wav(path):
    """Write the 24 s synthetic demo recording."""
    rng = random.Random(42)
    samples = []
    samples += _segment(rng, 8.0, "quiet")
    samples += _segment(rng, 3.0, "shout")
    samples += _segment(rng, 7.0, "quiet")
    samples += _segment(rng, 2.5, "shout")
    samples += _segment(rng, 3.5, "quiet")
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        frames = b"".join(
            struct.pack("<h", max(-32768, min(32767, int(s * 32767))))
            for s in samples
        )
        wav.writeframes(frames)
    return path


def run_demo(out_dir):
    """Write demo WAV + SRT into out_dir, run the pipeline, return the plan."""
    os.makedirs(out_dir, exist_ok=True)
    wav_path = os.path.join(out_dir, "demo.wav")
    srt_path = os.path.join(out_dir, "demo.srt")
    write_demo_wav(wav_path)
    with open(srt_path, "w", encoding="utf-8") as fh:
        fh.write(DEMO_SRT)
    samples, rate = read_wav(wav_path)
    rows = measure(samples, rate)
    baselines = local_baselines(rows)
    cues = load_srt(srt_path)
    hits = keyword_hits(cues)
    scored = score_windows(rows, baselines, cues, hits)
    moments = find_moments(scored, duration_s(samples, rate), top=10)
    plan = make_plan(
        moments, wav_path, duration_s(samples, rate),
        cues=cues, min_s=2.0, max_s=10.0, count=3,
    )
    return plan, moments
