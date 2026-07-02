"""DB-backed generation, versioning, publish and auto-repair — against a throwaway
in-memory SQLite so tests never touch the dev database."""
from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.tables import TimetableEntry, TimetableVersion
from app.scheduler.problem import TimeGrid
from app.scheduler.render import verify
from app.services import scheduling
from app.services.mapping import build_problem
from app.services.seed import seed_demo_school


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_seed_then_generate_persists_conflict_free_version(session):
    sid = seed_demo_school(session)
    version, solution = scheduling.generate_version(session, sid, max_seconds=15.0)
    assert version is not None and version.id is not None
    assert solution.ok

    # The persisted problem, rebuilt from the DB, is what got solved and is clean.
    problem = build_problem(session, sid)
    assert verify(problem, solution) == []

    entries = session.exec(
        select(TimetableEntry).where(TimetableEntry.version_id == version.id)
    ).all()
    assert len(entries) == len(solution.placements)


def test_publish_demotes_previous_published(session):
    sid = seed_demo_school(session)
    v1, _ = scheduling.generate_version(session, sid, max_seconds=15.0)
    v2, _ = scheduling.generate_version(session, sid, max_seconds=15.0)

    scheduling.publish_version(session, v1.id)
    scheduling.publish_version(session, v2.id)

    published = session.exec(
        select(TimetableVersion).where(TimetableVersion.status == "published")
    ).all()
    assert [p.id for p in published] == [v2.id]


def test_repair_keeps_pinned_cells_and_writes_new_version(session):
    sid = seed_demo_school(session)
    base, _ = scheduling.generate_version(session, sid, max_seconds=15.0)

    base_entries = session.exec(
        select(TimetableEntry).where(TimetableEntry.version_id == base.id)
    ).all()
    base_map = {(e.klass_code, e.subject, e.start_slot) for e in base_entries}

    # Free only Social; everything else must stay exactly where it was.
    repaired, sol = scheduling.repair_version(
        session, base.id, unlock={f"IX_A_Social_{i}" for i in range(5)}, max_seconds=15.0)
    assert repaired is not None and repaired.id != base.id
    assert sol.ok

    rep_entries = session.exec(
        select(TimetableEntry).where(TimetableEntry.version_id == repaired.id)
    ).all()
    # Every non-Social IX_A cell (and all other classes) is unchanged.
    for e in rep_entries:
        if not (e.klass_code == "IX_A" and e.subject == "Social"):
            assert (e.klass_code, e.subject, e.start_slot) in base_map
