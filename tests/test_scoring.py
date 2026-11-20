"""Tests for scoring, moment picking and weight refit."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_clip_finder.scoring import (
    DEFAULT_WEIGHTS,
    find_moments,
    refit_weights,
    score_windows,
)


def fake_rows(n=100, burst_at=50):
    """100 windows of 0.1 s; a loud burst around burst_at."""
    rows = []
    for i in range(n):
        loud = i == burst_at
        rows.append({
            "t": round(i * 0.1, 3),
            "rms": 0.5 if loud else 0.08,
            "zcr": 4000 if loud else 200,
            "band": 0.3 if loud else 0.02,
        })
    return rows


class TestScoring(unittest.TestCase):
    def test_burst_window_scores_highest(self):
        rows = fake_rows()
        baselines = [0.08] * len(rows)
        scored = score_windows(rows, baselines, [], {})
        best = max(scored, key=lambda s: s["score"])
        self.assertAlmostEqual(best["t"], 5.0, places=1)

    def test_keyword_word_boosts_window(self):
        rows = fake_rows()
        baselines = [0.08] * len(rows)
        cues = [{"start": 5.0, "end": 5.2, "text": "Wow!"}]
        hits = {0: ["wow"]}
        scored = score_windows(rows, baselines, cues, hits)
        with_words = [s for s in scored if s["t"] == 5.0][0]
        without = [s for s in scored if s["t"] == 5.1][0]
        self.assertGreater(with_words["score"], without["score"])


class TestFindMoments(unittest.TestCase):
    def test_finds_the_burst(self):
        rows = fake_rows()
        baselines = [0.08] * len(rows)
        scored = score_windows(rows, baselines, [], {})
        moments = find_moments(scored, 10.0, top=3)
        self.assertEqual(len(moments), 1)
        self.assertAlmostEqual(moments[0]["peak_t"], 5.0, places=1)
        self.assertEqual(moments[0]["signals"]["words"], 0.0)

    def test_min_gap_separates_close_peaks(self):
        rows = fake_rows()
        rows[52]["rms"] = 0.45  # a second burst 0.2 s after the first
        baselines = [0.08] * len(rows)
        scored = score_windows(rows, baselines, [], {})
        moments = find_moments(scored, 10.0, top=5, min_gap=8.0)
        self.assertEqual(len(moments), 1)

    def test_quiet_audio_has_no_moments(self):
        rows = [{
            "t": round(i * 0.1, 3), "rms": 0.08, "zcr": 200, "band": 0.02,
        } for i in range(100)]
        baselines = [0.08] * 100
        scored = score_windows(rows, baselines, [], {})
        # All scores are near the floor; the floor rule still yields peaks
        # only when a window clearly beats the rest — flat audio must not.
        moments = find_moments(scored, 10.0, top=3)
        self.assertEqual(len(moments), 0)


class TestRefitWeights(unittest.TestCase):
    def _ratings(self, signal, rating, n=8):
        return [
            {"signals": {"loud": 3.0, "voice": 1.0, "words": 0.0
                         if signal != "words" else 1.0,
                         **({signal: 5.0} if signal != "loud" else {})},
             "rating": rating}
            for _ in range(n)
        ]

    def test_fewer_than_8_ratings_keeps_defaults(self):
        ratings = self._ratings("loud", 5, n=7)
        self.assertEqual(refit_weights(ratings), DEFAULT_WEIGHTS)

    def test_five_star_loud_moments_raise_loud_weight(self):
        ratings = self._ratings("loud", 5)
        weights = refit_weights(ratings)
        self.assertGreater(weights["loud"], DEFAULT_WEIGHTS["loud"])

    def test_one_star_loud_moments_lower_loud_weight(self):
        ratings = self._ratings("loud", 1)
        weights = refit_weights(ratings)
        self.assertLess(weights["loud"], DEFAULT_WEIGHTS["loud"])

    def test_neutral_ratings_keep_weights(self):
        ratings = self._ratings("loud", 3)
        weights = refit_weights(ratings)
        self.assertAlmostEqual(weights["loud"], DEFAULT_WEIGHTS["loud"], places=2)
