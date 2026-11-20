"""Tests for audio measurement: WAV reading, RMS, ZCR, band energy, baselines."""

import math
import os
import struct
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_clip_finder.audio import (
    duration_s,
    local_baselines,
    measure,
    read_wav,
)

RATE = 16000


def synth_wav(path, segments):
    """segments: [(seconds, kind)] kinds: quiet sine / loud sine / noise."""
    samples = []
    for seconds, kind in segments:
        n = int(seconds * RATE)
        for i in range(n):
            t = i / RATE
            if kind == "quiet":
                samples.append(0.08 * math.sin(2 * math.pi * 220 * t))
            elif kind == "loud":
                samples.append(0.5 * math.sin(2 * math.pi * 300 * t))
            elif kind == "voice":
                samples.append(
                    0.4 * math.sin(2 * math.pi * 300 * t)
                    + 0.15 * math.sin(2 * math.pi * 3000 * t)
                )
            elif kind == "noise":
                samples.append(0.4 * ((i * 7919) % 100 / 50.0 - 1.0))
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(b"".join(
            struct.pack("<h", max(-32768, min(32767, int(s * 32767))))
            for s in samples
        ))
    return path


class TestReadWav(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_roundtrip_mono(self):
        path = os.path.join(self.tmp, "a.wav")
        synth_wav(path, [(1.0, "quiet")])
        samples, rate = read_wav(path)
        self.assertEqual(rate, RATE)
        self.assertAlmostEqual(duration_s(samples, rate), 1.0, places=2)
        self.assertTrue(all(-1.0 <= s <= 1.0 for s in samples))

    def test_empty_wav_rejected(self):
        path = os.path.join(self.tmp, "empty.wav")
        with wave.open(path, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(RATE)
            wav.writeframes(b"")
        with self.assertRaises(ValueError):
            read_wav(path)

    def test_stereo_mixed_down(self):
        path = os.path.join(self.tmp, "stereo.wav")
        with wave.open(path, "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(RATE)
            frames = b"".join(
                struct.pack("<hh", 16384, -16384) for _ in range(RATE)
            )
            wav.writeframes(frames)
        samples, _ = read_wav(path)
        self.assertEqual(len(samples), RATE)
        self.assertAlmostEqual(samples[0], 0.0, places=6)


class TestMeasure(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "mix.wav")
        synth_wav(self.path, [
            (2.0, "quiet"), (1.0, "loud"), (2.0, "quiet"),
            (1.0, "voice"), (2.0, "quiet"),
        ])
        self.samples, self.rate = read_wav(self.path)
        self.rows = measure(self.samples, self.rate)

    def test_loud_burst_has_high_rms(self):
        quiet = [r["rms"] for r in self.rows if r["t"] < 1.5]
        loud = [r["rms"] for r in self.rows if 2.0 <= r["t"] < 3.0]
        self.assertGreater(min(loud), 5 * max(quiet))

    def test_voice_band_above_quiet(self):
        quiet_band = [r["band"] for r in self.rows if r["t"] < 1.5]
        voice_band = [r["band"] for r in self.rows if 5.0 <= r["t"] < 6.0]
        self.assertGreater(min(voice_band), 3 * max(quiet_band))

    def test_noise_has_high_zcr(self):
        path = os.path.join(self.tmp, "noise.wav")
        synth_wav(path, [(1.0, "quiet"), (1.0, "noise")])
        samples, rate = read_wav(path)
        rows = measure(samples, rate)
        quiet_zcr = [r["zcr"] for r in rows if r["t"] < 0.9]
        noise_zcr = [r["zcr"] for r in rows if r["t"] >= 1.0]
        self.assertGreater(min(noise_zcr), 5 * max(quiet_zcr))

    def test_local_baseline_is_previous_block(self):
        baselines = local_baselines(self.rows)
        self.assertEqual(len(baselines), len(self.rows))
        # First block baseline = its own median; later windows in the same
        # short file share it (file is shorter than one 120 s block).
        self.assertAlmostEqual(baselines[0], baselines[-1])
        self.assertGreater(baselines[0], 0)
