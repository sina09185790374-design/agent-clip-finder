"""Tests for SRT parsing, sentence snapping, keyword hits."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_clip_finder.transcript import (
    cue_at,
    first_sentence,
    keyword_hits,
    parse_srt,
    snap_end,
    snap_start,
)

SRT = """1
00:00:00,000 --> 00:00:04,000
Hello and welcome to the show.

2
00:00:04,000 --> 00:00:07,500
Wow, oh my god, look at this!

3
00:00:07,500 --> 00:00:12,000
وای خدا، عجب بازی‌ای بود.

4
00:00:12,000 --> 00:00:15,000
And that is all for today.
"""


class TestParseSrt(unittest.TestCase):
    def test_parses_four_cues(self):
        cues = parse_srt(SRT)
        self.assertEqual(len(cues), 4)
        self.assertAlmostEqual(cues[0]["start"], 0.0)
        self.assertAlmostEqual(cues[1]["end"], 7.5)
        self.assertIn("welcome", cues[0]["text"])

    def test_malformed_blocks_skipped(self):
        cues = parse_srt("no timing here\n\n" + SRT)
        self.assertEqual(len(cues), 4)

    def test_empty_text(self):
        self.assertEqual(parse_srt(""), [])


class TestSnapping(unittest.TestCase):
    def setUp(self):
        self.cues = parse_srt(SRT)

    def test_snap_start_to_cue_start(self):
        self.assertAlmostEqual(snap_start(self.cues, 5.2), 4.0)

    def test_snap_end_to_cue_end(self):
        self.assertAlmostEqual(snap_end(self.cues, 5.2), 7.5)

    def test_snap_without_cues_is_identity(self):
        self.assertAlmostEqual(snap_start([], 5.2), 5.2)
        self.assertAlmostEqual(snap_end([], 5.2), 5.2)

    def test_cue_at(self):
        cue = cue_at(self.cues, 5.0)
        self.assertIn("Wow", cue["text"])
        self.assertIsNone(cue_at(self.cues, 99.0))


class TestKeywords(unittest.TestCase):
    def test_english_and_persian_hits(self):
        hits = keyword_hits(parse_srt(SRT))
        self.assertIn(1, hits)  # "Wow, oh my god"
        self.assertIn(2, hits)  # Persian "وای خدا"
        self.assertNotIn(0, hits)
        self.assertNotIn(3, hits)

    def test_first_sentence(self):
        self.assertEqual(
            first_sentence("Wow, oh my god, look at this! Did you see?"),
            "Wow, oh my god, look at this!",
        )
        self.assertEqual(first_sentence("Short."), "Short.")
