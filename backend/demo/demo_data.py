"""A small but realistic demo school, used by run_demo.py and the tests.

3 classes, ~6 teachers, a shared physics/computer lab, common lunch, an assembly
slot on Monday, subject weekly counts, one double period (Science lab), and a
morning preference for Maths. Enough to exercise every hard + soft constraint.
"""
from __future__ import annotations

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


def build_problem() -> Problem:
    grid = TimeGrid(days=["Mon", "Tue", "Wed", "Thu", "Fri"], periods_per_day=7)

    # Common lunch = period index 3 (P4) every day, blocked for everyone.
    lunch = {grid.slot(d, 3) for d in range(grid.num_days)}
    # Monday assembly = first period Monday.
    assembly = {grid.slot(0, 0)}
    global_blocked = lunch | assembly

    teachers = [
        Teacher(id="t_maths", name="Rao (Maths)", max_periods_per_day=5,
                preferred_slots={grid.slot(d, 1) for d in range(5)}),
        Teacher(id="t_sci", name="Iyer (Science)", max_periods_per_day=5),
        Teacher(id="t_eng", name="Khan (English)", max_periods_per_day=5),
        Teacher(id="t_soc", name="Das (Social)", max_periods_per_day=6),
        Teacher(id="t_cs", name="Nair (Computer)", max_periods_per_day=5),
        # Part-time Hindi teacher: unavailable Thursday & Friday.
        Teacher(id="t_hin", name="Verma (Hindi)", max_periods_per_day=6,
                unavailable_slots={grid.slot(d, p) for d in (3, 4) for p in range(7)}),
    ]

    classes = [
        Klass(id="IX_A", name="IX-A", class_teacher_id="t_maths"),
        Klass(id="IX_B", name="IX-B", class_teacher_id="t_eng"),
        Klass(id="X_A", name="X-A", class_teacher_id="t_sci"),
    ]

    lab_pools = [
        LabPool(kind="science_lab", capacity=1),
        LabPool(kind="computer_lab", capacity=1),
    ]

    # weekly plan per class: (subject, teacher, periods/week, lab?, pref, doubles)
    plan = [
        ("Maths",   "t_maths", 6, None,           Preference.MORNING, 0),
        ("Science", "t_sci",   5, None,           Preference.MORNING, 0),
        ("SciLab",  "t_sci",   2, "science_lab",  Preference.NONE,    1),  # 1 double
        ("English", "t_eng",   5, None,           Preference.NONE,    0),
        ("Social",  "t_soc",   5, None,           Preference.NONE,    0),
        ("Computer","t_cs",    2, "computer_lab", Preference.NONE,    1),  # 1 double
        ("Hindi",   "t_hin",   4, None,           Preference.NONE,    0),
    ]

    lessons: list[Lesson] = []
    for klass in classes:
        for subject, teacher, per_week, lab, pref, doubles in plan:
            n = per_week
            idx = 0
            # Emit `doubles` double-period blocks first, then singles.
            for _ in range(doubles):
                if n >= 2:
                    lessons.append(Lesson(
                        id=f"{klass.id}_{subject}_{idx}", klass_id=klass.id,
                        subject=subject, teacher_id=teacher, length=2,
                        lab_kind=lab, preference=pref))
                    n -= 2
                    idx += 1
            for _ in range(n):
                lessons.append(Lesson(
                    id=f"{klass.id}_{subject}_{idx}", klass_id=klass.id,
                    subject=subject, teacher_id=teacher, length=1,
                    lab_kind=lab, preference=pref))
                idx += 1

    return Problem(
        grid=grid,
        teachers=teachers,
        classes=classes,
        lessons=lessons,
        lab_pools=lab_pools,
        global_blocked_slots=global_blocked,
        config=SolverConfig(max_seconds=20.0, random_seed=42),
    )
