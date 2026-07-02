"""Seed a realistic demo school into the database, so the DB-backed endpoints and
tests have something to generate against without an Excel upload."""
from __future__ import annotations

from sqlmodel import Session

from app.models.tables import Klass, LabPool, PlanItem, School, Teacher


def seed_demo_school(session: Session, name: str = "Demo Public School") -> int:
    school = School(name=name, days_csv="Mon,Tue,Wed,Thu,Fri",
                    periods_per_day=7, lunch_period=4, assembly_mon=True)
    session.add(school)
    session.commit()
    session.refresh(school)
    sid = school.id

    teachers = [
        ("t_maths", "Rao (Maths)", 5, ""),
        ("t_sci", "Iyer (Science)", 6, ""),
        ("t_eng", "Khan (English)", 5, ""),
        ("t_soc", "Das (Social)", 6, ""),
        ("t_cs", "Nair (Computer)", 5, ""),
        ("t_hin", "Verma (Hindi)", 6, "Thu,Fri"),
    ]
    for code, tname, mx, unav in teachers:
        session.add(Teacher(school_id=sid, code=code, name=tname,
                            max_per_day=mx, unavailable_days_csv=unav))

    classes = [
        ("IX_A", "IX-A", "t_maths"),
        ("IX_B", "IX-B", "t_eng"),
        ("X_A", "X-A", "t_sci"),
    ]
    for code, cname, ct in classes:
        session.add(Klass(school_id=sid, code=code, name=cname, class_teacher_code=ct))

    session.add(LabPool(school_id=sid, kind="science_lab", capacity=1))
    session.add(LabPool(school_id=sid, kind="computer_lab", capacity=1))

    # (subject, teacher, per_week, double_blocks, lab_kind, preference)
    plan = [
        ("Maths", "t_maths", 6, 0, None, "morning"),
        ("Science", "t_sci", 5, 0, None, "morning"),
        ("SciLab", "t_sci", 2, 1, "science_lab", "none"),
        ("English", "t_eng", 5, 0, None, "none"),
        ("Social", "t_soc", 5, 0, None, "none"),
        ("Computer", "t_cs", 2, 1, "computer_lab", "none"),
        ("Hindi", "t_hin", 4, 0, None, "none"),
    ]
    for code, _cname, _ct in classes:
        for subject, teacher, pw, db, lab, pref in plan:
            session.add(PlanItem(school_id=sid, klass_code=code, subject=subject,
                                 teacher_code=teacher, per_week=pw, double_blocks=db,
                                 lab_kind=lab, preference=pref))

    session.commit()
    return sid
