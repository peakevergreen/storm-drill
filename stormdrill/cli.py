"""JSON on stdout; no network, no audio, no accounts."""
import argparse
import json
from pathlib import Path

from .burst import burst_plan
from .scenarios import RECORD_FIELDS, load_scenarios, observation_names
from .score import score_folder


def script_text(scenario):
    lines = [f"# {scenario['title']} ({scenario['id']})", "", scenario["setup"], "", "Caller says:"]
    lines += [f"  {number}. {line}" for number, line in enumerate(scenario["caller"], 1)]
    lines += ["", "After the call, answer true or false:"]
    lines += [f"  - {name}" for name in observation_names(scenario)] or ["  (nothing to observe; the record is scored)"]
    return "\n".join(lines)


def blank_result(scenario):
    return {"scenario_id": scenario["id"], "record": {name: None for name in RECORD_FIELDS},
            "outcome": {"status": "request_taken", "answered_seconds": None, "escalation_seconds": None,
                        "duplicate_of": None, "restricted_note": None},
            "observed": {name: None for name in observation_names(scenario)}}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="stormdrill", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List the scenarios")
    script = commands.add_parser("script", help="Print the call script for a tester")
    script.add_argument("scenario", nargs="?", help="Scenario ID; omit for all")
    blank = commands.add_parser("blank", help="Write empty result files to fill in after each call")
    blank.add_argument("folder", type=Path)
    score = commands.add_parser("score", help="Score a folder of filled-in result files")
    score.add_argument("folder", type=Path)
    score.add_argument("--answer-within", type=float, default=20.0, help="Seconds a call may ring before it counts as late")
    score.add_argument("--fail-on-critical", action="store_true", help="Exit 1 when a safety or consent scenario fails")
    burst = commands.add_parser("burst", help="Plan a burst of overlapping calls")
    burst.add_argument("--calls", type=int, default=20)
    burst.add_argument("--minutes", type=float, default=10.0)
    burst.add_argument("--lines", type=int, default=4)
    args = parser.parse_args(argv)
    _version, scenarios = load_scenarios()
    try:
        if args.command == "list":
            result = [{"id": item["id"], "group": item["group"], "title": item["title"],
                       "critical": bool(item["expect"].get("critical"))} for item in scenarios.values()]
        elif args.command == "script":
            if args.scenario is not None and args.scenario not in scenarios:
                raise ValueError("unknown scenario; run `stormdrill list`")
            chosen = [scenarios[args.scenario]] if args.scenario else list(scenarios.values())
            print("\n\n".join(script_text(item) for item in chosen))
            return 0
        elif args.command == "blank":
            if args.folder.exists() and any(args.folder.iterdir()):
                raise ValueError("blank needs a new or empty folder, so filled-in results are never replaced")
            args.folder.mkdir(parents=True, exist_ok=True)
            for item in scenarios.values():
                (args.folder / f"{item['id']}.json").write_text(json.dumps(blank_result(item), indent=2) + "\n", encoding="utf-8")
            result = {"written": len(scenarios), "folder": str(args.folder)}
        elif args.command == "burst":
            result = burst_plan(args.calls, args.minutes, args.lines)
        else:
            if not args.folder.is_dir():
                raise ValueError("score needs a folder of result files")
            if not args.answer_within > 0:
                raise ValueError("--answer-within must be above 0")
            result = score_folder(args.folder, answer_within=args.answer_within)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, allow_nan=False))
    if args.command == "score" and args.fail_on_critical and result["critical_failures"]:
        return 1
    return 0
