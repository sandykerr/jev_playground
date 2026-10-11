# LECOSPy context router

Select relevant repository sources, preserve source authority, and carry experiment
state across Codex sessions and HPC waits. Routing and basic terminal operation
use only the Python standard library. For multiline editing and Markdown replies,
install `python3 -m pip install -r jev_routing/requirements-jev.txt` from the repo root.

```bash
python3 jev_routing/scripts/jev_context.py \
  --task 'Resume world-model pretraining after the DDP failure' --offline
python3 jev_routing/scripts/evaluate_routing.py --workers 1
```

Start with [usage and design](docs/jev-context.md). The editable [catalog](catalog.json)
contains workflow reading maps and validation guidance; changing job IDs and
experiment results remain in the existing repository handoffs and trackers.

The optional `scripts/jev_codex.py` controller provides recovery records and
context compaction. `examples/experiment-handoff.json` is an empty experiment
state template. Imported workout files under `.agents/` and the Node dependency
are retained historical material and are not used by the LECOSPy router.

Jev prompt templates live in `prompts/`, and private recovery records and handoffs
in `context/` under this directory. Restart the controller after updates; Enter
inserts a line and Alt+Enter submits in the enhanced editor. See the guide for
legacy state migration, `/status`, output modes and resume instructions.

To stop a stuck Linux thread writer, run
`python3 jev_routing/scripts/jev_kill_writer.py THREAD_ID --dry-run` from the repo
root, then omit `--dry-run` to terminate the identified writer. See the guide for
shared-server protections, explicit `--also-stop THREAD_ID` acknowledgement, and
`--force` escalation.

Tool activity now uses `>` gutters labelled `[tool]`; assistant replies retain
normal Markdown. Default `--activity compact` shows output previews and diff
summaries. Use `--activity full` for complete tool transcripts.

Bounded local command evidence and recovery bundles live alongside private
checkpoints. Use `python3 jev_routing/scripts/jev_evidence.py --thread THREAD_ID --bundle`
or replace `--bundle` with `--get ev_SHA256` to inspect a unit; see the guide for capture limits,
redaction, explicit state updates and retention.

Controller-triggered compaction is disabled by default. Use `--auto-compact`
to opt in. Native Codex compaction and local evidence capture remain active
without this option; `--no-auto-compact` is retained for compatibility.
