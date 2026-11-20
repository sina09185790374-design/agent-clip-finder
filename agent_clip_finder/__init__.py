"""agent-clip-finder: find the loudest, most quotable moments in a long
recording — without watching the whole video.

Pattern (original code; pattern only, learned from today's radar):
iamajmeena/neonclipping finds clips audio-first: download audio only, score
sudden loudness jumps / raised voices / quiet-to-loud transitions against a
local baseline, let a judge read the transcript, snap clip edges to sentence
boundaries, and only then fetch the chosen video sections. This tool is that
idea as a small stdlib-only Python CLI over a WAV file + an optional SRT
transcript: it scores every 100 ms window, picks the peaks, snaps them to
sentence boundaries, and emits a 9:16 clip plan (JSON + ffmpeg commands).
No network, no keys, no dependencies.
"""

__version__ = "0.1.0"
