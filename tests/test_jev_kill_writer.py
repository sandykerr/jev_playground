"""Synthetic /proc metadata and mocked signals; no real sessions are stopped."""
import contextlib
import io
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import jev_kill_writer as kill


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'codex'
        self.locks = self.home / 'thread-writer-locks'
        self.locks.mkdir(parents=True)
        self.proc = self.root / 'proc'
        self.proc.mkdir()
        self.pid = 987654
        self.process = self.proc / str(self.pid)
        self.process.mkdir()
        self.process.joinpath('stat').write_text(
            f'{self.pid} (codex (test)) S 123 ' + '0 ' * 17 + '5678 0 0')
        self.process.joinpath('cmdline').write_bytes(b'/bin/codex\0app-server\0--listen\0stdio://\0')
        self.process.joinpath('exe').symlink_to('/bin/codex')
        self.target = self.locks / 'thread-one.lock'
        self.target.touch()
        self.proc.joinpath('locks').write_text(self.lock_record(self.target))

    def lock_record(self, path, pid=None, prefix='1:', kind='FLOCK'):
        identity = kill.file_identity(path)[1]
        major, minor, inode = identity
        return f'{prefix} {kind} ADVISORY WRITE {pid or self.pid} {major:02x}:{minor:02x}:{inode} 0 EOF\n'

    def inspect(self, thread='thread-one'):
        return kill.inspect_writer(thread, self.home, workers=1, proc_root=self.proc)

    def test_exact_kernel_lock_and_process_identity(self):
        writer = self.inspect()
        self.assertEqual((writer.pid, writer.ppid, writer.started), (self.pid, 123, 5678))

    def test_ignores_waiters_and_read_locks(self):
        self.proc.joinpath('locks').write_text(self.lock_record(self.target) +
            self.lock_record(self.target, pid=222, prefix='2: ->') +
            self.lock_record(self.target, pid=333).replace('WRITE', 'READ'))
        self.assertEqual(self.inspect().pid, self.pid)

    def test_no_match_does_not_guess_from_stale_filename(self):
        self.proc.joinpath('locks').write_text('')
        with self.assertRaisesRegex(kill.WriterError, 'No unique visible'):
            self.inspect()

    def test_missing_and_invalid_thread(self):
        for thread in ('missing', '../thread-one', '', 'a/b', 'a'*129):
            with self.subTest(thread=thread), self.assertRaises(kill.WriterError):
                self.inspect(thread)

    def test_ambiguous_or_unidentifiable_holder(self):
        for contents in (self.lock_record(self.target, pid=-1, kind='OFDLCK'),
                         self.lock_record(self.target) + self.lock_record(self.target, pid=333)):
            self.proc.joinpath('locks').write_text(contents)
            with self.assertRaisesRegex(kill.WriterError, 'No unique visible'):
                self.inspect()

    def test_shared_server_refused_other_server_allowed(self):
        other = self.locks / 'thread-two.lock'
        other.touch()
        self.proc.joinpath('locks').write_text(self.lock_record(self.target) + self.lock_record(other))
        with self.assertRaisesRegex(kill.WriterError, 'shared server'):
            self.inspect()
        self.proc.joinpath('locks').write_text(self.lock_record(self.target) + self.lock_record(other, pid=222))
        self.assertEqual(self.inspect().pid, self.pid)

    def test_shared_dry_run_reports_all_threads_without_acknowledgement(self):
        other = self.locks / 'thread-two.lock'
        other.touch()
        self.proc.joinpath('locks').write_text(self.lock_record(self.target) + self.lock_record(other))
        writer = kill.inspect_writer('thread-one', self.home, proc_root=self.proc, inspect_only=True)
        self.assertEqual(writer.threads, ('thread-one', 'thread-two'))

    def test_shared_requires_exact_acknowledged_set(self):
        other = self.locks / 'thread-two.lock'
        other.touch()
        self.proc.joinpath('locks').write_text(self.lock_record(self.target) + self.lock_record(other))
        writer = kill.inspect_writer('thread-one', self.home, proc_root=self.proc, also_stop=['thread-two'])
        self.assertEqual(writer.threads, ('thread-one', 'thread-two'))
        for allowed in ([], ['wrong'], ['thread-two', 'unexpected']):
            with self.subTest(allowed=allowed), self.assertRaisesRegex(kill.WriterError, 'shared server'):
                kill.inspect_writer('thread-one', self.home, proc_root=self.proc, also_stop=allowed)
        with self.assertRaisesRegex(kill.WriterError, 'Invalid thread ID'):
            kill.inspect_writer('thread-one', self.home, proc_root=self.proc, also_stop=['../bad'])

    def test_wrong_process_command_and_executable_refused(self):
        self.process.joinpath('cmdline').write_bytes(b'codex\0resume\0thread-one\0')
        with self.assertRaisesRegex(kill.WriterError, 'not a recognizable'):
            self.inspect()
        self.process.joinpath('cmdline').write_bytes(b'python\0script.py\0app-server\0')
        self.process.joinpath('exe').unlink()
        self.process.joinpath('exe').symlink_to('/bin/python')
        with self.assertRaisesRegex(kill.WriterError, 'not a recognizable'):
            self.inspect()

    def test_other_uid_and_self_refused(self):
        with patch.object(kill.os, 'getuid', return_value=os.getuid()+1):
            with self.assertRaisesRegex(kill.WriterError, 'another user'):
                self.inspect()
        with patch.object(kill.os, 'getpid', return_value=self.pid):
            with self.assertRaisesRegex(kill.WriterError, 'parent'):
                self.inspect()

    def test_symlink_refused_and_malformed_locks(self):
        self.target.unlink()
        self.target.symlink_to('/tmp/nonexistent-jev-target')
        with self.assertRaisesRegex(kill.WriterError, 'regular lock'):
            self.inspect()
        with self.assertRaisesRegex(kill.WriterError, 'Unrecognized'):
            kill.parse_locks('1: FLOCK ADVISORY WRITE 2 not-an-inode 0 EOF')

    def test_cli_dry_run_and_failure_never_signal(self):
        with patch.object(kill, 'inspect_writer', return_value=self.inspect()), patch.object(kill, 'stop_writer') as stop, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(kill.main(['thread-one', '--dry-run']), 0)
            stop.assert_not_called()
            self.assertIn(str(self.pid), output.getvalue())
        with patch.object(kill, 'inspect_writer', side_effect=kill.WriterError('not found')), patch.object(kill, 'stop_writer') as stop, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(kill.main(['thread-one']), 1)
            stop.assert_not_called()


class SignalTests(unittest.TestCase):
    def setUp(self):
        self.writer = kill.Writer('thread-one', 987654, 123, 5678, (0, 1, 2))
        self.inspect = self.enterContext(patch.object(kill, 'inspect_writer', return_value=self.writer))
        self.open = self.enterContext(patch.object(kill.os, 'pidfd_open', return_value=42, create=True))
        self.send = self.enterContext(patch.object(kill.signal, 'pidfd_send_signal', create=True))
        self.close = self.enterContext(patch.object(kill.os, 'close'))
        self.poller = Mock()
        self.poller.poll.return_value = [(42, 1)]
        self.enterContext(patch.object(kill.select, 'poll', return_value=self.poller))

    def test_term_and_wait(self):
        self.assertEqual(kill.stop_writer(self.writer, Path('/example')), 'terminated')
        self.send.assert_called_once_with(42, signal.SIGTERM)
        self.close.assert_called_once_with(42)

    def test_identity_changed_before_signal(self):
        self.inspect.return_value = kill.Writer('thread-one', 987654, 123, 9999, (0, 1, 2))
        with self.assertRaisesRegex(kill.WriterError, 'identity changed'):
            kill.stop_writer(self.writer, Path('/example'))
        self.send.assert_not_called()
        self.close.assert_called_once_with(42)

    def test_timeout_does_not_force_by_default(self):
        self.poller.poll.return_value = []
        with self.assertRaisesRegex(kill.WriterError, 'SIGTERM sent'):
            kill.stop_writer(self.writer, Path('/example'))
        self.send.assert_called_once_with(42, signal.SIGTERM)

    def test_explicit_force_revalidates_and_waits(self):
        self.poller.poll.side_effect = [[], [(42, 1)]]
        self.assertEqual(kill.stop_writer(self.writer, Path('/example'), force=True), 'killed')
        self.assertEqual([c.args for c in self.send.call_args_list], [(42, signal.SIGTERM), (42, signal.SIGKILL)])
        self.assertEqual(self.inspect.call_count, 2)

    def test_force_refuses_changed_owner(self):
        self.poller.poll.return_value = []
        self.inspect.side_effect = [self.writer, kill.Writer('thread-one', 222, 123, 9999, (0, 1, 2))]
        with self.assertRaisesRegex(kill.WriterError, 'ownership changed'):
            kill.stop_writer(self.writer, Path('/example'), force=True)
        self.send.assert_called_once_with(42, signal.SIGTERM)

    def test_pidfd_race_and_permission_errors_close_handle(self):
        for error in (ProcessLookupError(), PermissionError()):
            self.send.side_effect = error
            with self.assertRaises(type(error)):
                kill.stop_writer(self.writer, Path('/example'))
        self.assertEqual(self.close.call_count, 2)

    def test_cli_stop_dispatch(self):
        with patch.object(kill, 'stop_writer', return_value='terminated') as stop, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(kill.main(['thread-one', '--force', '--timeout', '2']), 0)
            self.assertEqual(stop.call_args.args[2:4], (2, True))

    def test_acknowledgement_propagates_to_every_signal_check(self):
        self.poller.poll.side_effect = [[], [(42, 1)]]
        kill.stop_writer(self.writer, Path('/example'), force=True, also_stop=['thread-two'])
        self.assertEqual(self.inspect.call_count, 2)
        for call in self.inspect.call_args_list:
            self.assertEqual(call.kwargs['also_stop'], ['thread-two'])

    def test_new_shared_thread_prevents_signal(self):
        self.inspect.side_effect = kill.WriterError('shared server changed')
        with self.assertRaisesRegex(kill.WriterError, 'shared server changed'):
            kill.stop_writer(self.writer, Path('/example'), also_stop=['thread-two'])
        self.send.assert_not_called()
        self.close.assert_called_once_with(42)

    def test_cli_shared_acknowledgement_and_dry_run(self):
        self.inspect.return_value = kill.Writer('thread-one', 987654, 123, 5678, (0, 1, 2),
                                               ('thread-one', 'thread-two'))
        with patch.object(kill, 'stop_writer', return_value='terminated') as stop, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(kill.main(['thread-one', '--dry-run']), 0)
            stop.assert_not_called()
            self.assertIn('thread-two', output.getvalue())
            self.assertTrue(self.inspect.call_args.kwargs['inspect_only'])
            self.assertEqual(kill.main(['thread-one', '--also-stop', 'thread-two']), 0)
            self.assertEqual(stop.call_args.kwargs['also_stop'], ['thread-two'])
