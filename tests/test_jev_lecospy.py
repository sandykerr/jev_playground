"""Small text/JSON fixtures only: no real jobs, model calls, raster I/O or timings."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import evaluate_routing as evaluation
import jev_catalog as catalogs
import jev_context as jev
import jev_codex as controller
import jev_handoff as handoffs
import jev_workers as workers


class LecospyRoutingTests(unittest.TestCase):
    def test_catalog_paths_and_ownership(self):
        catalog = catalogs.load_catalog()
        self.assertEqual(jev.ROOT, Path(__file__).resolve().parents[2])
        self.assertTrue(all(catalogs.availability(jev.ROOT, catalog["documents"], workers=1)))
        self.assertTrue(all(doc["owns"] for doc in catalog["documents"].values()))
        self.assertFalse(any("jev_routing/.agents/" in doc["path"] for doc in catalog["documents"].values()))

    def test_offline_gold_cases(self):
        cases = evaluation.load_cases(evaluation.DEFAULT_CASES, jev.CATALOG)
        rows = [evaluation.evaluate_case((case, jev.ROOT, jev.CATALOG, False))["local"] for case in cases]
        summary = evaluation.summarize(rows)
        self.assertTrue(summary["passed"], rows)
        self.assertEqual(summary["extra_reads"], 0)

    def test_ambiguous_names_and_sentence_punctuation(self):
        self.assertEqual(catalogs.pinned_documents("Read README.md and SKILL.md.", [], jev.CATALOG), set())
        self.assertEqual(catalogs.pinned_documents("Read dataset_context.md.", [], jev.CATALOG), {"fm_dataset"})
        self.assertEqual(catalogs.pinned_documents("notdataset_context.md dataset_context.md.bak", [], jev.CATALOG), set())
        path = ".agents/repo_context/world_model/README.md"
        self.assertEqual(catalogs.pinned_documents(f"Read {path}.", [], jev.CATALOG), {"wm_index"})

    def test_remote_skip_cannot_hide_authorities_or_instructions(self):
        answer = {"type": "choice", "choice": "skip", "confidence": 1,
                  "probabilities": {"skip": 1, "read": 0, "inspect": 0}}
        payload = jev.build_request("Read fm_latest_ckpt_plan.md", {})
        result = jev.route(payload, {"answers": {key: answer for key in jev.CATALOG["documents"]}}, workers=1)
        read = {doc["id"] for doc in result["documents"] if doc["action"] == "read"}
        self.assertTrue({"instructions", "execution_policy", "fm_migration", "fm_index", "fm_model", "fm_tracker"} <= read)

    def test_missing_pinned_document_keeps_required_action(self):
        with tempfile.TemporaryDirectory() as root:
            payload = jev.build_request("task", {}, ["fm_dataset"])
            result = jev.route(payload, required=["fm_dataset"], root=root, workers=1)
        doc = next(doc for doc in result["documents"] if doc["id"] == "fm_dataset")
        self.assertEqual(doc["action"], "missing")
        self.assertEqual(doc["requested_action"], "read")
        self.assertTrue(doc["required"])

    def test_shared_contract_does_not_select_an_unrelated_workflow(self):
        result = jev.route(jev.build_request("Review world-model normalization", {}), workers=1)
        self.assertEqual(result["workflows"], ["world_model"])
        read = {doc["id"] for doc in result["documents"] if doc["action"] == "read"}
        self.assertIn("wm_dataset", read)
        self.assertNotIn("tiling_skill", read)

    def test_remote_discovered_workflow_preserves_its_instructions(self):
        read = {"type": "choice", "choice": "read", "confidence": 1,
                "probabilities": {"skip": 0, "read": 1, "inspect": 0}}
        result = jev.route(jev.build_request("Continue yesterday's work", {}),
                           {"answers": {"wm_handoff": read}}, workers=1)
        self.assertEqual(result["workflows"], ["world_model"])
        selected = {doc["id"] for doc in result["documents"] if doc["action"] == "read"}
        self.assertTrue({"wm_skill", "wm_index", "wm_handoff"} <= selected)

    def test_full_prompt_pins_survive_routing_summary_truncation(self):
        full = "x" * 2000 + " Read dataset_context.md."
        required = controller.pinned_documents(full, [])
        result = jev.route(jev.build_request(full[:2000], {}, required), required=required, workers=1)
        self.assertEqual(next(doc for doc in result["documents"] if doc["id"] == "fm_dataset")["action"], "read")

    def test_root_and_custom_catalog_cli_from_other_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "chosen.md").write_text("PRIVATE DOCUMENT BODY")
            catalog = copy.deepcopy(jev.CATALOG)
            doc = catalog["documents"]["instructions"]
            doc["path"] = "chosen.md"
            catalog["documents"] = {"chosen": doc}
            path = root / "catalog.json"
            path.write_text(json.dumps(catalog))
            cmd = [sys.executable, str(jev.ROOT / "jev_routing/scripts/jev_context.py"),
                   "--repo-root", str(root), "--catalog", str(path), "--task", "Review chosen.md.",
                   "--offline", "--workers", "1"]
            result = subprocess.run(cmd, cwd=root, check=True, capture_output=True, text=True)
            data = json.loads(result.stdout)
            self.assertEqual(data["repository_root"], str(root))
            self.assertEqual(data["documents"][0]["action"], "read")
            dry = subprocess.run(cmd + ["--dry-run"], cwd=root, check=True, capture_output=True, text=True)
            self.assertNotIn("PRIVATE DOCUMENT BODY", dry.stdout)
            self.assertNotIn(str(root), dry.stdout)

    def test_catalog_rejects_bad_references_and_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            for field, value in (("requires", ["missing"]), ("path", "../outside.md"),
                                 ("workflows", ["nutrition"]), ("status", "verified")):
                catalog = copy.deepcopy(jev.CATALOG)
                catalog["documents"]["fm_index"][field] = value
                path.write_text(json.dumps(catalog))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    catalogs.load_catalog(path)
            root = Path(directory) / "root"
            root.mkdir()
            (root / "link").symlink_to(path)
            with self.assertRaises(ValueError):
                catalogs.availability(root, {"link": {"path": "link"}}, workers=1)

    def test_worker_serial_and_spawn_results(self):
        with patch.dict(os.environ, {"SLURM_CPUS_PER_TASK": "8"}):
            self.assertEqual(workers.worker_count(jobs=3), 3)
            self.assertEqual(workers.worker_count(1, jobs=3), 1)
        with patch.object(workers, "ProcessPoolExecutor", side_effect=AssertionError("serial spawned")):
            self.assertEqual(workers.bounded_map(abs, [-2, -1], 1), [2, 1])
        self.assertEqual(workers.bounded_map(abs, [-2, -1], 2), [2, 1])
        for count in (0, -1, "bad"):
            with self.assertRaises(ValueError):
                workers.worker_count(count, 2)


def active_handoff():
    data = handoffs.template()
    data["objective"] = "PRIVATE experiment description"
    data["jobs"] = [{"job_id": "12345", "state": "running", "description": "DDP smoke",
                     "evidence_status": "submitted", "evidence": ["submission receipt"],
                     "next_action": "Inspect returned smoke and resume reports"}]
    return data


class HandoffTests(unittest.TestCase):
    def test_evidence_status_and_unknown_identity(self):
        data = active_handoff()
        self.assertIsNone(handoffs.validate(data)["checkpoint"])
        data["jobs"][0]["state"] = "completed"
        with self.assertRaises(ValueError):
            handoffs.validate(data)
        data["jobs"][0]["evidence_status"] = "user_reported"
        handoffs.validate(data)
        data["jobs"][0]["evidence_status"] = "independently_verified"
        data["jobs"][0]["evidence"] = []
        with self.assertRaises(ValueError):
            handoffs.validate(data)

    def test_invalid_or_unbounded_handoff(self):
        for field, value in (("workflows", ["diet"]), ("next_action", ""), ("code_revision", []),
                             ("objective", "x" * 2001), ("jobs", {})):
            data = active_handoff()
            data[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                handoffs.validate(data)


class HandoffControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / "experiment.json"
        self.path.write_text(json.dumps(active_handoff()))
        self.trace = self.root / "trace.jsonl"
        self.peer = Path(__file__).with_name("fake_codex_app_server.py")
        self.client = self.make_client(self.path)

    def make_client(self, handoff=None):
        return controller.Controller(root=self.root, offline=True, workers=1, handoff=handoff, auto_compact=True,
                                     turn_timeout=5, input_fn=lambda _: "", output=lambda *a, **k: None)

    def connect(self, scenario="normal", resume=None):
        self.client.connect([sys.executable, str(self.peer), "--trace", str(self.trace),
                             "--scenario", scenario], resume=resume)

    def requests(self):
        return [json.loads(line) for line in self.trace.read_text().splitlines()]

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_detached_job_saved_and_restored_on_resume(self):
        self.connect()
        self.client.run_task("Review the experiment")
        record = json.loads(self.client.last_checkpoint.read_text())
        self.assertEqual(record["experiment_handoff"]["state"]["jobs"][0]["state"], "running")
        self.assertIn("thread/compact/start", [r.get("method") for r in self.requests()])
        self.assertEqual(os.stat(self.client.last_checkpoint).st_mode & 0o777, 0o600)
        self.client.close()
        self.client = self.make_client()
        self.connect("low", resume="thr_test")
        self.assertEqual(self.client.handoff_path, self.path)
        self.client.run_task("Continue")
        turn = [r for r in self.requests() if r.get("method") == "turn/start"][-1]
        self.assertIn('12345', turn["params"]["input"][2]["text"])
        self.assertIn('running', turn["params"]["input"][2]["text"])

    def test_changed_handoff_during_boundary_judgment_blocks_compaction(self):
        self.connect("medium")
        def change(*args, **kwargs):
            data = active_handoff()
            data["next_action"] = "New evidence needs review"
            self.path.write_text(json.dumps(data))
            return {"provider": "jev", "answer": {"type": "noul", "noul": 0.99}}
        with patch.object(controller.compact_policy, "judge_boundary", side_effect=change):
            self.client.run_task("Review experiment")
        self.assertNotIn("thread/compact/start", [r.get("method") for r in self.requests()])
        self.assertFalse(self.client.boundary_context()["handoff_saved"])

    def test_missing_handoff_blocks_compaction(self):
        self.connect("low")
        self.client.run_task("Review experiment")
        self.path.unlink()
        self.assertFalse(self.client.boundary_context()["handoff_saved"])
        with self.assertRaises(OSError):
            self.client.run_task("Continue")

    def test_invalid_handoff_at_turn_end_prevents_checkpoint_and_compaction(self):
        self.connect()
        original = self.client.wait_turn
        def invalidated(*args, **kwargs):
            turn = original(*args, **kwargs)
            self.path.write_text('{"schema_version": 99}')
            return turn
        with patch.object(self.client, "wait_turn", side_effect=invalidated):
            with self.assertRaises(ValueError):
                self.client.run_task("Review experiment")
        self.assertIsNone(self.client.last_checkpoint)
        self.assertNotIn("thread/compact/start", [r.get("method") for r in self.requests()])

    def test_handoff_never_sent_to_jev(self):
        self.connect("low")
        self.client.offline = False
        with patch.dict(os.environ, {"JEV_API_KEY": "test"}), patch.object(jev, "ask", return_value={"answers": {}}) as ask:
            self.client.run_task("Review experiment")
        self.assertEqual(ask.call_count, 1)
        serialized = json.dumps(ask.call_args.args[0])
        self.assertNotIn("PRIVATE", serialized)
        self.assertNotIn("12345", serialized)
        self.assertNotIn(str(self.path), serialized)


if __name__ == "__main__":
    unittest.main()
