# Enhancements over the SRS

The SRS is strong on *features* but thin on the engineering that makes an AI
scheduler trustworthy in production. These additions are either implemented now
(Phase 1) or specified as concrete near-term work.

## Implemented in Phase 1

### 1. Feasibility diagnosis (not just "generation failed")
When no timetable satisfies the hard constraints, the engine returns a plain-language
diagnosis instead of a dead end:
- pre-checks each lesson for *any* legal slot (fails fast with the exact lesson),
- compares per-teacher / per-class demand vs. available slots,
- checks lab-pool pressure across the week.

This is the single biggest real-world pain in timetabling — "it won't generate and
I don't know why." See `engine._diagnose()` and `test_overcommitted_teacher_is_diagnosed`.

### 2. Locked-cell auto-repair (warm start)
The SRS lists "One-click Auto Repair" as a future idea. It's implemented properly:
locked lessons are pinned as hard constraints, so after a manual edit the solver
moves **only** the unlocked lessons. Same code path as full generation — no separate
"repair engine" to keep in sync. See `Problem.locked` and
`test_locked_cells_are_honoured_for_repair`.

### 3. Explainable optimization score
Every soft-constraint term is tagged with the rule it came from, so the final score
ships with a per-rule breakdown (e.g. `+224 preferred_time`, `-90 spread_same_subject`).
This directly powers the SRS's "AI Rule Explainer" and makes tuning weights obvious.
See `engine._explain_score()`.

### 4. Independent conflict verifier
`render.verify()` re-checks the produced timetable against the hard constraints from
scratch — it shares no state with the solver. If the engine ever regresses, tests
catch it. Trust, but verify.

### 5. Deterministic, reproducible runs
`SolverConfig.random_seed` fixes the search seed, so the same input yields the same
timetable. Essential for testing, versioning, and "why did this change?" diffs.

### 6. Rules-as-data & weighted soft constraints
Soft constraints (morning subjects, teacher-preferred slots, subject spread, teacher
gap minimisation, class-teacher-first) are driven by `SolverConfig` weights, not
hard-coded logic — the first step toward the SRS's fully configurable Rule Engine.

## Specified for the next phases

- **Multi-tenancy from day one** — `school_id` / `branch_id` on every entity so
  multi-campus and SaaS are structural, not a later migration. (The SRS defers this.)
- **Automatic timetable versioning** — snapshot on every publish; the deterministic
  seed makes version diffs meaningful.
- **What-if simulator / hiring forecast** — the demand-vs-capacity math already in
  `_diagnose()` generalises directly into "add Section VIII-A → need N more teachers".
- **Multi-campus travel optimisation** — model teacher travel as extra unavailability
  or soft movement penalties on the existing slot grid.
- **Natural-language / voice commands** — an LLM maps "regenerate Class IX only" to a
  partial re-solve (lock everything else, unlock Class IX) over this same engine.

## Explicitly deferred (correctly, per the roadmap)
Fees, payroll, transport, hostel, biometric/CCTV/RFID, mobile apps — Phase 5 ERP
scope. Not blocked by anything in the scheduler core.
