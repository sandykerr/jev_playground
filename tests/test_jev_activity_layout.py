"""User replies and literal tool transcripts have distinct presentation."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import jev_codex as router


class ActivityLayoutTests(unittest.TestCase):
    def test_literal_tool_markdown_stays_inside_gutter(self):
        item = {'type': 'commandExecution', 'id': 'c', 'command': 'cat notes.md',
                'status': 'completed', 'exitCode': 0}
        output = '# Heading\n```bash\nrm example\n```\n\n> quoted\n\x1b[2J'
        result = router.ActivityFormatter('never').render(item, True, output)
        self.assertTrue(all(line.startswith('> ') for line in result.splitlines()))
        self.assertIn('> [tool] Ran: cat notes.md', result)
        self.assertIn('> # Heading', result)
        self.assertIn('> \\u001b[2J', result)
        self.assertNotIn('\x1b', result)

    def test_compact_diff_and_full_diff_preserve_source(self):
        diff = '--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+new\n unchanged'
        item = {'type': 'fileChange', 'id': 'f', 'status': 'completed', 'changes': [
            {'path': 'a.py', 'kind': {'type': 'update'}, 'diff': diff}]}
        compact = router.ActivityFormatter('never').render(item, True)
        self.assertIn('Edited: a.py', compact)
        self.assertIn('Diff: +1/-1; 6 lines hidden', compact)
        self.assertNotIn('-old', compact)
        full = router.ActivityFormatter('never', 'full').render(item, True)
        self.assertIn('> -old\n> +new', full)
        self.assertNotIn('lines hidden', full)
        self.assertEqual(item['changes'][0]['diff'], diff)

    def test_long_commands_and_output_in_both_modes(self):
        command = 'python - <<\'PY\'\n' + 'x' * 300 + '\nPY'
        item = {'type': 'commandExecution', 'id': 'c', 'command': command, 'status': 'completed', 'exitCode': 2}
        output = '\n'.join(f'line {n}' for n in range(20))
        compact = router.ActivityFormatter('never').render(item, True, output)
        self.assertIn('…', compact)
        self.assertIn('+10 more lines hidden', compact)
        self.assertIn('exit 2', compact)
        full = router.ActivityFormatter('never', 'full').render(item, True, output)
        self.assertIn('x' * 300, full)
        self.assertIn('> line 19', full)
        self.assertNotIn('more lines hidden', full)

    def test_agent_markdown_remains_unquoted_and_complete(self):
        output = []
        client = router.Controller(output=lambda text, **kw: output.append(text), color='never')
        client.thread_id = 't'
        client.mode = 'task'
        message = 'Run this:\n\n```bash\npython example.py\n```\n' + '\n'.join(str(n) for n in range(30))
        client.event('item/completed', {'threadId': 't', 'item': {'id': 'answer', 'type': 'agentMessage', 'text': message}})
        self.assertEqual(output, [message])
        self.assertEqual(client.messages['answer']['text'], message)

    def test_declines_and_failures_remain_visible(self):
        item = {'type': 'commandExecution', 'id': 'c', 'command': 'false', 'status': 'declined'}
        text = router.ActivityFormatter('never').render(item, True)
        self.assertIn('> [tool] Declined: false', text)
        self.assertIn('c; declined', text)
