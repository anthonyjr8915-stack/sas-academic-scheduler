"""Translate persisted rows into a solver `Problem` and back into entry rows.

This is the seam between the database and the pure engine: the engine never sees
SQLModel, and the tables never see CP-SAT.
"""
from __future__ import annotations

from sqlmodel import Session, select

from app.models.tables import (
    Klass as KlassRow,
    LabPool as LabRow,
    PlanItem,
    School,
    Teacher as TeacherRow,
    TimetableEntry,
)
from app.scheduler.engine import Solution
from app.scheduler.problem import (
    Klass,
    LabPool,
    Lesson,
    Preference,
    Problem,
    SolverConfig,
    Teacher,
    TimeGrid,
)


def build_problem(session: Session, school_id: int, *, seed: int = 42,
                  max_seconds: float = 20.0,
                  locked: dict[str, int] | None = None) -> Problem:
    school = session.get(School, school_id)
    if school is None:
        raise ValueError(f"School {school_id} not found")

    days = [d.strip() for d in school.days_csv.split(",")]
    grid = TimeGrid(days=days, periods_per_day=school.periods_per_day)
    day_index = {name.lower(): i for i, name in enumerate(days)}

    global_blocked: set[int] = set()
    if school.lunch_period:
        lp = school.lunch_period - 1
        global_blocked |= {grid.slot(d, lp) for d in range(grid.num_days)}
    if school.assembly_mon:
        global_blocked |= {grid.slot(0, 0)}

    def rows(model):
        return session.exec(select(model).where(model.school_id == school_id)).all()

    teachers = []
    for t in rows(TeacherRow):
        unavailable: set[int] = set()
        for tok in t.unavailable_days_csv.split(","):
            d = day_index.get(tok.strip().lower())
            if d is not None:
                unavailable |= set(grid.slots_on_day(d))
        teachers.append(Teacher(id=t.code, name=t.name,
                                max_periods_per_day=t.max_per_day,
                                unavailable_slots=unavailable))

    classes = [Klass(id=c.code, name=c.name, class_teacher_id=c.class_teacher_code)
               for c in rows(KlassRow)]
    lab_pools = [LabPool(kind=l.kind, capacity=l.capacity) for l in rows(LabRow)]

    lessons: list[Lesson] = []
    for p in rows(PlanItem):
        n, idx = p.per_week, 0
        pref = Preference(p.preference)
        for _ in range(p.double_blocks):
            if n >= 2:
                lessons.append(Lesson(id=f"{p.klass_code}_{p.subject}_{idx}",
                                      klass_id=p.klass_code, subject=p.subject,
                                      teacher_id=p.teacher_code, length=2,
                                      lab_kind=p.lab_kind, preference=pref))
                n -= 2
                idx += 1
        for _ in range(n):
            lessons.append(Lesson(id=f"{p.klass_code}_{p.subject}_{idx}",
                                  klass_id=p.klass_code, subject=p.subject,
                                  teacher_id=p.teacher_code, length=1,
                                  lab_kind=p.lab_kind, preference=pref))
            idx += 1

    return Problem(
        grid=grid, teachers=teachers, classes=classes, lessons=lessons,
        lab_pools=lab_pools, global_blocked_slots=global_blocked,
        locked=locked or {},
        config=SolverConfig(max_seconds=max_seconds, random_seed=seed),
    )


def solution_to_entries(version_id: int, solution: Solution) -> list[TimetableEntry]:
    return [
        TimetableEntry(
            version_id=version_id, lesson_id=pl.lesson_id, klass_code=pl.klass_id,
            subject=pl.subject, teacher_code=pl.teacher_id, start_slot=pl.start_slot,
            length=pl.length, lab_kind=pl.lab_kind,
        )
        for pl in solution.placements
    ]
