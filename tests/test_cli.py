"""End-to-end CLI tests: demo, feedback round-trip, check gate."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "agent_clip_finder", *args],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
        )

    def test_demo_finds_both_bursts(self):
        out = os.path.join(self.tmp, "demo")
        result = self._run("demo", "--out", out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASSED the gate", result.stdout)
        self.assertIn("moments found: 2", result.stdout)
        self.assertTrue(os.path.exists(os.path.join(out, "demo.wav")))
        self.assertTrue(os.path.exists(os.path.join(out, "demo.srt")))

    def test_plan_and_check_roundtrip(self):
        demo_dir = os.path.join(self.tmp, "demo")
        self._run("demo", "--out", demo_dir)
        plan_path = os.path.join(self.tmp, "plan.json")
        result = self._run(
            "plan", os.path.join(demo_dir, "demo.wav"),
            "--srt", os.path.join(demo_dir, "demo.srt"),
            "--min", "2", "--max", "10", "--count", "2", "--out", plan_path,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(plan_path, encoding="utf-8") as fh:
            plan = json.load(fh)
        self.assertEqual(len(plan["clips"]), 2)
        check = self._run("check", plan_path)
        self.assertEqual(check.returncode, 0, check.stdout)
        self.assertIn("PASS", check.stdout)

    def test_analyze_writes_moments(self):
        demo_dir = os.path.join(self.tmp, "demo")
        self._run("demo", "--out", demo_dir)
        moments_path = os.path.join(self.tmp, "moments.json")
        result = self._run(
            "analyze", os.path.join(demo_dir, "demo.wav"),
            "--srt", os.path.join(demo_dir, "demo.srt"),
            "--out", moments_path,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(moments_path, encoding="utf-8") as fh:
            moments = json.load(fh)
        self.assertGreaterEqual(len(moments), 2)
        self.assertAlmostEqual(moments[0]["peak_t"], 8.0, delta=2.0)

    def test_rate_and_weights(self):
        feedback = os.path.join(self.tmp, "feedback.jsonl")
        for i in range(8):
            result = self._run(
                "rate", "--feedback", feedback, "--moment", f"moment-{i}",
                "--rating", "5",
                "--signals", '{"loud": 4.0, "voice": 1.0, "words": 1.0}',
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        weights = self._run("weights", "--feedback", feedback)
        self.assertEqual(weights.returncode, 0, weights.stderr)
        self.assertIn("ratings: 8", weights.stdout)
        parsed = json.loads(weights.stdout.split("\n", 1)[1])
        self.assertGreater(parsed["loud"], 1.0)

    def test_bad_rating_rejected(self):
        feedback = os.path.join(self.tmp, "feedback.jsonl")
        result = self._run(
            "rate", "--feedback", feedback, "--moment", "moment-1",
            "--rating", "9",
        )
        self.assertNotEqual(result.returncode, 0)
