"""Engine guarantees: conflict-free output, feasibility diagnosis, and locked-cell
repair. These are the properties the whole product rests on, so they're tested
directly against the independent verifier (not the solver's own bookkeeping)."""
from __future__ import annotations

import copy

from app.scheduler.engine import TimetableEngine
from app.scheduler.problem import Lesson, Teacher
from app.scheduler.render import verify
from demo.demo_data import build_problem


def _solve(problem):
    problem.config.max_seconds = 15.0
    return TimetableEngine(problem).solve()


def test_demo_is_solvable_and_conflict_free():
    problem = build_problem()
    solution = _solve(problem)
    assert solution.ok, solution.diagnosis
    # Every lesson is placed exactly once.
    assert len(solution.placements) == len(problem.lessons)
    # No hard-constraint violations, per the independent verifier.
    assert verify(problem, solution) == []


def test_breaks_are_respected():
    problem = build_problem()
    solution = _solve(problem)
    blocked = problem.global_blocked_slots
    for pl in solution.placements:
        span = {pl.start_slot + k for k in range(pl.length)}
        assert span.isdisjoint(blocked), f"{pl.lesson_id} lands on a break"


def test_doubles_stay_within_one_day():
    problem = build_problem()
    solution = _solve(problem)
    per_day = problem.grid.periods_per_day
    for pl in solution.placements:
        if pl.length == 2:
            assert pl.start_slot // per_day == (pl.start_slot + 1) // per_day


def test_overcommitted_teacher_is_diagnosed():
    problem = build_problem()
    # One teacher, one class, more lesson-periods than slots in the week.
    problem.teachers = [Teacher(id="solo", name="Solo")]
    problem.classes = problem.classes[:1]
    cid = problem.classes[0].id
    problem.classes[0].class_teacher_id = "solo"
    problem.lessons = [
        Lesson(id=f"L{i}", klass_id=cid, subject="X", teacher_id="solo")
        for i in range(problem.grid.num_slots + 5)
    ]
    solution = _solve(problem)
    assert not solution.ok
    assert any("over" in d.lower() for d in solution.diagnosis)


def test_locked_cells_are_honoured_for_repair():
    problem = build_problem()
    base = _solve(problem)
    assert base.ok
    # Lock every placement except one subject, then re-solve: locked stays put.
    repair = copy.deepcopy(problem)
    repair.locked = {
        pl.lesson_id: pl.start_slot
        for pl in base.placements
        if pl.subject != "Social"
    }
    resolved = _solve(repair)
    assert resolved.ok
    placed = {pl.lesson_id: pl.start_slot for pl in resolved.placements}
    for lid, slot in repair.locked.items():
        assert placed[lid] == slot, f"locked {lid} moved"
