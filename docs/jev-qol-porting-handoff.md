# Jev Codex terminal quality of life porting handoff

Port these interface improvements into another repository that uses the same Python Jev router and Codex App Server controller. The destination can have a completely different document catalog. These changes operate on terminal input, App Server events, and display formatting; they do not depend on the subject matter of the routed files.

This handoff describes the source working tree, including changes that may not be committed. Use the actual files or the implementation contracts below rather than assuming a particular commit contains the work. The destination agent should inspect its own instructions and controller before editing.

## Scope and adopted defaults

| Feature | Behavior to port |
|---|---|
| Prompt editor | Multiline drafts, arrow keys, Home/End, bracketed paste, in-memory prompt history |
| Submission | Enter inserts a line; Alt+Enter or Esc then Enter submits; `/status` and `/quit` also accept Enter |
| Replies | Streaming Markdown with headings, emphasis, lists, tables, links, and highlighted code blocks |
| Activity display | Named commands and tools, readable file changes, status and exit codes, terminal colors |
| Command output | First **10 logical lines**, followed by a **bold** `+X more lines hidden` when needed |
| Heartbeat | At least **30 seconds without agent text** before “Codex is still working…” |
| Exit | Ctrl+C and `/quit` print the thread ID and a complete resume command |
| Status | Thread, context usage, auto-compaction setting, live weekly account usage bar and reset time |
| Routing policy | Skip requires both probability and confidence **at least 75%**; read remains **65%** |
| Dependencies | `prompt-toolkit>=3.0.52,<4` and `rich>=13.9,<15`, with basic-mode fallbacks |

The routing threshold is a separate policy change, included because it was adopted alongside the UI improvements. It can be ported independently of the terminal features. It is a chosen default, not a benchmarked optimum for every repository.

## Source map

Paths below are relative to the source repository. Map them to the destination's equivalents; the names are not requirements.

| Source | Reusable pieces |
|---|---|
| [scripts/jev_terminal.py](../scripts/jev_terminal.py) | `PromptEditor`, `MarkdownReplies`; no project catalog imports |
| [scripts/jev_codex.py](../scripts/jev_codex.py) | `display_text`, `ActivityFormatter`, `weekly_limit_status`, controller event handling, heartbeat, CLI wiring and cleanup |
| [scripts/jev_context.py](../scripts/jev_context.py) | `choice` probability validation and threshold change only |
| [requirements-jev.txt](../requirements-jev.txt) | Optional UI dependency ranges |
| [tests/test_jev_terminal.py](../tests/test_jev_terminal.py) | Actual input-key sequences, Markdown rendering, interrupted output and fallbacks |
| [tests/test_jev_codex.py](../tests/test_jev_codex.py) | Exit, status, heartbeat, truncation, formatting and App Server integration tests |
| [tests/fake_codex_app_server.py](../tests/fake_codex_app_server.py) | Deterministic protocol peer, including rate-limit responses and rejection |
| [tests/test_jev_context.py](../tests/test_jev_context.py) | Routing validation and probability boundary tests |
| [docs/jev-context.md](jev-context.md) | Source user-facing controls and operational documentation |

If source files are accessible, copy the self-contained terminal module and adapt the controller methods. Avoid replacing the destination controller or router wholesale: either may contain project-specific behavior. If only this handoff is available, implement the contracts below using the named libraries and equivalent event handlers.

## Preserve the destination routing infrastructure

Keep the destination's document IDs, paths, catalog descriptions, project root, required-document pins, local instructions, and source-authority rules. Do not import this source repository's catalog or content.

Keep the existing approval and sandbox behavior, authentication, checkpoint format, thread filtering, timeouts, and compaction policy unless a particular UI change below requires a display hook. In particular:

- A router recommendation remains advisory. `inspect` means targeted headings/search, not automatically reading the first N lines or every listed document.
- Jev receives catalog metadata and bounded task/context information, not the document bodies. The source controller caps the current task text sent to Jev at 2,000 characters; Codex receives the complete prompt. Preserve the destination's existing privacy and routing contract.
- Display truncation changes terminal presentation only. It must not shorten the command result sent to Codex, alter a command, or change the model's answer stored in recovery records.
- Never infer weekly account usage from context-token counts, or infer a context-window size when telemetry is absent.

## Recommended implementation order

1. Map the destination's launcher, controller, RPC client, router, tests, and dependency mechanism. Record its existing behavior and run its baseline checks.
2. Add the UI dependencies using the destination's normal environment setup. Add the terminal module with optional imports so noninteractive/basic operation still works without those dependencies.
3. Wire the prompt editor and Markdown lifecycle into the controller, including interruption and error cleanup.
4. Port command formatting, the 10-line display cap, idle heartbeat timing, and exit resume information.
5. Add `/status` account-limit reads after checking the installed Codex protocol schema.
6. Apply the 75% skip rule if porting the complete adopted defaults. Preserve the destination catalog and validation logic.
7. Adapt the focused tests, run the destination regression suite, perform a real-terminal smoke test, and document the new controls. Restart the launcher before evaluating its new behavior.

## Multiline prompt editing

Create one `prompt_toolkit.PromptSession` for the interactive session, not one per prompt. Configure `multiline=True`, `InMemoryHistory()`, a continuation prompt such as ` ... `, and `reserve_space_for_menu=0`.

Bind Enter to insert `\n`, except when the entire stripped buffer is exactly `/status` or `/quit`; those commands should call `event.current_buffer.validate_and_handle()`. Retain prompt-toolkit's default multiline submission binding, Alt+Enter / Escape followed by Enter. Bind Ctrl+P to `history_backward()` and Ctrl+N to `history_forward()`. Default editor bindings supply arrow-key navigation and Home/End.

Keep the history in memory. Reuse the session so a multiline draft is recalled as one prompt. Bracketed paste should insert the complete pasted text without submitting it. Do not call `.strip()` on the prompt passed to the model; use stripping only to recognize launcher commands or empty input.

Enable the enhanced editor only when stdin and stdout are terminals, `TERM` is not `dumb`, and prompt-toolkit is installed. Otherwise use `input()`; importing `readline` where available improves this fallback. Preserve `--prompt` and `--prompt-file` batch paths without creating an interactive editor.

Ctrl+C still propagates `KeyboardInterrupt` to the launcher's existing exit handler. Ctrl+D on an empty draft raises `EOFError`. This source does not add persistent history, an output pager, or editing during an active model turn. Approval and tool-question prompts retain their existing input path.

Reference: [prompt-toolkit prompts and sessions](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/asking_for_input.html).

## Streaming Markdown rendering

Use Rich's `Console`, `Markdown`, and `Live`. A small renderer object should expose:

```python
renderer.enabled
renderer.delta(item_id, safe_text)
renderer.complete(item_id, safe_text_or_none)
renderer.close()
```

Maintain text buffers keyed by message item ID and at most one active live display. Parse/render accumulated text, not individual tokens: Markdown delimiters, table rows, and code fences commonly span delta boundaries.

Use `Live(..., auto_refresh=False, vertical_overflow="ellipsis")`. Start the preview on the first nonempty delta. Limit subsequent parsing and redraws to roughly once per 0.1 seconds, using `time.monotonic()`. Always render the complete final text on completion and stop the live display. Rich then leaves the full answer in scrollback, including content outside the live preview's height.

Use `Markdown(text, hyperlinks=False)` to retain readable links without terminal hyperlink escapes. The source uses blue prose when colors are enabled, with Markdown emphasis and syntax highlighting. Raw reply text remains in recovery records.

### Controller event wiring

| Event or lifecycle point | Required action |
|---|---|
| Initialization | Create the renderer once; inject it into the controller only if enabled. Keep a `None` path for plain output and existing controller tests. |
| Agent delta in the active task | Update the agent-output timestamp for nonempty text. Escape remote control characters, then call `delta(itemId, text)`. Do not also print the raw delta. |
| Agent item completion | Store the original reply in recovery state. Pass the complete sanitized `text` to `complete`; pass `None` if the field is absent so buffered deltas are used. |
| No Markdown renderer | Preserve raw streaming. Track streamed IDs so a completed reply is not printed a second time. |
| Turn completion | Flush/close remaining renderer buffers, including replies that lack an item-completed notification. |
| Ctrl+C or error | Close the renderer before printing exit/error information so cursor state and redirected streams are restored. |
| Controller cleanup | Close the renderer and put RPC cleanup in `finally`, so rendering cleanup cannot prevent server cleanup. |

Keep the existing active-thread filter before processing thread-scoped events. Do not render compaction's internal messages as task replies. Empty deltas must not reset the heartbeat.

Add `--markdown auto|always|never`, default `auto`. In auto mode, render in a supported terminal and retain raw streaming Markdown when redirected. `never` uses the original raw-text path. `always` renders redirected replies once complete when the console is noninteractive. The source's explicit `--color always` can force terminal output; avoid combining it with redirection unless ANSI output is intended.

Make missing Rich an optional-dependency fallback. `--color never` suppresses styling while retaining Markdown layout; live terminal cursor controls can still be used for redraw. Respect `NO_COLOR` in auto color mode. Rich Live handles ordinary stdout/stderr output above its preview, so router/tool messages should use that coordinated output path instead of writing raw cursor-control sequences.

References: [Rich Markdown](https://rich.readthedocs.io/en/stable/markdown.html), [Rich Live display](https://rich.readthedocs.io/en/latest/live.html).

## Command and activity formatting

Display a command immediately when it starts, with its item ID and working directory if reported. On completion show the command, its output, status, and exit code. Treat nonzero exit codes as failures even if the protocol status is `completed`.

Prefer the completion item's `aggregatedOutput` when it is not `None`; otherwise join buffered `item/commandExecution/outputDelta` chunks for that command ID. An explicitly empty aggregated output is authoritative. Buffer overlapping commands separately and clear buffers after completion and at new task boundaries. Do not print both deltas and the aggregate.

Apply the line cap after escaping remote control characters and after joining all chunks. Preserve text unchanged when it is at most 10 lines. Otherwise:

```python
output_lines = escaped_output.splitlines()
hidden = len(output_lines) - 10
if hidden > 0:
    visible = "\n".join(output_lines[:10])
    visible += "\n" + style(f"+{hidden} more lines hidden", bold=True)
else:
    visible = escaped_output
```

Count blank lines. Do not count a single terminating newline as an extra output line. Keep the command header and status metadata outside the 10-line cap. Empty output displays `(no output)`. The hidden-lines marker is bold only when terminal styling is enabled.

This is a logical-line cap, not a terminal-row or byte cap. A very long line can still wrap. It does not truncate code in an agent reply or file-change diffs, and it does not bound the memory used to buffer command output.

The source also displays file additions, edits, deletions, moves, and completed diffs; tool names and tool-progress notifications; and active-item descriptions in heartbeat messages. Preserve its distinction between proposed actions and completed actions. Do not expose tool argument/result payloads or reasoning merely to improve activity labels.

Use green successful-action headings, red failure/decline and deletion headings, green added diff lines, red removed diff lines, and neutral diff context/header lines. Command output itself remains neutral: a successful command can print an error example or a diff. Support `--color auto|always|never` and reset every emitted style.

The source `display_text` preserves printable characters, tabs, and newlines, and visibly escapes other remote characters. Apply this before terminal formatting; only the client's renderer should generate active terminal styling.

## Idle heartbeat instead of periodic interruption

Store `last_agent_output_at`, initially `None`. Set it to `time.monotonic()` when a nonempty agent delta is received for the active task, or when a complete nonempty unstreamed reply is displayed.

Keep the existing wait-loop timeout and RPC pumping. Before its heartbeat check, defer the ordinary task heartbeat:

```python
heartbeat = time.monotonic() + 30  # Initialize once before the wait loop.
# Inside the loop, before deciding whether to print:
if not compact and last_agent_output_at is not None:
    heartbeat = max(heartbeat, last_agent_output_at + 30)
```

After a heartbeat is emitted, schedule the next one 30 seconds later. Continuous reply streaming therefore suppresses the message, while a stalled stream eventually produces a liveness notice. Keep the separate “Waiting for Codex compaction…” behavior.

This timing measures agent-text activity, not all command output or all protocol events. Do not extend the actual task timeout merely because a delta arrived. Ignore empty deltas and events for other threads when updating this timestamp.

## Resume details on exit

For both Ctrl+C and `/quit`, print the current thread ID and a complete command invoking the destination launcher with `--resume THREAD_ID`. Print only a known thread ID; an interruption before thread creation must not produce a command containing `None`.

Keep Ctrl+C's exit status `130` and `/quit`'s normal status `0`. Close the Markdown renderer before printing the footer, and always close the dedicated App Server process in the final cleanup path. Preserve the existing process-group isolation rather than terminating unrelated Codex sessions.

Adapt the command to the destination launcher and normal interpreter. The source prints a repo-relative `python3 scripts/jev_codex.py --resume ...`; it assumes the user runs it from the repository root and does not preserve custom CLI flags. A destination using a virtual environment or wrapper should print that entrypoint and shell-quote paths when necessary. EOF exits normally in the source but does not currently print the same footer.

## Account usage in status

Make `/status` call a dedicated method without starting a model turn or a new Jev routing request. Drain queued events, then show the thread ID, latest context-token usage, and auto-compaction setting. Fetch account usage on demand:

```python
response = rpc.call("account/rateLimits/read", {}, timeout=10)
```

Prefer `response["rateLimitsByLimitId"]["codex"]` when populated, falling back to `response["rateLimits"]`. Inspect both `primary` and `secondary` and select the window whose `windowDurationMins` equals `10080`. Do not assume `secondary` always means weekly or mistake the five-hour window for a week.

Read `usedPercent`, requiring a nonnegative integer and rejecting booleans. Build a 20-character bar representing **usage**, with filled `█` and empty `░` cells:

```python
remaining = max(0, 100 - used)
filled = min(20, (used + 2) // 5)
bar = "█" * filled + "░" * (20 - filled)
```

Show both `% used` and `% left` so the bar's direction is explicit. For example, `35% used · 65% left`. Convert a valid `resetsAt` Unix timestamp to local time with `datetime.fromtimestamp(...).astimezone()`. Invalid or missing reset times should omit only the reset annotation.

Missing/invalid weekly data, unsupported methods, timeouts, or RPC/OS errors should display `Weekly limit: unavailable` with a useful reason. Do not invent zero usage or terminate the interactive session just because a status read fails. Preserve token-context details even when account limits are unavailable.

Verify this API against the destination's installed Codex rather than assuming all installations expose the same schema:

```bash
codex app-server generate-json-schema --out /path/to/temporary-schema-directory
```

Inspect `GetAccountRateLimitsResponse`, `RateLimitSnapshot`, and `RateLimitWindow`. This feature only reads usage; it must not redeem reset credits, change plans, or change authentication.

## Routing threshold change

In the router's answer-selection function, change the skip floor from `0.90` to `0.75`, while retaining `0.65` for read:

```python
floor = 0.75 if selected == "skip" else 0.65
return selected if confidence >= floor and probabilities[selected] >= floor else "inspect"
```

Keep validation before this step: expected answer type and choice, complete probability keys, finite values in `[0, 1]`, a sum near one, and the selected choice having maximal probability. Missing, malformed, or insufficiently confident answers still become `inspect`; explicit required-document pins still force `read`.

These floors apply to both confidence and the selected-option probability. A 90% skip probability with 70% confidence still yields `inspect`. Do not add a new CLI setting unless the destination needs configurability; in this source the floor is a code default. Numeric probabilities remain in routing/checkpoint data, not the short terminal list or the reading-plan categories sent to Codex.

## Verification and acceptance

The source's last implementation run passed **91 automated Jev tests**. Separate PTY checks exercised actual multiline editing, submission, Markdown tables/code, and terminal restoration. Tests and a live read also verified the weekly account endpoint. These are source results, not evidence that a destination port is correct.

Install the optional dependencies before testing; otherwise the editor/Markdown test classes can skip. The source was exercised with Python 3.14, prompt-toolkit 3.0.53, and Rich 13.9.4. The code targets Python 3.10+; validate the destination's Python and terminal as well.

```bash
python3 -m pip install -r requirements-jev.txt
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_jev*.py'
git diff --check
```

Use the destination's package manager/virtual environment instead if appropriate. Subprocess integration tests need writable temporary directories but no real model or Jev calls. Retain existing compaction and approval regression coverage.

| Area | Required checks |
|---|---|
| Editing | Enter inserts a line; Alt+Enter submits; left/right/up/down and Home/End edit correctly; bracketed paste remains one draft; history recalls multiline text; Ctrl+C/Ctrl+D and slash commands retain their meanings |
| Markdown | Delimiters split across chunks; tables/lists/fenced code; reply longer than terminal height; authoritative final text; unstreamed replies; partial output on interruption; no duplicate final reply; no active remote control sequences; cursor/streams restored |
| Output modes | Terminal auto mode, redirected output, `--markdown never`, `--markdown always`, `--color never`, `NO_COLOR`, missing optional packages |
| Truncation | 9, 10, and 11 lines; larger output; final newline present/absent; blank lines; chunk boundaries inside lines; overlapping commands; aggregate takes precedence; hidden count exact; bold marker; exit metadata remains visible |
| Heartbeat | Stream for more than 30 seconds without a heartbeat; stop streaming and get one after 30 seconds of silence; empty/foreign-thread events do not postpone it; compaction and task timeout still work |
| Exit | Ctrl+C at prompt and during a task; `/quit`; interruption before thread creation; usable resume command; server cleanup |
| Status | Weekly window in either slot; multi-bucket vs legacy data; 0%, 100%, over-limit values; absent/malformed limits; timeout/rejection followed by another task; no new model turn |
| Routing | Both skip values exactly 0.75; either just below 0.75; read threshold unchanged; malformed responses fall back; required files stay pinned |

Perform a real-terminal smoke test after the automated suite: enter and edit a multiline prompt, paste another, recall it from history, request a reply containing a Markdown table and code fence, run `cat` on a nonsecret file longer than 10 lines, invoke `/status`, and exit/resume. Check both ordinary terminal scrollback and redirected output. Do not rely on captured ANSI strings alone to judge the live interface.

## Task to give the destination agent

> Port the Jev/Codex quality of life changes in this handoff into this repository's existing routing controller. First map the local equivalents of the launcher, event handlers, router, tests, and dependencies. Preserve this repository's catalog, instructions, approval/sandbox behavior, and compaction semantics. Implement multiline prompt editing, streaming Markdown, readable activity formatting, 10-line command-output truncation with a bold hidden count, idle-aware heartbeat timing, exit resume details, and weekly account status. Apply the 75% skip default while retaining the 65% read threshold. Add/adapt meaningful tests, run the existing regression suite, and verify the terminal behavior. Finish with the changed files, test results, any remaining limitations, and the restart/usage instructions. Do not claim the source repository's test results as validation of this port.
