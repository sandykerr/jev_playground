# Plyometric and jump context

Adult program; high-school teaching doses are separate. Shared health facts:
[index](project-context.md). Calendar: [periodization](periodization.md).

## User intent

### Latest decision closeout — 2026-09-26

This checkpoint supersedes conflicting historical statements below.

- P3 High Day 1 triple broads now **2×3 triple sequences in all four weeks**
  (18 jumps/session), implemented in-place. No P3 COD change: user closed COD
  design, retains current slots/doses, and handles execution as they go.
- Original altitude-drop 6 sets/week P2 → 3 P3 idea withdrawn/closed. Retain
  current P2 Thursday 2×5 and P3 Thursday 2×3; do not reopen that old proposal.
- P5 drop height and phase-specific braking exercise selection closed as
  athlete-managed choices to test during implementation. No fixed selection is
  needed to resolve the audit. Current P5 drop prescription is 1×4, superseding
  historical 6–8/8–10/6 notes. No dose change was made to it in this closeout.
- Approved taxonomy is now implemented in `audit_updates/audit_rules.py`, used
  by `working_audit.py`. Primary categories are exclusive; Approach jump is an
  overlapping tag only. Altitude and variable braking landings are separate.
  Tier/intent/role/GCT are separate axes; unknown is not zero. Sequence and
  explicit per-leg multipliers applied; unknown Heiden rep basis stays unknown.
- Full plyometric workbook/chart refresh is closed as a decision and reserved
  for the user's forthcoming audit run; not claimed completed now.

### Approved braking/landing slot — 2026-09-26

Added to the original P2–5 trackers: **Single-leg braking / landing — phase
choice**, **2×4/leg on each scheduled high day** (normally Tue/Thu/Sat).
The user has resources and chooses the exercise for each phase; exercise notes
explicitly refer to those resources and weekly Notes provide space to record
the choice. No particular drill or mandatory directional rotation was selected.
Implementation default: controlled low/moderate amplitude, bodyweight, reset each
rep, 60–90 seconds between sets; stop/regress for lost control or worsening
symptoms. These are not high single-leg drop or maximal run-in prescriptions.

The fixed dose applies in reduced weeks too, without adding omitted sessions:
P2 W5 has two exposures; P3 preserves shifted Mon/Wed/Fri weeks and full rest;
P4 W1 Thursday remains blank/gray. P1/P6 and unused templates are unchanged.
P2 scheduled W5 visible blocks and hidden reference copies are synchronized.
Each session prescribes 16 repetitions across both legs; normal weeks prescribe
48. Weekly totals: P2 48/48/48/48/32; P3 48/48/48/48 (training weeks only);
P4 32/48/48/48; P5 48/48/48. Physical contact counts depend on the selected drill:
16 repetitions means 16 landings only for one-landing-per-rep executions.

This is an **addition**, not an approved replacement of existing jumps/landings.
The proposal to move Saturday cuts to Tue/Thu has been declined and closed;
no replacement of overlapping jumps is requested. COD, existing jumps, sprints,
lifts and conditioning were not changed by the landing-slot addition. Variable
drill contacts remain unknown in reporting, not an open decision for the user.
Full plyometric workbook/chart refresh is reserved for the next audit run; do
not silently classify all these repetitions as true plyometrics.
Migration/verification: `audit_updates/add_braking_landings.py`; backup manifest
and row insertions: `audit_updates/braking-landings/changes.json`.

Speed is a priority, but **jumping is a development goal in its own right**.
User values dedicated plyometrics for stretch-shortening-cycle demands and has
historically included multiple such movements. Counting skips/dribbles as load
does not establish that they replace dedicated reactive work. Do not treat jumping
as merely sprint preparation or optional filler.

Distinguish low-amplitude reactive preparation, developmental hops/bounds/rebounds,
and approach/maximal jump practice. These are planning roles, not a newly approved
exercise/contact prescription. Heavy/ballistic lifts do not fully describe the
bodyweight plyometric dose. SSC is not exclusive to “pure plyometrics”; execution,
timing, output, direction and repetition matter.

## User's working movement taxonomy — 2026-09-26

Use this classification in future discussions and proposed audit revisions.
The user bases it on **execution intent and ground contact time**, not just the
exercise name. These are adopted project categories, not claims of a universal
scientific taxonomy or evidence that ground contact times have been measured.

| User category | Movements |
| --- | --- |
| True plyos | Hops; straight-leg bounds; consecutive hurdle hops; drop jumps |
| Close to true plyos | Approach jumps; non-consecutive/stick Heidens; continuous/quick rebound Heidens; triple broad jumps; depth jumps |
| Jump training | Non-consecutive hurdle jumps; non-consecutive broad jumps; CMJ |

Latest clarification: the user explicitly places both non-consecutive Heidens
and P5 quick-rebound Heidens in “close to plyos.” Preserve that classification
literally; still distinguish execution and stress rather than treating them as
identical exercises. Approach jumps are also “close to plyos,” superseding the
earlier jump-training label.

Keep quick rebound Heidens distinct from ordinary/reset Heiden bounds, and
consecutive executions distinct from jump-and-stick/reset executions. For this
project, preserve the user's drop-jump versus depth-jump distinction instead of
collapsing the names into one category. Previously confirmed pogos/pogos with
hurdle classifications remain; this new list does not withdraw those decisions.

Altitude drop-and-stick work remains separately identifiable as landing/force-
acceptance work, with no rebound; do not count it as a drop jump merely because
both start from a box. The user did not assign altitude drops a new category in
the three-row list above. Retain their execution details when discussing the
combined jump-training/landings stress allocation.

This taxonomy refines/supersedes conflicting historical classifications below.
It does not assign Watson light/medium/ping tiers automatically: output tier,
preparation versus development, and the user's movement category are separate
descriptors. No numerical GCT thresholds, contact totals, doses, or spreadsheet
changes were supplied or implemented by this context update. Broader audit
calculation/overlap decisions remain open, but these named categories are no
longer an unanswered user preference.

Discuss these movements within the phase-wide [stress-budget model](periodization.md),
alongside lifting, sprints, conditioning, and COD; do not evaluate their volume
as an isolated bucket.

## Reference context

- [Watson transcript](../Diet_Training_Agent_2026_2027/Transcripts/Training/plyo-focused/matt_watson_plyos.md):
  systematic year-round progression. Light/medium/ping are intensity/output tiers
  retaining reactive-contact goals, NOT low/medium/high GCT bins. Deep yielding
  is supporting work in his terminology. Contact examples and physiological
  claims are not adopted personal doses or independently verified guarantees.
- THP: one-/two-foot approach technique, sequencing, retention across blocks.
  Jumping Jacked: dedicated jump practice alongside strength/accessories.
  See [PDF context](example-program-context.md).
- Blaine/Ratelle/JT/Overtime/Coach Q support purposeful exposures and manageable
  volume. Don't copy in-season minimums into offseason development. Detailed
  transcript context remains in the [backlog](../audit_updates/pending_decisions.md).

## Additional plyo-focused transcripts — reviewed

The three sources below were read in full after the user supplied additional
context. Together with the previously reviewed `matt_watson_plyos.md`, they
inform the framework; no exercise, dose or rehabilitation protocol was adopted
by adding these files. Review used local text, not linked videos or visual demos.
Transcription errors and incomplete passages limit exact movement interpretation.

### Deep-tier programming

Source: [deep-tier programming](../Diet_Training_Agent_2026_2027/Transcripts/Training/plyo-focused/matt_watson_deep_tier_programming.md).

Watson describes two distinct roles:

1. Preparatory oscillations: supported then unsupported deep-range movement to
   practice positions/confidence before lifting. His examples mention 8–12
   landings per set and 2–3 sets total, with 1–3 movement options; the allocation
   across options is not fully specified. Keep fatigue low enough for the lift.
2. Developmental deep eccentric loading at velocity: larger takeoffs and deeper
   yielding landings, such as split-stance leaps. He discusses placing these
   after reactive plyos, as a main gym exercise, or in a contrast with lifting.
   Example ranges are 6–10 reps, usually 1–2 exposures/week and roughly no more
   than 5–6 sets/week, depending on dose/intensity. These are source examples,
   not targets for this user. Stop sets when quality deteriorates.

Implication: deep-tier work is not automatically low intensity, low fatigue,
or warm-up work. Its role changes with landing speed, depth, height and dose.
Do not infer mandatory contrast pairing; Ratelle's transcript offers a different
view of its practicality. Neither framework overrides the user's session goals.

### Achilles modifications and a personal training session

Source: [deep-tier Achilles discussion](../Diet_Training_Agent_2026_2027/Transcripts/Training/plyo-focused/matt_watson_deep_tier_achilles.md).

The instructional portion proposes retaining selected yielding jumping work
when stiff/reactive work is poorly tolerated. Examples include front-foot-elevated
split-stance oscillations with relatively fixed shin position; normal split-stance
leaps; split exchanges; stepping/slalom variations; bilateral oscillations and
full leaps; forward low-ceiling leaps; and balance hops. These are candidate
modifications, not a mandatory linear progression or proven individual treatment.
Some exercise names are unclear in the transcript; inspect demonstrations before
prescribing unfamiliar variants.

His progression variables include support, shin excursion, range, takeoff height,
forward motion and speed/reactivity. His suggestion to increase stiffness/speed
by 5–10% is subjective, not a measurable tendon-load formula or universal rule.
Claims that a position reduces Achilles demand or will be tolerated remain
source claims requiring separate clinical/evidence review for this user. More
knee/hip contribution does not establish negligible Achilles loading.

The later portion is Watson's personal session, including weighted jumps,
broad-to-vertical combinations, resisted treadmill bounds/accelerations, heavy
machine squatting and hamstring curls, with fatigue and groin-recovery commentary.
Do not copy his loads, session density, symptom decisions or readiness thresholds
to the user. The instructional Achilles examples and personal groin-recovery
session are different contexts. Adopted calf programming remains unchanged.

### Advanced plyometric options

Source: [three advanced plyometric methods](../Diet_Training_Agent_2026_2027/Transcripts/Training/plyo-focused/top_3_elite_plyos.md).

- Speed hops: incoming speed and same-leg cycling/loading are key variables.
  He proposes short run-ins before longer ones, low frequency and quality-limited
  volume. The 20–30 m example is not a starting prescription. Part 1 ends with
  an explicit omission marker, so it is an incomplete transcript segment.
- Horizontal-to-vertical combinations: flat-to-high hops or bilateral jumps
  train receiving horizontal momentum and redirecting the movement upward.
  A source “rep” means a flat/high pair, not one physical jump/contact; the audit
  must define component actions and landings explicitly before counting.
- Depth versus drop jumps: in his terminology, depth jumps prioritize height/
  explosive output, while drop jumps combine height with short contact time.
  Terminology varies; do not classify by name alone. His discussion of heights
  above 70 cm is not an adopted minimum, progression requirement or clearance.
  He also discusses no-box alternatives. A drop-and-stick altitude landing is
  not interchangeable with either rebound task.

He does not recommend automatically stacking all three methods. His reactive
block example emphasizes speed hops/drop jumps; his explosive block example
uses depth jumps and horizontal-to-vertical combinations. Output quality,
frequency and other training constrain the dose. “Elite,” “superhuman” and
guaranteed-improvement language are promotional claims, not established outcomes.

## Implications for the next programming decision

Use separate axes for purpose (preparation/development/practice), contact-time
intent, output/intensity, yielding depth, incoming speed, direction, unilateral
basis, and reset/repeated execution. The new material strengthens the case for
purposeful jump development but does not require every advanced option.
Possible phase emphases are topics for discussion, not adopted changes: early
controlled/deeper force acceptance, then more explosive redirection, then more
reactive emphasis while retaining other qualities. Do not equate all deep work
with early/easy work or abruptly introduce high-impact drills at a phase boundary.

## Implemented exercise choices — 2026-09-26 follow-up

### Latest manual edits and clarification implementation

This checkpoint supersedes conflicting doses/execution descriptions below.

- Verified user edits: P3 Tuesday Heidens are now **jump and stick**; P4 Tuesday
  Heidens are **continuous**. P4 Thursday now uses consecutive hurdle jumps,
  with the user's intended medium amplitude/higher GCT bridging to snappier P5
  contacts. Existing volumes were not altered in this clarification pass.
- Approach jumps: **2×3/leg in every scheduled week across P1–6**, explicitly
  including reduced/travel and taper weeks. This means 12 jumps per session.
  Updated the visible P2 W5 block and its hidden reference consistently. No
  sessions were added to unused P3 W5 templates or unscheduled weeks. Other P6
  development remains deferred; only this explicit dose change was applied.
- P4 Thursday W1: the entire weekly block is gray and prescription/header
  contents below the retained “W1 NOT SCHEDULED” label are cleared. No workout.
- P5 straight-leg hurdle bounds: **4/leg per set = eight total repetitions**,
  all three weeks. Two sets retained from W1 and used as the implementation
  default for the malformed W2/W3 set cells: 2×4/leg throughout. The user
  specified the per-leg repetition count; the two-set default is agent-chosen
  from the existing W1 prescription, not a separately specified user dose.
- P5 quick Heidens remain on Day 1. Day 3 COD now has its own Sets/Reps/Rest
  header; flying sprints retain Reps/Dist/Rest. COD volume is unchanged.
- Agent corrected the stale P4 Heiden “stick” weekly note to “continuous.”
  Existing wrapping, weekly heading merges, and dosage alignment were retained.

The user favors stable jump doses within phases; this pass implements the
explicit approach-jump and straight-leg-bound decisions, not every possible
weekly-dose normalization. P3 fixed triple broads 2×3 and COD 2×3/leg from the
prior discussion still need implementation; broader audit tables/charts remain
stale. See `audit_updates/jump-clarifications-followup/changes.json` for the
cell-level change log and the timestamped source-folder backups for recovery.

Latest A08 clarification: medium-tier 1×2–4 is **preparation**, with P3 single-leg
hops counted **per leg**. P5 drop-jump doses are **complete drop-and-jump reps**:
1×6–8 / 1×8–10 / 1×6, not a combined count of rebound and final landings. Each
rep includes a rebound and final landing; count physical landing events separately
if needed. Drop height remains unspecified and must not inherit P3 high drops.

Approach jumps are primarily technique practice. User approved reaching 3–4 reps
per set in peak weeks of P4–6. Implemented with existing set counts preserved:

| Phase | W1 | W2 | W3 | W4 |
| --- | --- | --- | --- | --- |
| P4 | 1×2 | 2×2 | 2×3 | 2×2 |
| P5 | 2×2 | 2×4 | 2×2 | — |
| P6 | 2×2 | 3×3 | 1×2 | — |

Peak weeks selected from existing phase progression: P4 W3, P5 W2, P6 W2.
Choosing three versus four reps is the implementation within the user's range,
not a separately user-specified exact allocation. Full reset/recovery and quality
stop rules retained; no extra sets or taper increases. P6 remains otherwise
provisional. This supersedes the historical four-attempts-every-week concern below.

Later A06 scheduling decision supersedes the P2 W5 entries in the table below:
W5 now uses reduced normal Tue/Sat templates, executed Tue Nov 10/Thu Nov 12.
Tuesday has normal broads 1×3; Thursday has approach jumps 1×2 and COD 1×2.
Weighted CMJ and extra pogos no longer occur in the scheduled W5 Tuesday session;
the altitude-drop/Heiden Thursday template is retained but marked unused. Its
unresolved load/height/execution choices are no longer active-week blockers.
P4 Christmas W1 now has Tue Heidens 1×3/leg and triple broads 1×2 sequences
(six jumps), Sat approach jumps 1×2 and COD 1×2, and no Thursday high session.
P3/P4 hop/pogo and P5 drop-jump definitions otherwise remain unchanged.

These latest user choices supersede conflicting pending/historical notes below.
Original P2–5 trackers updated in place; broader thought 6 remains in progress.

| Slot | Adopted exercise / dose |
| --- | --- |
| P2 Tuesday | Normal non-consecutive broad jumps; jump, stick, reset. Existing 2×3/3/4/4 retained. |
| P2 W5 Thursday | Altitude drop-and-stick 2×5 instead of Pogo / Landing; height unspecified. Heiden bounds 2×5/leg instead of snap-down; stick execution retained as P2-style assumption. |
| P2 W5 Tuesday | Weighted CMJ 2×2; external load not supplied, marked TBD. Separate pogos unchanged. |
| P3 Thursday primer | Medium-tier single-leg hops, 1×2–4/leg; preparation only. |
| P3 Thursday altitude drops | Drop-and-stick, no rebound, user-requested 40–50 inches (102–127 cm); existing 2×3 retained. Not described as very low fatigue. |
| P4 Thursday primer | Medium-tier pogos (user calls these Watson's “leaps”); preparation only, W1 omitted, W2–3 1×2–4, W4 1×2. |
| P4 Thursday main rhythmic slot | Pogos with Hurdle; classify as pogos. Existing 3×4, 3×5, 4×4, 2×4 retained. |
| P5 Thursday prep | Submax drop jumps with rebound: 1×6–8 / 1×8–10 / 1×6 complete repetitions. Box height unspecified. |
| P2–3 Thursday reset hurdles | Jump training, not reactive plyos in user's taxonomy; athlete chooses hurdle height. Existing 2×3 retained. |

The 40–50-inch target applies only to P3 altitude landings, not P2 drops or P5
rebound jumps. It is a user-selected target, not medical clearance or an established
safe entry height. Recurrent Achilles symptoms warrant individual assessment and
tolerance-based progression; notes specify stopping/regressing for worsening
symptoms or loss of control. Do not infer safety from the Thursday submax label.
Reference for individualized progressive loading: AOPT/JOSPT 2024 Achilles CPG,
https://www.orthopt.org/uploads/content_files/files/Achilles_Pain_revision_2024.pdf.

The audit's plyometric totals/charts are stale after these changes and now carry
a visible refresh warning. Specific user classifications above are adopted, while
the broader A02 category redesign stays deferred. No GCT measurements inferred.

## Historical audit findings — before latest exercise choices

- P2 low-GCT 0/0/0/0/16; 16 is Tuesday W5 pogos 2×8. Another Thursday W5
  “Pogo / Landing” 2×8 is ambiguous and excluded.
- P3 W1–4 zero assigned low-GCT contacts; W5 unknown, not zero.
- Medium/high-GCT bins count only 2×2 approach jumps/week. Consecutive broads and
  continuous P3 Heidens are grouped with “non-true plyos,” obscuring differences
  from reset jumps. Actual ground contact time was not measured.
- Phase comparisons show peak weeks, not normal build-week exposure.
- Adopted warm-up adds bounds by yardage; exact contacts unknown. See [sprinting](sprinting.md).

## Pending, not adopted

### Adopted notation clarification — 2026-09-26

User defines normal broad jumps as non-consecutive jump-and-stick executions,
and triple broad jumps as three consecutive executions per sequence. User favors
triples as a later-phase elastic progression. Their higher-ground-reaction-force
rationale is the user's rationale, not a measured load comparison in this project.
P3/P4 existing triple-rep slots now explicitly use one rep = three linked jumps,
reset between sequences and stick final landing; bilateral `e` removed, sets and
numeric reps unchanged. No phase reassignment implemented. P2 subsequently
confirmed and changed to normal non-consecutive broads; see latest choices above.
Audit broad counts need recounting for triple sequences; this is flagged in its
method notes. Category decisions (A02) are deferred by user. Vague names are
listed in the latest backlog checkpoint for user classification.

### Thought 6 — in progress, parked for user revisit (2026-09-24)

User requested saving the P2–5 tracker assessment as an in-progress change to
revisit later. No new exercise or dose was approved; spreadsheets remain unchanged.
The [backlog checkpoint](../audit_updates/pending_decisions.md) owns action status.

- P2: reasonable horizontal/lateral landing foundation; regular explicit rhythmic
  rebound preparation is the main gap, not an absence of meaningful jumping.
- P3: continuous Heidens advance beyond P2 stick landings; Thursday's vague
  primer, altitude landings and reset hurdles leave vertical rebound development
  underdefined. Replacing reset hurdles is a candidate, not an adopted change.
- P4: explicit Thursday rhythm/pogos are a positive progression (3×4, 3×5, 4×4,
  2×4). Tuesday returns to stick Heidens; broad-jump instructions remain ambiguous.
  Clarify explosive-output progression and consider horizontal-to-vertical work
  as a replacement for part of existing broad work, not an automatic addition.
- P5: coherent short-contact Tuesday and rhythmic lateral/bilateral Thursday
  work with a Week 3 reduction. Preserve most of the structure; assess Thursday's
  combined jumping, lifting and hard conditioning load before adding volume.
- Approach jumps stay 2×2 weekly across P2–5 build weeks. A more deliberate
  practice/output progression deserves consideration; this small dose is not
  proven ineffective. Ballistic lifting and sprint warm-ups do not substitute
  for evaluating jump-specific development.

Resume with exercise selection, placement, dose, progression and quality criteria.
Consider current Achilles tolerance and stage changes rather than increasing
reactive volume and maximal approach attempts simultaneously. These are assessment
and proposal notes, not medical clearance or implemented programming.

Backlog A01–A03/A07–A11/A14 owns status: regular reactive dose/progression;
execution/intensity/GCT classifications; broad `e` and “Triple rep” ambiguity;
broad reclassification; overlapping approach-jump tag; P4 missing intent split;
literal `23` placeholders. Selected exercises now approved as listed above;
broader dose/progression review remains incomplete.

User proposal for altitude drops: 6 sets/week P2 then 3 P3. Not implemented.
P2 build weeks currently none; P3 2×3 is six landings, not six sets. Review dose
and rationale before editing. Achilles symptoms inform entry/progression but
are neither clearance nor a categorical ban on plyometrics.

## Additional source context — 2026-10-07

THP's six-week-protocol excerpt contains principles and marketing, but no six-week
dose/progression. Its reactive/shock emphasis does not supersede the user's jump
taxonomy or Watson's separate preparatory/deep roles. THP's general-work jump
circuits still contribute jumping exposure. Its individualized athlete symptom
stories and commercial improvement claims establish neither suitable doses nor
clearance for this user's current Achilles symptoms.

See the [source register](training-source-context.md#additional-ratelle-and-thp-transcripts--second-review-2026-10-07)
for exact files, attribution and limits. Reference review only; no programming
changes were adopted or implemented.
