# SAS — SSAPS Academic Scheduler

**Live demo:** https://frontend-six-chi-ap249v5evl.vercel.app · **Repo:** https://github.com/anthonyjr8915-stack/sas-academic-scheduler

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
#   Stateless (Excel in / JSON or Excel out):
#   GET  /health
#   GET  /timetable/template            -> download a blank import workbook
#   POST /timetable/generate            -> upload workbook, get JSON timetable
#   POST /timetable/export              -> upload workbook, download formatted .xlsx
#   POST /timetable/generate-demo       -> run the demo, no upload
#
#   Persisted & versioned (DB-backed):
#   POST /schools/seed-demo             -> create a demo school, returns id
#   POST /schools/{id}/generate         -> solve + save a new timetable version
#   GET  /schools/{id}/versions         -> list versions (score, status, seed)
#   GET  /versions/{id}                 -> version metadata + all entries
#   POST /versions/{id}/publish         -> publish (demotes prior published)
#   POST /versions/{id}/repair          -> auto-repair: re-solve, keep pinned cells

# 3) Tests
python -m pytest -q
```

A typical DB-backed flow: `seed-demo` → `generate` → `publish`; after a manual
change, `repair` with the freed lesson ids re-solves only those cells and saves a
new version, leaving the original untouched. The store defaults to SQLite
(`backend/sas.db`); set `SAS_DATABASE_URL` to a PostgreSQL DSN for production.

## Architecture

```
Excel (import) ─┐                                              ┌─► JSON API
                ├─► Problem (pure data) ─► CP-SAT Engine ─► Solution ─┼─► Excel export
DB (PostgreSQL)─┘        problem.py           engine.py              ├─► conflict verifier
      ▲                                                              │
      └───────────────  versioned snapshots  ──────────────────────┘
```

- `app/scheduler/problem.py` — pure dataclass model of a scheduling problem.
- `app/scheduler/engine.py` — CP-SAT solver: hard constraints, soft objective,
  score explanation, feasibility diagnosis, locked-cell repair.
- `app/scheduler/render.py` — independent conflict verifier + text renderers.
- `app/models/tables.py` — multi-tenant SQLModel schema (system of record).
- `app/db.py` — SQLite (dev) / PostgreSQL (prod) bootstrap via `SAS_DATABASE_URL`.
- `app/services/` — DB↔engine mapping, generation + **versioning** (generate,
  publish, auto-repair), demo seed.
- `app/io/excel.py` — the **only** Excel touchpoint (import/export/template).
- `app/api/main.py` — thin FastAPI surface (stateless + DB-backed endpoints).
- `demo/` — a realistic small school used by the demo and tests.

**Key decision (from the SRS):** Excel is an *interchange* format only. The system
of record will be PostgreSQL; Excel is imported/exported around it. This keeps
multi-user editing, audit logs, versioning and multi-school SaaS on the table.

## Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Excel import, generation, conflict detection, reports | **Done** |
| 2 | Persistence + versioning + REST API · web dashboard & drag-drop editor | **Backend done; UI next** |
| 3 | Leave management, substitutions, exam scheduler, notifications | Planned |
| 4 | AI assistant, natural-language scheduling, multi-school | Planned |
| 5 | Full ERP (attendance, fees, library, transport, HR, apps) | Planned |

Tech stack (target): Next.js + TS frontend · FastAPI + Celery + Redis backend ·
OR-Tools CP-SAT engine · PostgreSQL · S3/R2 storage · JWT/OAuth/RBAC.

## Deployment

- **Frontend → Vercel.** Root Directory = `frontend`. The deployed site renders a
  real engine-generated timetable bundled at build time, so it works with no
  backend. Point it at a live backend by setting `NEXT_PUBLIC_API_URL` in the
  Vercel project's Environment Variables.
- **Backend → not Vercel.** The OR-Tools CP-SAT solver is CPU-heavy and long-running;
  it needs a persistent host (Railway / Render / Fly.io / a VM), not Vercel's
  serverless functions. Deploy `backend/` there and set `SAS_DATABASE_URL` to a
  managed PostgreSQL instance.
- **Redeploy the frontend:** `cd frontend && vercel deploy --prod` (or connect the
  GitHub repo in the Vercel dashboard for automatic deploys on every push to `main`).
