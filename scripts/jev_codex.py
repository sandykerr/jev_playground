#!/usr/bin/env python3
"""Interactive Jev controller for Codex App Server (optional terminal UI)."""
import argparse
from collections import deque
from datetime import datetime
import getpass
import json
import os
from pathlib import Path
import queue
import re
import signal
import shlex
import subprocess
import sys
import threading
import tempfile
import time

import jev_context as jev
import jev_compaction as compact_policy
import jev_handoff as handoffs
from jev_evidence import EvidenceStore
from jev_storage import migrate_context, relocated_handoff
from jev_terminal import MarkdownReplies, PromptEditor, WorkingNotice


class RpcError(RuntimeError):
    pass


class RpcRejected(RpcError):
    """The server explicitly rejected a request, rather than losing transport."""


class AppServer:
    """One stdio connection; service notifications/approvals while awaiting replies."""

    def __init__(self, command, cwd, on_event, on_request):
        self.events = queue.Queue()
        self.stderr = deque(maxlen=12)
        self.on_event, self.on_request = on_event, on_request
        self.next_id = 0
        self.replies = {}
        self.process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, encoding="utf-8", start_new_session=True)
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self):
        try:
            while True:
                line = self.process.stdout.readline(16 * 1024 * 1024)
                if not line:
                    break
                if not line.endswith("\n"):
                    raise ValueError("oversized or incomplete protocol message")
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError("protocol message is not an object")
                self.events.put(message)
        except (OSError, ValueError) as error:
            self.events.put(RpcError(f"Invalid App Server stream: {error}"))
        finally:
            self.events.put(RpcError("App Server closed the connection. Check Codex startup/configuration."))

    def _read_stderr(self):
        for line in self.process.stderr:
            self.stderr.append(line.rstrip())

    def send(self, message):
        try:
            self.process.stdin.write(json.dumps(message) + "\n")
            self.process.stdin.flush()
        except (OSError, ValueError) as error:
            raise RpcError("Cannot write to App Server") from error

    def pump(self, timeout=0.25):
        try:
            message = self.events.get(timeout=timeout)
        except queue.Empty:
            return
        if isinstance(message, Exception):
            raise message
        if "method" in message:
            if "id" in message:
                result = self.on_request(message["method"], message.get("params", {}))
                if result is None:
                    self.send({"id": message["id"], "error": {
                        "code": -32601, "message": "This client does not support that server request"}})
                else:
                    self.send({"id": message["id"], "result": result})
            else:
                self.on_event(message["method"], message.get("params", {}))
        elif "id" in message:
            self.replies[message["id"]] = message

    def drain(self):
        while not self.events.empty():
            self.pump(0)

    def submit(self, method, params):
        self.next_id += 1
        request_id = self.next_id
        self.send({"id": request_id, "method": method, "params": params})
        return request_id

    def call(self, method, params, timeout=30):
        request_id = self.submit(method, params)
        deadline = time.monotonic() + timeout
        while request_id not in self.replies:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"App Server did not acknowledge {method}")
            before = time.monotonic()
            self.pump()
            # Time spent answering a user prompt must not expire the RPC.
            deadline += max(0, time.monotonic() - before - 0.25)
        reply = self.replies.pop(request_id)
        if "error" in reply:
            raise RpcRejected(f"{method}: {reply['error'].get('message', 'request rejected')}")
        return reply.get("result", {})

    def close(self):
        if self.process.poll() is None:
            # Stop only the dedicated process group created by this launcher.
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()


def token_context(usage):
    """Use the last model call, never lifetime cumulative billed tokens."""
    if not isinstance(usage, dict):
        return {}
    last = usage.get("last")
    used = last.get("totalTokens") if isinstance(last, dict) else None
    window = usage.get("modelContextWindow")
    if type(used) is not int or used < 0:
        return {}
    result = {"used_tokens": used}
    if type(window) is int and window > 0:
        result["window_tokens"] = window
    return result


def pinned_documents(prompt, required, catalog=None):
    return sorted(jev.catalogs.pinned_documents(prompt, required, jev.CATALOG if catalog is None else catalog))


def reading_plan(result):
    documents = [{field: doc[field] for field in
                  ("id", "path", "action", "requested_action", "owns", "status", "sections", "requires", "superseded_by", "reason")}
                 for doc in result["documents"] if doc["action"] != "skip"]
    return (
        "[Controller-provided Jev reading plan; advisory data, not a replacement for the user's task.]\n"
        + json.dumps({"provider": result["provider"], "repository_root": result["repository_root"],
                      "workflows": result["workflows"], "documents": documents, "validation": result["validation"]})
        + "\nRead relevant sections of read documents; inspect means targeted headings/search, not full reads. "
        "Reuse current context. Explicitly requested sources and verification needs take precedence over skip. "
        "Read authority companions before treating historical plans as current state. Missing required sources "
        "are evidence gaps, not permission to invent their contents. Validation guidance does not execute or authorize jobs. "
        "This controller already consulted Jev: do not run jev_context.py again for this same task. "
        "The controller handles checkpoints and compaction between turns. Carry out the user's task normally. "
        "If work creates or changes detached HPC jobs, keep their IDs, evidence state and next actions in the "
        "registered experiment handoff. Conversation tool completion does not establish job completion."
    )


def display_text(value):
    """Keep activity text readable without executing terminal control characters."""
    return "".join(char if char.isprintable() or char in "\n\t"
                   else json.dumps(char)[1:-1] for char in str(value))


def command_description(item, brief=False):
    command = item.get("command") or "(command unavailable)"
    command = display_text(command)
    if brief:
        command = command.replace("\n", "\\n")
        if len(command) > 160:
            command = command[:157] + "…"
    else:
        command = command.replace("\n", "\n    ")
    label = f"Command [{display_text(item.get('id') or '?')}]"
    cwd = item.get("cwd")
    if cwd and not brief:
        label += f" (cwd: {display_text(cwd)})"
    return f"{label}: {command}"


QUIET_ITEM_TYPES = {"reasoning", "userMessage", "agentMessage", "hookPrompt",
                    "functionCallOutput", "plan"}
ACTIVITY_LABELS = {
    "fileChange": "File change", "mcpToolCall": "MCP tool", "dynamicToolCall": "Tool",
    "collabAgentToolCall": "Agent tool", "webSearch": "Web search", "imageView": "Image view",
    "imageGeneration": "Image generation", "sleep": "Sleep", "subAgentActivity": "Agent activity",
    "enteredReviewMode": "Review", "exitedReviewMode": "Review",
}


def activity_description(item, completed=False, brief=False):
    kind = item.get("type")
    if kind == "commandExecution" and not completed:
        return command_description(item, brief=brief)
    label = "Command" if kind == "commandExecution" else ACTIVITY_LABELS.get(kind, kind or "Activity")
    label = f"{label} [{item.get('id') or '?'}]"
    state = item.get("status") or ("finished" if completed else "started")
    if kind == "dynamicToolCall" and completed and item.get("success") is False:
        state = "failed"
    details = []
    if kind == "commandExecution":
        if item.get("exitCode") is not None:
            state += f" (exit {item['exitCode']})"
    elif kind == "fileChange":
        for change in item.get("changes") or []:
            change_kind = change.get("kind") or {}
            action = change_kind.get("type", "change")
            path = change.get("path") or "(path unavailable)"
            if change_kind.get("move_path"):
                path += f" -> {change_kind['move_path']}"
            details.append(f"{action}: {path}")
    elif kind in ("mcpToolCall", "dynamicToolCall", "collabAgentToolCall"):
        details.append("/".join(str(value) for value in
                       (item.get("server") or item.get("namespace"), item.get("tool")) if value)
                       or "(tool unavailable)")
        if item.get("receiverThreadIds"):
            details.append("agents: " + ", ".join(item["receiverThreadIds"]))
    elif kind == "webSearch":
        action = item.get("action") or {}
        if action.get("type") in ("openPage", "findInPage"):
            details.append(f"{action['type']}: {action.get('url') or '(URL unavailable)'}")
            if action.get("pattern"):
                details.append(f"find: {action['pattern']}")
        else:
            details.extend(action.get("queries") or [action.get("query") or item.get("query") or "(query unavailable)"])
    elif kind in ("imageView", "imageGeneration"):
        details.append(item.get("path") or item.get("savedPath") or "(path unavailable)")
    elif kind == "sleep" and item.get("durationMs") is not None:
        details.append(f"{item['durationMs']} ms")
    elif kind == "subAgentActivity":
        details.append(item.get("agentPath") or item.get("agentThreadId") or "(agent unavailable)")
    detail = display_text("; ".join(details)).replace("\n", "\\n")
    if brief and len(detail) > 160:
        detail = detail[:159] + "…"
    return display_text(f"{label}: {state}") + (f" — {detail}" if detail else "")


def weekly_limit_status(response):
    """Report the actual weekly account window, never context-token telemetry."""
    unavailable = "Weekly limit: unavailable"
    if not isinstance(response, dict):
        return unavailable + " (invalid response)"
    buckets = response.get("rateLimitsByLimitId")
    snapshot = buckets.get("codex") if isinstance(buckets, dict) else None
    if not snapshot:
        snapshot = response.get("rateLimits")
    if not isinstance(snapshot, dict):
        return unavailable + " (missing account limits)"
    for slot in ("primary", "secondary"):
        window = snapshot.get(slot)
        if not isinstance(window, dict) or window.get("windowDurationMins") != 10080:
            continue
        used = window.get("usedPercent")
        if type(used) is not int or used < 0:
            return unavailable + " (invalid weekly usage)"
        filled = min(20, (used + 2) // 5)
        result = f"Weekly limit: [{'█' * filled}{'░' * (20 - filled)}] {used}% used · {max(0, 100 - used)}% left"
        reset = window.get("resetsAt")
        if type(reset) is int:
            try:
                result += " · resets " + datetime.fromtimestamp(reset).astimezone().strftime("%Y-%m-%d %H:%M %Z")
            except (OverflowError, OSError, ValueError):
                pass
        return result
    return unavailable + " (weekly window not reported)"


class ActivityFormatter:
    """Terminal styling owned by the client; remote text is always escaped."""

    def __init__(self, color="auto", activity="compact"):
        self.activity = activity
        self.color = color == "always" or (
            color == "auto" and sys.stdout.isatty()
            and os.getenv("TERM") != "dumb" and not os.getenv("NO_COLOR"))

    def style(self, text, color=None, bold=False, dim=False):
        codes = (["2"] if dim else []) + (["1"] if bold else []) + ({"green": ["32"], "red": ["31"], "blue": ["34"]}.get(color, []))
        return f"\x1b[{';'.join(codes)}m{text}\x1b[0m" if self.color and codes else text

    def header(self, label, detail, color=None):
        return self.style(label, color, bold=True) + ": " + self.style(detail, color)

    def render(self, item, completed=False, command_output=None):
        # A blockquote gutter separates literal tool transcripts from agent Markdown.
        # Never parse command output as Markdown: headings/fences in files are data.
        body = self.render_body(item, completed, command_output)
        gutter = self.style("> ", dim=True)
        return "\n".join(gutter + line for line in ("[tool] " + body).split("\n"))

    def render_body(self, item, completed=False, command_output=None):
        kind = item.get("type")
        state = item.get("status") or ("finished" if completed else "started")
        failed = state in ("failed", "declined", "interrupted") or item.get("success") is False
        if kind == "commandExecution" and item.get("exitCode") not in (None, 0):
            failed = True
        success = completed and not failed and state == "completed"
        color = "red" if failed else "green" if success else None
        item_id = display_text(item.get("id") or "?")
        if kind == "commandExecution":
            command = display_text(item.get("command") or "(command unavailable)")
            if self.activity == "compact":
                command = command.replace("\n", "\\n")
                if len(command) > 160:
                    command = command[:157] + "…"
            else:
                command = command.replace("\n", "\n    ")
            label = "Declined" if state == "declined" else "Ran" if completed else "Running"
            lines = [self.header(label, command, color)]
            metadata = [item_id, display_text(state)]
            if item.get("exitCode") is not None:
                metadata[-1] += f" (exit {display_text(item['exitCode'])})"
            if item.get("cwd"):
                metadata.append("cwd: " + display_text(item["cwd"]))
            # Output remains neutral: a successful command can print error text or a diff.
            if completed:
                escaped = display_text(command_output) if command_output else "(no output)"
                output_lines = escaped.splitlines()
                if self.activity == "compact" and len(output_lines) > 10:
                    escaped = "\n".join(output_lines[:10]) + "\n" + self.style(
                        f"+{len(output_lines) - 10} more lines hidden", bold=True)
                lines.append(escaped)
            lines.append("  [" + "; ".join(metadata) + "]")
            return "\n".join(lines)
        if kind == "fileChange":
            blocks = []
            for change in item.get("changes") or []:
                change_kind = change.get("kind") or {}
                action = change_kind.get("type")
                path = display_text(change.get("path") or "(path unavailable)")
                if change_kind.get("move_path"):
                    path += " -> " + display_text(change_kind["move_path"])
                if success:
                    label = {"add": "Added", "delete": "Deleted", "update": "Edited"}.get(action, "Changed")
                    heading_color = "red" if action == "delete" else "green"
                else:
                    label = "File change " + state if completed else "Proposed " + (action or "change")
                    heading_color = color
                lines = [self.header(label, path, heading_color)]
                if completed:
                    diff = change.get("diff") or ""
                    diff_lines = diff.splitlines()
                    if diff and self.activity == "compact":
                        added = sum(line.startswith("+") and not line.startswith("+++") for line in diff_lines)
                        removed = sum(line.startswith("-") and not line.startswith("---") for line in diff_lines)
                        counts = f"+{added}/-{removed}; " if added or removed else ""
                        lines.append(self.style(
                            f"Diff: {counts}{len(diff_lines)} lines hidden (use --activity full)", dim=True))
                    for line in diff_lines if self.activity == "full" else []:
                        line_color = {"add": "green", "delete": "red"}.get(action)
                        if line.startswith(("--- ", "+++ ", "@@", " ")):
                            line_color = None
                        if line.startswith("+") and not line.startswith("+++ "):
                            line_color = "green"
                        elif line.startswith("-") and not line.startswith("--- "):
                            line_color = "red"
                        lines.append(self.style(display_text(line), line_color))
                    if not diff:
                        lines.append("(diff unavailable)")
                lines.append(f"  [{item_id}; {display_text(state)}]")
                blocks.append("\n".join(lines))
            return "\n".join(blocks) or self.header("File change", f"[{item_id}; {display_text(state)}]", color)
        return self.style(activity_description(item, completed=completed), color)


class Controller:
    def __init__(self, root=jev.ROOT, offline=False, required=(), auto_compact=False,
                 input_fn=input, output=print, turn_timeout=1800, pressure=None,
                 compact_cooldown=60, color="auto", catalog=None, workers=None, handoff=None, renderer=None, activity="compact", working_notice=None):
        self.root = Path(root).resolve()
        self.catalog = jev.CATALOG if catalog is None else catalog
        self.workers = workers
        jev.worker_count(workers)
        self.handoff_path = Path(handoff).resolve() if handoff else None
        self.saved_handoff = None
        self.evidence = None
        self.saved_evidence = None
        if self.handoff_path:
            handoffs.load(self.handoff_path)
        self.offline, self.required, self.auto_compact = offline, required, auto_compact
        self.input_fn, self.turn_timeout = input_fn, turn_timeout
        self.working_notice = working_notice if working_notice is not None else WorkingNotice()
        if working_notice is None and output is not print:
            self.working_notice.enabled = False
        self._output = output
        self.turn_started_at = None
        self.rpc = None
        self.thread_id = None
        self.active_turn = None
        self.mode = None
        self.usage = None
        self.completed = {}
        self.active_items = set()
        self.items = {}
        self.messages = {}
        self.streamed = set()
        self.compaction_seen = False
        self.last_checkpoint = None
        self.last_task = None
        self.last_turn_ok = False
        self.pressure = pressure or compact_policy.Pressure()
        self.compact_cooldown = compact_cooldown
        self.last_compact_at = None
        self.notice_pending = None
        self.notice_requests = {}
        self.steering_supported = True
        self.plan_counts = {}
        self.context_notices = []
        self.formatter = ActivityFormatter(color, activity)
        self.command_output = {}
        self.renderer = renderer
        self.last_agent_output_at = None
        self.reply_deltas = {}

    def output(self, *args, **kwargs):
        self.working_notice.clear()
        self._output(*args, **kwargs)

    def show_activity(self, item, completed=False):
        output = None
        if completed and item.get("type") == "commandExecution":
            chunks = self.command_output.pop(item.get("id"), [])
            output = item.get("aggregatedOutput")
            if output is None:
                output = "".join(chunks)
        self.output("\n" + self.formatter.render(item, completed, output), flush=True)

    def status(self, text):
        prefix = self.formatter.style("[router]", bold=True)
        self.output(f"\n{prefix} {text}", flush=True)

    def activity_status(self):
        elapsed = max(0, int(time.monotonic() - self.turn_started_at)) if self.turn_started_at is not None else 0
        label = f"Codex is still working [{elapsed}s]"
        if self.working_notice.enabled:
            if self.renderer:
                self.renderer.stop_preview()
            self.working_notice.show(label)
            return
        activities = [activity_description(item, brief=True) for item_id, item in self.items.items()
                      if item_id in self.active_items and item.get("type") not in QUIET_ITEM_TYPES]
        if activities:
            self.status(label + " on:\n  " + "\n  ".join(activities))
        else:
            self.status(label)

    def event(self, method, params):
        if params.get("threadId") != self.thread_id:
            return
        if self.evidence and self.mode == "task":
            self.evidence.event(method, params)
            if self.handoff_path and (method == "item/completed" or (
                    method == "item/started" and params.get("item", {}).get("type") == "contextCompaction")):
                self.evidence.handoff(handoffs.load(self.handoff_path))
        if method == "thread/tokenUsage/updated":
            self.usage = params.get("tokenUsage")
            if self.auto_compact and self.mode == "task":
                stage = self.pressure.advance(token_context(self.usage))
                if stage:
                    label = ("notice", "recommend", "request")[stage - 1]
                    self.status(f"Context {label}: {json.dumps(token_context(self.usage))}")
                    self.context_notices.append({"stage": label, "usage": token_context(self.usage)})
                    self.notice_pending = (stage, params.get("turnId"))
        elif method == "turn/plan/updated":
            self.plan_counts = {}
            steps = []
            for step in params.get("plan", []):
                status = step.get("status", "unknown")
                self.plan_counts[status] = self.plan_counts.get(status, 0) + 1
                steps.append(f"  {display_text(status)}: {display_text(step.get('step', ''))}")
            if steps:
                self.status("Plan updated:\n" + "\n".join(steps))
        elif method == "item/mcpToolCall/progress":
            item = self.items.get(params.get("itemId"), {})
            if params.get("itemId") in self.active_items and item.get("type") == "mcpToolCall":
                self.status(activity_description(item, brief=True) + " — " + display_text(params.get("message", "")))
        elif method == "item/fileChange/patchUpdated":
            item = self.items.get(params.get("itemId"), {})
            if params.get("itemId") in self.active_items and item.get("type") == "fileChange":
                item["changes"] = params.get("changes", [])
                self.show_activity(item)
        elif method == "item/commandExecution/outputDelta":
            item_id = params.get("itemId")
            if item_id in self.active_items and self.items.get(item_id, {}).get("type") == "commandExecution":
                self.command_output.setdefault(item_id, []).append(params.get("delta", ""))
        elif method == "turn/started":
            self.active_turn = params["turn"]["id"]
        elif method == "turn/completed":
            turn = params["turn"]
            self.completed[turn["id"]] = turn
            if self.mode == "task":
                self.finish_replies()
        elif method == "item/agentMessage/delta" and self.mode == "task":
            delta = params.get("delta", "")
            if delta:
                self.working_notice.clear()
                self.last_agent_output_at = time.monotonic()
                item_id = params["itemId"]
                self.streamed.add(item_id)
                self.reply_deltas[item_id] = self.reply_deltas.get(item_id, "") + delta
                if self.renderer:
                    self.renderer.delta(item_id, display_text(delta))
                else:
                    self.output(self.formatter.style(display_text(delta), "blue"), end="", flush=True)
        elif method in ("item/started", "item/completed"):
            item = params.get("item", {})
            item_id, kind = item.get("id"), item.get("type")
            if method == "item/completed":
                item = {**self.items.get(item_id, {}), **item}
            if kind == "contextCompaction":
                self.status("Context compaction: " + ("completed" if method == "item/completed" else "started"))
                if method == "item/completed":
                    self.compaction_seen = True
                    # Never act again on pre-compaction telemetry.
                    self.usage = None
                    self.pressure.reset()
                    self.notice_pending = None
                    self.last_compact_at = time.monotonic()
                return
            if method == "item/started":
                self.active_items.add(item_id)
                if kind not in QUIET_ITEM_TYPES:
                    self.show_activity(item)
            else:
                self.active_items.discard(item_id)
                if kind not in QUIET_ITEM_TYPES:
                    self.show_activity(item, completed=True)
                if kind == "agentMessage":
                    text = item.get("text")
                    buffered = self.reply_deltas.pop(item_id, "")
                    self.messages[item_id] = {"text": text if text is not None else buffered,
                                              "phase": item.get("phase")}
                    if self.mode == "task":
                        self.working_notice.clear()
                        if text and item_id not in self.streamed:
                            self.last_agent_output_at = time.monotonic()
                        if self.renderer:
                            self.renderer.complete(item_id, display_text(text) if text is not None else None)
                        elif item_id not in self.streamed:
                            self.output(self.formatter.style(display_text(text or ""), "blue"), flush=True)
            if kind not in ("reasoning", "userMessage", "agentMessage"):
                self.items[item_id] = {key: item[key] for key in
                                      ("id", "type", "status", "command", "cwd", "exitCode", "changes", "tool",
                                       "server", "namespace", "success", "receiverThreadIds", "query", "action",
                                       "path", "savedPath", "durationMs", "agentPath", "agentThreadId")
                                      if key in item}

    def _answer(self, prompt):
        try:
            return self.input_fn(prompt).strip()
        except EOFError:
            return ""

    def server_request(self, method, params):
        self.working_notice.clear()
        if params.get("threadId") not in (None, self.thread_id):
            return None
        if method in ("item/commandExecution/requestApproval", "item/fileChange/requestApproval"):
            detail = {key: params[key] for key in
                      ("reason", "command", "cwd", "grantRoot", "additionalPermissions", "networkApprovalContext")
                      if key in params}
            if method == "item/fileChange/requestApproval":
                detail["changes"] = self.items.get(params.get("itemId"), {}).get("changes", [])
            self.status("Codex requests approval: " + json.dumps(detail, indent=2))
            accept = self._answer("Approve this action once? [y/N] ").lower() == "y"
            available = params.get("availableDecisions")
            if accept and available is not None and "accept" not in available:
                self.status("One-time approval is not offered; declining.")
                accept = False
            return {"decision": "accept" if accept else "decline"}
        if method == "item/permissions/requestApproval":
            self.status("Codex requests permissions: " + json.dumps(params.get("permissions", {}), indent=2))
            self.status(params.get("reason", "No reason supplied"))
            accept = self._answer("Grant these permissions for this turn? [y/N] ").lower() == "y"
            return {"permissions": params.get("permissions", {}) if accept else {}, "scope": "turn"}
        if method in ("item/tool/requestUserInput", "tool/requestUserInput"):
            answers = {}
            for question in params.get("questions", []):
                self.status(question["question"])
                options = question.get("options") or []
                for i, option in enumerate(options, 1):
                    self.output(f"  {i}. {option['label']} — {option.get('description', '')}")
                if question.get("isSecret") and self.input_fn is input and sys.stdin.isatty():
                    value = getpass.getpass("Answer (hidden): ")
                else:
                    value = self._answer("Answer (number or text; blank to decline): ")
                if value.isdigit() and 1 <= int(value) <= len(options):
                    value = options[int(value) - 1]["label"]
                answers[question["id"]] = {"answers": [value] if value else []}
            return {"answers": answers}
        if method == "mcpServer/elicitation/request":
            self.status("MCP request: " + str(params.get("message", "")))
            self.status("This terminal client does not support MCP forms or URL authentication; declining.")
            return {"action": "decline", "content": None}
        self.status(f"Unsupported server request: {method}")
        return None

    def connect(self, command, resume=None, model=None, check=False):
        if not check:
            migrate_context(self.root)
            if self.handoff_path:
                self.handoff_path = relocated_handoff(self.handoff_path, self.root)
        self.rpc = AppServer(command, self.root, self.event, self.server_request)
        result = self.rpc.call("initialize", {"clientInfo": {
            "name": "jev_context_router", "title": "Jev context router", "version": "0.2.0"}})
        self.rpc.send({"method": "initialized", "params": {}})
        if check:
            return result
        # Omit sandbox/approval/base-instruction overrides: inherit Codex configuration.
        params = {"cwd": str(self.root)}
        if model:
            params["model"] = model
        if resume:
            params["threadId"] = resume
        result = self.rpc.call("thread/resume" if resume else "thread/start", params)
        self.thread_id = result["thread"]["id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", self.thread_id):
            raise RpcError("Unexpected thread ID format")
        if result["thread"].get("status", {}).get("type") == "active":
            raise RpcError("Thread is already active; use an idle thread with one controller")
        registration = self.root / "jev_routing" / "context" / "jev-router" / self.thread_id / "handoff.json"
        if resume and self.handoff_path is None and registration.is_file():
            with registration.open(encoding="utf-8") as stream:
                raw = stream.read(8193)
            if len(raw) > 8192:
                raise ValueError("handoff registration exceeds 8 KiB")
            saved = json.loads(raw)
            if (not isinstance(saved, dict) or set(saved) != {"path"}
                    or not isinstance(saved["path"], str) or not Path(saved["path"]).is_absolute()):
                raise ValueError("invalid experiment handoff registration")
            self.handoff_path = relocated_handoff(saved["path"], self.root)
        if self.handoff_path:
            handoffs.load(self.handoff_path)
            registration.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Private atomic registration lets --resume recover the same live handoff.
            fd, temporary = tempfile.mkstemp(dir=registration.parent)
            try:
                with os.fdopen(fd, "w") as output:
                    json.dump({"path": str(self.handoff_path)}, output)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, registration)
            finally:
                Path(temporary).unlink(missing_ok=True)
        self.evidence = EvidenceStore(self.root, self.thread_id, self.workers)
        self.status(f"Thread {self.thread_id}. Resume with --resume {self.thread_id}")
        self.status(f"Codex model: {result.get('model', 'configured default')}")
        return result

    def flush_notices(self):
        """Send guarded steering asynchronously, never start a new turn for a late notice."""
        for request_id in list(self.notice_requests):
            reply = self.rpc.replies.pop(request_id, None)
            if reply is not None:
                self.notice_requests.pop(request_id)
                if "error" in reply:
                    self.status("Context notice was not delivered; turn-end compaction remains available.")
                    if reply["error"].get("code") == -32601:
                        self.steering_supported = False
            elif time.monotonic() - self.notice_requests[request_id] > 30:
                self.notice_requests.pop(request_id)
                self.status("Context notice acknowledgement timed out; not retrying.")
        if not self.notice_pending:
            return
        stage, expected_turn = self.notice_pending
        self.notice_pending = None
        if (not self.auto_compact or not self.steering_supported or self.mode != "task"
                or not expected_turn or expected_turn != self.active_turn or expected_turn in self.completed):
            return
        messages = {
            1: "Context notice: usage crossed the notice threshold. Continue the user's task normally; "
               "avoid rereading already available sources.",
            2: "Context recommendation: prepare for possible compaction at the natural end of this turn. "
               "Preserve important decisions, source paths, verification outcomes, and open questions "
               "in your final response or a local handoff. Continue the user's task.",
            3: "Context request: the controller will request native compaction after this turn finishes "
               "successfully and its recovery record is saved. Preserve the objective, user constraints, "
               "adopted decisions, source paths, completed work, verification, and next steps. "
               "Do not abort running tools or mark unfinished work complete merely because of this request. "
               "Complete the user's task normally; the controller handles compaction.",
        }
        request_id = self.rpc.submit("turn/steer", {"threadId": self.thread_id,
            "expectedTurnId": expected_turn, "input": [{"type": "text", "text": messages[stage]}]})
        self.notice_requests[request_id] = time.monotonic()

    def wait_turn(self, turn_id=None, compact=False):
        self.working_notice.clear()
        if compact or self.turn_started_at is None:
            self.turn_started_at = time.monotonic()
        try:
            return self._wait_turn(turn_id, compact)
        finally:
            self.working_notice.clear()

    def _wait_turn(self, turn_id=None, compact=False):
        deadline = time.monotonic() + self.turn_timeout
        heartbeat = time.monotonic() + 30
        while True:
            target = turn_id or self.active_turn
            if target in self.completed:
                turn = self.completed.pop(target)
                self.active_turn = None
                if compact and (turn.get("status") != "completed" or not self.compaction_seen):
                    raise RpcError("Compaction did not finish successfully; stopping to preserve thread state")
                return turn
            if time.monotonic() >= deadline:
                raise TimeoutError("Codex turn timed out; restart with --resume after checking its status")
            if not compact and self.last_agent_output_at is not None:
                heartbeat = max(heartbeat, self.last_agent_output_at + 30)
            if time.monotonic() >= heartbeat:
                if compact:
                    elapsed = max(0, int(time.monotonic() - self.turn_started_at))
                    label = f"Waiting for Codex compaction [{elapsed}s]"
                    if self.working_notice.enabled:
                        self.working_notice.show(label)
                    else:
                        self.status(label)
                else:
                    self.activity_status()
                heartbeat = time.monotonic() + (1 if self.working_notice.enabled else 30)
            before = time.monotonic()
            self.rpc.pump()
            self.flush_notices()
            deadline += max(0, time.monotonic() - before - 0.25)

    def save_record(self, kind, record):
        directory = self.root / "jev_routing" / "context" / "jev-router" / self.thread_id
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = directory / f"{time.time_ns()}-{kind}.json"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as output:
            json.dump(record, output, indent=2)
            output.flush()
            os.fsync(output.fileno())
        return path

    def checkpoint(self, prompt, plan, turn):
        snapshot = handoffs.load(self.handoff_path) if self.handoff_path else None
        if self.evidence and snapshot:
            self.evidence.handoff(snapshot)
        record = {"thread_id": self.thread_id, "turn_id": turn["id"], "status": turn["status"],
                  "task": prompt, "agent_messages": list(self.messages.values()),
                  "actions": list(self.items.values()), "routing": plan, "token_usage": self.usage,
                  "previous_checkpoint": str(self.last_checkpoint) if self.last_checkpoint else None,
                  "context_notices": self.context_notices, "experiment_handoff": snapshot,
                  "evidence_recovery": self.evidence.reference() if self.evidence else None,
                  "note": "Local recovery record, not a model-written summary. Earlier records and native "
                          "Codex history retain prior decisions. Bounded command evidence is stored separately; reasoning is not copied."}
        path = self.save_record("turn", record)
        self.last_checkpoint = path
        self.saved_handoff = snapshot
        self.saved_evidence = record["evidence_recovery"]
        self.status(f"Checkpoint: {path.relative_to(self.root)}")

    def boundary_context(self):
        # Detached jobs may continue through compaction if their current handoff was saved.
        # A changed/missing/invalid file must never reuse a stale recovery snapshot.
        fresh = True
        if self.handoff_path:
            try:
                fresh = handoffs.load(self.handoff_path) == self.saved_handoff
            except (OSError, ValueError):
                fresh = False
        if self.evidence:
            try:
                fresh = fresh and bool(self.saved_evidence) and self.evidence.current_digest() == self.saved_evidence["sha256"]
            except (OSError, ValueError):
                fresh = False
        return {**token_context(self.usage), "at_boundary": self.last_turn_ok,
                "pending_actions": bool(self.active_turn or self.active_items),
                "handoff_saved": bool(self.last_checkpoint and self.last_checkpoint.is_file() and fresh)}

    def cooling_down(self):
        return self.last_compact_at is not None and time.monotonic() - self.last_compact_at < self.compact_cooldown

    def compact(self, decision, label):
        if not self.auto_compact or decision["action"] != "recommend_compact":
            return
        # Jev may take seconds. Process any queued native-compaction/usage events
        # and reapply code gates before acting on the earlier judgment.
        self.rpc.drain()
        fresh = compact_policy.decision(self.pressure, self.boundary_context(),
                                         decision.get("answer"), self.cooling_down())
        if fresh["action"] != "recommend_compact":
            decision.update(fresh)
            return
        self.status(f"Compacting {label}: " + decision["reason"])
        before = self.boundary_context()
        self.mode = "compact"
        self.active_turn = None
        self.compaction_seen = False
        try:
            self.rpc.call("thread/compact/start", {"threadId": self.thread_id})
        except RpcRejected as error:
            self.status(f"Compaction request rejected: {error}. Automatic compaction disabled for this run.")
            self.auto_compact = False
        else:
            self.wait_turn(compact=True)
            decision["executed"] = True
            self.status("Compaction completed.")
        self.save_record("compaction", {"thread_id": self.thread_id, "context_before": before,
                         "checkpoint": str(self.last_checkpoint), "decision": decision})

    def compact_at_turn_end(self, prompt, previous_task):
        context = self.boundary_context()
        stage = self.pressure.stage(context)
        if (not self.auto_compact or stage < 2 or not self.last_turn_ok
                or not context["handoff_saved"] or context["pending_actions"] or self.cooling_down()):
            return
        judgment = {"provider": "policy", "answer": None}
        if stage == 2:
            counts = {}
            for item in self.items.values():
                kind = item["type"]
                counts[kind] = counts.get(kind, 0) + 1
            payload = compact_policy.boundary_request(prompt, previous_task, context, counts, self.plan_counts)
            self.status("Asking Jev whether this turn boundary is a useful time to compact…")
            judgment = compact_policy.judge_boundary(payload, offline=self.offline)
        decision = compact_policy.decision(self.pressure, context, judgment["answer"])
        decision["judgment"] = judgment
        self.save_record("compaction-check", {"context": context, "decision": decision})
        self.compact(decision, "at turn end")

    def run_task(self, prompt):
        if not prompt.strip():
            return
        self.rpc.drain()
        state = self.boundary_context()
        required = pinned_documents(prompt, self.required, self.catalog)
        if len(prompt) > 2000:
            self.status("Jev receives only the first 2,000 characters; Codex receives your complete prompt.")
        payload = jev.build_request(prompt[:2000], state, required, previous_task=self.last_task, catalog=self.catalog)
        plan = jev.evaluate(payload, required, offline=self.offline, root=self.root,
                            catalog=self.catalog, workers=self.workers)
        self.status(f"Context route: {plan['provider']}" +
                    (f" ({plan['fallback_reason']})" if plan["fallback_reason"] else ""))
        for action in ("read", "inspect", "missing"):
            names = [doc["id"] for doc in plan["documents"] if doc["action"] == action]
            if names:
                self.status(f"{action}: {', '.join(names)}")
        decision = compact_policy.decision(self.pressure, state, plan["compaction_answer"], self.cooling_down())
        plan["compaction"] = decision
        self.compact(decision, "before the next task")
        self.mode = "task"
        self.last_turn_ok = False
        self.messages, self.items, self.streamed = {}, {}, set()
        self.plan_counts, self.context_notices = {}, []
        self.notice_pending = None
        self.active_items.clear()
        self.command_output.clear()
        self.reply_deltas.clear()
        self.last_agent_output_at = None
        snapshot = handoffs.load(self.handoff_path) if self.handoff_path else None
        recovery = ""
        if self.evidence:
            self.evidence.request(prompt)
            if snapshot:
                self.evidence.handoff(snapshot)
            recovery = self.evidence.prompt()
        inputs = [{"type": "text", "text": prompt}, {"type": "text", "text": reading_plan(plan) + recovery}]
        if snapshot:
            inputs.append({"type": "text", "text": handoffs.prompt(snapshot)})
        self.turn_started_at = time.monotonic()
        result = self.rpc.call("turn/start", {"threadId": self.thread_id, "input": inputs})
        self.active_turn = result["turn"]["id"]
        turn = self.wait_turn(self.active_turn)
        self.output("", flush=True)
        self.checkpoint(prompt, plan, turn)
        previous_task = self.last_task
        self.last_task = prompt[:2000]
        self.last_turn_ok = turn["status"] == "completed" and not self.active_items
        if turn["status"] != "completed":
            self.status(f"Turn ended: {turn['status']}. {turn.get('error') or ''}")
        self.compact_at_turn_end(prompt, previous_task)
        return turn

    def finish_replies(self):
        self.working_notice.clear()
        for item_id, text in self.reply_deltas.items():
            self.messages.setdefault(item_id, {"text": text, "phase": None})
        self.reply_deltas.clear()
        if self.renderer:
            self.renderer.close()

    def show_status(self):
        try:
            self.rpc.drain()
        except (RpcError, OSError, TimeoutError) as error:
            self.status("Event refresh unavailable: " + display_text(error))
        self.status(json.dumps({"thread": self.thread_id, "usage": token_context(self.usage),
                               "auto_compact": self.auto_compact}))
        try:
            response = self.rpc.call("account/rateLimits/read", {}, timeout=10)
            self.status(weekly_limit_status(response))
        except (RpcError, OSError, TimeoutError, ValueError) as error:
            self.status("Weekly limit: unavailable (" + display_text(error) + ")")

    def exit_details(self):
        self.finish_replies()
        if self.thread_id:
            command = shlex.join([sys.executable, str(Path(__file__).resolve()),
                                  "--repo-root", str(self.root), "--resume", self.thread_id])
            self.status(f"Thread: {display_text(self.thread_id)}\nResume: {display_text(command)}")

    def close(self):
        try:
            self.finish_replies()
        finally:
            try:
                if self.evidence:
                    self.evidence.flush()
            finally:
                if self.rpc:
                    self.rpc.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", help="Run one task and exit; omit for an interactive session")
    parser.add_argument("--prompt-file", type=Path, help="Read one complete task from a UTF-8 file")
    parser.add_argument("--resume", help="Resume an idle Codex thread by ID")
    parser.add_argument("--model", help="Optional Codex model override; defaults to your Codex settings")
    parser.add_argument("--codex", default="codex", help="Path to the Linux Codex executable")
    parser.add_argument("--color", choices=("auto", "always", "never"), default="auto",
                        help="Activity colors/bold: auto uses a terminal and respects NO_COLOR (default: auto)")
    parser.add_argument("--activity", choices=("compact", "full"), default="compact",
                        help="Tool blockquotes: compact previews and diff summaries, or full transcripts")
    parser.add_argument("--markdown", choices=("auto", "always", "never"), default="auto",
                        help="Render Markdown replies; auto uses supported terminals")
    parser.add_argument("--offline-jev", action="store_true", help="Local routing fallback; Codex still runs normally")
    compaction = parser.add_mutually_exclusive_group()
    compaction.add_argument("--auto-compact", action="store_true",
                            help="Opt into controller notices and compaction requests (default: disabled)")
    compaction.add_argument("--no-auto-compact", dest="auto_compact", action="store_false",
                            help="Explicitly retain the default: native Codex compaction only")
    parser.set_defaults(auto_compact=False)
    parser.add_argument("--compact-thresholds", default="50,65,85", help="Notice,recommend,request percentages (default: 50,65,85)")
    parser.add_argument("--compact-token-thresholds", help="Override percentages with absolute counts, e.g. 6000,10000,14000")
    parser.add_argument("--compact-cooldown", type=int, default=60, help="Minimum seconds between compactions (default: 60)")
    parser.add_argument("--require", action="append", default=[], help="Catalog source ID to pin")
    parser.add_argument("--repo-root", type=Path, default=jev.ROOT)
    parser.add_argument("--catalog", type=Path, default=jev.catalogs.DEFAULT_CATALOG)
    parser.add_argument("--workers", type=int, help="Metadata workers; default SLURM_CPUS_PER_TASK or 1")
    parser.add_argument("--handoff", type=Path, help="Validated local experiment state; reloaded each turn, never sent to Jev")
    parser.add_argument("--turn-timeout", type=int, default=1800, help="Seconds per turn (default: 1800)")
    parser.add_argument("--check", action="store_true", help="Check App Server handshake and key presence; no model calls")
    args = parser.parse_args()
    if args.prompt is not None and args.prompt_file:
        parser.error("choose --prompt or --prompt-file")
    if args.turn_timeout < 1:
        parser.error("--turn-timeout must be positive")
    try:
        catalog = jev.catalogs.load_catalog(args.catalog)
        jev.worker_count(args.workers)
        pinned_documents("", args.require, catalog)
        if not args.repo_root.is_dir():
            raise ValueError("repository root must be an existing directory")
        if args.handoff:
            handoffs.load(args.handoff)
        percentages = compact_policy.thresholds(args.compact_thresholds)
        if percentages[-1] > 100 or args.compact_cooldown < 0:
            raise ValueError("percentages must be <=100 and cooldown must be nonnegative")
        tokens = compact_policy.thresholds(args.compact_token_thresholds) if args.compact_token_thresholds else None
    except (OSError, ValueError) as error:
        parser.error(str(error))
    renderer = MarkdownReplies(args.markdown, args.color)
    controller = Controller(renderer=renderer if renderer.enabled else None, root=args.repo_root, catalog=catalog, workers=args.workers, handoff=args.handoff,
                            offline=args.offline_jev, required=args.require,
                            auto_compact=args.auto_compact, turn_timeout=args.turn_timeout,
                            color=args.color, activity=args.activity,
                            pressure=compact_policy.Pressure(percentages, tokens), compact_cooldown=args.compact_cooldown)
    try:
        configured = bool(os.getenv("JEV_API_KEY") or os.getenv("TYPESAFE_API_KEY"))
        controller.status("Jev key configured." if configured else "No Jev key; using local inspection fallback.")
        result = controller.connect([args.codex, "app-server", "--listen", "stdio://"],
                                    resume=args.resume, model=args.model, check=args.check)
        if args.check:
            controller.status("App Server handshake succeeded: " + str(result.get("userAgent", "connected")))
            return 0
        prompt = args.prompt_file.read_text() if args.prompt_file else args.prompt
        if prompt is not None:
            turn = controller.run_task(prompt)
            return 0 if turn and turn["status"] == "completed" else 1
        editor = PromptEditor()
        controller.status("Enter a task. /status shows usage; /quit exits. Ctrl+C stops the launcher.")
        if editor.enabled:
            controller.status("Enter inserts a line; Alt+Enter (or Esc then Enter) submits. Ctrl+P/N recalls history.")
        while True:
            try:
                prompt = editor.prompt()
            except EOFError:
                break
            if prompt.strip() == "/quit":
                break
            if prompt.strip() == "/status":
                controller.show_status()
                continue
            controller.run_task(prompt)
        controller.exit_details()
        return 0
    except KeyboardInterrupt:
        controller.exit_details()
        return 130
    except (OSError, RpcError, TimeoutError, ValueError) as error:
        controller.finish_replies()
        controller.status(display_text(error))
        if controller.rpc and controller.rpc.process.poll() is not None:
            for line in controller.rpc.stderr:
                print(line, file=sys.stderr)
        return 1
    finally:
        controller.close()


if __name__ == "__main__":
    sys.exit(main())
