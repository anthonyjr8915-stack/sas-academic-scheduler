# SAS — SSAPS Academic Scheduler

AI-powered academic timetable generation, built as the scheduling core of a future
School ERP. Given classes, teachers, subjects, labs and a rule set, it produces a
**conflict-free, optimized** weekly timetable — or, when none exists, an explanation
of *why*.

This repository implements **Phase 1 (MVP)** of the SRS: Excel import, timetable
generation, conflict detection, and printable/exportable reports.

## Why this is more than a timetable generator

The engine is built on **Google OR-Tools CP-SAT** (constraint programming), so it
searches the real solution space instead of shuffling cells with heuristics. On top
of the SRS, the following were added — see [docs/ENHANCEMENTS.md](docs/ENHANCEMENTS.md):

- **Feasibility diagnosis** — infeasible inputs return *which* teacher/class/lab is
  over-committed, not just "failed".
- **Locked-cell auto-repair** — pin what you like, re-solve only the rest (warm start).
- **Explainable optimization score** — a per-rule points breakdown, powering the
  "AI Rule Explainer".
- **Multi-tenant-ready** data model and **deterministic seeds** for reproducible runs.

## Quick start

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS/Linux

# 1) Generate & print the built-in demo timetable
python -m demo.run_demo

# 2) Run the API
uvicorn app.api.main:app --reload
#   GET  /health
#   GET  /timetable/template        -> download a blank import workbook
#   POST /timetable/generate        -> upload workbook, get JSON timetable
#   POST /timetable/export          -> upload workbook, download formatted .xlsx
#   POST /timetable/generate-demo   -> run the demo, no upload

# 3) Tests
python -m pytest -q
```

## Architecture

```
Excel (import)  ─┐
                 ├─►  Problem (pure data)  ─►  CP-SAT Engine  ─►  Solution ─┬─► JSON API
DB / API (later)─┘         problem.py            engine.py                  ├─► Excel export
                                                                            └─► conflict verifier
```

- `app/scheduler/problem.py` — pure dataclass model of a scheduling problem.
- `app/scheduler/engine.py` — CP-SAT solver: hard constraints, soft objective,
  score explanation, feasibility diagnosis, locked-cell repair.
- `app/scheduler/render.py` — independent conflict verifier + text renderers.
- `app/io/excel.py` — the **only** Excel touchpoint (import/export/template).
- `app/api/main.py` — thin FastAPI surface.
- `demo/` — a realistic small school used by the demo and tests.

**Key decision (from the SRS):** Excel is an *interchange* format only. The system
of record will be PostgreSQL; Excel is imported/exported around it. This keeps
multi-user editing, audit logs, versioning and multi-school SaaS on the table.

## Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Excel import, generation, conflict detection, reports | **In progress (this repo)** |
| 2 | Web dashboard, drag-and-drop editor, scoring, manual locking | Next |
| 3 | Leave management, substitutions, exam scheduler, notifications | Planned |
| 4 | AI assistant, natural-language scheduling, multi-school | Planned |
| 5 | Full ERP (attendance, fees, library, transport, HR, apps) | Planned |

Tech stack (target): Next.js + TS frontend · FastAPI + Celery + Redis backend ·
OR-Tools CP-SAT engine · PostgreSQL · S3/R2 storage · JWT/OAuth/RBAC.
