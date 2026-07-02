"""
FastAPI surface for the scheduling engine.

Kept thin on purpose: parse input -> build `Problem` -> run `TimetableEngine` ->
serialise `Solution`. The DB/ERP layers will slot in behind these same endpoints
later without changing the contract.

Run:  uvicorn app.api.main:app --reload   (from backend/)
"""
from __future__ import annotations

import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session, init_db
from app.io import excel
from app.models.tables import School, TimetableEntry, TimetableVersion
from app.scheduler.engine import Solution, TimetableEngine
from app.scheduler.problem import Problem
from app.services import scheduling
from app.services.seed import seed_demo_school

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="SAS — SSAPS Academic Scheduler",
    version="0.2.0",
    description="AI-powered timetable generation engine with persisted, versioned "
                "timetables (Phase 1–2).",
    lifespan=lifespan,
)


def solution_to_dict(problem: Problem, solution: Solution) -> dict:
    grid = problem.grid
    return {
        "status": solution.status,
        "ok": solution.ok,
        "solve_seconds": solution.solve_seconds,
        "score": solution.score,
        "score_breakdown": [
            {"rule": s.rule, "points": s.points, "detail": s.detail}
            for s in solution.score_breakdown
        ],
        "diagnosis": solution.diagnosis,
        "placements": [
            {
                "lesson_id": p.lesson_id,
                "class_id": p.klass_id,
                "subject": p.subject,
                "teacher_id": p.teacher_id,
                "start_slot": p.start_slot,
                "day": grid.day_of(p.start_slot),
                "period": grid.period_of(p.start_slot),
                "length": p.length,
                "lab_kind": p.lab_kind,
            }
            for p in solution.placements
        ],
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "sas-scheduler"}


@app.post("/timetable/generate-demo")
def generate_demo() -> JSONResponse:
    """Generate the built-in demo timetable — no upload needed. Great for smoke tests."""
    from demo.demo_data import build_problem

    problem = build_problem()
    problem.config.max_seconds = 10.0
    solution = TimetableEngine(problem).solve()
    return JSONResponse(solution_to_dict(problem, solution))


@app.post("/timetable/generate")
async def generate(file: UploadFile = File(...)) -> JSONResponse:
    """Upload a filled import workbook; get the generated timetable as JSON."""
    problem = await _problem_from_upload(file)
    solution = TimetableEngine(problem).solve()
    return JSONResponse(solution_to_dict(problem, solution))


@app.post("/timetable/export")
async def export(file: UploadFile = File(...)) -> FileResponse:
    """Upload an import workbook; download a formatted timetable workbook."""
    problem = await _problem_from_upload(file)
    solution = TimetableEngine(problem).solve()
    out = Path(tempfile.gettempdir()) / "sas_timetable.xlsx"
    excel.write_solution(problem, solution, out)
    return FileResponse(out, filename="timetable.xlsx",
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/timetable/template")
def template() -> FileResponse:
    """Download a blank import workbook showing the expected format."""
    out = Path(tempfile.gettempdir()) / "sas_template.xlsx"
    excel.write_template(out)
    return FileResponse(out, filename="sas_import_template.xlsx",
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


async def _problem_from_upload(file: UploadFile) -> Problem:
    data = await file.read()
    tmp = Path(tempfile.gettempdir()) / "sas_upload.xlsx"
    tmp.write_bytes(data)
    return excel.read_problem(tmp)


# ===========================================================================
# Persisted, versioned timetables (DB-backed)
# ===========================================================================
class GenerateRequest(BaseModel):
    label: str = "draft"
    seed: int = 42
    max_seconds: float = 20.0


class RepairRequest(BaseModel):
    unlock: list[str] = []           # lesson ids to free; everything else stays pinned
    max_seconds: float = 20.0


def _version_summary(v: TimetableVersion) -> dict:
    return {
        "id": v.id, "school_id": v.school_id, "label": v.label, "status": v.status,
        "solver_status": v.solver_status, "score": v.score, "seed": v.seed,
        "solve_seconds": v.solve_seconds, "created_at": v.created_at.isoformat(),
    }


@app.post("/schools/seed-demo")
def seed_demo(session: Session = Depends(get_session)) -> dict:
    """Create a ready-to-schedule demo school; returns its id."""
    sid = seed_demo_school(session)
    return {"school_id": sid, "message": "Demo school seeded. POST /schools/{id}/generate next."}


@app.get("/schools")
def list_schools(session: Session = Depends(get_session)) -> list[dict]:
    schools = session.exec(select(School)).all()
    return [{"id": s.id, "name": s.name} for s in schools]


@app.post("/schools/{school_id}/generate")
def generate_for_school(school_id: int, req: GenerateRequest = GenerateRequest(),
                        session: Session = Depends(get_session)) -> JSONResponse:
    """Generate a timetable for a school and persist it as a new version."""
    if session.get(School, school_id) is None:
        raise HTTPException(404, f"School {school_id} not found")
    version, solution = scheduling.generate_version(
        session, school_id, label=req.label, seed=req.seed, max_seconds=req.max_seconds)
    if version is None:
        return JSONResponse(status_code=422, content={
            "ok": False, "status": solution.status, "diagnosis": solution.diagnosis})
    return JSONResponse({
        "ok": True, "version": _version_summary(version),
        "score_breakdown": [
            {"rule": s.rule, "points": s.points, "detail": s.detail}
            for s in solution.score_breakdown],
    })


@app.get("/schools/{school_id}/versions")
def list_versions(school_id: int, session: Session = Depends(get_session)) -> list[dict]:
    versions = session.exec(
        select(TimetableVersion)
        .where(TimetableVersion.school_id == school_id)
        .order_by(TimetableVersion.created_at.desc())
    ).all()
    return [_version_summary(v) for v in versions]


@app.get("/versions/{version_id}")
def get_version(version_id: int, session: Session = Depends(get_session)) -> dict:
    version = session.get(TimetableVersion, version_id)
    if version is None:
        raise HTTPException(404, f"Version {version_id} not found")
    school = session.get(School, version.school_id)
    days = [d.strip() for d in school.days_csv.split(",")]
    ppd = school.periods_per_day
    entries = session.exec(
        select(TimetableEntry).where(TimetableEntry.version_id == version_id)
    ).all()
    return {
        "version": _version_summary(version),
        "grid": {"days": days, "periods_per_day": ppd},
        "entries": [
            {
                "class_id": e.klass_code, "subject": e.subject,
                "teacher_id": e.teacher_code, "start_slot": e.start_slot,
                "day": e.start_slot // ppd, "period": e.start_slot % ppd,
                "length": e.length, "lab_kind": e.lab_kind,
            }
            for e in entries
        ],
    }


@app.post("/versions/{version_id}/publish")
def publish(version_id: int, session: Session = Depends(get_session)) -> dict:
    try:
        version = scheduling.publish_version(session, version_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"ok": True, "version": _version_summary(version)}


@app.post("/versions/{version_id}/repair")
def repair(version_id: int, req: RepairRequest = RepairRequest(),
           session: Session = Depends(get_session)) -> JSONResponse:
    """Auto-repair: re-solve, keeping every cell pinned except `unlock`. Saves a
    new version so the original is never mutated."""
    try:
        version, solution = scheduling.repair_version(
            session, version_id, unlock=set(req.unlock), max_seconds=req.max_seconds)
    except ValueError as e:
        raise HTTPException(404, str(e))
    if version is None:
        return JSONResponse(status_code=422, content={
            "ok": False, "status": solution.status, "diagnosis": solution.diagnosis})
    return JSONResponse({"ok": True, "version": _version_summary(version)})
