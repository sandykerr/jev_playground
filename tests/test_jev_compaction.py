import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import jev_compaction as policy


class CompactionPolicyTests(unittest.TestCase):
    def test_three_stages_deduplicate_until_reset(self):
        pressure = policy.Pressure()
        self.assertEqual([pressure.advance({"used_tokens": n, "window_tokens": 100})
                          for n in [10, 50, 55, 65, 65, 90]], [0, 1, 0, 2, 0, 3])
        pressure.reset()
        self.assertEqual(pressure.advance({"used_tokens": 50, "window_tokens": 100}), 1)

    def test_video_thresholds_and_unknown_window(self):
        pressure = policy.Pressure(tokens=(6000, 10000, 14000))
        self.assertEqual([pressure.stage({"used_tokens": n}) for n in [5999, 6000, 10000, 14000]], [0, 1, 2, 3])
        self.assertEqual(policy.Pressure().stage({"used_tokens": 100000}), 0)
        self.assertEqual(pressure.stage({}), 0)

    def test_invalid_thresholds(self):
        for value in ["1,2", "2,2,3", "0,2,3", "3,2,1", "a,b,c", "NaN,2,3"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                policy.thresholds(value)

    def test_guards_and_probabilities(self):
        state = {"used_tokens": 70, "window_tokens": 100, "at_boundary": True,
                 "pending_actions": False, "handoff_saved": True}
        for answer in [None, {}, {"type": "noul", "noul": float("nan")},
                       {"type": "noul", "noul": True}, {"type": "noul", "noul": 0.79}]:
            self.assertEqual(policy.decision(policy.Pressure(), state, answer)["action"], "continue")
        self.assertEqual(policy.decision(policy.Pressure(), state, {"type": "noul", "noul": 0.8})["action"], "recommend_compact")
        state["used_tokens"] = 90
        self.assertEqual(policy.decision(policy.Pressure(), state)["action"], "recommend_compact")
        self.assertEqual(policy.decision(policy.Pressure(), state, cooldown=True)["action"], "continue")
        state["pending_actions"] = True
        self.assertEqual(policy.decision(policy.Pressure(), state)["action"], "continue")

    def test_payload_excludes_assistant_and_document_content(self):
        payload = policy.boundary_request("task", "prior task", {"used_tokens": 70},
                                          {"commandExecution": 2}, {"completed": 2})
        self.assertEqual(set(payload["state"]), {"task", "previous_task", "context",
                                                  "completed_action_types", "plan_status_counts"})
        self.assertEqual(list(payload["questions"]), ["compact"])

    def test_service_failure_does_not_invent_judgment(self):
        with patch.dict(policy.os.environ, {"JEV_API_KEY": "test"}), \
             patch.object(policy.jev, "ask", side_effect=TimeoutError("private error text")):
            result = policy.judge_boundary({})
        self.assertEqual(result, {"provider": "fallback", "answer": None, "reason": "TimeoutError"})
