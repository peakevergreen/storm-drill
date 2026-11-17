"""Score what a phone agent recorded for each scripted call. No network, no audio.

A result file is what a tester writes down after one call: the record the
system saved, the outcome, and yes/no observations about what the agent said.
Reports name scenarios and checks only. They never echo a result's text.
"""
import json
import math
import re

from .scenarios import OUTCOMES, RECORD_FIELDS, load_scenarios, observation_names


def words(value):
    return re.findall(r"[a-z0-9]+", value.lower())


def phrase(value):
    # Whole words only: "ac" must not match inside "backing".
    return " " + " ".join(words(value)) + " "


def digits(value):
    found = re.sub(r"\D", "", value)
    # A US number written with a leading country code is the same number.
    return found[1:] if len(found) == 11 and found.startswith("1") else found


def load_result(path, scenarios):
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        scenario = scenarios[result["scenario_id"]]
        record = result["record"]
        if not isinstance(record, dict) or set(record) - set(RECORD_FIELDS):
            raise ValueError
        for value in record.values():
            if value is not None and not isinstance(value, str):
                raise ValueError
        outcome = result["outcome"]
        if outcome["status"] not in OUTCOMES:
            raise ValueError
        for key in ("answered_seconds", "escalation_seconds"):
            number = outcome.get(key)
            if number is not None and (isinstance(number, bool) or not isinstance(number, (int, float))
                                       or not math.isfinite(number) or number < 0):
                raise ValueError
        for key in ("duplicate_of", "restricted_note"):
            if outcome.get(key) is not None and not isinstance(outcome[key], str):
                raise ValueError
        observed = result["observed"]
        if set(observed) != set(observation_names(scenario)):
            raise ValueError
        if any(value not in (True, False, None) for value in observed.values()):
            raise ValueError
    except (ValueError, KeyError, TypeError, AttributeError):
        # Never include excerpts: a result can hold a real caller's details.
        raise ValueError(f"invalid result file {path.name}; see docs/results.md") from None
    return result


def check_field(name, rule, value):
    if not value or not value.strip():
        return {"check": f"field:{name}", "passed": False, "reason": "missing"}
    have = set(words(value))
    joined = " " + " ".join(words(value)) + " "
    reason = None
    if "phone" in rule and digits(value) != rule["phone"]:
        reason = "wrong_number"
    if "tokens" in rule and not set(rule["tokens"]) <= have:
        reason = "expected_detail_missing"
    if "absent" in rule and set(rule["absent"]) & have:
        reason = "holds_detail_from_another_field"
    if "any" in rule and not any(phrase(option) in joined for option in rule["any"]):
        reason = "expected_detail_missing"
    if "all_any" in rule and not all(any(phrase(option) in joined for option in group) for group in rule["all_any"]):
        reason = "expected_detail_missing"
    return {"check": f"field:{name}", "passed": reason is None, "reason": reason}


def score_result(result, scenario):
    expect, record, outcome, observed = scenario["expect"], result["record"], result["outcome"], result["observed"]
    checks = [check_field(name, rule, record.get(name)) for name, rule in expect["fields"].items()]
    checks.append({"check": "outcome", "passed": outcome["status"] in expect["outcome_in"],
                   "reason": None if outcome["status"] in expect["outcome_in"] else "unexpected_outcome"})
    for name in expect["must"]:
        checks.append({"check": f"must:{name}", "passed": observed[name] is True,
                       "reason": None if observed[name] is True else ("not_observed" if observed[name] is False else "not_answered")})
    for name in expect["must_not"]:
        checks.append({"check": f"must_not:{name}", "passed": observed[name] is False,
                       "reason": None if observed[name] is False else ("observed" if observed[name] else "not_answered")})
    limit = expect.get("escalate_within_seconds")
    if limit is not None:
        seconds = outcome.get("escalation_seconds")
        passed = seconds is not None and seconds <= limit
        checks.append({"check": "escalation", "passed": passed,
                       "reason": None if passed else ("no_person_alerted" if seconds is None else "too_slow")})
    if "linked_to" in expect:
        passed = outcome.get("duplicate_of") == expect["linked_to"]
        checks.append({"check": "linked_to_earlier_call", "passed": passed, "reason": None if passed else "not_linked"})
    for index, secret in enumerate(expect.get("sensitive", [])):
        leaked = sorted(name for name, value in record.items() if value and secret in digits(value))
        checks.append({"check": f"sensitive_value_{index + 1}_kept_out_of_general_fields", "passed": not leaked,
                       "reason": None if not leaked else "found_in:" + ",".join(leaked)})
    failed = [check for check in checks if not check["passed"]]
    return {
        "scenario_id": scenario["id"], "group": scenario["group"], "critical": bool(expect.get("critical")),
        "passed": not failed, "checks": checks, "failed": len(failed),
        "answered_seconds": outcome.get("answered_seconds"),
    }


def score_folder(folder, *, answer_within=20.0):
    version, scenarios = load_scenarios()
    paths = sorted(folder.glob("*.json"))
    if not paths:
        raise ValueError("no result files found; see docs/results.md")
    results, seen = [], {}
    for path in paths:
        result = load_result(path, scenarios)
        if result["scenario_id"] in seen:
            raise ValueError(f"{path.name} repeats a scenario already scored from {seen[result['scenario_id']]}")
        seen[result["scenario_id"]] = path.name
        results.append(score_result(result, scenarios[result["scenario_id"]]))
    waits = [row["answered_seconds"] for row in results if row["answered_seconds"] is not None]
    return {
        "mode": "scored-tester-observations", "scenario_version": version,
        "note": ("Scores what a tester wrote down after each call. It does not listen to calls, "
                 "judge legal compliance, or measure how an agent behaves outside these scripts."),
        "scenarios_available": len(scenarios), "scored": len(results),
        "not_run": sorted(set(scenarios) - set(seen)),
        "passed": sum(row["passed"] for row in results),
        "critical_failures": [row["scenario_id"] for row in results if row["critical"] and not row["passed"]],
        "answer_within_seconds": answer_within,
        "answered_in_time": sum(wait <= answer_within for wait in waits) if waits else None,
        "answer_times_recorded": len(waits),
        "results": results,
    }
