"""
FastAPI surface for the scheduling engine.

Kept thin on purpose: parse input -> build `Problem` -> run `TimetableEngine` ->
serialise `Solution`. The DB/ERP layers will slot in behind these same endpoints
later without changing the contract.

Run:  uvicorn app.api.main:app --reload   (from backend/)
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.io import excel
from app.scheduler.engine import Solution, TimetableEngine
from app.scheduler.problem import Problem

app = FastAPI(
    title="SAS — SSAPS Academic Scheduler",
    version="0.1.0",
    description="AI-powered timetable generation engine (Phase 1 MVP).",
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
