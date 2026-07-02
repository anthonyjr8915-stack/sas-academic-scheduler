"""
CP-SAT timetabling engine — the heart of the platform.

Given a `Problem`, it produces a conflict-free `Solution` (or an infeasibility
diagnosis explaining which requirements can't be satisfied). It also computes an
explainable optimization-score breakdown so the UI can tell an admin *why* a
timetable scored what it did.

Design choices worth knowing:
* Teachers are pre-allocated to lessons, so the only decision per lesson is *when*
  it happens (its start slot). This matches how schools actually assign staff and
  keeps the model small and fast.
* Block lengths (doubles) are handled with start-slot variables + an occupancy
  map, so class/teacher/lab resources are reserved for every period a block spans.
* Locked lessons are pinned as hard constraints — that is exactly what makes
  incremental "auto-repair" re-solves cheap: pin everything the user kept, let the
  solver move only the rest.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from .problem import Preference, Problem


@dataclass
class Placement:
    lesson_id: str
    klass_id: str
    subject: str
    teacher_id: str
    start_slot: int
    length: int
    lab_kind: str | None


@dataclass
class ScoreLine:
    rule: str
    points: int
    detail: str


@dataclass
class Solution:
    status: str                       # OPTIMAL | FEASIBLE | INFEASIBLE | UNKNOWN
    placements: list[Placement] = field(default_factory=list)
    score: int = 0
    score_breakdown: list[ScoreLine] = field(default_factory=list)
    # Populated only when status == INFEASIBLE.
    diagnosis: list[str] = field(default_factory=list)
    solve_seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.status in ("OPTIMAL", "FEASIBLE")


def _valid_starts(problem: Problem, lesson) -> list[int]:
    """Start slots where a block of `lesson.length` fits within one day and is
    not blocked for the class, the teacher, or the whole school."""
    grid = problem.grid
    klass = problem.klass(lesson.klass_id)
    teacher = problem.teacher(lesson.teacher_id)
    blocked = problem.global_blocked_slots | klass.blocked_slots | teacher.unavailable_slots
    starts: list[int] = []
    for day in range(grid.num_days):
        day_slots = grid.slots_on_day(day)
        for i in range(len(day_slots) - lesson.length + 1):
            span = day_slots[i : i + lesson.length]
            if all(s not in blocked for s in span):
                starts.append(span[0])
    return starts


def _span(problem: Problem, start_slot: int, length: int) -> list[int]:
    return [start_slot + k for k in range(length)]


class TimetableEngine:
    def __init__(self, problem: Problem):
        self.p = problem

    # ------------------------------------------------------------------ solve
    def solve(self) -> Solution:
        p = self.p
        model = cp_model.CpModel()

        # start[lesson][slot] = 1  <=>  lesson begins at slot
        start: dict[str, dict[int, cp_model.IntVar]] = {}
        valid: dict[str, list[int]] = {}
        for lesson in p.lessons:
            starts = _valid_starts(p, lesson)
            valid[lesson.id] = starts
            if not starts:
                # No feasible slot exists at all -> report before even solving.
                return self._infeasible_no_slot(lesson)
            vars_ = {s: model.NewBoolVar(f"s_{lesson.id}_{s}") for s in starts}
            start[lesson.id] = vars_
            model.AddExactlyOne(vars_.values())

            # Honour locks (pin the lesson) — powers incremental repair.
            if lesson.id in p.locked:
                pinned = p.locked[lesson.id]
                if pinned not in vars_:
                    return Solution(
                        status="INFEASIBLE",
                        diagnosis=[
                            f"Locked lesson {lesson.id} is pinned to slot {pinned}, "
                            f"which is blocked or off-grid."
                        ],
                    )
                model.Add(vars_[pinned] == 1)

        # occ[lesson][slot] — does the lesson occupy this slot (for blocks)?
        def occ(lesson_id: str, slot: int) -> list[cp_model.IntVar]:
            """Return the start vars that cause `lesson_id` to occupy `slot`."""
            lesson = next(l for l in p.lessons if l.id == lesson_id)
            out = []
            for s in valid[lesson_id]:
                if slot in _span(p, s, lesson.length):
                    out.append(start[lesson_id][s])
            return out

        grid = p.grid

        # --- HARD: a class does at most one thing per slot ---------------------
        for klass in p.classes:
            klass_lessons = [l for l in p.lessons if l.klass_id == klass.id]
            for slot in range(grid.num_slots):
                occupying = []
                for l in klass_lessons:
                    occupying += occ(l.id, slot)
                if occupying:
                    model.Add(sum(occupying) <= 1)

        # --- HARD: a teacher does at most one thing per slot ------------------
        for teacher in p.teachers:
            t_lessons = [l for l in p.lessons if l.teacher_id == teacher.id]
            for slot in range(grid.num_slots):
                occupying = []
                for l in t_lessons:
                    occupying += occ(l.id, slot)
                if occupying:
                    model.Add(sum(occupying) <= 1)

        # --- HARD: lab pools are capacity-limited per slot --------------------
        for pool in p.lab_pools:
            pool_lessons = [l for l in p.lessons if l.lab_kind == pool.kind]
            for slot in range(grid.num_slots):
                occupying = []
                for l in pool_lessons:
                    occupying += occ(l.id, slot)
                if occupying:
                    model.Add(sum(occupying) <= pool.capacity)

        # --- HARD: teacher max periods/day ------------------------------------
        for teacher in p.teachers:
            if teacher.max_periods_per_day is None:
                continue
            t_lessons = [l for l in p.lessons if l.teacher_id == teacher.id]
            for day in range(grid.num_days):
                load = []
                for slot in grid.slots_on_day(day):
                    for l in t_lessons:
                        load += occ(l.id, slot)
                if load:
                    model.Add(sum(load) <= teacher.max_periods_per_day)

        # --- SOFT: build the objective ----------------------------------------
        terms = self._build_objective(model, start, valid, occ)
        model.Maximize(sum(terms))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = p.config.max_seconds
        solver.parameters.random_seed = p.config.random_seed
        solver.parameters.num_search_workers = p.config.workers
        status = solver.Solve(model)

        return self._extract(solver, status, start, valid)

    # ---------------------------------------------------------------- objective
    def _build_objective(self, model, start, valid, occ):
        """Return a list of weighted BoolVar terms; also records which term maps
        to which rule so we can explain the score afterwards."""
        p = self.p
        grid = p.grid
        cfg = p.config
        self._score_terms: list[tuple[str, int, cp_model.IntVar]] = []
        terms = []

        def add(rule: str, weight: int, var):
            self._score_terms.append((rule, weight, var))
            terms.append(weight * var)

        # Subject time-of-day preference + teacher preferred slots.
        for lesson in p.lessons:
            for s in valid[lesson.id]:
                var = start[lesson.id][s]
                if lesson.preference == Preference.MORNING and grid.is_morning(s):
                    add("preferred_time", cfg.w_preferred_time, var)
                elif lesson.preference == Preference.AFTERNOON and not grid.is_morning(s):
                    add("preferred_time", cfg.w_preferred_time, var)
                if s in p.teacher(lesson.teacher_id).preferred_slots:
                    add("teacher_preferred_slot", cfg.w_teacher_preferred_slot, var)

        # Class teacher in first period (soft bonus).
        for klass in p.classes:
            if not klass.class_teacher_id:
                continue
            first_slots = {grid.slot(d, 0) for d in range(grid.num_days)}
            for lesson in p.lessons:
                if lesson.klass_id != klass.id or lesson.teacher_id != klass.class_teacher_id:
                    continue
                for s in valid[lesson.id]:
                    if s in first_slots:
                        add("class_teacher_first", cfg.w_class_teacher_first,
                            start[lesson.id][s])

        # Spread: penalise the same subject appearing twice in one class-day.
        for klass in p.classes:
            subjects = {l.subject for l in p.lessons if l.klass_id == klass.id}
            for subject in subjects:
                subj_lessons = [
                    l for l in p.lessons if l.klass_id == klass.id and l.subject == subject
                ]
                if len(subj_lessons) < 2:
                    continue
                for day in range(grid.num_days):
                    day_slots = set(grid.slots_on_day(day))
                    count_terms = []
                    for l in subj_lessons:
                        for s in valid[l.id]:
                            if s in day_slots:
                                count_terms.append(start[l.id][s])
                    if len(count_terms) < 2:
                        continue
                    # extra = max(0, (#same-subject-that-day) - 1)
                    extra = model.NewIntVar(0, len(count_terms), f"extra_{klass.id}_{subject}_{day}")
                    model.Add(extra >= sum(count_terms) - 1)
                    self._score_terms.append(("spread_same_subject", -cfg.w_spread_same_subject, extra))
                    terms.append(-cfg.w_spread_same_subject * extra)

        # Teacher idle-gap minimisation, per teacher per day.
        for teacher in p.teachers:
            t_lessons = [l for l in p.lessons if l.teacher_id == teacher.id]
            if not t_lessons:
                continue
            for day in range(grid.num_days):
                day_slots = grid.slots_on_day(day)
                busy = {}
                for slot in day_slots:
                    occupying = []
                    for l in t_lessons:
                        occupying += occ(l.id, slot)
                    b = model.NewBoolVar(f"busy_{teacher.id}_{slot}")
                    if occupying:
                        model.Add(b == sum(occupying))  # occupying is 0/1 by class-overlap constraints
                    else:
                        model.Add(b == 0)
                    busy[slot] = b
                # gaps = (#busy periods spanned) - (#busy periods); penalise span holes.
                # Approximate with adjacent "hole" indicators: hole if idle between two busy.
                for i in range(1, len(day_slots) - 1):
                    prev_b, cur_b, next_b = busy[day_slots[i - 1]], busy[day_slots[i]], busy[day_slots[i + 1]]
                    hole = model.NewBoolVar(f"hole_{teacher.id}_{day_slots[i]}")
                    # hole => prev busy AND next busy AND current idle
                    model.Add(hole <= prev_b)
                    model.Add(hole <= next_b)
                    model.Add(hole <= 1 - cur_b)
                    model.Add(hole >= prev_b + next_b + (1 - cur_b) - 2)
                    self._score_terms.append(("teacher_gap", -cfg.w_teacher_gap, hole))
                    terms.append(-cfg.w_teacher_gap * hole)

        return terms

    # ------------------------------------------------------------------ extract
    def _extract(self, solver, status, start, valid) -> Solution:
        status_name = solver.StatusName(status)
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            placements = []
            for lesson in self.p.lessons:
                for s in valid[lesson.id]:
                    if solver.Value(start[lesson.id][s]) == 1:
                        placements.append(
                            Placement(
                                lesson_id=lesson.id,
                                klass_id=lesson.klass_id,
                                subject=lesson.subject,
                                teacher_id=lesson.teacher_id,
                                start_slot=s,
                                length=lesson.length,
                                lab_kind=lesson.lab_kind,
                            )
                        )
                        break
            breakdown = self._explain_score(solver)
            total = sum(line.points for line in breakdown)
            return Solution(
                status="OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
                placements=placements,
                score=total,
                score_breakdown=breakdown,
                solve_seconds=round(solver.WallTime(), 3),
            )
        return Solution(
            status="INFEASIBLE" if status == cp_model.INFEASIBLE else "UNKNOWN",
            diagnosis=self._diagnose() if status == cp_model.INFEASIBLE else
            ["Solver hit the time limit without proving a result. "
             "Try raising SolverConfig.max_seconds."],
            solve_seconds=round(solver.WallTime(), 3),
        )

    def _explain_score(self, solver) -> list[ScoreLine]:
        """Aggregate the achieved objective terms by rule for the UI."""
        agg: dict[str, int] = {}
        for rule, weight, var in self._score_terms:
            val = solver.Value(var)
            if val:
                agg[rule] = agg.get(rule, 0) + weight * val
        details = {
            "preferred_time": "Subjects placed in their preferred half of the day",
            "teacher_preferred_slot": "Teachers teaching in slots they prefer",
            "class_teacher_first": "Class teacher takes the first period",
            "spread_same_subject": "Penalty: same subject repeated within a day",
            "teacher_gap": "Penalty: idle gaps in a teacher's day",
        }
        return [
            ScoreLine(rule=rule, points=pts, detail=details.get(rule, rule))
            for rule, pts in sorted(agg.items(), key=lambda kv: -abs(kv[1]))
        ]

    # --------------------------------------------------------------- diagnosis
    def _infeasible_no_slot(self, lesson) -> Solution:
        klass = self.p.klass(lesson.klass_id)
        teacher = self.p.teacher(lesson.teacher_id)
        return Solution(
            status="INFEASIBLE",
            diagnosis=[
                f"Lesson '{lesson.id}' ({klass.name} · {lesson.subject} · {teacher.name}) "
                f"has no valid slot: every period is blocked for the class, the teacher, "
                f"or the whole school (block length = {lesson.length})."
            ],
        )

    def _diagnose(self) -> list[str]:
        """Cheap structural feasibility checks that explain common infeasibilities
        without needing the solver's internal cores."""
        p = self.p
        grid = p.grid
        out: list[str] = []

        # Per-teacher demand vs. available slots.
        for teacher in p.teachers:
            demand = sum(l.length for l in p.lessons if l.teacher_id == teacher.id)
            avail = grid.num_slots - len(
                p.global_blocked_slots | teacher.unavailable_slots
            )
            if demand > avail:
                out.append(
                    f"Teacher {teacher.name} is over-committed: {demand} periods of "
                    f"lessons but only {avail} available slots."
                )

        # Per-class demand vs. available slots.
        for klass in p.classes:
            demand = sum(l.length for l in p.lessons if l.klass_id == klass.id)
            avail = grid.num_slots - len(p.global_blocked_slots | klass.blocked_slots)
            if demand > avail:
                out.append(
                    f"Class {klass.name} is over-subscribed: {demand} periods required "
                    f"but only {avail} teaching slots available."
                )

        # Lab pool pressure (rough upper bound).
        for pool in p.lab_pools:
            demand = sum(l.length for l in p.lessons if l.lab_kind == pool.kind)
            capacity = pool.capacity * grid.num_slots
            if demand > capacity:
                out.append(
                    f"Lab '{pool.kind}' is over-booked: {demand} lab-periods needed but "
                    f"capacity is {capacity} ({pool.capacity} rooms × {grid.num_slots} slots)."
                )

        if not out:
            out.append(
                "No timetable satisfies all hard constraints. The demand fits in "
                "aggregate, so the conflict is structural (e.g. two classes need the "
                "same teacher at the only slot both are free). Try relaxing teacher "
                "availability or lab capacity."
            )
        return out
