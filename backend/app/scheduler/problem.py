"""
Problem model for the timetabling engine.

This is a *pure data* description of a scheduling problem. It has no dependency
on the database or the web layer, so the solver can be unit-tested and reused
from a CLI, a Celery worker, or an API request identically.

Terminology
-----------
Slot      A single (day, period) cell in the grid. Slots are numbered
          0..(days*periods - 1) in row-major order (day-major).
Lesson    One atomic teaching unit that must be placed: a given class is taught
          a given subject by a given teacher for `length` consecutive periods.
          A subject that meets 5x/week produces 5 single lessons (or e.g. one
          double + three singles if the subject is configured for a double).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Preference(str, Enum):
    """Time-of-day placement preference for a subject."""

    NONE = "none"
    MORNING = "morning"
    AFTERNOON = "afternoon"


@dataclass(frozen=True)
class TimeGrid:
    """The shape of the week: which days, how many periods, and slot geometry."""

    days: list[str]              # e.g. ["Mon", "Tue", ... , "Sat"]
    periods_per_day: int         # teaching periods per day (excludes breaks)

    @property
    def num_days(self) -> int:
        return len(self.days)

    @property
    def num_slots(self) -> int:
        return self.num_days * self.periods_per_day

    def slot(self, day: int, period: int) -> int:
        return day * self.periods_per_day + period

    def day_of(self, slot: int) -> int:
        return slot // self.periods_per_day

    def period_of(self, slot: int) -> int:
        return slot % self.periods_per_day

    def slots_on_day(self, day: int) -> list[int]:
        base = day * self.periods_per_day
        return list(range(base, base + self.periods_per_day))

    def is_morning(self, slot: int) -> bool:
        # First half of the teaching day counts as "morning".
        return self.period_of(slot) < (self.periods_per_day + 1) // 2


@dataclass
class Teacher:
    id: str
    name: str
    # Slots the teacher is NOT available (leave, part-time, other duties).
    unavailable_slots: set[int] = field(default_factory=set)
    max_periods_per_day: int | None = None
    # Slots the teacher would *prefer* to teach (soft bonus).
    preferred_slots: set[int] = field(default_factory=set)


@dataclass
class Klass:
    """A class-section, e.g. 'IX-A'. Named Klass to avoid the `class` keyword."""

    id: str
    name: str
    # Slots blocked for this class (assembly, sports, lunch handled globally).
    blocked_slots: set[int] = field(default_factory=set)
    # Optional: id of the teacher who should get this class's first period.
    class_teacher_id: str | None = None


@dataclass
class LabPool:
    """A shared, capacity-limited resource, e.g. 'physics_lab' with 2 rooms."""

    kind: str
    capacity: int


@dataclass
class Lesson:
    """One placeable teaching unit. Teacher is pre-allocated (as real schools do)."""

    id: str
    klass_id: str
    subject: str
    teacher_id: str
    length: int = 1                       # consecutive periods (1 = single, 2 = double)
    lab_kind: str | None = None           # required lab pool, if any
    preference: Preference = Preference.NONE


@dataclass
class SolverConfig:
    """Tunables that don't change the problem, only how we solve/score it."""

    max_seconds: float = 20.0
    random_seed: int = 42
    workers: int = 8
    # Soft-constraint weights (see engine for how each is applied).
    w_preferred_time: int = 8
    w_teacher_preferred_slot: int = 6
    w_spread_same_subject: int = 15       # penalty for same subject twice in a day
    w_teacher_gap: int = 3                # penalty per idle gap in a teacher's day
    w_class_teacher_first: int = 12       # bonus for class teacher in period 0


@dataclass
class Problem:
    grid: TimeGrid
    teachers: list[Teacher]
    classes: list[Klass]
    lessons: list[Lesson]
    lab_pools: list[LabPool] = field(default_factory=list)
    # Slots blocked for *everyone* (school assembly, common lunch).
    global_blocked_slots: set[int] = field(default_factory=set)
    # Assignments the user has locked (lesson_id -> start_slot). Honoured as hard
    # constraints; this is what powers incremental "auto-repair" re-solves.
    locked: dict[str, int] = field(default_factory=dict)
    config: SolverConfig = field(default_factory=SolverConfig)

    # --- convenience lookups -------------------------------------------------
    def teacher(self, tid: str) -> Teacher:
        return next(t for t in self.teachers if t.id == tid)

    def klass(self, cid: str) -> Klass:
        return next(c for c in self.classes if c.id == cid)

    def lab_capacity(self, kind: str) -> int:
        return next((p.capacity for p in self.lab_pools if p.kind == kind), 0)
