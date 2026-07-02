"""End-to-end demo: build a school, generate a timetable, verify, and print it.

Run from the backend/ directory:
    python -m demo.run_demo
"""
from __future__ import annotations

from app.scheduler.engine import TimetableEngine
from app.scheduler.render import class_grid, score_report, teacher_grid, verify
from demo.demo_data import build_problem


def main() -> None:
    problem = build_problem()
    print(f"Lessons to place: {len(problem.lessons)}  "
          f"(classes={len(problem.classes)}, teachers={len(problem.teachers)}, "
          f"slots={problem.grid.num_slots})\n")

    solution = TimetableEngine(problem).solve()
    print(f"Solver status: {solution.status}  ({solution.solve_seconds}s)\n")

    if not solution.ok:
        print("Could not generate a timetable. Diagnosis:")
        for line in solution.diagnosis:
            print(f"  - {line}")
        return

    conflicts = verify(problem, solution)
    print("Conflict check:", "CLEAN [OK]" if not conflicts else f"{len(conflicts)} ISSUES [X]")
    for c in conflicts:
        print("  !", c)
    print()

    for klass in problem.classes:
        print(class_grid(problem, solution, klass.id))
        print()

    print(teacher_grid(problem, solution, "t_maths"))
    print()
    print(score_report(solution))


if __name__ == "__main__":
    main()
