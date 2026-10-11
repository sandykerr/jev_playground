"""Optional UI tests use synthetic text and actual prompt-toolkit key sequences."""
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import jev_terminal as terminal


class FallbackTests(unittest.TestCase):
    def test_editor_basic_and_missing_dependency(self):
        with patch.object(terminal, "PromptSession", None):
            editor = terminal.PromptEditor(input_fn=lambda _: "  draft  ")
            self.assertFalse(editor.enabled)
            self.assertEqual(editor.prompt(), "  draft  ")

    def test_missing_rich_and_output_modes(self):
        with patch.object(terminal, "Console", None):
            self.assertFalse(terminal.MarkdownReplies("always").enabled)
        with patch.object(terminal, "terminal_supported", return_value=False):
            self.assertFalse(terminal.MarkdownReplies().enabled)
        self.assertFalse(terminal.MarkdownReplies("never").enabled)


@unittest.skipUnless(terminal.PromptSession, "optional prompt-toolkit unavailable")
class EditorTests(unittest.TestCase):
    def setUp(self):
        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.output import DummyOutput
        from prompt_toolkit.application import create_app_session
        self.pipe = self.enterContext(create_pipe_input())
        self.enterContext(create_app_session(input=self.pipe, output=DummyOutput()))
        self.enterContext(patch.object(terminal.sys.stdin, "isatty", return_value=True))
        self.enterContext(patch.object(terminal, "terminal_supported", return_value=True))
        self.editor = terminal.PromptEditor()

    def read(self, keys):
        self.pipe.send_text(keys)
        return self.editor.prompt()

    def test_multiline_submit_and_whitespace(self):
        self.assertEqual(self.read("  first\rsecond  \x1b\r"), "  first\nsecond  ")

    def test_paste_does_not_submit(self):
        self.assertEqual(self.read("\x1b[200~one\ntwo\x1b[201~!\x1b\r"), "one\ntwo!")

    def test_arrows_home_end(self):
        self.assertEqual(self.read("ac\x1b[Db\x1b[C!\x1b[H>\x1b[F<\x1b\r"), ">abc!<")

    def test_up_down_edit(self):
        self.assertEqual(self.read("ab\rcd\x1b[A!\x1b[B?\x1b\r"), "ab!\ncd?")

    def test_multiline_history(self):
        self.assertEqual(self.read("one\rtwo\x1b\r"), "one\ntwo")
        self.assertEqual(self.read("\x10\x1b\r"), "one\ntwo")
        self.assertEqual(self.read("\x10\x0enew\x1b\r"), "new")

    def test_slash_commands(self):
        for command in ("/status", "/quit"):
            self.assertEqual(self.read(command + "\r"), command)

    def test_interrupt_and_eof(self):
        for key, error in (("\x03", KeyboardInterrupt), ("\x04", EOFError)):
            with self.assertRaises(error):
                self.read(key)


@unittest.skipUnless(terminal.Console, "optional Rich unavailable")
class MarkdownTests(unittest.TestCase):
    def renderer(self, tty=False, color="never"):
        output = io.StringIO()
        with patch.object(sys, "stdout", output):
            renderer = terminal.MarkdownReplies("always", color)
        renderer.console = terminal.Console(file=output, force_terminal=tty, width=65, height=6,
                                             color_system=None if color == "never" else "standard")
        return renderer, output

    def test_redirected_chunked_markdown_and_final_authority(self):
        renderer, output = self.renderer()
        renderer.delta("a", "**old")
        renderer.delta("a", " text**")
        self.assertEqual(output.getvalue(), "")
        renderer.complete("a", "# Final\n\n| Name | Value |\n|---|---|\n| test | 12 |\n\n- item\n\n```python\nx = 1\n```\n[link](https://example.com)")
        text = output.getvalue()
        for value in ("Final", "Name", "Value", "test", "item", "x = 1", "https://example.com"):
            self.assertIn(value, text)
        self.assertNotIn("old text", text)
        self.assertNotIn("\x1b", text)

    def test_buffered_missing_final_interruption_and_interleaving(self):
        renderer, output = self.renderer()
        renderer.delta("a", "**first")
        renderer.delta("b", "second")
        renderer.delta("a", "**")
        renderer.complete("b", None)
        renderer.close()
        renderer.close()
        self.assertEqual(output.getvalue().count("first"), 1)
        self.assertEqual(output.getvalue().count("second"), 1)
        self.assertFalse(renderer.buffers)

    def test_live_full_scrollback_and_stream_restoration(self):
        renderer, output = self.renderer(tty=True)
        stdout, stderr = sys.stdout, sys.stderr
        renderer.delta("a", "preview")
        live = renderer.live
        with patch.object(live, "update", wraps=live.update) as update, patch.object(terminal.time, "monotonic", return_value=renderer.last_refresh + 0.01):
            renderer.delta("a", " more")
            update.assert_not_called()
        renderer.complete("a", "\n\n".join(f"paragraph {n}" for n in range(30)))
        self.assertIs(sys.stdout, stdout)
        self.assertIs(sys.stderr, stderr)
        self.assertIsNone(renderer.live)
        self.assertIn("paragraph 29", output.getvalue())
        renderer.close()

    def test_color_environment(self):
        with patch.dict(os.environ, {"NO_COLOR": "1"}), patch.object(terminal, "terminal_supported", return_value=True):
            renderer = terminal.MarkdownReplies(color="auto")
            self.assertEqual(renderer.style, "none")
            self.assertIsNone(renderer.console.color_system)

    def test_explicit_empty_final_discards_preview(self):
        renderer, output = self.renderer()
        renderer.delta("a", "discard me")
        renderer.complete("a", "")
        renderer.close()
        self.assertEqual(output.getvalue(), "")
