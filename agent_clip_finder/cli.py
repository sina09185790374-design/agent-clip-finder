"""CLI: analyze / plan / rate / weights / check / demo."""

import argparse
import json
import os
import sys
import tempfile

from . import __version__
from .audio import duration_s, local_baselines, measure, read_wav
from .check import check_plan_file
from .demo import run_demo
from .feedback import append_rating, load_ratings
from .plan import check_plan, make_plan
from .scoring import DEFAULT_WEIGHTS, find_moments, refit_weights, score_windows
from .transcript import keyword_hits, load_srt


def _load_weights(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return dict(DEFAULT_WEIGHTS)


def _analyze(audio_path, srt_path, weights, top):
    samples, rate = read_wav(audio_path)
    rows = measure(samples, rate)
    baselines = local_baselines(rows)
    cues = load_srt(srt_path) if srt_path else []
    hits = keyword_hits(cues) if cues else {}
    scored = score_windows(rows, baselines, cues, hits, weights)
    moments = find_moments(scored, duration_s(samples, rate), top=top)
    return moments, cues, duration_s(samples, rate)


def _emit(data, out_path):
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"wrote {out_path}")
    else:
        print(text)


def cmd_analyze(args):
    moments, _, _ = _analyze(args.audio, args.srt, _load_weights(args.weights), args.top)
    _emit(moments, args.out)
    return 0


def cmd_plan(args):
    if args.moments:
        with open(args.moments, encoding="utf-8") as fh:
            moments = json.load(fh)
        cues = load_srt(args.srt) if args.srt else []
        samples, rate = read_wav(args.audio)
        duration = duration_s(samples, rate)
    else:
        moments, cues, duration = _analyze(
            args.audio, args.srt, _load_weights(args.weights), args.top
        )
    plan = make_plan(
        moments, args.audio or "", duration, cues=cues,
        min_s=args.min, max_s=args.max, count=args.count,
    )
    problems = check_plan(plan, duration)
    if problems:
        print("plan has problems:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    _emit(plan, args.out)
    return 0


def cmd_rate(args):
    signals = json.loads(args.signals) if args.signals else None
    record = append_rating(args.feedback, args.moment, args.rating, signals)
    print(f"rated {record['moment_id']}: {record['rating']}/5")
    return 0


def cmd_weights(args):
    ratings = load_ratings(args.feedback) if args.feedback else []
    weights = refit_weights(ratings, _load_weights(args.weights))
    print(f"ratings: {len(ratings)} (refit needs 8)")
    print(json.dumps(weights, indent=2))
    return 0


def cmd_check(args):
    problems, _ = check_plan_file(args.plan)
    if problems:
        print("FAIL")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("PASS")
    return 0


def cmd_demo(args):
    out_dir = args.out or tempfile.mkdtemp(prefix="clip-finder-demo-")
    plan, moments = run_demo(out_dir)
    problems = check_plan(plan)
    print(f"demo files in {out_dir}")
    print(f"moments found: {len(moments)}")
    for clip in plan["clips"]:
        print(f"  {clip['id']}: {clip['start']:.1f}s-{clip['end']:.1f}s "
              f"score={clip['score']} title={clip['title']!r}")
    if problems:
        print("demo plan FAILED the gate:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print("demo plan PASSED the gate")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="agent-clip-finder",
        description="Find the loudest, most quotable moments in a recording.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("analyze", help="score windows, list moments")
    p.add_argument("audio")
    p.add_argument("--srt")
    p.add_argument("--weights")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--out")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("plan", help="build a 9:16 clip plan")
    p.add_argument("audio")
    p.add_argument("--srt")
    p.add_argument("--moments", help="moments JSON from analyze (else analyze inline)")
    p.add_argument("--weights")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--min", type=float, default=30.0)
    p.add_argument("--max", type=float, default=80.0)
    p.add_argument("--count", type=int, default=3)
    p.add_argument("--out")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("rate", help="rate a moment 1-5 (teaches the weights)")
    p.add_argument("--feedback", required=True)
    p.add_argument("--moment", required=True)
    p.add_argument("--rating", required=True)
    p.add_argument("--signals", help='JSON like {"loud": 3.2, "voice": 1.1, "words": 1.0}')
    p.set_defaults(func=cmd_rate)

    p = sub.add_parser("weights", help="show current (refit) signal weights")
    p.add_argument("--feedback")
    p.add_argument("--weights")
    p.set_defaults(func=cmd_weights)

    p = sub.add_parser("check", help="CI gate for a plan JSON file")
    p.add_argument("plan")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("demo", help="run the pipeline on a synthetic recording")
    p.add_argument("--out")
    p.set_defaults(func=cmd_demo)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)
