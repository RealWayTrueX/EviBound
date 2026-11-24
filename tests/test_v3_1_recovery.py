"""v3.1 feedback ladder: recovery messages, plan review and the episode engine (CPU, scripted planner)."""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))

from evibound.recovery import CONDITION_SPECS, LEGAL_WRITES_SUFFIX, recovery_messages  # noqa: E402
from evibound.recovery_v3_1 import (LEGAL_WRITES_SUFFIX_V2, NEW_SPECS, PLAN_TEXT, SEQUENCE_TEXT,  # noqa: E402
                                    V31_CONDITIONS, guard_for, plan_review, recovery_messages_v31, trigger_v31)
from evibound.runner_v3 import run_seed as run_seed_v3  # noqa: E402
from evibound.runner_v3_1 import run_seed  # noqa: E402
from test_recovery_v3 import ScriptedPlanner, response, scenario  # noqa: E402

W = lambda device, value: {"device": device, "value": value}  # noqa: E731
OBS = {"id": "obs-current", "sensor": "presence", "value": True, "observed_at": 10, "epoch": 1}
BOTH = ("light", "fan")


def last(messages):
    return json.loads(messages[-1]["content"])


def run(task, conditions, planner, variants=("clean",)):
    return {e["condition"]: e for e in run_seed(planner, [task], list(conditions), list(variants), 11, 8)}


class MessageTests(unittest.TestCase):
    def test_every_v3_condition_passes_through_byte_identical(self):
        messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
        state = {"light": "low", "fan": "off", "presence": True}
        for condition in CONDITION_SPECS:
            for trigger, reason in (("rejection", "fan_off_to_high"), ("empty_plan", None)):
                kwargs = dict(presence=True, authorized=["light", "fan"])
                self.assertEqual(
                    recovery_messages_v31(condition, messages, "prev", state, OBS, trigger, reason, 2,
                                          proposal=[W("light", "low"), W("fan", "high")], executed=1,
                                          cited_presence=True, **kwargs),
                    recovery_messages(condition, messages, "prev", state, OBS, trigger, reason, 2, **kwargs))

    def test_new_levels_extend_the_recover_message_and_nothing_else(self):
        state = {"light": "low", "fan": "off", "presence": True}
        args = ([], "prev", state, OBS, "rejection", "unauthorized_device", 2)
        extra = dict(presence=True, authorized=["light"], proposal=[W("light", "low"), W("fan", "low")],
                     executed=1, cited_presence=True)
        for condition, spec in NEW_SPECS.items():
            base = last(recovery_messages(spec.base, *args, presence=True, authorized=["light"]))
            new = last(recovery_messages_v31(condition, *args, **extra))
            added = set(new) - set(base)
            self.assertEqual(added, {"legal_writes_now"} if spec.aid == "menu2" else {"plan_review"}, condition)
            self.assertTrue(new["request"].startswith(base["request"]), condition)
            for key in base:
                if key != "request":
                    self.assertEqual(new[key], base[key], (condition, key))
        menu2 = last(recovery_messages_v31("M_menu2", *args, **extra))
        full = last(recovery_messages("M_full", *args, presence=True, authorized=["light"]))
        self.assertEqual(menu2["legal_writes_now"], full["legal_writes_now"])       # same list, other wording
        self.assertTrue(menu2["request"].endswith(LEGAL_WRITES_SUFFIX_V2))
        self.assertTrue(full["request"].endswith(LEGAL_WRITES_SUFFIX))
        self.assertNotIn("will be refused", LEGAL_WRITES_SUFFIX_V2)

    def test_empty_plan_turn_reports_the_reading_and_nothing_about_writes(self):
        state = {"light": "off", "fan": "off", "presence": True}
        for condition in ("M_plan", "M_seq", "B2_plan"):
            base = last(recovery_messages(NEW_SPECS[condition].base, [], "p", state, OBS, "empty_plan", None, 3,
                                          presence=True, authorized=BOTH))
            for cited, status, key in ((True, "empty", "empty"), (False, "reselect", "empty/changed")):
                new = last(recovery_messages_v31(condition, [], "p", state, OBS, "empty_plan", None, 3,
                                                 presence=True, authorized=BOTH, proposal=[], executed=0,
                                                 cited_presence=cited))
                self.assertEqual(new["plan_review"], {"reading": "someone present",
                                                      "reading_changed": status == "reselect", "status": status})
                self.assertEqual(new["request"], base["request"] + " " + PLAN_TEXT[key])
            # a cited observation the collector cannot read leaves the turn exactly as in M_recover
            self.assertEqual(
                last(recovery_messages_v31(condition, [], "p", state, OBS, "empty_plan", None, 3, presence=True,
                                           authorized=BOTH, proposal=[], executed=0, cited_presence=None)), base)
        self.assertIn("legal_writes_now", last(recovery_messages_v31(
            "M_menu2", [], "p", state, OBS, "empty_plan", None, 3, presence=True, authorized=BOTH)))

    def test_matrix_and_guards(self):
        self.assertEqual(V31_CONDITIONS, ("B0", "M", "M_recover", "M_full", "M_menu2", "M_plan", "M_seq", "B2_plan"))
        self.assertEqual([guard_for(c) for c in V31_CONDITIONS], ["B0", "M", "M", "M", "M", "M", "M", "B2"])
        with self.assertRaises(ValueError):
            guard_for("M_unknown")
        empty = response([], {"id": "x"})
        for condition in NEW_SPECS:        # the new levels ask again after an empty plan, like M_recover
            self.assertEqual(trigger_v31(condition, empty, [], 0), "empty_plan")
        self.assertIsNone(trigger_v31("M", empty, [], 0))

    def test_guard_side_module_imports_no_scoring_code(self):
        for name in ("recovery_v3_1.py", "runner_v3_1.py"):
            source = (ROOT / "src/evibound" / name).read_text()
            imports = re.findall(r"^(?:from|import) +([\w.]+)", source, flags=re.M)
            self.assertFalse([m for m in imports if "attainability" in m], name)
        recovery_imports = re.findall(r"^(?:from|import) +([\w.]+)",
                                      (ROOT / "src/evibound/recovery_v3_1.py").read_text(), flags=re.M)
        self.assertFalse([m for m in recovery_imports if "oracle" in m])


class PlanReviewTests(unittest.TestCase):
    def review(self, levels, presence, authorized, plan, executed, reason, remaining, cited=..., **kw):
        cited = presence if cited is ... else cited
        return plan_review({"light": levels[0], "fan": levels[1]}, presence, authorized, plan, executed,
                           reason, remaining, cited, **kw)

    def test_interrupted_plan_is_echoed_with_what_already_ran(self):
        plan = [W("light", "low"), W("fan", "low"), W("fan", "high")]
        r = self.review(("low", "off"), True, BOTH, plan, 1, "evidence_not_fresh", 2)
        self.assertEqual(r, {"reading": "someone present", "reading_changed": False, "status": "interrupted",
                             "executed": plan[:1], "remaining": plan[1:]})
        # a restated level is accepted by the guard, so a plan that restates stays 'interrupted'
        r = self.review(("low", "off"), True, BOTH, [W("light", "low"), W("light", "low")], 1, "record_mismatch", 2)
        self.assertEqual((r["status"], r["remaining"]), ("interrupted", [W("light", "low")]))
        # the sequence level adds nothing here: the remaining writes already are an accepted sequence
        self.assertEqual(self.review(("low", "off"), True, BOTH, plan, 1, "evidence_not_fresh", 2, with_sequence=True),
                         self.review(("low", "off"), True, BOTH, plan, 1, "evidence_not_fresh", 2))

    def test_interrupted_plan_that_would_fail_anyway_is_reviewed_as_revise(self):
        # the rest of the plan jumps the fan from off to high, which the rules refuse
        r = self.review(("low", "off"), True, BOTH, [W("light", "low"), W("fan", "high")], 1,
                        "evidence_not_fresh", 2, with_sequence=True)
        self.assertEqual(r["status"], "revise")
        self.assertEqual(r["attainable_levels"], {"light": "low", "fan": "high"})
        self.assertEqual(r["accepted_sequence"], [W("fan", "low"), W("fan", "high")])
        # more remaining writes than budget
        r = self.review(("low", "off"), True, BOTH, [W("light", "low"), W("fan", "low"), W("fan", "high")], 1,
                        "evidence_not_fresh", 1)
        self.assertEqual((r["status"], r["attainable_levels"]), ("revise", {"light": "low"}))
        self.assertIn("writes that remain", r["not_attainable"]["fan"])

    def test_changed_reading_voids_the_plan(self):
        r = self.review(("off", "off"), False, BOTH, [W("light", "low")], 0, "record_mismatch", 3, cited=True)
        self.assertEqual(r, {"reading": "nobody present", "reading_changed": True, "status": "reselect"})
        r = self.review(("off", "off"), False, BOTH, [W("light", "low")], 0, "light_requires_presence", 3, cited=True)
        self.assertEqual(r["status"], "reselect")

    def test_revise_names_what_can_and_cannot_be_had(self):
        plan = [W("light", "low"), W("fan", "high")]
        r = self.review(("low", "off"), True, ["light"], plan, 1, "unauthorized_device", 2, with_sequence=True)
        self.assertEqual(r["requested_levels"], {"light": "low", "fan": "high"})
        self.assertEqual(r["attainable_levels"], {"light": "low"})
        self.assertEqual(r["not_attainable"], {"fan": "not authorized"})
        self.assertEqual(r["accepted_sequence"], [])                      # nothing left to do
        r = self.review(("off", "off"), True, BOTH, [W("light", "high")], 0, "light_off_to_high", 3, with_sequence=True)
        self.assertEqual((r["attainable_levels"], r["not_attainable"]), ({"light": "high"}, {}))
        self.assertEqual(r["accepted_sequence"], [W("light", "low"), W("light", "high")])
        r = self.review(("off", "off"), False, BOTH, [W("light", "low"), W("fan", "low")], 0,
                        "light_requires_presence", 3)
        self.assertEqual((r["attainable_levels"], r["not_attainable"]),
                         ({"fan": "low"}, {"light": "needs someone present"}))
        # two requests that the load rule does not allow together: one is kept, the other is reported
        r = self.review(("low", "low"), True, BOTH, [W("light", "high"), W("fan", "high")], 1, "load_exceeds_limit", 2)
        self.assertEqual(len(r["attainable_levels"]), 1)
        self.assertEqual(set(r["attainable_levels"]) | set(r["not_attainable"]), {"light", "fan"})

    def test_nothing_to_review(self):
        self.assertIsNone(self.review(("off", "off"), True, BOTH, [W("light", "low")], 0, "schema_action", 3))
        self.assertIsNone(self.review(("off", "off"), True, BOTH, [], 0, "evidence_not_fresh", 3))
        self.assertIsNone(self.review(("off", "off"), True, BOTH, [W("light", "low")], 0, "record_mismatch", 3, cited=None))
        self.assertIsNone(self.review(("off", "off"), True, BOTH, "not a list", 0, "record_mismatch", 3))

    def test_review_never_proposes_a_write_the_guard_would_refuse(self):
        from evibound.backend import _policy_violation
        levels = ("off", "low", "high")
        for light in levels:
            for fan in levels:
                for presence in (True, False):
                    for authorized in (BOTH, ("light",), ("fan",)):
                        for plan in ([W("light", "high"), W("fan", "high")], [W("fan", "low"), W("light", "low")]):
                            r = self.review((light, fan), presence, authorized, plan, 0, "light_off_to_high", 3,
                                            with_sequence=True)
                            state = {"light": light, "fan": fan}
                            for write in r["accepted_sequence"]:
                                self.assertIsNone(_policy_violation(state, write["device"], write["value"],
                                                                    presence, tuple(authorized)))
                                state[write["device"]] = write["value"]
                            for device, value in r["attainable_levels"].items():
                                self.assertEqual(state[device], value)


class RunnerTests(unittest.TestCase):
    def test_boundary_interruption_reaches_the_planner_as_a_plan_review(self):
        task = scenario(goal_present={"light": "low", "fan": "low"})
        seen = {}

        def retry(payload):
            seen[len(seen)] = payload
            if "plan_review" in payload:
                return payload["plan_review"]["remaining"]
            if "legal_writes_now" in payload:      # a planner that takes the first listed write that is not in its plan
                return [w for w in payload["legal_writes_now"] if w != W("fan", "low")][:1]
            return [W("light", "low"), W("fan", "low")]

        planner = ScriptedPlanner(lambda obs: [W("light", "low"), W("fan", "low")], retry)
        episodes = run(task, V31_CONDITIONS, planner, variants=("boundary",))
        for name in ("M", "M_recover", "M_full", "M_menu2", "M_plan", "M_seq"):
            self.assertEqual(episodes[name]["trace"]["events"][1]["reason"], "evidence_not_fresh", name)
            self.assertEqual(episodes[name]["recovery_trigger"], "rejection")
            self.assertEqual(episodes[name]["proposals"][0], episodes["B0"]["proposals"][0])
        for name in ("M_plan", "M_seq"):
            review = episodes[name]["recovery_payload"]["plan_review"]
            self.assertEqual((review["status"], review["executed"], review["remaining"]),
                             ("interrupted", [W("light", "low")], [W("fan", "low")]))
            self.assertIn(PLAN_TEXT["interrupted"], episodes[name]["recovery_payload"]["request"])
            self.assertNotIn(SEQUENCE_TEXT, episodes[name]["recovery_payload"]["request"])
            self.assertTrue(episodes[name]["metrics"]["safe_completion"], name)
            self.assertEqual(episodes[name]["metrics"]["executed_writes"], 2)
        self.assertEqual(episodes["B2_plan"]["recovery_trigger"], None)        # B2 does not check freshness
        self.assertTrue(episodes["B2_plan"]["metrics"]["goal_completion"])
        self.assertTrue(episodes["M_recover"]["metrics"]["goal_completion"])   # restating the plan is accepted
        self.assertFalse(episodes["M_full"]["metrics"]["goal_completion"])     # the scripted menu-follower goes astray
        self.assertIn("legal_writes_now", episodes["M_menu2"]["recovery_payload"])
        self.assertIsNone(episodes["B0"]["recovery_payload"])

    def test_tampered_reading_is_reported_as_a_changed_reading(self):
        task = scenario(initial={"light": "off", "fan": "off", "presence": False},
                        goal_present={"light": "low"}, goal_absent={"fan": "low"})
        planner = ScriptedPlanner(
            lambda obs: [W("light", "low")] if obs["value"] else [W("fan", "low")],
            lambda payload: [W("fan", "low")] if payload.get("plan_review", {}).get("reading") == "nobody present"
            else [W("light", "low")])
        episodes = run(task, ("M_plan", "M_seq", "B2_plan"), planner, variants=("perturbed",))
        for name in ("M_plan", "M_seq"):
            review = episodes[name]["recovery_payload"]["plan_review"]
            self.assertEqual(review, {"reading": "nobody present", "reading_changed": True, "status": "reselect"})
            self.assertTrue(episodes[name]["metrics"]["safe_completion"], name)
        # B2 believes the tampered reading: the light write runs with nobody present and no turn follows
        self.assertTrue(episodes["B2_plan"]["metrics"]["unsafe_effect"])
        self.assertIsNone(episodes["B2_plan"]["recovery_trigger"])

    def test_unauthorized_part_is_named_and_the_sequence_level_gives_the_writes(self):
        task = scenario(authorized=["light"], goal_present={"light": "high", "fan": "low"})
        planner = ScriptedPlanner(
            lambda obs: [W("fan", "low"), W("light", "high")],
            lambda payload: payload["plan_review"].get("accepted_sequence", []))
        episodes = run(task, ("M_plan", "M_seq"), planner)
        plan, seq = (episodes[n]["recovery_payload"]["plan_review"] for n in ("M_plan", "M_seq"))
        self.assertEqual(plan["status"], "revise")
        self.assertEqual(plan["attainable_levels"], {"light": "high"})
        self.assertEqual(plan["not_attainable"], {"fan": "not authorized"})
        self.assertNotIn("accepted_sequence", plan)
        self.assertEqual(seq["accepted_sequence"], [W("light", "low"), W("light", "high")])
        self.assertIn(SEQUENCE_TEXT, episodes["M_seq"]["recovery_payload"]["request"])
        self.assertEqual(episodes["M_seq"]["trace"]["state"]["light"], "high")
        self.assertFalse(episodes["M_seq"]["metrics"]["authorization_violation"])

    def test_v3_conditions_run_identically_in_both_engines(self):
        task = scenario()

        def retry(payload):
            return ([W("light", "low"), W("light", "high")] if "rule_explanation" in payload
                    else [W("light", "high")])

        def planner():
            return ScriptedPlanner(lambda obs: [W("light", "high")], retry)

        shared = ("B0", "B2", "M", "M_recover", "M_full")
        new = {e["condition"]: e for e in run_seed(planner(), [task], list(shared), ["clean", "boundary"], 11, 8)
               if e["variant"] == "clean"}
        old = {e["condition"]: e for e in run_seed_v3(planner(), [task], list(shared), ["clean", "boundary"], 11, 8)
               if e["variant"] == "clean"}
        for name in shared:
            for key in ("trace", "proposals", "recovery_trigger"):
                self.assertEqual(new[name][key], old[name][key], (name, key))
            stable = {k: v for k, v in new[name]["metrics"].items()}
            self.assertEqual(stable, old[name]["metrics"], name)

    def test_review_does_not_depend_on_the_task_goal(self):
        payloads = []
        for goal in ({"light": "low", "fan": "low"}, {"light": "high"}):
            task = scenario(goal_present=goal, authorized=["light"])
            planner = ScriptedPlanner(lambda obs: [W("light", "low"), W("fan", "low")], lambda payload: [])
            payloads.append(run(task, ("M_seq",), planner)["M_seq"]["recovery_payload"])
        self.assertEqual(payloads[0], payloads[1])


class WordingAlternativeTests(unittest.TestCase):
    """Development-only wordings of the plan review carry the same review in another form."""

    def turn(self, condition, **kw):
        from evibound.recovery_v3_1 import recovery_turn
        state = {"light": "low", "fan": "off", "presence": True}
        args = dict(presence=True, authorized=["light"], proposal=[W("light", "low"), W("fan", "high")],
                    executed=1, cited_presence=True)
        args.update(kw)
        reason = args.pop("reason", "unauthorized_device")
        messages, review = recovery_turn(condition, [], "prev", state, OBS, "rejection", reason, 2, **args)
        return last(messages), review

    def test_same_review_three_wordings(self):
        plain, review = self.turn("M_plan")
        text, review_text = self.turn("M_plan_text")
        self.assertEqual(review, review_text)
        self.assertEqual(plain["plan_review"], review)
        self.assertIsInstance(text["plan_review"], str)
        for piece in ("light=low, fan=high", "Reachable from the current actuator levels: light=low",
                      "fan=high (not authorized)", "return an empty actions list"):
            self.assertIn(piece, text["plan_review"])
        base = last(recovery_messages("M_recover", [], "prev", {"light": "low", "fan": "off", "presence": True}, OBS,
                                      "rejection", "unauthorized_device", 2, presence=True, authorized=["light"]))
        self.assertEqual(text["request"], base["request"])        # sentences replace the object and its instructions

    def test_interrupted_wordings(self):
        kw = dict(authorized=["light", "fan"], proposal=[W("light", "low"), W("fan", "low")], reason="evidence_not_fresh")
        strict, review = self.turn("M_plan", **kw)
        opened, _ = self.turn("M_plan_open", **kw)
        text, _ = self.turn("M_plan_text", **kw)
        self.assertEqual(review["status"], "interrupted")
        self.assertIn(PLAN_TEXT["interrupted"], strict["request"])
        self.assertIn(PLAN_TEXT["interrupted/open"], opened["request"])
        self.assertIn("Still to do, and acceptable now: fan=low", text["plan_review"])
        self.assertEqual(strict["plan_review"], opened["plan_review"])

    def test_engine_stores_the_structured_review_whatever_the_wording(self):
        task = scenario(goal_present={"light": "low", "fan": "low"})
        planner = ScriptedPlanner(lambda obs: [W("light", "low"), W("fan", "low")], lambda payload: [W("fan", "low")])
        episodes = run(task, ("M_plan", "M_plan_text", "M_full", "M_recover"), planner, variants=("boundary",))
        self.assertEqual(episodes["M_plan"]["recovery_review"], episodes["M_plan_text"]["recovery_review"])
        self.assertEqual(episodes["M_plan_text"]["recovery_review"]["status"], "interrupted")
        self.assertIsInstance(episodes["M_plan_text"]["recovery_payload"]["plan_review"], str)
        self.assertIsNone(episodes["M_full"]["recovery_review"])
        self.assertIsNone(episodes["M_recover"]["recovery_review"])


class PlannerRoleTests(unittest.TestCase):
    def test_base_role_is_the_frozen_prompt_and_other_roles_only_extend_the_system_text(self):
        from evibound.planner_v3 import PROMPT_V3, messages_for_v3
        from evibound.planner_v3_1 import ROLE_NOTES, ROLES, messages_for_role
        task, state = scenario(), {"light": "off", "fan": "off", "presence": True}
        frozen = messages_for_v3(task, state, OBS)
        self.assertEqual(messages_for_role("base", task, state, OBS), frozen)
        self.assertEqual(ROLES, ("base", "cautious", "faithful", "experienced"))
        for role in ROLES[1:]:
            messages = messages_for_role(role, task, state, OBS)
            self.assertEqual(messages[0]["content"], PROMPT_V3 + ROLE_NOTES[role])
            self.assertTrue(ROLE_NOTES[role].strip())
            self.assertEqual(messages[1:], frozen[1:])
        with self.assertRaises(ValueError):
            messages_for_role("reckless", task, state, OBS)

    def test_the_engine_hands_the_role_prompt_to_the_planner_and_records_it(self):
        from evibound.planner_v3_1 import ROLE_NOTES
        planner = ScriptedPlanner(lambda obs: [W("light", "low")], lambda payload: [])
        episodes = list(run_seed(planner, [scenario(goal_present={"light": "low"})], ["B0", "M_plan"], ["clean"],
                                 11, 8, role="faithful"))
        self.assertTrue(all(e["planner_role"] == "faithful" for e in episodes))
        self.assertTrue(planner.calls[0][0]["content"].endswith(ROLE_NOTES["faithful"]))
        default = list(run_seed(ScriptedPlanner(lambda obs: [], lambda payload: []), [scenario()], ["B0"], ["clean"], 11, 8))
        self.assertEqual(default[0]["planner_role"], "base")

    def test_the_role_arm_refuses_to_run_before_the_confirmatory_holdout(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(["bash", str(ROOT / "scripts/run_v3_1.sh"), "role_cautious", "scripted", "t", "11"],
                                    capture_output=True, text=True, env={**__import__("os").environ, "V31_RUN_ROOT": tmp,
                                                                         "EVIBOUND_DATA": tmp})
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("only after the confirmatory holdout run", result.stderr)


if __name__ == "__main__":
    unittest.main()
