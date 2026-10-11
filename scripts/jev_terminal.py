"""Optional terminal UI; no routing, account, or project dependencies."""
import os
import sys
import time

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.key_binding import KeyBindings
except ImportError:
    PromptSession = None

try:
    from rich.console import Console
    from rich.live import Live
    from rich.markdown import Markdown
except ImportError:
    Console = None


def terminal_supported():
    return sys.stdout.isatty() and os.getenv("TERM") != "dumb"


class PromptEditor:
    def __init__(self, input_fn=input):
        self.input_fn = input_fn
        self.enabled = bool(PromptSession and sys.stdin.isatty() and terminal_supported())
        self.session = None
        if self.enabled:
            bindings = KeyBindings()

            @bindings.add("enter")
            def enter(event):
                if event.current_buffer.text.strip() in ("/status", "/quit"):
                    event.current_buffer.validate_and_handle()
                else:
                    event.current_buffer.insert_text("\n")

            @bindings.add("c-p")
            def previous(event):
                event.current_buffer.history_backward()

            @bindings.add("c-n")
            def following(event):
                event.current_buffer.history_forward()

            self.session = PromptSession(multiline=True, history=InMemoryHistory(),
                                         prompt_continuation=" ... ", reserve_space_for_menu=0,
                                         key_bindings=bindings)
        else:
            try:
                import readline  # noqa: F401 -- improves input() where available
            except ImportError:
                pass

    def prompt(self):
        return self.session.prompt("\nyou> ") if self.enabled else self.input_fn("\nyou> ")


class MarkdownReplies:
    """One live preview, with complete replies retained in terminal scrollback.

    Callers supply sanitized text; originals remain in controller recovery state.
    Rendering stays serial because Rich owns shared terminal/cursor state.
    """

    def __init__(self, mode="auto", color="auto"):
        self.enabled = bool(Console and mode != "never" and (mode == "always" or terminal_supported()))
        self.buffers = {}
        self.live = None
        self.active = None
        self.last_refresh = None
        self.console = None
        self.style = "none"
        if self.enabled:
            styled = color == "always" or (color == "auto" and terminal_supported()
                                            and not os.getenv("NO_COLOR"))
            self.style = "blue" if styled else "none"
            self.console = Console(force_terminal=True if color == "always" else None,
                                   color_system="auto" if styled else None,
                                   no_color=not styled)

    def render(self, text):
        return Markdown(text, hyperlinks=False, style=self.style)

    def stop_preview(self):
        live, self.live = self.live, None
        self.active = None
        if live:
            live.stop()

    def delta(self, item_id, safe_text):
        if not self.enabled or not safe_text:
            return
        self.buffers[item_id] = self.buffers.get(item_id, "") + safe_text
        if not self.console.is_terminal:
            return
        now = time.monotonic()
        if self.active != item_id:
            self.stop_preview()
            self.active = item_id
            self.live = Live(self.render(self.buffers[item_id]), console=self.console,
                             auto_refresh=False, vertical_overflow="ellipsis", transient=True)
            self.live.start(refresh=True)
            self.last_refresh = now
        elif now - self.last_refresh >= 0.1:
            self.live.update(self.render(self.buffers[item_id]), refresh=True)
            self.last_refresh = now

    def complete(self, item_id, safe_text_or_none):
        if not self.enabled:
            return
        text = self.buffers.pop(item_id, "") if safe_text_or_none is None else safe_text_or_none
        self.buffers.pop(item_id, None)
        self.stop_preview()
        if text:
            self.console.print(self.render(text))

    def close(self):
        try:
            self.stop_preview()
        finally:
            for item_id in list(self.buffers):
                self.complete(item_id, None)


class WorkingNotice:
    """A single transient terminal line. All writes occur on the controller thread."""

    def __init__(self, stream=None):
        self.stream = stream if stream is not None else sys.stdout
        self.enabled = self.stream.isatty() and os.getenv("TERM") != "dumb"
        self.visible = False

    def show(self, text):
        if not self.enabled:
            return
        # Only fixed client text and elapsed seconds are passed here. Keep one row.
        import shutil
        width = shutil.get_terminal_size(fallback=(80, 24)).columns
        prefix = "" if self.visible else "\n"
        self.stream.write(prefix + "\r\x1b[2K" + text[:max(0, width - 1)])
        self.stream.flush()
        self.visible = True

    def clear(self):
        if self.visible:
            self.stream.write("\r\x1b[2K")
            self.stream.flush()
            self.visible = False
