"""Read a WAV file and measure it in short windows.

All measurements are pure stdlib (``wave`` + ``struct`` + ``math``).
Supported input: PCM WAV, 8/16/24/32-bit, any channel count (mixed down
to mono by averaging). Anything else raises ValueError.

Signals per 100 ms window:
- ``rms`` — loudness (root mean square of the samples).
- ``zcr`` — zero-crossing rate, a cheap proxy for noisy/shouty content.
- ``band`` — magnitude of the 2-4 kHz band (Goertzel at 2.5 and 3.5 kHz),
  where raised voices carry most of their energy.

The loudness baseline is local, like the pattern: the audio is split into
120-second blocks and each window is compared against the median RMS of
the *previous* block (the first block uses its own median), so a loud
section late in a long recording is judged against what came before it,
not against a quiet intro an hour earlier.
"""

import math
import struct
import wave
from statistics import median

WINDOW_S = 0.1
BASELINE_BLOCK_S = 120.0
# Three probes across the 2-4 kHz raised-voice band. A pure tone exactly
# between two probes (e.g. 3 kHz vs probes at 2.5/3.5 kHz) is 50 bins away
# in a 100 ms window, and a Hann window kills it almost completely — so
# the middle of the band needs its own probe.
VOICE_FREQS = (2500.0, 3000.0, 3500.0)


def read_wav(path):
    """Return (samples, sample_rate): mono float samples in [-1, 1]."""
    with wave.open(path, "rb") as wav:
        n_channels = wav.getnchannels()
        width = wav.getsampwidth()
        rate = wav.getframerate()
        n_frames = wav.getnframes()
        raw = wav.readframes(n_frames)
    if width not in (1, 2, 3, 4):
        raise ValueError(f"unsupported sample width: {width} bytes")
    if n_frames == 0:
        raise ValueError("empty WAV file")
    fmt = {1: "B", 2: "h", 3: None, 4: "i"}[width]
    samples = []
    if width == 3:
        # 24-bit: manual little-endian decode.
        for i in range(0, len(raw), 3):
            value = int.from_bytes(raw[i:i + 3], "little", signed=True)
            samples.append(value / 8388608.0)
    else:
        count = len(raw) // width
        values = struct.unpack(f"<{count}{fmt}", raw[:count * width])
        scale = {1: 128.0, 2: 32768.0, 4: 2147483648.0}[width]
        offset = 128.0 if width == 1 else 0.0
        samples = [(v - offset) / scale for v in values]
    if n_channels > 1:
        mono = []
        for i in range(0, len(samples) - n_channels + 1, n_channels):
            mono.append(sum(samples[i:i + n_channels]) / n_channels)
        samples = mono
    return samples, rate


def _windows(samples, rate, window_s=WINDOW_S):
    """Yield (start_s, [samples]) for consecutive non-overlapping windows."""
    size = max(1, int(round(rate * window_s)))
    for i in range(0, len(samples), size):
        chunk = samples[i:i + size]
        yield i / rate, chunk


def _goertzel(chunk, rate, freq):
    """Magnitude of one frequency bin (Goertzel algorithm).

    The chunk is Hann-windowed first: without it, a tone that completes
    a whole number of cycles in the window leaks exactly zero into the
    other bins (a spectral null), so a 3 kHz shout would score the same
    as silence at the 2.5/3.5 kHz probes.
    """
    n = len(chunk)
    if n == 0:
        return 0.0
    windowed = [
        x * 0.5 * (1.0 - math.cos(2.0 * math.pi * i / (n - 1)))
        for i, x in enumerate(chunk)
    ]
    k = int(round(freq * n / rate))
    w = 2.0 * math.pi * k / n
    coeff = 2.0 * math.cos(w)
    s1 = 0.0
    s2 = 0.0
    for x in windowed:
        s0 = x + coeff * s1 - s2
        s2 = s1
        s1 = s0
    power = s1 * s1 + s2 * s2 - coeff * s1 * s2
    return math.sqrt(max(power, 0.0)) / n


def measure(samples, rate, window_s=WINDOW_S):
    """Return a list of per-window dicts: {t, rms, zcr, band}."""
    rows = []
    for start, chunk in _windows(samples, rate, window_s):
        n = len(chunk)
        rms = math.sqrt(sum(x * x for x in chunk) / n) if n else 0.0
        crossings = sum(
            1 for a, b in zip(chunk, chunk[1:]) if (a < 0) != (b < 0)
        )
        zcr = crossings / (2.0 * window_s) if window_s else 0.0
        band = max(_goertzel(chunk, rate, f) for f in VOICE_FREQS)
        rows.append({"t": start, "rms": rms, "zcr": zcr, "band": band})
    return rows


def local_baselines(rows, window_s=WINDOW_S, block_s=BASELINE_BLOCK_S):
    """Median RMS of the previous 120 s block, per window.

    Returns a list of baseline values aligned with ``rows``.
    """
    if not rows:
        return []
    block_windows = max(1, int(round(block_s / window_s)))
    baselines = []
    current = None
    for i, row in enumerate(rows):
        block = i // block_windows
        if i % block_windows == 0:
            # Start of a new block: freeze the previous block's median
            # as the baseline for this whole block (first block: its own
            # median, computed from the block itself below).
            if block == 0:
                stop = min(len(rows), block_windows)
                current = median(r["rms"] for r in rows[:stop]) or 1e-9
            else:
                start = (block - 1) * block_windows
                stop = min(len(rows), block * block_windows)
                current = median(r["rms"] for r in rows[start:stop]) or 1e-9
        baselines.append(current)
    return baselines


def duration_s(samples, rate):
    return len(samples) / rate if rate else 0.0
