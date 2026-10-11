# PLAN PROMPT

## Objective

Write or update `IMPLEMENTATION_PLAN.md` as a concrete checklist for the current LecoSpy task.

## Planning Rules

1. Read the relevant code and docs first.
2. Keep the plan grounded in the actual pipeline:
   - autoencoder
   - ViT / eval-fix pretraining
   - transfer learning for PFT prediction
   - visualization and reporting
3. Break work into steps that are:
   - technically specific
   - independently verifiable
   - small enough to complete in one pass
4. Include validation steps, not just implementation steps.
5. Include documentation updates whenever behavior or conclusions will change.
6. If the task concerns transformer quality, the plan should explicitly separate:
   - data issues
   - architecture issues
   - loss/objective issues
   - evaluation/visualization issues
   - downstream transfer implications

## Required Format

Use checklist sections such as:

## Phase 1

- [ ] step
- [ ] step

## Completion Criterion

`IMPLEMENTATION_PLAN.md` is complete when it is actionable, unambiguous, and covers implementation, validation, and documentation. When the plan is complete, output `<promise>COMPLETE</promise>`. Do not implement the plan in this mode.
