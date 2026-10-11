# Generic Jev routing implementation plan

Make Jev reusable across Codex projects by separating the routing engine,
project configuration, and private session state. An unrelated repository must
be able to use Jev by adding configuration and a catalog, without changing
Python code or adopting a prescribed source directory structure.

Status: planned. Check off each step only after its implementation and relevant
validation are complete. Execute the stages in order.

## Starting point and constraints

The routing algorithm already uses catalog metadata for source selection,
authority relationships, and workflow guidance. The main coupling is in root
discovery, private storage paths, import-time catalog loading, experiment
handoffs, and bundled project content.

The initial standalone-checkout audit found that the default root resolves one
directory above this repository. With the correct root explicitly supplied,
27 of the 28 bundled catalog sources are missing. The 16-case offline evaluator
fails on missing sources and required reads, with no workflow mismatches or
false skips. These are baseline portability failures, not evidence of a newly
introduced regression.

Preserve these properties throughout the refactor:

- Standard-library Python remains sufficient for routing and basic operation.
- Explicit sources, applicable instructions, authority companions, and
  verification needs take precedence over advisory skip decisions.
- Catalog authority metadata remains descriptive; live task outcomes belong in
  their owning records. Source existence does not establish correctness.
- Jev requests contain bounded task text and catalog metadata, not source
  bodies, handoffs, evidence records, or conversation transcripts.
- Existing private evidence and historical recovery records retain their bytes,
  hashes, permissions, and references. Imported `.agents/` material is retained
  without modification and is not used as active configuration.
- Worker pools remain bounded, spawn-based, and non-nested. Event ordering,
  reconciliation, and record publication remain parent-owned.
- This work does not require provider wire-format changes. Any later protocol
  change requires current provider documentation and separate compatibility
  verification.

## Stage 1 Centralize workspace configuration and paths

Outcome: the target workspace and its state are independent of the location of
the Jev implementation.

- [ ] **1.1 Define a versioned project manifest.** Use JSON to preserve Python
  3.10 standard-library support. Include `workspace_root`, `catalog`,
  `evaluation_cases`, and `state_dir`. Reject unsupported versions and malformed
  fields with actionable errors.
- [ ] **1.2 Implement deterministic configuration resolution.** Explicit CLI
  configuration wins; otherwise discover the nearest `.jev/config.json` from
  the invocation directory upward, stopping at the repository boundary when
  present. Resolve manifest paths relative to its directory and catalog source
  paths relative to the selected workspace. Resolve explicit CLI paths relative
  to the caller's directory. Keep `--repo-root` and `--catalog` overrides and
  define their precedence in help and documentation. Do not infer the workspace
  from the installed script path or silently select an unrelated parent project.
- [ ] **1.3 Introduce one shared workspace configuration object.** Pass resolved
  paths and the loaded catalog into routing, controller, evidence, handoff, and
  evaluation entry points. Remove `parents[2]` workspace defaults and the
  import-time `CATALOG = load_catalog()` dependency. Importing the engine must
  work without a project catalog on disk.
- [ ] **1.4 Centralize private state layout.** Derive checkpoint, registration,
  evidence, and handoff locations from `state_dir`. Update recovery instructions,
  evidence retrieval commands, and resume commands to preserve the selected
  workspace and configuration. Keep per-thread isolation and existing path
  containment and private-publication safeguards.
- [ ] **1.5 Isolate legacy layout support.** Recognize the existing root
  `context/` and embedded `jev_routing/context/` layouts explicitly. Require an
  explicit migration action rather than moving arbitrary directories on every
  connection. Preserve collision refusal and historical snapshot integrity;
  relocate only live references through a documented compatibility path.
- [ ] **1.6 Validate the path contract.** Add focused temporary-directory tests
  for CLI precedence, subdirectory invocation, alternate installation locations,
  missing configuration, paths containing spaces, source traversal and symlink
  escape, separate workspace state, and legacy migration collisions. Verify
  resume and evidence retrieval use the same resolved configuration.

Stage acceptance: the same router and fake-server controller can operate on two
temporary workspaces with different catalogs and storage locations, without
reading or writing relative to the Jev installation.

Proposed project layout and manifest, to be implemented in this stage:

```text
any-project/
  .jev/
    config.json
    catalog.json
    routing-cases.json
    state/                 # private and ignored by Git
```

```json
{
  "schema_version": 1,
  "workspace_root": "..",
  "catalog": "catalog.json",
  "evaluation_cases": "routing-cases.json",
  "state_dir": "state"
}
```

Only configuration and state use these default locations. Project code and
documentation may live anywhere within the selected workspace.

## Stage 2 Separate project content and generalize task recovery

Outcome: the engine has no built-in project purpose, workflow names, or
scientific experiment requirements.

- [ ] **2.1 Preserve LECOSPy as an optional example.** Move its catalog,
  evaluation cases, domain prompts, and HPC benchmark wrapper into an explicitly
  named example directory. Explain which files require the original project.
  Keep historical verification claims scoped to that project and revision;
  example sources must not be treated as present in a generic checkout.
- [ ] **2.2 Provide a working catalog for this repository.** Use stable source
  IDs mapped to existing repository-relative paths. Retain `owns`, `requires`,
  `superseded_by`, `workflows`, and `entrypoint` semantics. Replace the active
  scientific workflow catalog with one describing this routing repository.
  Supply a separate minimal example for onboarding unrelated projects.
- [ ] **2.3 Generalize instructions and prompts.** Update root `AGENTS.md`,
  README, usage documentation, CLI help, and controller reading-plan text.
  Remove assumptions about LECOSPy, training pipelines, required plan filenames,
  and universal HPC execution. Keep project-specific validation guidance in
  project instructions and catalog workflows. Preserve imported `.agents/`
  documents unchanged.
- [ ] **2.4 Version the generic task handoff.** Define objective, workflow IDs,
  authoritative sources, decisions, validation evidence, unresolved questions,
  next action, and optional background jobs. Validate workflow IDs against the
  selected catalog. Put dataset, split, container, and checkpoint identities in
  a bounded optional domain extension instead of mandatory generic fields.
- [ ] **2.5 Preserve recovery compatibility.** Keep version-1 experiment
  handoffs readable through an explicit legacy validator; write new generic
  handoffs with a new schema version. Update registration, evidence capture,
  recovery prompts, and compaction freshness checks for both versions without
  rewriting immutable snapshots. Preserve the distinction between submitted,
  reported, and verified outcomes and keep incomplete background work visible.
- [ ] **2.6 Separate execution policy from generic behavior.** Use an explicit
  worker override and a portable default of one in the generic configuration.
  Retain Slurm allocation handling and project-container requirements in the
  HPC example. Keep bounded spawn execution and serial publication guarantees.
  Actual parallel speedup measurements remain HPC-only and unverified until run.
- [ ] **2.7 Validate domain independence.** Test custom workflow names, tasks
  with no background jobs, optional domain metadata, legacy handoff loading,
  evidence-reference preservation, and malformed-record rejection. Audit active
  code and documentation for remaining project names and fixed storage prefixes;
  intentional legacy support and examples must be clearly scoped.

Stage acceptance: a project with unrelated terminology can route tasks and
preserve session state without scientific fields, Slurm, or LECOSPy files.

## Stage 3 Prove portability and add onboarding

Outcome: a new project can configure, inspect, and evaluate routing through
documented commands, with meaningful regression coverage.

- [ ] **3.1 Replace checkout-dependent tests with explicit fixtures.** Create
  small temporary projects with different purposes and directory structures.
  Pass their catalogs and roots explicitly. Preserve coverage for authority
  companions, explicit-source overrides, ambiguous filenames, missing files,
  malformed service responses, and fallback behavior. Keep LECOSPy regression
  cases separate from generic engine tests.
- [ ] **3.2 Add an `init` entry point.** Create the manifest, minimal catalog,
  starter evaluation cases, and narrowly scoped state ignore rule. Refuse to
  overwrite existing user configuration. Any discovery should propose local
  candidates for review; it must not infer verified authority, crawl excluded
  historical material, or send document bodies to Jev.
- [ ] **3.3 Add a read-only `doctor` entry point.** Report resolved workspace,
  catalog, evaluation, and state paths; validate source existence, companion
  references, containment, and configuration. Identify legacy layouts without
  migrating them. Emit actionable diagnostics and a failing exit status for
  invalid required configuration without making service calls.
- [ ] **3.4 Expose stable commands.** Provide a documented module or packaged
  command entry point for routing, controller launch, evidence retrieval,
  evaluation, initialization, and diagnostics. Keep existing scripts as thin
  compatibility wrappers where practical. Declare terminal dependencies as
  optional and verify basic commands in a standard-library-only environment.
- [ ] **3.5 Run the focused regression suite and offline evaluator.** Exercise
  text/mock/terminal tests under this repository's `tests/`, including the fake
  App Server. Evaluate this repository's catalog against existing files and the
  generic fixtures against their own expected reads and workflows. Require zero
  missed required reads, false skips, missing required files, and workflow
  mismatches; report extra reads separately. Check serial and bounded-worker
  result equivalence without claiming a local performance speedup.
- [ ] **3.6 Verify onboarding end to end.** Initialize two unrelated temporary
  repositories, run diagnostics and offline routing from roots and subfolders,
  launch and resume fake-server sessions, and retrieve evidence. Confirm that
  commands do not depend on a directory named `jev_routing` in either target and
  that configuration and private state do not leak across workspaces.
- [ ] **3.7 Publish migration and usage guidance.** Document setup, path
  precedence, catalog maintenance, state privacy, legacy migration, evaluation,
  and the limits of discovery. Record exactly which checks passed. Keep live
  Jev quality, real Codex App Server compatibility, and HPC timing as separate
  verification items; run offline evaluation before any opt-in live evaluation.

Stage acceptance: a user can initialize an unrelated project, diagnose its
configuration, route a task, and resume a session using the documented commands,
without editing Jev implementation files.

## Completion criteria

- [ ] All three stage acceptance criteria are satisfied.
- [ ] This repository's default catalog resolves to its own maintained sources.
- [ ] Generic tests run without access to the original LECOSPy checkout.
- [ ] Legacy recovery data remains readable and unchanged unless explicitly
  migrated through the documented compatibility path.
- [ ] Documentation distinguishes implemented behavior, verified behavior, and
  pending live-service or HPC verification.
