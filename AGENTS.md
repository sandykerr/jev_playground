# LECOSPy context routing

Follow the repository-root AGENTS.md and local/HPC testing protocol. Work from
the LECOSPy root, not the imported personal-project directory.

The active catalog is `jev_routing/catalog.json`. Keep paths repository-relative
and keep authority metadata descriptive: current job IDs, dataset pins and
execution outcomes belong in the existing owning handoffs/trackers. The imported
`jev_routing/.agents/` workout documents are historical material, not LECOSPy
instructions or active routing sources. They are retained without modification.

Use `python3 jev_routing/scripts/jev_context.py --task 'short task' --offline`
to inspect routing. A controller-provided reading plan replaces a duplicate
router call. Explicit sources, required instructions and verification needs
override advisory skip decisions. Missing or uncertain sources require local
search, not invented facts or approval requests for routine reads.

Routing and basic operation use standard-library Python; optional terminal UI
dependencies are declared in `requirements-jev.txt`. The original `typesafe-ai` skill
reference belonged to the imported project and is not a prerequisite for this
adaptation. Consult current provider documentation before changing wire formats;
mock tests do not establish live service compatibility.

The controller owns only its launched/resumed App Server thread. Context notices
never replace the user's task or imply completion. Never invent usage telemetry.
Registered experiment handoffs preserve detached job IDs, evidence states and
next actions; submitted jobs are not verified results. Keep handoffs current
before compaction and read the registered handoff on resumption.

Run the focused text/mock/terminal tests under `jev_routing/tests`, not broad
repository discovery. Use the offline evaluator before any opt-in live routing
evaluation. Worker pools must be spawn-based, bounded and non-nested; ordered
reconciliation, controller events and record publication remain parent-owned.
Actual parallel speedup measurements are HPC-only and remain pending until run.

See `jev_routing/docs/jev-context.md` for setup, data boundaries and verification.
