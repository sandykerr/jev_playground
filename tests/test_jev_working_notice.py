import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import jev_terminal as terminal
import jev_codex as router


class WorkingNoticeTests(unittest.TestCase):
    def test_reuses_line_and_clears_without_ansi_when_redirected(self):
        stream = io.StringIO()
        stream.isatty = lambda: True
        with patch.dict(terminal.os.environ, {'TERM': 'xterm'}):
            notice = terminal.WorkingNotice(stream)
        notice.show('Codex is still working [90s]')
        notice.show('Codex is still working [91s]')
        self.assertEqual(stream.getvalue().count('\n'), 1)
        self.assertIn('\r\x1b[2KCodex is still working [91s]', stream.getvalue())
        notice.clear()
        self.assertFalse(notice.visible)
        redirected = io.StringIO()
        basic = terminal.WorkingNotice(redirected)
        basic.show('test')
        basic.clear()
        self.assertEqual(redirected.getvalue(), '')

    def test_idle_timer_updates_each_second_then_clears(self):
        notice = Mock(enabled=True)
        client = router.Controller(output=lambda *a, **k: None, working_notice=notice)
        client.thread_id = 't'
        client.mode = 'task'
        client.turn_started_at = 0
        client.rpc = Mock()
        now = [0]
        def pump():
            now[0] += 1
            if now[0] == 34:
                client.completed['turn'] = {'status': 'completed'}
        client.rpc.pump.side_effect = pump
        with patch.object(router.time, 'monotonic', side_effect=lambda: now[0]), patch.object(client, 'flush_notices'):
            client.wait_turn('turn')
        self.assertEqual([c.args[0] for c in notice.show.call_args_list],
                         [f'Codex is still working [{n}s]' for n in range(30, 34)])
        notice.clear.assert_called()

    def test_markdown_preview_yields_to_notice_and_delta_clears_it(self):
        notice = Mock(enabled=True)
        renderer = Mock()
        client = router.Controller(output=lambda *a, **k: None, renderer=renderer, working_notice=notice)
        client.thread_id = 't'
        client.mode = 'task'
        client.turn_started_at = 10
        with patch.object(router.time, 'monotonic', return_value=100):
            client.activity_status()
        renderer.stop_preview.assert_called_once()
        notice.show.assert_called_once_with('Codex is still working [90s]')
        client.event('item/agentMessage/delta', {'threadId': 't', 'itemId': 'a', 'delta': 'answer'})
        notice.clear.assert_called()
        renderer.delta.assert_called_once_with('a', 'answer')
        client.output('tool output')
        self.assertGreaterEqual(notice.clear.call_count, 2)

    def test_timeout_and_interrupt_clear_line(self):
        for error in (TimeoutError('timeout'), KeyboardInterrupt()):
            notice = Mock(enabled=True)
            client = router.Controller(output=lambda *a, **k: None, working_notice=notice)
            with patch.object(client, '_wait_turn', side_effect=error):
                with self.assertRaises(type(error)):
                    client.wait_turn('turn')
            self.assertEqual(notice.clear.call_count, 2)
