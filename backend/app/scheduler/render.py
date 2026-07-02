"""Human-readable rendering + a post-solve conflict verifier.

The verifier is deliberately independent of the solver: it re-checks the produced
placements against the hard constraints from scratch. If the engine ever regresses,
this catches it — trust, but verify.
"""
from __future__ import annotations

from collections import defaultdict

from .engine import Solution
from .problem import Problem


def verify(problem: Problem, solution: Solution) -> list[str]:
    """Return a list of hard-constraint violations. Empty list == conflict-free."""
    grid = problem.grid
    conflicts: list[str] = []
    class_slot: dict[tuple[str, int], str] = {}
    teacher_slot: dict[tuple[str, int], str] = {}
    lab_load: dict[tuple[str, int], int] = defaultdict(int)

    for pl in solution.placements:
        for k in range(pl.length):
            slot = pl.start_slot + k
            ck = (pl.klass_id, slot)
            if ck in class_slot:
                conflicts.append(
                    f"Class {pl.klass_id} double-booked at slot {slot}: "
                    f"{class_slot[ck]} vs {pl.subject}"
                )
            class_slot[ck] = pl.subject

            tk = (pl.teacher_id, slot)
            if tk in teacher_slot:
                conflicts.append(
                    f"Teacher {pl.teacher_id} double-booked at slot {slot}: "
                    f"{teacher_slot[tk]} vs {pl.klass_id}/{pl.subject}"
                )
            teacher_slot[tk] = f"{pl.klass_id}/{pl.subject}"

            if pl.lab_kind:
                lab_load[(pl.lab_kind, slot)] += 1

    for (kind, slot), load in lab_load.items():
        cap = problem.lab_capacity(kind)
        if load > cap:
            conflicts.append(
                f"Lab '{kind}' over capacity at slot {slot}: {load} > {cap}"
            )
    return conflicts


def class_grid(problem: Problem, solution: Solution, klass_id: str) -> str:
    grid = problem.grid
    cell: dict[int, str] = {}
    for pl in solution.placements:
        if pl.klass_id != klass_id:
            continue
        for k in range(pl.length):
            tag = pl.subject if k == 0 else f"{pl.subject}+"
            cell[pl.start_slot + k] = tag[:9]

    klass = problem.klass(klass_id)
    header = f"  {'Period':<8}" + "".join(f"{d:<11}" for d in grid.days)
    lines = [f"Class {klass.name}", header]
    for period in range(grid.periods_per_day):
        row = f"  P{period + 1:<7}"
        for day in range(grid.num_days):
            slot = grid.slot(day, period)
            if slot in (problem.global_blocked_slots | klass.blocked_slots):
                row += f"{'-break-':<11}"
            else:
                row += f"{cell.get(slot, '.'):<11}"
        lines.append(row)
    return "\n".join(lines)


def teacher_grid(problem: Problem, solution: Solution, teacher_id: str) -> str:
    grid = problem.grid
    cell: dict[int, str] = {}
    for pl in solution.placements:
        if pl.teacher_id != teacher_id:
            continue
        for k in range(pl.length):
            cell[pl.start_slot + k] = f"{pl.klass_id}:{pl.subject}"[:10]

    t = problem.teacher(teacher_id)
    header = f"  {'Period':<8}" + "".join(f"{d:<12}" for d in grid.days)
    lines = [f"Teacher {t.name}", header]
    for period in range(grid.periods_per_day):
        row = f"  P{period + 1:<7}"
        for day in range(grid.num_days):
            slot = grid.slot(day, period)
            row += f"{cell.get(slot, '.'):<12}"
        lines.append(row)
    return "\n".join(lines)


def score_report(solution: Solution) -> str:
    lines = [f"Optimization score: {solution.score}", "  Breakdown:"]
    for line in solution.score_breakdown:
        sign = "+" if line.points >= 0 else ""
        lines.append(f"    {sign}{line.points:>5}  {line.rule:<24} {line.detail}")
    return "\n".join(lines)
