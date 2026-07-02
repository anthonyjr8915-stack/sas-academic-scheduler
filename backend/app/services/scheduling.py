"""Generation + versioning service: run the engine for a school and persist the
result as an immutable `TimetableVersion` snapshot with its entries."""
from __future__ import annotations

from sqlmodel import Session, select

from app.models.tables import TimetableEntry, TimetableVersion
from app.scheduler.engine import Solution, TimetableEngine
from app.services.mapping import build_problem, solution_to_entries


def generate_version(session: Session, school_id: int, *, label: str = "draft",
                     seed: int = 42, max_seconds: float = 20.0,
                     locked: dict[str, int] | None = None
                     ) -> tuple[TimetableVersion | None, Solution]:
    """Solve for `school_id` and, if feasible, save a new version. Returns the
    saved version (or None when infeasible) alongside the raw solution."""
    problem = build_problem(session, school_id, seed=seed,
                            max_seconds=max_seconds, locked=locked)
    solution = TimetableEngine(problem).solve()

    if not solution.ok:
        return None, solution

    version = TimetableVersion(
        school_id=school_id, label=label, status="draft",
        solver_status=solution.status, score=solution.score,
        seed=seed, solve_seconds=solution.solve_seconds,
    )
    session.add(version)
    session.commit()
    session.refresh(version)

    session.add_all(solution_to_entries(version.id, solution))
    session.commit()
    return version, solution


def repair_version(session: Session, version_id: int, *,
                   unlock: set[str] | None = None, max_seconds: float = 20.0
                   ) -> tuple[TimetableVersion | None, Solution]:
    """Auto-repair: re-solve a version keeping every entry pinned except lessons
    whose id is in `unlock`. Saves the result as a new version (non-destructive)."""
    version = session.get(TimetableVersion, version_id)
    if version is None:
        raise ValueError(f"Version {version_id} not found")
    unlock = unlock or set()

    entries = session.exec(
        select(TimetableEntry).where(TimetableEntry.version_id == version_id)
    ).all()
    # Pin every entry to its slot except the ones being freed. lesson_id was stored
    # at generation time, so no fragile reconstruction is needed.
    locked = {e.lesson_id: e.start_slot for e in entries if e.lesson_id not in unlock}

    return generate_version(session, version.school_id, label=f"repair_of_{version_id}",
                            seed=version.seed, max_seconds=max_seconds, locked=locked)


def publish_version(session: Session, version_id: int) -> TimetableVersion:
    """Mark one version published and demote any previously published one for the
    same school. The published snapshot is what teachers/students see."""
    version = session.get(TimetableVersion, version_id)
    if version is None:
        raise ValueError(f"Version {version_id} not found")

    others = session.exec(
        select(TimetableVersion).where(
            TimetableVersion.school_id == version.school_id,
            TimetableVersion.status == "published",
        )
    ).all()
    for o in others:
        o.status = "draft"
        session.add(o)

    version.status = "published"
    session.add(version)
    session.commit()
    session.refresh(version)
    return version
