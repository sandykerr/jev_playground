# LECOSPy context routing and experiment handoffs

The router selects useful repository sources and preserves source ownership,
historical caveats and workflow boundaries. It does not read document bodies,
certify experiment results, schedule jobs or authorize changes to frozen data.
Python 3.10+ and the standard library are sufficient for routing and basic terminal
operation. Optional Python UI dependencies enable editing and Markdown; the imported Node package
and workout documents are not used by the active integration.

## Start with advisory routing

From the LECOSPy repository root:

```bash
python3 jev_routing/scripts/jev_context.py \
  --task 'Compare Peter checkpoints for CHM with head-only versus staged fine-tuning' \
  --offline

python3 jev_routing/scripts/jev_context.py \
  --task 'Resume world-model pretraining after the DDP failure' \
  --require wm_handoff --offline
```

Output is JSON with matched workflows, `read`/`inspect`/`skip` sources, authority
metadata, reasons, required companions and validation guidance. Missing sources
have `action: missing` and retain their `requested_action`. Source existence is
not evidence that its contents or reported results are correct.

Use the route once per materially changed task or evidence gap. Read relevant
sections; `inspect` means headings or targeted search, not loading everything.
Explicit file requests, applicable instructions and verification needs override
advisory skips. Single explicit reads and self-contained tasks need no router.

The default root is the checkout containing `jev_routing/`, regardless of shell
working directory. `--repo-root /path/to/lecospy` changes both source checks and
controller working directory. `--catalog /path/to/catalog.json` selects another
validated catalog. Explicit CLI paths such as catalog, context and handoff files
are resolved relative to the caller's working directory. Catalog source paths
are always repository-relative; traversal and symlink escape are rejected.

## Catalog and authority

`jev_routing/catalog.json` defines five overlapping workflows:

- `foundation_model`: existing AE + ViT checkpoint/task adaptation experiments.
- `world_model`: masked pretraining, normalization, architecture and GPU gates.
- `geography`: site selection, reservations, frozen splits and overlap exclusions.
- `tiling`: candidate validity, raster alignment, materialization and publication.
- `routing`: this integration and its evaluations.

Each document declares `path`, `description`, `owns`, `status`, `workflows`,
`keywords`, `sections`, `requires`, `superseded_by`, `always` and `entrypoint`.
`status` is `instructions`, `current`, `mixed` or `historical`; it describes source
role, not independent verification. `superseded_by` points to current companions,
without preventing a requested historical read. For a mixed document, consult
its ownership/section caveats rather than treating the entire document as stale.

Update the catalog when files move or authority changes. Do not copy current job
IDs, dataset pins or run results into it. Existing owning handoffs and trackers
remain authoritative for those details. Root instructions and local/HPC policy
are always read. Explicit sources and matched workflow entry points cannot be
skipped by Jev. Required/current companions are expanded to a fixed point.

The offline baseline matches bounded keywords and explicit catalog paths, supports
multiple workflows, reads matched entry points and relevant documents, and leaves
uncertain relevance at `inspect`. With a recognized workflow, unrelated workflow
sources may be skipped. Ambiguous `CHM`, `README.md` or `SKILL.md` alone does not
select a workflow; a full path or an unambiguous basename pins a source. It does
not infer intent from file contents or understand negation. Search outside the
catalog whenever the task needs it.

## Optional Jev service

Set `JEV_API_KEY` or `TYPESAFE_API_KEY` in the launching environment; optionally
set `JEV_MODEL` (default `jev-latest`). Omit `--offline` to use the configured
service. Preview the exact payload first if useful:

```bash
python3 jev_routing/scripts/jev_context.py \
  --task 'Review world-model normalization' --dry-run
```

Each advisory call sends the short task (1–2,000 characters), hand-authored
catalog metadata and optional numeric/boolean context telemetry. It sends no
source bodies, experiment handoff, directory crawl or conversation transcript.
The controller also sends at most 2,000 characters of the previous task and pins
explicit filenames from the full current prompt before truncating its routing
summary. The full prompt still goes to Codex. Task text itself leaves the machine;
use deliberately brief descriptions or offline routing when appropriate.

The transport retains the imported TypeSafe contract: one batched request to
`https://api.typesafe.ai/v1/systemone`, ten-second timeout, no redirects and a
bounded response. No key or transport failure uses the local baseline. Uncertain,
missing or malformed classifier answers become `inspect`; deterministic required
sources remain reads. `read` needs selected probability and confidence >=0.65;
`skip` needs both >=0.75. These are policy thresholds, not calibrated guarantees.
Live TypeSafe compatibility and routing quality are not established by mock tests.

## Optional Codex controller

The advisory script works without this client. The client launches or resumes a
separate Codex App Server thread; it does not attach to an already-active chat.
It inherits Codex configuration, tools, authentication, model and approval rules.
Jev does not approve commands. Run `--check` in an environment with a usable
Codex installation and writable Codex home; it performs a protocol handshake,
not a model call or account-access test.

```bash
python3 jev_routing/scripts/jev_codex.py --check
python3 jev_routing/scripts/jev_codex.py --offline-jev
python3 jev_routing/scripts/jev_codex.py --offline-jev \
  --prompt 'Review the current world-model resume evidence' --require wm_handoff
python3 jev_routing/scripts/jev_codex.py --resume THREAD_ID --offline-jev
```

`--model`, `--codex`, `--prompt-file`, `--turn-timeout`, `--color`, `--repo-root`,
`--catalog`, `--markdown`, `--activity` and `--workers` are available. `/status` shows thread/usage;
`/quit` exits. `--offline-jev` disables TypeSafe calls, not the Codex backend.

Install the optional UI packages in your normal Python environment, then restart
the launcher (a running process keeps the previous code):

```bash
python3 -m pip install -r jev_routing/requirements-jev.txt
python3 jev_routing/scripts/jev_codex.py --offline-jev
# Or append --resume THREAD_ID to continue an idle thread.
```

With the enhanced editor, Enter inserts a line; Alt+Enter (or Esc then Enter)
submits. Arrow keys and Home/End edit the draft; Ctrl+P/Ctrl+N recall whole prompts
from in-memory history. Bracketed paste stays in the draft. `/status` and `/quit`
also accept Enter. Ctrl+D exits from an empty draft. No history is written to disk.
Non-terminal/dumb-terminal input or missing prompt-toolkit falls back to single-line
`input()`. Batch `--prompt` and `--prompt-file` bypass the editor and preserve
whitespace. Approval and tool-question prompts keep their existing input path.

Replies render headings, lists, emphasis, tables, links and highlighted code using
Rich. `--markdown auto` renders in supported terminals, `never` keeps raw Markdown,
and `always` also renders redirected answers once complete. Missing Rich falls
back to raw streaming. Live previews redraw at most roughly ten times per second;
complete answers remain in scrollback. `--color never` removes styling while
keeping Markdown layout (live cursor controls still operate). `NO_COLOR` suppresses
auto colors. `--color always` explicitly allows ANSI output, including redirection.
The implementations follow [prompt-toolkit sessions](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/asking_for_input.html)
and [Rich Live](https://rich.readthedocs.io/en/stable/live.html).

Codex's messages use normal Markdown: explanations, tables and fenced commands
remain prominent and copyable. Execution details use a separate blockquote-style
`>` gutter and `[tool]` label. This classification comes from App Server event
types, not command-name guesses or a model's judgment of usefulness. Tool text is
literal: Markdown-looking file contents are not rendered as assistant instructions.
The gutter also works without Rich, with `--color never`, and in redirected logs.

`--activity compact` is the default. Commands are shown on one logical line,
limited to 160 characters, with embedded newlines shown as `\n`. Completed command
output shows its first **10 logical lines**, followed by a bold
`+X more lines hidden` if needed. Blank lines count; a final newline does not add
an extra line. File changes show the action/path and a diff summary with hidden
line count and addition/deletion counts when the diff contains those markers.
Proposed and failed actions retain their status; commands keep exit code, item ID
and working directory outside the output cap.

For example (plain terminal representation):

```text
> [tool] Ran: cat config.py
> first output line
> second output line
> +15 more lines hidden
>   [cmd1; completed (exit 0); cwd: /work/project]

> [tool] Edited: config.py
> Diff: +3/-1; 12 lines hidden (use --activity full)
>   [edit1; completed]
```

Start with `--activity full` to show complete commands, command output and file
diffs inside the same gutter. This is a launch-time display mode, not an interactive
expand/collapse control. It is independent of `--markdown`, which controls only
assistant replies. Restart a running launcher to load the new display behavior.

Both modes affect display only: commands, model-visible results, assistant replies
and recovery data are unchanged. Agent replies are never truncated or quoted as
tool output. Command buffers remain uncapped in memory. Terminal colors retain
success/failure and diff coloring; the tool gutter and compact diff summaries are
dimmed where color is enabled. Ordered rendering stays serial because it shares
the terminal and streaming reply preview.
After 30 seconds without agent text, a terminal shows a single transient line:
`Codex is still working [90s]`. The number measures elapsed wall time since the
current turn request began (not time since the last reply), using a monotonic
clock. It refreshes in place once per second. The line clears before other output,
user questions, resumed reply streaming, completion, errors or Ctrl+C. Markdown
previews yield the terminal while the notice is shown; reply buffers are retained.
Redirected and dumb-terminal output uses ordinary notices every 30 seconds with
no cursor controls. Compaction uses its own `Waiting for Codex compaction [Ns]`
notice. Neither timer extends the task timeout. Terminal updates remain serial
on the controller's event loop; no background redraw thread is added.

`/status` reads `account/rateLimits/read` without starting a model turn or routing
request. It shows context usage separately from the account's weekly usage bar,
percentage used/left and local reset time when available. The weekly window is
identified by its 10,080-minute duration in either slot, preferring the `codex`
bucket. Missing data or RPC failures show `Weekly limit: unavailable`; no quota is
inferred from context tokens. This is a read-only endpoint. Ctrl+C (exit 130),
`/quit` and EOF print the known thread ID and a shell-quoted resume command after
closing any preview. The command preserves interpreter, launcher and repository
root; reapply custom model, catalog, routing or executable flags if needed.

The client streams answers and tool activity, handles command/file/permission
approvals and text questions, and declines unsupported MCP form/URL elicitation.
Use a full client for those authentication flows. Command output is grouped at
completion; terminal control characters are escaped. Colors follow TTY,
`NO_COLOR`, `TERM` and `--color`. Full tool output/reasoning are not copied into
recovery records. Records can contain prompts, assistant text and action metadata,
including commands and changed-file paths; treat them as private.

The retained protocol follows the [official App Server documentation](https://learn.chatgpt.com/docs/app-server).
Generate a schema from the installed version before changing protocol fields:
`codex app-server generate-json-schema --out /tmp/jev-app-server-schema`.
Fake-server tests do not establish compatibility with the installed live server.

## Stopping a stuck thread writer (Linux)

If resuming reports `already has an active writer`, stop the original launcher
with Ctrl+C when possible. Otherwise, run this helper on the same host as Codex,
outside an agent PID sandbox:

```bash
python3 jev_routing/scripts/jev_kill_writer.py THREAD_ID --dry-run
python3 jev_routing/scripts/jev_kill_writer.py THREAD_ID
# Only if normal termination times out:
python3 jev_routing/scripts/jev_kill_writer.py THREAD_ID --force
```

The helper uses the existing `$CODEX_HOME/thread-writer-locks/THREAD_ID.lock`
(default `~/.codex`) and matches its device/inode to an exclusive writer in
Linux `/proc/locks`. It works with existing writers without a launcher restart
or registration change. `--codex-home PATH` overrides the home; `--timeout 5`
sets the wait per signal (maximum 30 seconds). No model or Jev requests are made.
The command prints writer and parent PIDs before signaling. A dry run sends no
signals. Missing or ambiguous ownership returns an error rather than guessing
from filenames, command lines, or stale PIDs.

Only a same-user process whose executable is `codex`/`codex.exe` and whose arguments
include `app-server` is eligible. If it owns another visible native thread lock,
the helper refuses to stop that shared server unless every additional thread is
explicitly acknowledged with `--also-stop OTHER_THREAD_ID` (repeat as needed).
This stops the whole server and interrupts all its listed threads; it cannot kill
one thread inside a shared process. `--force` only controls signal escalation and
does not bypass this acknowledgement. For example:

```bash
python3 jev_routing/scripts/jev_kill_writer.py THREAD_A --dry-run
python3 jev_routing/scripts/jev_kill_writer.py THREAD_A --also-stop THREAD_B
```

Dry-run reports the PID and all affected threads even for shared servers. The
acknowledged set must exactly match the discovered set before either signal; a
new or changed thread causes refusal. Avoid other sessions starting work during
this operation. To preserve the other thread, stop the hanging task through its
original client instead of terminating the shared process.

It rechecks ownership after opening
a Linux pidfd, sends SIGTERM to that exact process, and waits for process exit.
`--force` permits SIGKILL after the timeout and another ownership check. It never
signals an entire process group, deletes lock/session files, or follows a new
writer PID. Stopping an active writer interrupts its work; detached jobs are not
cancelled by this command. An old launcher waiting at its prompt may remain open;
exit it with Ctrl+C, then retry `jev_codex.py --resume THREAD_ID`.

This depends on the installed Codex native lock layout and Linux pidfd support.
A missing lock can indicate an inactive thread, another Codex home, or an
unsupported layout. A lock with no visible owner can reflect PID namespace or
permission restrictions. Run from your normal host terminal in those cases;
do not remove the lock file to bypass ownership. Discovery is a snapshot, not a
reservation: avoid concurrently starting/resuming threads while stopping a writer.
Metadata checks use the existing bounded workers (`--workers`, default
`SLURM_CPUS_PER_TASK` or one). Owner reconciliation, revalidation and signals stay
serial because they are ordered process-control operations.

Implementation references: [Linux lock ownership fields](https://man7.org/linux/man-pages/man5/proc_locks.5.html)
and [Python process descriptors](https://docs.python.org/3/library/os.html#os.pidfd_open).
Tests use synthetic lock/process metadata and mocked signals; they do not stop
real Codex sessions.

## Experiment handoffs and detached jobs

Use a separate file per experiment/session. The template is intentionally empty
of real run identities; `null` means unknown, not inferred:

```bash
mkdir -p jev_routing/context/jev-handoffs
(umask 077; python3 jev_routing/scripts/jev_handoff.py --template \
  > jev_routing/context/jev-handoffs/my-experiment.json)
# Edit the file with the actual adopted decisions and evidence references.
python3 jev_routing/scripts/jev_handoff.py \
  --validate jev_routing/context/jev-handoffs/my-experiment.json
python3 jev_routing/scripts/jev_codex.py --offline-jev \
  --handoff jev_routing/context/jev-handoffs/my-experiment.json
```

The same template is in `jev_routing/examples/experiment-handoff.json`. Record
objective, workflows, code revision, configuration, container, dataset/split
identity, checkpoint, authoritative sources, adopted decisions, validation,
unresolved questions and next action. Put proposals in evidence records or label
them explicitly; do not silently turn them into adopted decisions.

Job records have exactly these fields (illustrative values, not a real job):

```json
{
  "job_id": "12345",
  "state": "running",
  "description": "DDP smoke",
  "evidence_status": "submitted",
  "evidence": ["path/to/submission-receipt.txt"],
  "next_action": "Inspect the returned smoke and resume reports"
}
```

Evidence status is `proposed`, `submitted`, `user_reported` or
`independently_verified`. Job state is `unknown`, `pending`, `running`,
`completed`, `failed` or `cancelled`. Proposed jobs may have null IDs; submitted
jobs require IDs and cannot claim a terminal state on submission evidence alone.
Validation records use the same description/evidence/next-action fields without
job ID/state. Independently verified records require evidence references. This
validates record structure, not the referenced artifacts or the truth of labels.

The handoff is bounded to 32 KiB, loaded into Codex's task input and reloaded at
checkpoint time. It is never included in Jev payloads. Each private recovery
record snapshots its content and canonical SHA-256. A private per-thread
registration restores the handoff path on `--resume`; an explicit `--handoff`
can replace that registration. A missing/invalid registered file stops dependent
work; restore it from the last recovery snapshot if needed.

Detached Slurm jobs can remain running through compaction when their current
state and next action have been saved. If the handoff changes after checkpointing,
compaction is blocked until a fresh checkpoint saves it. The client does not query
Slurm or discover jobs automatically: maintain the handoff when submitting or
reviewing jobs. Without a registered handoff it only knows conversation activity.

## Local evidence and recovery

The controller now captures bounded **command execution** evidence locally using
`scripts/jev_evidence.py`. It does not collect reasoning, arbitrary MCP payloads,
or a complete conversation trace. This implements Step 1 of the
[compaction evidence plan](../../docs/jev/compaction_evidence_plan.md).

Each thread has a private `evidence/` directory below
`jev_routing/context/jev-router/THREAD_ID/`. `units/ev_SHA256.json` files are
immutable, content-addressed version-1 records. `bundle.json` is an atomically
updated, checksummed index. Units retain thread/turn/item identifiers and source
references. Supported start/result events pair by those identifiers, including
out-of-order events and overlapping commands. Starts are saved immediately;
completions are saved when received, before turn-end compaction. A missing result
remains pending with an explicit reason. Graceful shutdown captures available
partial output; abrupt process death may leave only the durable start record.

Results include the captured command, working directory, protocol status, exit
code, and bounded output. An explicitly empty aggregate is authoritative; absent
aggregates use buffered deltas. The output source is labelled. Explicit `FAILED`,
`FAIL:` and `ERROR:` lines in the captured excerpt are retained as failing-case
labels; the controller does not infer a test case or diagnose the failure.
`observed_protocol_result` means an event was observed, not that a scientific
claim or test coverage was independently verified. Failures remain in
`failures_needing_review`; later successful commands do not automatically resolve
them. Explicit declared state can explain a resolution with evidence references.

The bundle references user-request captures, current command exchanges, failures
needing review, the latest validated registered handoff, and optional explicitly
declared state. Requests are recorded as source text, not automatically parsed
into constraints. Handoff evidence retains its job/validation labels as assertions,
with the source path and original handoff hash; it never submits or polls jobs.
Handoffs are refreshed at task start, item completion, native compaction start,
and checkpoint time. Missing/invalid registered handoffs stop dependent work.

Task inputs contain recovery paths and retrieval instructions. New checkpoints
add `evidence_recovery`, pointing to an immutable bundle snapshot plus the live
bundle path. During a turn, the live bundle may contain newer evidence than its
initial snapshot. Changed evidence after a checkpoint blocks controller-triggered
compaction until a new checkpoint is saved. Old checkpoint and handoff formats
remain readable and their historical bytes/hashes are not rewritten. A resumed
legacy thread starts collecting evidence on new work; prior command output is
not reconstructed or claimed to be available.

From the repository root:

```bash
python3 jev_routing/scripts/jev_evidence.py --thread THREAD_ID --bundle
python3 jev_routing/scripts/jev_evidence.py --thread THREAD_ID --get ev_SHA256
python3 jev_routing/scripts/jev_evidence.py --thread THREAD_ID --update-state state.json
```

`--repo-root` selects another checkout; `--workers` controls bounded metadata
validation. Retrieval verifies the evidence ID against its content hash and
checks the schema/thread. Missing, altered, oversized, symlinked, or unsupported
sources return explicit errors. `--get` and `--bundle` do not modify the store.
Hashes detect content changes; they do not certify the truth of recorded claims.

An explicit state update replaces the current declared state while retaining its
previous immutable unit. Use this shape, substituting existing evidence IDs:

```json
{
  "constraints": [{"text": "Keep the existing job running", "sources": ["ev_SHA256"]}],
  "decisions": [],
  "proposals": [],
  "unresolved_questions": [],
  "next_action": [{"text": "Inspect the returned report", "sources": ["ev_SHA256"]}]
}
```

Each category permits at most 16 records, with 1,024-byte text and 1–8 evidence IDs
per record. Every source must exist and pass integrity checks before publication.
Keep adopted decisions and proposals separate. Declared state has
`recorded_assertion` status, not automatic independent verification. Maintain this
state or the registered handoff when decisions and next actions change; the
controller cannot infer their meaning reliably from event status alone.

Capture limits: 4 KiB command text, 2 KiB working directory, 16 KiB output/request
text, and a 64 KiB raw delta buffer per tracked exchange. Common credential forms
and known environment credential values are redacted **before** retained text is
clipped. A truncated delta buffer drops its trailing partial line. Records mark
redaction, truncation, result availability and pairing separately. Unredacted
original output is not archived by this feature (`original_available: false`).
It stores a bounded excerpt, not a guaranteed full log. Existing legacy recovery
records have their prior privacy behavior; this is not a retroactive secret scrub.
Known-pattern redaction cannot detect every secret: avoid printing sensitive data
and do not treat captured excerpts as safe for publication.

A document is at most 64 KiB. Per-thread storage is capped at 2,048 units and
32 MiB of unit data; a live bundle has at most 256 command exchanges and 32
user-request references. Serialized document limits can bind earlier. Capacity
errors stop dependent work rather than silently evicting critical evidence. No
automatic deletion is performed: explicitly archive the thread's entire evidence
store with its references and begin a new thread when limits are reached. Files
are mode 0600 and evidence directories 0700. Publication uses a local write lock,
temporary files, atomic replacement and fsync; partial publication cannot replace
a valid old bundle, and orphaned units are accounted for on restart.

Event reconciliation and publication are serial because they share ordered thread
state. Independent unit-size checks use the existing bounded spawn workers,
defaulting to `SLURM_CPUS_PER_TASK` or one. Capture/redaction does not alter commands,
model-visible command results, terminal previews, the routing catalog, or Jev's
metadata-only external payload. Evidence content is local and is never appended
to a Jev request. Step 2 continuation evaluation and Step 3 shadow selection are
not enabled by this change.

## Recovery and compaction

Private mode-0600 recovery records live under
`jev_routing/context/jev-router/THREAD_ID/*-turn.json`; registration and snapshots are ignored
by Git. `jev_routing/context/jev-handoffs/` is also ignored. Jev prompt templates
live under `jev_routing/prompts/`; all active Jev implementation, dependencies,
examples, private state and docs now live under `jev_routing/`.

Stop old launchers before restarting. On connection, the controller migrates only
legacy root `context/jev-router/` and `context/jev-handoffs/` into the new context
directory, preserving bytes and permissions. It preflights collisions and refuses
to overwrite either record. Other root context files remain untouched. Registered
live handoff paths are relocated on resume; historical recovery snapshots and
checksums remain exact. No records are replayed into Codex. Legacy ignore rules
remain so a still-running old launcher cannot expose its last private checkpoint.
Use new paths for explicit `--handoff` arguments.

Controller notices and compaction requests are disabled by default. Pass
`--auto-compact` to opt in; evidence capture and native Codex compaction remain
available without it. When enabled, the controller uses three default stages
based on reported latest-call usage:
50% notice, 65% preserve state/ask Jev about the boundary, 85% request compaction
at successful turn end. `--compact-thresholds 50,65,85`,
`--compact-token-thresholds 6000,10000,14000`, and `--compact-cooldown 60` customize
the policy. Absolute token thresholds are demonstration settings, not recommended
LECOSPy defaults. Missing telemetry never creates a context-pressure estimate.

Both automatic paths require a successful turn, no active conversation items,
a saved current recovery record and the cooldown. Native compaction clears old
usage. The client waits for compaction-item and successful-turn completion.
`--no-auto-compact` remains an explicit spelling of the default and cannot be
combined with `--auto-compact`. Native automatic compaction can occur inside a turn independently;
keep handoffs current rather than relying only on controller boundaries.

Compaction notices do not authorize ending unfinished work. Recovery snapshots
are exact records, not model-written experiment summaries or proof of completion.

## Local validation and evaluation

These checks use text/JSON fixtures, terminal key input and a simulated App Server
only. Install the optional UI dependencies above to avoid skipped UI test classes:

```bash
python3 -m unittest discover -s jev_routing/tests -p 'test_jev*.py'
python3 jev_routing/scripts/evaluate_routing.py --workers 1
```

The 16 curated tasks cover both model families, mixed workflows, historical
sources, explicit paths, ambiguous CHM/README requests, unrelated code and
required-source overrides. Reports include missed required reads, false skips,
extra reads, inspection counts, workflow confusion, missing files and catalog/
fixture hashes. Missing required reads, files or workflow matches fail the check;
extra reads are reported separately. This is a maintained regression set, not
held-out evidence of general model quality. Add new representative cases without
silently weakening expected source requirements to accommodate router outputs.

`--live` explicitly sends these curated tasks to Jev and reports both local and
service results. It requires a key; transport fallbacks are counted and make the
live evaluation incomplete/failing. Live concurrency is capped at four requests.
No service call is made during the default evaluation or unit tests.

Initial adaptation verification on 2026-10-09: 81 focused tests passed. All 16 curated
offline cases passed with zero missed required sources, false skips, missing
files, extra reads or workflow mismatches; two-worker evaluation also passed.
Python syntax, shell parsing and diff whitespace checks passed. A real `--check`
attempt stopped at App Server startup because Codex's home was read-only in the
managed session. No Jev key or Slurm allocation was available, so live routing
quality, real-server operation and HPC speedup remain unverified.

QoL port verification on 2026-10-09: 112 focused tests passed with prompt-toolkit
3.0.53 and Rich 13.9.4, including editor key sequences, Markdown cleanup, display
limits, heartbeat clocks, weekly status/rejection, exit cleanup and legacy state
migration. All 16 offline routing cases passed with zero missed required reads,
false skips, missing files, extra reads or workflow mismatches. The installed
Codex App Server schema confirmed `GetAccountRateLimitsResponse`,
`RateLimitSnapshot` and `RateLimitWindow`. A PTY smoke test with the fake server
exercised editing, multiline paste/history, tables/code, output truncation, status
exit/resume, Ctrl+C (130), and redirected Markdown without ANSI. This does not establish live account endpoint or model-service behavior;
a human terminal/scrollback review and real-server smoke remain separate checks.
No live Jev calls or HPC performance measurements were run for this port.

Independent source-existence checks and evaluation cases use spawn processes with
at most two queued jobs per worker. `--workers` overrides the default
`SLURM_CPUS_PER_TASK` (otherwise one), capped by independent jobs. One worker uses
a true serial path. Case workers run inner metadata checks serially to avoid
nested pools. Catalog parsing, dependency reconciliation, controller event
ordering and record/report publication stay serial because they are small shared
state or ordered operations. Prompt editing, terminal redraw and private-state
migration also stay serial because they own shared input/output or publication
state. No numerical libraries or internal thread pools are
used. Small catalogs may be slower with processes; no speedup is assumed.

Actual serial/parallel timing must run on HPC in the project container:

```bash
export LECOSPY_REPO_ROOT=/absolute/hpc/checkout
export LECOSPY_CONTAINER=/absolute/path/to/project.sif
# Optional: LECOSPY_CONTAINER_RUNTIME=singularity, JEV_WORKERS=4
sbatch jev_routing/scripts/sbatch_routing_benchmark.sh
```

Supply the cluster's account/partition options as needed. The wrapper records Git
revision/status and compares repeated offline evaluation runs with one versus
allocated workers, checking identical results and reporting measured timing
ratios. It uses no raster data or model service. Review the returned report before
making throughput claims. HPC timing, live Jev quality and real App Server
operation remain separate validation steps.
