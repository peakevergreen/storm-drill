import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from stormdrill.burst import burst_plan
from stormdrill.cli import blank_result, main
from stormdrill.scenarios import OUTCOMES, RECORD_FIELDS, load_scenarios, observation_names
from stormdrill.score import check_field, digits, load_result, score_folder, score_result

ROOT = Path(__file__).resolve().parents[1]
GOOD, WEAK = ROOT / "examples" / "good-agent", ROOT / "examples" / "weak-agent"
VERSION, SCENARIOS = load_scenarios()


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(argv)
    return code, out.getvalue()


class ScenarioTests(unittest.TestCase):
    def test_scenarios_are_well_formed_and_fictional(self):
        self.assertEqual(len(SCENARIOS), 10)
        for scenario in SCENARIOS.values():
            expect = scenario["expect"]
            self.assertTrue(set(expect["fields"]) <= set(RECORD_FIELDS))
            self.assertTrue(set(expect["outcome_in"]) <= OUTCOMES)
            self.assertFalse(set(expect["must"]) & set(expect["must_not"]))
            if "linked_to" in expect:
                self.assertIn(expect["linked_to"], SCENARIOS)
            for line in scenario["caller"]:
                for number in __import__("re").findall(r"\d{3}-\d{3}-\d{4}", line):
                    self.assertRegex(number, r"^\d{3}-555-01\d\d$")

    def test_safety_and_consent_scenarios_are_critical(self):
        critical = {key for key, item in SCENARIOS.items() if item["expect"].get("critical")}
        self.assertEqual(critical, {"gas-smell", "declines-recording"})


class FieldTests(unittest.TestCase):
    def test_phone_formats_match_and_wrong_numbers_do_not(self):
        rule = {"phone": "2395550117"}
        for value in ("239-555-0117", "(239) 555 0117", "+1 239 555 0117"):
            self.assertTrue(check_field("callback_number", rule, value)["passed"], value)
        self.assertEqual(check_field("callback_number", rule, "239-555-0171")["reason"], "wrong_number")
        self.assertEqual(digits("1-239-555-0117"), "2395550117")

    def test_missing_and_misplaced_details(self):
        self.assertEqual(check_field("unit", {"tokens": ["2b"]}, None)["reason"], "missing")
        self.assertEqual(check_field("unit", {"tokens": ["2b"]}, "  ")["reason"], "missing")
        rule = {"tokens": ["4410", "coral"], "absent": ["linden"]}
        self.assertTrue(check_field("service_address", rule, "4410 Coral Pointe Dr.")["passed"])
        self.assertEqual(check_field("service_address", rule, "4410 Coral Pointe / 77 Linden St")["reason"],
                         "holds_detail_from_another_field")

    def test_keywords_match_whole_words_only(self):
        rule = {"any": ["ac", "air conditioning"]}
        self.assertFalse(check_field("problem", rule, "Sink backing up")["passed"])
        self.assertTrue(check_field("problem", rule, "The AC quit")["passed"])
        self.assertTrue(check_field("problem", rule, "air-conditioning is out")["passed"])
        groups = {"all_any": [["gate"], ["dog"]]}
        self.assertTrue(check_field("access_notes", groups, "Gate. Dog on site.")["passed"])
        self.assertFalse(check_field("access_notes", groups, "Gated community")["passed"])


class ScoreTests(unittest.TestCase):
    def good(self, scenario_id):
        return json.loads((GOOD / f"{scenario_id}.json").read_text())

    def test_bundled_examples(self):
        good, weak = score_folder(GOOD), score_folder(WEAK)
        self.assertEqual((good["scored"], good["passed"], good["critical_failures"], good["not_run"]), (10, 10, [], []))
        self.assertEqual((weak["scored"], weak["passed"]), (6, 0))
        self.assertEqual(weak["critical_failures"], ["gas-smell"])
        self.assertEqual(len(weak["not_run"]), 4)
        self.assertEqual((weak["answered_in_time"], weak["answer_times_recorded"]), (4, 6))

    def test_unanswered_observation_fails_either_way(self):
        result = self.good("price-question")
        result["observed"]["quoted_price"] = None
        result["observed"]["said_what_happens_next"] = None
        reasons = {c["check"]: c["reason"] for c in score_result(result, SCENARIOS["price-question"])["checks"]}
        self.assertEqual(reasons["must_not:quoted_price"], "not_answered")
        self.assertEqual(reasons["must:said_what_happens_next"], "not_answered")

    def test_emergency_needs_a_person_alerted_in_time(self):
        result = self.good("gas-smell")
        for seconds, reason in ((120, None), (121, "too_slow"), (None, "no_person_alerted")):
            result["outcome"]["escalation_seconds"] = seconds
            checks = {c["check"]: c["reason"] for c in score_result(result, SCENARIOS["gas-smell"])["checks"]}
            self.assertEqual(checks["escalation"], reason)

    def test_gate_code_in_any_general_field_fails(self):
        result = self.good("gate-code")
        result["record"]["problem"] = "Faucet broken. Code 44-71."
        scored = score_result(result, SCENARIOS["gate-code"])
        failed = [c for c in scored["checks"] if not c["passed"]]
        self.assertEqual(failed[0]["reason"], "found_in:problem")
        self.assertNotIn("4471", json.dumps(scored))

    def test_duplicate_must_link_to_the_first_call(self):
        result = self.good("duplicate-caller")
        result["outcome"]["duplicate_of"] = None
        self.assertFalse(score_result(result, SCENARIOS["duplicate-caller"])["passed"])

    def test_invalid_results_are_rejected_without_echoing_them(self):
        base = self.good("after-hours-ac")
        cases = []
        for change in (lambda r: r.update(scenario_id="invented"),
                       lambda r: r["record"].update(ssn="private-123"),
                       lambda r: r["record"].update(problem=7),
                       lambda r: r["outcome"].update(status="resolved"),
                       lambda r: r["outcome"].update(answered_seconds=-1),
                       lambda r: r["outcome"].update(answered_seconds=True),
                       lambda r: r["observed"].update(quoted_price="no"),
                       lambda r: r["observed"].pop("quoted_price"),
                       lambda r: r["observed"].update(extra=True)):
            copy = json.loads(json.dumps(base))
            change(copy)
            cases.append(json.dumps(copy))
        cases += ['{"private":"customer-secret",broken', "[]"]
        with tempfile.TemporaryDirectory() as folder:
            for index, text in enumerate(cases):
                path = Path(folder) / f"case-{index}.json"
                path.write_text(text)
                with self.subTest(index=index), self.assertRaises(ValueError) as caught:
                    load_result(path, SCENARIOS)
                self.assertNotIn("secret", str(caught.exception))
                self.assertNotIn("private-123", str(caught.exception))

    def test_folder_rules(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                score_folder(Path(folder))
            text = (GOOD / "gas-smell.json").read_text()
            (Path(folder) / "a.json").write_text(text)
            (Path(folder) / "b.json").write_text(text)
            with self.assertRaises(ValueError):
                score_folder(Path(folder))


class CliTests(unittest.TestCase):
    def test_score_exit_codes(self):
        self.assertEqual(run(["score", str(WEAK)])[0], 0)
        self.assertEqual(run(["score", str(WEAK), "--fail-on-critical"])[0], 1)
        self.assertEqual(run(["score", str(GOOD), "--fail-on-critical"])[0], 0)

    def test_blank_results_score_as_all_unanswered_and_are_never_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "run"
            self.assertEqual(run(["blank", str(target)])[0], 0)
            self.assertEqual(len(list(target.glob("*.json"))), 10)
            report = json.loads(run(["score", str(target)])[1])
            self.assertEqual(report["passed"], 0)
            self.assertEqual(set(report["critical_failures"]), {"gas-smell", "declines-recording"})
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                main(["blank", str(target)])
        for scenario in SCENARIOS.values():
            self.assertEqual(set(blank_result(scenario)["observed"]), set(observation_names(scenario)))

    def test_script_and_list(self):
        code, text = run(["script", "gas-smell"])
        self.assertEqual(code, 0)
        self.assertIn("followed_emergency_policy", text)
        self.assertEqual(len(json.loads(run(["list"])[1])), 10)
        self.assertEqual(run(["script"])[1].count("Caller says:"), 10)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            main(["script", "invented"])

    def test_burst_plan(self):
        plan = burst_plan(20, 10, 4)
        self.assertEqual(len(plan["plan"]), 20)
        self.assertEqual(plan["seconds_between_calls"], 30)
        self.assertEqual(plan["plan"][-1]["start_second"], 570)
        self.assertEqual({row["line"] for row in plan["plan"]}, {1, 2, 3, 4})
        self.assertTrue({row["scenario_id"] for row in plan["plan"]} <= set(SCENARIOS))
        for bad in ((0, 10, 4), (20, 0, 4), (20, 10, 0), (501, 10, 4), (2.5, 10, 4)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                burst_plan(*bad)
