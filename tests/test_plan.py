"""Tests for the clip plan: snapping, length bounds, overlap, the gate."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_clip_finder.plan import check_plan, make_plan

CUES = [
    {"start": 0.0, "end": 4.0, "text": "Hello and welcome."},
    {"start": 4.0, "end": 7.5, "text": "Wow, oh my god, look at this!"},
    {"start": 7.5, "end": 12.0, "text": "Back to the quiet part."},
    {"start": 12.0, "end": 15.0, "text": "No way, that was insane!"},
]

MOMENTS = [
    {"id": "moment-1", "start": 4.2, "end": 6.8, "peak_t": 5.0,
     "score": 4.5, "signals": {"loud": 4.0, "voice": 2.0, "words": 1.0}},
    {"id": "moment-2", "start": 12.3, "end": 14.5, "peak_t": 13.0,
     "score": 4.0, "signals": {"loud": 3.5, "voice": 1.5, "words": 1.0}},
    {"id": "moment-3", "start": 4.5, "end": 6.0, "peak_t": 5.2,
     "score": 3.0, "signals": {"loud": 3.0, "voice": 1.0, "words": 0.0}},
]


class TestMakePlan(unittest.TestCase):
    def test_snaps_to_sentence_boundaries(self):
        plan = make_plan(MOMENTS, "x.wav", 15.0, cues=CUES,
                         min_s=2.0, max_s=10.0, count=3)
        clip = plan["clips"][0]
        self.assertEqual(clip["start"], 4.0)
        self.assertEqual(clip["end"], 7.5)

    def test_drops_overlapping_lower_moment(self):
        plan = make_plan(MOMENTS, "x.wav", 15.0, cues=CUES,
                         min_s=2.0, max_s=10.0, count=3)
        ids = [c["id"] for c in plan["clips"]]
        self.assertIn("moment-1", ids)
        self.assertNotIn("moment-3", ids)  # overlaps moment-1, lower score

    def test_titles_come_from_transcript(self):
        plan = make_plan(MOMENTS, "x.wav", 15.0, cues=CUES,
                         min_s=2.0, max_s=10.0, count=3)
        self.assertIn("Wow", plan["clips"][0]["title"])

    def test_min_length_extended(self):
        short = [dict(MOMENTS[0], start=4.9, end=5.1)]
        plan = make_plan(short, "x.wav", 15.0, cues=CUES,
                         min_s=5.0, max_s=10.0, count=1)
        self.assertGreaterEqual(plan["clips"][0]["length"], 5.0)

    def test_max_length_trimmed(self):
        long_moment = [dict(MOMENTS[0], start=0.0, end=14.0)]
        plan = make_plan(long_moment, "x.wav", 15.0, cues=CUES,
                         min_s=2.0, max_s=6.0, count=1)
        self.assertLessEqual(plan["clips"][0]["length"], 6.0)

    def test_ffmpeg_command_present(self):
        plan = make_plan(MOMENTS, "input.wav", 15.0, cues=CUES,
                         min_s=2.0, max_s=10.0, count=1)
        self.assertIn("ffmpeg", plan["clips"][0]["ffmpeg"])
        self.assertIn("1080:1920", plan["clips"][0]["ffmpeg"])

    def test_clips_sorted_by_start(self):
        plan = make_plan(MOMENTS, "x.wav", 15.0, cues=CUES,
                         min_s=2.0, max_s=10.0, count=3)
        starts = [c["start"] for c in plan["clips"]]
        self.assertEqual(starts, sorted(starts))


class TestCheckPlan(unittest.TestCase):
    def test_valid_plan_passes(self):
        plan = make_plan(MOMENTS, "x.wav", 15.0, cues=CUES,
                         min_s=2.0, max_s=10.0, count=3)
        self.assertEqual(check_plan(plan), [])

    def test_overlap_caught(self):
        plan = {"duration": 20.0, "min_s": 2.0, "max_s": 10.0, "clips": [
            {"id": "a", "start": 1.0, "end": 5.0, "title": "A"},
            {"id": "b", "start": 4.0, "end": 8.0, "title": "B"},
        ]}
        problems = check_plan(plan)
        self.assertTrue(any("overlap" in p for p in problems))

    def test_too_short_caught(self):
        plan = {"duration": 20.0, "min_s": 5.0, "max_s": 10.0, "clips": [
            {"id": "a", "start": 1.0, "end": 3.0, "title": "A"},
        ]}
        problems = check_plan(plan)
        self.assertTrue(any("shorter" in p for p in problems))

    def test_missing_title_caught(self):
        plan = {"duration": 20.0, "min_s": 2.0, "max_s": 10.0, "clips": [
            {"id": "a", "start": 1.0, "end": 5.0, "title": ""},
        ]}
        problems = check_plan(plan)
        self.assertTrue(any("title" in p for p in problems))

    def test_empty_plan_caught(self):
        plan = {"duration": 20.0, "min_s": 2.0, "max_s": 10.0, "clips": []}
        self.assertTrue(check_plan(plan))
