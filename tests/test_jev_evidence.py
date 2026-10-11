"""Small local JSON/event fixtures; no live model, real logs, or job submissions."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import jev_evidence as evidence
import jev_codex as router
import jev_handoff as handoffs


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = evidence.EvidenceStore(self.root, 'thread', workers=1, redactor=evidence.Redactor({}))

    def event(self, method, item_id='cmd', turn='turn', **data):
        params = {'threadId': 'thread', 'turnId': turn}
        if method == 'item/commandExecution/outputDelta':
            params.update(itemId=item_id, **data)
        else:
            params['item'] = {'id': item_id, 'type': 'commandExecution', **data}
        self.store.event(method, params)

    def latest(self, item_id='cmd', turn='turn'):
        key = evidence.digest(['thread', turn, item_id])
        return self.store.get(self.store.bundle()['exchanges'][key])

    def test_overlapping_pairing_and_literal_output(self):
        for key in ('a', 'b'):
            self.event('item/started', key, command=f'echo {key}', cwd='/work')
        self.event('item/commandExecution/outputDelta', 'a', delta='one\n')
        self.event('item/commandExecution/outputDelta', 'b', delta='two\n')
        self.event('item/completed', 'b', status='completed', exitCode=0)
        self.event('item/completed', 'a', status='failed', exitCode=1)
        self.assertEqual(self.latest('a')['output']['text'], 'one\n')
        self.assertEqual(self.latest('b')['output']['text'], 'two\n')
        self.assertTrue(self.latest('a')['paired'])
        self.assertEqual(self.latest('b')['evidence_status'], 'observed_protocol_result')
        self.assertEqual(self.latest('a')['exit_code'], 1)

    def test_output_before_start_and_completion_before_start(self):
        self.event('item/commandExecution/outputDelta', delta='failure')
        self.event('item/completed', status='failed', exitCode=2)
        self.assertFalse(self.latest()['paired'])
        self.assertEqual(self.latest()['incomplete_reason'], 'missing_start_event')
        self.event('item/started', command='pytest', cwd='/work')
        self.assertTrue(self.latest()['paired'])
        self.assertEqual(self.latest()['status'], 'failed')
        self.assertEqual(self.latest()['output']['text'], 'failure')

    def test_empty_aggregate_overrides_deltas_and_late_chunks(self):
        self.event('item/started', command='test')
        self.event('item/commandExecution/outputDelta', delta='not authoritative')
        self.event('item/completed', aggregatedOutput='', status='completed', exitCode=0)
        self.event('item/commandExecution/outputDelta', delta='late')
        self.assertEqual(self.latest()['output']['text'], '')
        self.assertTrue(self.latest()['output_available'])
        self.assertEqual(self.latest()['output_source'], 'aggregate')

    def test_late_chunks_without_aggregate_are_captured(self):
        self.event('item/started', command='test')
        self.event('item/completed', status='completed', exitCode=0)
        self.event('item/commandExecution/outputDelta', delta='late delta')
        self.assertEqual(self.latest()['output']['text'], 'late delta')

    def test_partial_and_interrupted_exchange_survives_restart(self):
        self.event('item/started', command='long task')
        self.event('item/commandExecution/outputDelta', delta='partial')
        self.store.flush()
        restored = evidence.EvidenceStore(self.root, 'thread', workers=1)
        saved = restored.get(next(iter(restored.bundle()['exchanges'].values())))
        self.assertFalse(saved['result_seen'])
        self.assertEqual(saved['incomplete_reason'], 'controller_closed_without_result')
        self.assertEqual(saved['output']['text'], 'partial')
        self.assertIsNone(saved['exit_code'])

    def test_started_unit_exists_before_turn_end(self):
        self.event('item/started', command='test')
        restored = evidence.EvidenceStore(self.root, 'thread', workers=1)
        self.assertEqual(len(restored.bundle()['exchanges']), 1)
        self.assertEqual(self.latest()['incomplete_reason'], 'awaiting_result')
        self.store.event('turn/completed', {'threadId': 'thread', 'turn': {'id': 'turn', 'status': 'failed'}})
        self.assertEqual(self.latest()['incomplete_reason'], 'turn_ended_without_result')

    def test_foreign_threads_and_unsupported_payloads_are_excluded(self):
        self.store.event('item/completed', {'threadId': 'other', 'turnId': 't', 'item': {'type': 'commandExecution', 'id': 'a'}})
        self.store.event('item/completed', {'threadId': 'thread', 'turnId': 't', 'item': {'type': 'reasoning', 'id': 'a', 'content': 'private'}})
        self.assertEqual(self.store.bundle()['exchanges'], {})

    def test_redaction_before_clipping_and_split_secrets(self):
        self.store.redact = evidence.Redactor({'JEV_API_KEY': 'very-secret-key'})
        self.event('item/started', command='curl --token abc123', cwd='/work')
        for chunk in ('Bearer abc', 'def\nvery-secret-', 'key\npassword="hide me"\n'):
            self.event('item/commandExecution/outputDelta', delta=chunk)
        self.event('item/completed', status='failed', exitCode=1)
        saved = self.latest()
        self.assertTrue(saved['output']['redacted'])
        text = '\n'.join(p.read_text() for p in (self.store.path / 'units').glob('*.json'))
        for secret in ('very-secret-key', 'abcdef', 'hide me', 'abc123'):
            self.assertNotIn(secret, text)
        self.assertIn('[REDACTED]', text)

    def test_capture_limits_and_explicit_failed_case(self):
        self.event('item/started', command='pytest')
        self.event('item/completed', status='failed', exitCode=1,
                   aggregatedOutput='FAILED test_x.py::test_y\n' + 'x' * (evidence.TEXT_BYTES + 100))
        saved = self.latest()
        self.assertTrue(saved['output']['truncated'])
        self.assertFalse(saved['original_available'])
        self.assertEqual(saved['failing_cases'], ['FAILED test_x.py::test_y'])
        self.assertLessEqual(len(saved['output']['text'].encode()), evidence.TEXT_BYTES)

    def test_delta_cap_discards_partial_secret_line(self):
        self.event('item/started', command='test')
        self.event('item/commandExecution/outputDelta', delta='prefix\n' + 'x' * evidence.RAW_BYTES)
        self.event('item/completed', status='failed')
        self.assertEqual(self.latest()['output']['text'], 'prefix')
        self.assertTrue(self.latest()['output']['truncated'])

    def test_immutable_reference_and_integrity(self):
        request = self.store.request('first request')
        ref = self.store.reference()
        before = Path(ref['path']).read_bytes()
        self.store.request('second request')
        self.assertEqual(Path(ref['path']).read_bytes(), before)
        self.assertEqual(self.store.get(ref['evidence_id'])['bundle']['requests'], [request])
        path = self.store.path / 'units' / f'{request}.json'
        data = json.loads(path.read_text())
        data['content']['text'] = 'changed'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(evidence.EvidenceError, 'integrity'):
            self.store.get(request)
        with self.assertRaises(FileNotFoundError):
            self.store.get('ev_' + '0' * 64)
        with self.assertRaises(evidence.EvidenceError):
            self.store.get('../outside')

    def test_private_atomic_files_and_failed_publish(self):
        self.store.request('a')
        for path in (self.store.path, self.store.path / 'units'):
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)
        for path in [self.store.path / 'bundle.json', *list((self.store.path / 'units').glob('*.json'))]:
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        old = (self.store.path / 'bundle.json').read_bytes()
        with patch.object(evidence.os, 'replace', side_effect=OSError('write failed')):
            with self.assertRaises(OSError):
                self.store.request('b')
        self.assertEqual((self.store.path / 'bundle.json').read_bytes(), old)
        self.assertFalse(list(self.store.path.glob('tmp*')))

    def test_capacity_never_evicts_existing_sources(self):
        ref = self.store.request('a')
        with patch.object(evidence, 'MAX_UNITS', 1):
            with self.assertRaisesRegex(evidence.EvidenceError, 'capacity'):
                self.store.request('b')
        self.assertEqual(self.store.get(ref)['content']['text'], 'a')

    def test_state_sources_and_handoff_labels(self):
        source = self.store.request('Keep the running job')
        state = {key: [] for key in ('constraints', 'decisions', 'proposals', 'unresolved_questions', 'next_action')}
        state['constraints'] = [{'text': 'Keep the job', 'sources': [source]}]
        state['proposals'] = [{'text': 'Maybe change settings', 'sources': [source]}]
        ref = self.store.update_state(state)
        self.assertEqual(self.store.get(ref)['evidence_status'], 'recorded_assertion')
        state['decisions'] = [{'text': 'Verified!', 'sources': ['ev_' + '0' * 64]}]
        with self.assertRaises(FileNotFoundError):
            self.store.update_state(state)
        data = handoffs.template()
        data['next_action'] = 'Inspect result; password=secret'
        path = self.root / 'handoff.json'
        path.write_text(json.dumps(data))
        ref = self.store.handoff(handoffs.load(path))
        saved = self.store.get(ref)
        self.assertEqual(saved['evidence_status'], 'recorded_assertion')
        self.assertIn('[REDACTED]', saved['state']['next_action'])
        self.assertEqual(json.loads(path.read_text()), data)

    def test_cli_retrieval_and_legacy_missing_store(self):
        ref = self.store.request('request')
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(evidence.main(['--repo-root', str(self.root), '--thread', 'thread', '--get', ref]), 0)
        self.assertEqual(json.loads(out.getvalue())['content']['text'], 'request')
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(evidence.main(['--repo-root', str(self.root), '--thread', 'legacy', '--bundle']), 1)
        self.assertFalse((self.root / 'jev_routing/context/jev-router/legacy').exists())


class ControllerEvidenceTests(unittest.TestCase):
    def test_fake_server_checkpoint_resume_and_jev_payload_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / 'jev_routing/context/jev-router/thr_test/old-turn.json'
            legacy.parent.mkdir(parents=True)
            legacy.write_text('{"legacy": true}')
            original = legacy.read_bytes()
            peer = Path(__file__).with_name('fake_codex_app_server.py')
            command = [sys.executable, str(peer), '--trace', str(root / 'trace'), '--scenario', 'command_activity']
            client = router.Controller(root=root, offline=True, auto_compact=False, workers=1,
                                       input_fn=lambda _: 'y', output=lambda *a, **k: None)
            try:
                client.connect(command)
                client.run_task('Run the synthetic test')
                record = json.loads(client.last_checkpoint.read_text())
                ref = record['evidence_recovery']
                self.assertTrue(Path(ref['path']).is_file())
                refs = client.evidence.bundle()['exchanges']
                unit = client.evidence.get(next(iter(refs.values())))
                self.assertEqual(unit['output']['text'], 'test\n')
                self.assertEqual(unit['exit_code'], 0)
                trace = [json.loads(line) for line in (root / 'trace').read_text().splitlines()]
                task = next(r for r in trace if r.get('method') == 'turn/start')
                self.assertIn('Local evidence recovery', task['params']['input'][1]['text'])
            finally:
                client.close()
            restored = router.Controller(root=root, offline=True, auto_compact=False, workers=1,
                                         input_fn=lambda _: 'y', output=lambda *a, **k: None)
            try:
                restored.connect(command, resume='thr_test')
                self.assertEqual(restored.evidence.get(ref['evidence_id'])['kind'], 'recovery_bundle')
                payload = router.jev.build_request('Next task', {}, catalog=restored.catalog)
                self.assertNotIn('evidence', payload['state'])
                self.assertNotIn('Local evidence recovery', json.dumps(payload))
                self.assertEqual(legacy.read_bytes(), original)
            finally:
                restored.close()


class RecoveryGuardTests(unittest.TestCase):
    def test_bundle_changes_block_compaction_and_handshake_does_not_create_store(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            peer = Path(__file__).with_name('fake_codex_app_server.py')
            command = [sys.executable, str(peer), '--trace', str(root / 'trace'), '--scenario', 'low']
            client = router.Controller(root=root, offline=True, workers=1, output=lambda *a, **k: None)
            try:
                client.connect(command, check=True)
                self.assertIsNone(client.evidence)
                self.assertFalse((root / 'jev_routing').exists())
            finally:
                client.close()
            client = router.Controller(root=root, offline=True, workers=1, output=lambda *a, **k: None)
            try:
                client.connect(command)
                client.run_task('synthetic task')
                self.assertTrue(client.boundary_context()['handoff_saved'])
                source = client.evidence.bundle()['requests'][0]
                state = {key: [] for key in ('constraints', 'decisions', 'proposals', 'unresolved_questions', 'next_action')}
                state['next_action'] = [{'text': 'A newly adopted next step', 'sources': [source]}]
                client.evidence.update_state(state)
                self.assertFalse(client.boundary_context()['handoff_saved'])
            finally:
                client.close()

    def test_orphan_after_failed_bundle_publish_is_accounted_on_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            store = evidence.EvidenceStore(directory, 't', workers=1)
            with patch.object(store, 'publish', side_effect=OSError('simulated crash')):
                with self.assertRaises(OSError):
                    store.request('a')
            self.assertEqual(store.bundle()['requests'], [])
            restored = evidence.EvidenceStore(directory, 't', workers=1)
            self.assertEqual(restored.bundle()['unit_count'], 1)
            self.assertEqual(restored.bundle()['requests'], [])
            restored.request('a')
            self.assertEqual(restored.bundle()['unit_count'], 1)

    def test_corrupt_schema_and_symlink_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            store = evidence.EvidenceStore(directory, 't', workers=1)
            bundle = store.bundle()
            bundle['schema_version'] = 99
            store.publish(bundle)
            with self.assertRaises(evidence.EvidenceError):
                evidence.EvidenceStore(directory, 't', workers=1)
            for malformed in ([], {'data': []}):
                evidence.atomic_write(store.path / 'bundle.json', malformed)
                with self.assertRaises(evidence.EvidenceError):
                    store.bundle()
            bundle['schema_version'] = 1
            bundle['exchanges'] = []
            store.publish(bundle)
            with self.assertRaises(evidence.EvidenceError):
                store.bundle()
            store.path.joinpath('bundle.json').unlink()
            store.path.joinpath('bundle.json').symlink_to(Path(directory) / 'elsewhere')
            with self.assertRaises(evidence.EvidenceError):
                evidence.EvidenceStore(directory, 't', workers=1)

    def test_failure_review_is_not_automatically_cleared_by_successful_test(self):
        with tempfile.TemporaryDirectory() as directory:
            store = evidence.EvidenceStore(directory, 't', workers=1)
            for ident, code in (('failed', 1), ('success', 0)):
                store.event('item/completed', {'threadId': 't', 'turnId': 'turn', 'item': {
                    'id': ident, 'type': 'commandExecution', 'command': 'pytest',
                    'status': 'completed', 'exitCode': code, 'aggregatedOutput': 'diagnostic'}})
            refs = store.bundle()['failures_needing_review']
            self.assertEqual(len(refs), 1)
            self.assertEqual(store.get(next(iter(refs.values())))['item_id'], 'failed')
