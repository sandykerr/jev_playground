# EXECUTE PROMPT

## Objective

Execute the current task plan for LecoSpy while keeping the repo, docs, and experiment artifacts internally consistent.

## Instructions

1. Read `PROMPT.md`, `README.md`, and the relevant task-specific docs before editing.
2. If `IMPLEMENTATION_PLAN.md` applies, execute the first unfinished item that is still current.
3. Make the smallest defensible change set.
4. Validate the change appropriately:
   - run tests for code-path changes when practical
   - run syntax checks for script-only updates
   - inspect artifacts for training/visualization tasks
5. Update the matching markdown docs when behavior, assumptions, or conclusions change.
6. Do not mix checkpoints or logs across incompatible run roots.
7. If the task touches transformer quality, report separately on:
   - autoencoder baseline
   - raw transformer reconstruction
   - masked inpainting behavior
   - transfer-learning implications for PFT estimation
8. Only mark a plan item complete when the change and the validation are both done.

## Completion Criterion

The task is complete when the requested work is implemented, validated, and documented. If the active plan is fully complete, output `<promise>COMPLETE</promise>`.
