import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/jev_context.py"
spec = importlib.util.spec_from_file_location("jev_context", SCRIPT)
jev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jev)


def answer(selected="read", confidence=0.98):
    return {"type": "choice", "choice": selected, "confidence": confidence,
            "probabilities": {key: 0.98 if key == selected else 0.01 for key in jev.READ_OPTIONS}}


class ContextRoutingTests(unittest.TestCase):
    def test_payload_uses_catalog_without_reading_documents(self):
        with patch.object(Path, "read_text", side_effect=AssertionError("document read")):
            payload = jev.build_request("Review world-model pretraining", {})
        self.assertEqual(set(payload["state"]), {"task", "documents", "context"})
        self.assertEqual(len(payload["questions"]), len(jev.CATALOG["documents"]) + 1)
        self.assertLess(len(json.dumps(payload)), 50000)

    def test_pin_cannot_be_overridden_by_skip(self):
        payload = jev.build_request("Review CHM data", {}, ["fm_dataset"])
        result = jev.route(payload, {"answers": {"fm_dataset": answer("skip")}}, ["fm_dataset"])
        self.assertNotIn("fm_dataset", payload["questions"])
        self.assertEqual(next(d for d in result["documents"] if d["id"] == "fm_dataset")["action"], "read")

    def test_skip_needs_stronger_confidence(self):
        self.assertEqual(jev.choice(answer("skip", 0.74)), "inspect")
        self.assertEqual(jev.choice(answer("skip")), "skip")
        self.assertEqual(jev.choice(answer("read", 0.8)), "read")
        self.assertEqual(jev.choice(answer("read", 0.4)), "inspect")

    def test_malformed_answers_never_suppress_reads(self):
        invalid = [None, [], {}, {**answer(), "choice": []}, {**answer(), "choice": "delete"},
                   {**answer("skip"), "confidence": float("nan")},
                   {**answer("skip"), "probabilities": {"skip": 1}},
                   {**answer("skip"), "probabilities": {k: 1 for k in jev.READ_OPTIONS}},
                   {**answer("read"), "choice": "skip"}]
        for value in invalid:
            with self.subTest(value=value):
                self.assertEqual(jev.choice(value), "inspect")

    def test_missing_answers_are_inspected(self):
        result = jev.route(jev.build_request("Review calendar", {}), {"answers": {}})
        self.assertTrue(all(d["action"] == ("read" if d["always"] else "inspect")
                            for d in result["documents"]))

    def test_unknown_telemetry_is_not_invented(self):
        self.assertEqual(jev.compaction({})["action"], "unknown")
        self.assertIsNone(jev.compaction({})["usage_ratio"])
        state = {"at_boundary": True, "pending_actions": False}
        self.assertEqual(jev.compaction(state)["action"], "save_handoff")

    def test_compaction_requires_boundary_and_current_handoff(self):
        state = {"used_tokens": 90, "window_tokens": 100}
        self.assertEqual(jev.compaction(state)["action"], "save_handoff")
        state.update(at_boundary=True, pending_actions=False, handoff_saved=True)
        self.assertEqual(jev.compaction(state)["action"], "recommend_compact")
        state["pending_actions"] = True
        self.assertEqual(jev.compaction(state)["action"], "wait")
        self.assertFalse(jev.compaction(state)["executed"])

    def test_middle_band_uses_jev_but_low_usage_does_not(self):
        state = {"used_tokens": 70, "window_tokens": 100, "at_boundary": True,
                 "pending_actions": False, "handoff_saved": True}
        self.assertEqual(jev.compaction(state)["action"], "notice")
        self.assertEqual(jev.compaction(state, {"type": "noul", "noul": 0.9})["action"], "recommend_compact")
        state["used_tokens"] = 20
        self.assertEqual(jev.compaction(state, {"type": "noul", "noul": 1})["action"], "continue")

    def test_reject_transcript_and_invalid_telemetry(self):
        for state in [{"transcript": "private"}, {"window_tokens": 0},
                      {"used_tokens": True}, {"at_boundary": "yes"}, []]:
            with self.subTest(state=state), self.assertRaises(ValueError):
                jev.build_request("task", state)
        with self.assertRaises(ValueError):
            jev.build_request("x" * 2001, {})

    def test_timeout_falls_back_without_echoing_error(self):
        argv = [str(SCRIPT), "--task", "Review workload"]
        with patch.object(sys, "argv", argv), patch.dict(jev.os.environ, {"JEV_API_KEY": "test"}), \
             patch.object(jev, "ask", side_effect=TimeoutError("sensitive response")), \
             patch("builtins.print") as output:
            jev.main()
        result = json.loads(output.call_args.args[0])
        self.assertEqual(result["provider"], "fallback")
        self.assertNotIn("sensitive", result["fallback_reason"])

    def test_redirects_are_rejected(self):
        with self.assertRaises(ValueError):
            jev.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid")

    def test_http_contract_and_bad_response(self):
        payload = jev.build_request("Review foundation-model dataset", {})
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.read.return_value = b'{"answers": {"fm_dataset": {"type": "choice"}}}'
        with patch.object(jev.urllib.request, "build_opener", return_value=opener):
            self.assertIn("fm_dataset", jev.ask(payload, "test-key")["answers"])
            request = opener.open.call_args.args[0]
            self.assertEqual(request.full_url, jev.ENDPOINT)
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(json.loads(request.data), payload)
            self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
            for raw in (b'not json', b'{"answers": []}', b'[]', b'x' * 131073):
                response.read.return_value = raw
                with self.subTest(raw=raw[:40]), self.assertRaises(ValueError):
                    jev.ask(payload, "test-key")

    def test_offline_cli(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--task", "Review foundation-model dataset",
                                 "--require", "fm_dataset", "--offline"], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        self.assertEqual(data["provider"], "fallback")
        self.assertEqual(data["fallback_reason"], "offline requested")


if __name__ == "__main__":
    unittest.main()
