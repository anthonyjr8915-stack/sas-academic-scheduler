"""
Persistence schema — the system of record (SRS: PostgreSQL, not Excel).

Multi-tenant from day one: every domain row carries `school_id`, so multi-campus
and SaaS are structural rather than a later migration. Human-facing identifiers
used by the engine (e.g. "t_maths", "IX_A") live in the `code` columns and are
unique *within* a school; database primary keys stay integer surrogates.

Timetables are versioned: each generation produces a `TimetableVersion` snapshot
with its own entries, score and seed, so publishing, rollback and "why did this
change?" diffs all work.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class School(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    days_csv: str = "Mon,Tue,Wed,Thu,Fri"
    periods_per_day: int = 7
    lunch_period: int | None = 4          # 1-based; None = no fixed lunch slot
    assembly_mon: bool = True             # block Monday period 1 for assembly
    created_at: datetime = Field(default_factory=_now)


class Teacher(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    school_id: int = Field(index=True, foreign_key="school.id")
    code: str = Field(index=True)         # engine id, unique per school
    name: str
    max_per_day: int | None = None
    unavailable_days_csv: str = ""        # e.g. "Thu,Fri"


class Klass(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    school_id: int = Field(index=True, foreign_key="school.id")
    code: str = Field(index=True)
    name: str
    class_teacher_code: str | None = None


class LabPool(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    school_id: int = Field(index=True, foreign_key="school.id")
    kind: str
    capacity: int = 1


class PlanItem(SQLModel, table=True):
    """One line of the weekly teaching plan: a class needs `subject` for
    `per_week` periods from `teacher_code`, with `double_blocks` of them doubled."""

    id: int | None = Field(default=None, primary_key=True)
    school_id: int = Field(index=True, foreign_key="school.id")
    klass_code: str = Field(index=True)
    subject: str
    teacher_code: str
    per_week: int
    double_blocks: int = 0
    lab_kind: str | None = None
    preference: str = "none"              # none | morning | afternoon


class TimetableVersion(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    school_id: int = Field(index=True, foreign_key="school.id")
    label: str = "draft"
    status: str = "draft"                 # draft | published
    solver_status: str = ""               # OPTIMAL | FEASIBLE | INFEASIBLE | UNKNOWN
    score: int = 0
    seed: int = 42
    solve_seconds: float = 0.0
    created_at: datetime = Field(default_factory=_now)


class TimetableEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    version_id: int = Field(index=True, foreign_key="timetableversion.id")
    lesson_id: str = Field(index=True)   # engine lesson id; used for locked-cell repair
    klass_code: str = Field(index=True)
    subject: str
    teacher_code: str = Field(index=True)
    start_slot: int
    length: int = 1
    lab_kind: str | None = None
