"""CI gate: validate a clip plan file before it is used."""

import json
import os

from .plan import check_plan


def check_plan_file(plan_path):
    """Validate a plan JSON file; returns (problems, plan)."""
    problems = []
    if not os.path.exists(plan_path):
        return [f"plan file not found: {plan_path}"], None
    try:
        with open(plan_path, encoding="utf-8") as fh:
            plan = json.load(fh)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [f"plan file is not valid JSON: {exc}"], None
    problems = check_plan(plan)
    source = plan.get("source")
    if source and not os.path.exists(source):
        problems.append(f"source audio not found: {source}")
    return problems, plan
