"""Controller QoL regressions; mocked clocks, RPC, and temporary text only."""
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import jev_codex as router
import jev_context as jev


class OutputTests(unittest.TestCase):
    def test_line_boundaries_and_control_escaping(self):
        item = {"id": "c", "type": "commandExecution", "command": "test", "exitCode": 1, "status": "completed"}
        for count in (9, 10, 11, 100):
            for trailing in ("", "\n"):
                with self.subTest(count=count, trailing=trailing):
                    output = "\n".join(["a", "", "\x1b[31m"] + [str(n) for n in range(count - 3)]) + trailing
                    result = router.ActivityFormatter("always").render(item, True, output)
                    self.assertIn("exit 1", result)
                    self.assertIn("\\u001b[31m", result)
                    if count > 10:
                        self.assertIn(f"\x1b[1m+{count-10} more lines hidden\x1b[0m", result)
                    else:
                        self.assertNotIn("hidden", result)
                        self.assertIn(router.display_text(output).replace("\n", "\n\x1b[2m> \x1b[0m"), result)

    def test_overlapping_buffers_aggregate_and_empty_override(self):
        output = []
        client = router.Controller(output=lambda s, **k: output.append(s), color="never")
        client.thread_id = "t"
        def event(method, **values):
            client.event(method, {"threadId": "t", **values})
        for ident in ("a", "b", "c"):
            event("item/started", item={"id": ident, "type": "commandExecution", "command": ident})
            for delta in ("first", " line\n", "\n".join(str(n) for n in range(11))):
                event("item/commandExecution/outputDelta", itemId=ident, delta=delta)
        event("item/completed", item={"id": "a", "type": "commandExecution", "aggregatedOutput": "authoritative"})
        self.assertIn("authoritative", output[-1])
        self.assertNotIn("first", output[-1])
        event("item/completed", item={"id": "b", "type": "commandExecution", "aggregatedOutput": ""})
        self.assertIn("(no output)", output[-1])
        event("item/completed", item={"id": "c", "type": "commandExecution"})
        self.assertIn("first line", output[-1])
        self.assertIn("+2 more lines hidden", output[-1])
        self.assertEqual(client.command_output, {})


class ControllerUITests(unittest.TestCase):
    def setUp(self):
        self.lines = []
        self.client = router.Controller(output=lambda s, **k: self.lines.append(s), renderer=Mock())
        self.client.thread_id = "t"
        self.client.mode = "task"
        self.client.rpc = Mock()

    def event(self, method, **params):
        self.client.event(method, {"threadId": "t", **params})

    def test_renderer_sanitizes_preserves_raw_and_flushes_missing_completion(self):
        self.event("item/agentMessage/delta", itemId="a", delta="raw\x1b[31m")
        self.client.renderer.delta.assert_called_once_with("a", "raw\\u001b[31m")
        self.event("item/completed", item={"id": "a", "type": "agentMessage", "text": "final\x1b[31m"})
        self.assertEqual(self.client.messages["a"]["text"], "final\x1b[31m")
        self.client.renderer.complete.assert_called_once_with("a", "final\\u001b[31m")
        self.event("item/agentMessage/delta", itemId="b", delta="unfinished")
        self.event("turn/completed", turn={"id": "turn", "status": "completed"})
        self.assertEqual(self.client.messages["b"]["text"], "unfinished")
        self.client.renderer.close.assert_called()
        self.assertEqual(self.lines, [])

    def test_missing_final_uses_deltas(self):
        self.event("item/agentMessage/delta", itemId="a", delta="buffered")
        self.event("item/completed", item={"id": "a", "type": "agentMessage"})
        self.client.renderer.complete.assert_called_once_with("a", None)
        self.assertEqual(self.client.messages["a"]["text"], "buffered")

    def test_no_renderer_duplicate_and_empty_delta(self):
        self.client.renderer = None
        self.event("item/agentMessage/delta", itemId="a", delta="")
        self.assertIsNone(self.client.last_agent_output_at)
        self.event("item/completed", item={"id": "a", "type": "agentMessage", "text": "answer"})
        self.assertEqual(self.lines, ["answer"])
        self.event("item/agentMessage/delta", itemId="b", delta="streamed")
        self.event("item/completed", item={"id": "b", "type": "agentMessage", "text": "streamed"})
        self.assertEqual(self.lines, ["answer", "streamed"])

    def test_foreign_and_compaction_messages_do_not_render(self):
        self.client.event("item/agentMessage/delta", {"threadId": "other", "itemId": "a", "delta": "foreign"})
        self.client.mode = "compact"
        self.event("item/agentMessage/delta", itemId="a", delta="internal")
        self.event("item/completed", item={"id": "a", "type": "agentMessage", "text": "internal"})
        self.client.renderer.delta.assert_not_called()
        self.client.renderer.complete.assert_not_called()
        self.assertIsNone(self.client.last_agent_output_at)

    def test_idle_heartbeat_after_streaming_stalls(self):
        now = [0]
        self.client.turn_timeout = 200
        def pump():
            now[0] += 1
            if now[0] <= 40:
                self.event("item/agentMessage/delta", itemId="a", delta="x")
            else:
                self.event("item/agentMessage/delta", itemId="a", delta="")
                self.client.event("item/agentMessage/delta", {"threadId": "other", "itemId": "z", "delta": "foreign"})
            if now[0] == 75:
                self.client.completed["turn"] = {"status": "completed"}
        self.client.rpc.pump.side_effect = pump
        beats = []
        with patch.object(router.time, "monotonic", side_effect=lambda: now[0]), patch.object(self.client, "flush_notices"), patch.object(self.client, "activity_status", side_effect=lambda: beats.append(now[0])):
            self.client.wait_turn("turn")
        self.assertEqual(beats, [70])

    def test_streaming_does_not_extend_timeout(self):
        now = [0.0]
        self.client.turn_timeout = 2
        def pump():
            now[0] += 0.25
            self.event("item/agentMessage/delta", itemId="a", delta="x")
        self.client.rpc.pump.side_effect = pump
        with patch.object(router.time, "monotonic", side_effect=lambda: now[0]), patch.object(self.client, "flush_notices"):
            with self.assertRaises(TimeoutError):
                self.client.wait_turn("turn")
        self.assertEqual(now[0], 2)

    def test_exit_and_cleanup(self):
        self.client.exit_details()
        resume = self.lines[-1].split("Resume: ")[1]
        command = shlex.split(resume)
        self.assertEqual(command[-2:], ["--resume", "t"])
        self.assertTrue(Path(command[1]).is_file())
        self.client.thread_id = None
        self.lines.clear()
        self.client.exit_details()
        self.assertEqual(self.lines, [])
        self.client.renderer.close.side_effect = RuntimeError("render error")
        with self.assertRaises(RuntimeError):
            self.client.close()
        self.client.rpc.close.assert_called_once()

    def test_status_failure_keeps_context(self):
        self.client.usage = {"last": {"totalTokens": 123}}
        for error in (TimeoutError("timeout"), router.RpcRejected("unsupported"), OSError("broken")):
            self.client.rpc.call.side_effect = error
            self.client.show_status()
            self.assertIn("unavailable", self.lines[-1])
            self.assertIn('"used_tokens": 123', self.lines[-2])
        self.assertEqual(self.client.rpc.call.call_args.args, ("account/rateLimits/read", {}))


class WeeklyLimitTests(unittest.TestCase):
    def test_weekly_in_either_slot_and_bucket_preference(self):
        for slot in ("primary", "secondary"):
            for used in (0, 35, 100, 123):
                snapshot = {slot: {"windowDurationMins": 10080, "usedPercent": used, "resetsAt": 1800000000}}
                result = router.weekly_limit_status({"rateLimitsByLimitId": {"codex": snapshot}, "rateLimits": {}})
                self.assertIn(f"{used}% used", result)
                self.assertIn(f"{max(0,100-used)}% left", result)
                self.assertIn("resets", result)
                self.assertEqual(result.count("█") + result.count("░"), 20)
                self.assertEqual(result, router.weekly_limit_status({"rateLimits": snapshot}))

    def test_invalid_missing_and_reset(self):
        for response in (None, {}, {"rateLimits": []}, {"rateLimits": {"secondary": {"windowDurationMins": 300, "usedPercent": 5}}}):
            self.assertIn("unavailable", router.weekly_limit_status(response))
        for used in (-1, True, 1.5, "30", None):
            self.assertIn("unavailable", router.weekly_limit_status({"rateLimits": {"primary": {"windowDurationMins": 10080, "usedPercent": used}}}))
        for reset in (None, "bad", True, 10**100):
            result = router.weekly_limit_status({"rateLimits": {"primary": {"windowDurationMins": 10080, "usedPercent": 5, "resetsAt": reset}}})
            self.assertIn("5% used", result)
            self.assertNotIn("resets", result)


class RoutingThresholdTests(unittest.TestCase):
    def test_probability_and_confidence_boundaries(self):
        for selected, floor in (("skip", .75), ("read", .65)):
            for probability, confidence, expected in ((floor, floor, selected), (floor-.0001, floor, "inspect"), (floor, floor-.0001, "inspect")):
                probs = {key: (1-probability)/2 for key in jev.READ_OPTIONS}
                probs[selected] = probability
                self.assertEqual(jev.choice({"type": "choice", "choice": selected, "confidence": confidence, "probabilities": probs}), expected)


class StatusIntegrationTests(unittest.TestCase):
    def test_status_and_rejection_allow_next_task_and_new_recovery_location(self):
        for scenario in ("low", "reject_limits"):
            with tempfile.TemporaryDirectory() as root:
                trace = Path(root) / "trace.jsonl"
                output = []
                client = router.Controller(root=root, offline=True, auto_compact=False, output=lambda s, **k: output.append(s))
                try:
                    client.connect([sys.executable, str(Path(__file__).with_name("fake_codex_app_server.py")), "--trace", str(trace), "--scenario", scenario])
                    client.show_status()
                    self.assertIn("unavailable" if scenario == "reject_limits" else "35% used", output[-1])
                    client.run_task("synthetic task")
                    methods = [json.loads(line).get("method") for line in trace.read_text().splitlines()]
                    self.assertEqual(methods.count("turn/start"), 1)
                    self.assertEqual(methods.count("account/rateLimits/read"), 1)
                    self.assertEqual(client.last_checkpoint.parent, Path(root) / "jev_routing/context/jev-router/thr_test")
                    self.assertFalse((Path(root) / "context").exists())
                    self.assertEqual(os.stat(client.last_checkpoint).st_mode & 0o777, 0o600)
                finally:
                    client.close()


class StorageTests(unittest.TestCase):
    def test_legacy_state_migrates_and_registration_resumes(self):
        from jev_storage import migrate_context, relocated_handoff
        import jev_handoff as handoffs
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "context/jev-router/thr_test"
            old.mkdir(parents=True)
            record = old / "old-turn.json"
            record.write_bytes(b'{"historical":"unaltered"}\n')
            record.chmod(0o600)
            handoff = root / "context/jev-handoffs/experiment.json"
            handoff.parent.mkdir()
            # The checked-in template is a valid empty handoff.
            handoff.write_bytes((jev.ROOT / "jev_routing/examples/experiment-handoff.json").read_bytes())
            (old / "handoff.json").write_text(json.dumps({"path": str(handoff)}))
            new = root / "jev_routing/context/jev-router/thr_test"
            new.mkdir(parents=True)
            (new / "new-turn.json").write_text("new record")
            migrate_context(root)
            self.assertFalse((root / "context").exists())
            self.assertEqual((new / "old-turn.json").read_bytes(), b'{"historical":"unaltered"}\n')
            self.assertEqual(os.stat(new / "old-turn.json").st_mode & 0o777, 0o600)
            moved = relocated_handoff(handoff, root)
            handoffs.load(moved)
            client = router.Controller(root=root, output=lambda *a, **k: None)
            try:
                client.connect([sys.executable, str(Path(__file__).with_name("fake_codex_app_server.py")), "--trace", str(root / "trace")], resume="thr_test")
                self.assertEqual(client.handoff_path, moved)
                self.assertEqual(json.loads((new / "handoff.json").read_text())["path"], str(moved))
            finally:
                client.close()

    def test_collision_preflight_and_unrelated_context(self):
        from jev_storage import migrate_context
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "context/jev-router/t"
            new = root / "jev_routing/context/jev-router/t"
            old.mkdir(parents=True)
            new.mkdir(parents=True)
            (old / "a.json").write_text("move me")
            (old / "z.json").write_text("old")
            (new / "z.json").write_text("new")
            with self.assertRaisesRegex(ValueError, "collision"):
                migrate_context(root)
            self.assertTrue((old / "a.json").is_file())
            self.assertEqual((new / "z.json").read_text(), "new")
            (new / "z.json").unlink()
            unrelated = root / "context/unrelated.txt"
            unrelated.write_text("keep")
            migrate_context(root)
            self.assertEqual(unrelated.read_text(), "keep")
            self.assertFalse(old.exists())


class LauncherExitTests(unittest.TestCase):
    def test_quit_interrupt_and_batch_skip_editor(self):
        for mode in ("quit", "interrupt", "early_interrupt", "batch"):
            argv = ["jev_codex.py", "--offline-jev"]
            if mode == "batch":
                argv += ["--prompt", "  batch prompt  "]
            with patch.object(sys, "argv", argv), patch.object(router, "Controller") as factory, patch.object(router, "PromptEditor") as editor_factory, patch.object(router, "MarkdownReplies"):
                client = factory.return_value
                client.run_task.return_value = {"status": "completed"}
                editor_factory.return_value.prompt.side_effect = KeyboardInterrupt if mode == "interrupt" else ["/quit"]
                if mode == "early_interrupt":
                    client.connect.side_effect = KeyboardInterrupt
                result = router.main()
                self.assertEqual(result, 130 if "interrupt" in mode else 0)
                client.close.assert_called_once()
                if mode == "batch":
                    editor_factory.assert_not_called()
                    client.run_task.assert_called_once_with("  batch prompt  ")
                else:
                    client.exit_details.assert_called_once()
