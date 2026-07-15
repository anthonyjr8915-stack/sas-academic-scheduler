"use client";

import { useMemo, useState } from "react";
import type { Timetable } from "@/lib/types";
import TimetableGrid from "./TimetableGrid";
import ScoreBreakdown from "./ScoreBreakdown";

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl bg-white/[0.03] px-4 py-3 ring-1 ring-white/10">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-white">{value}</div>
      {sub && <div className="text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

export default function Dashboard({ data, live }: { data: Timetable; live: boolean }) {
  const [mode, setMode] = useState<"class" | "teacher">("class");
  const entities = mode === "class" ? data.classes : data.teachers;
  const [entityId, setEntityId] = useState(entities[0]?.id ?? "");

  const current =
    entities.find((e) => e.id === entityId)?.id ?? entities[0]?.id ?? "";

  const utilization = useMemo(() => {
    const slots = data.grid.days.length * data.grid.periods_per_day;
    const avail = slots - data.global_blocked_slots.length;
    const taught = data.placements.reduce((n, p) => n + p.length, 0);
    return Math.round((taught / (data.teachers.length * avail)) * 100);
  }, [data]);

  return (
    <div className="mx-auto max-w-6xl px-5 py-8">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">
            SAS <span className="text-sky-400">·</span> Academic Scheduler
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            AI-generated, conflict-free timetables · OR-Tools CP-SAT engine
          </p>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium ring-1 ${
            live
              ? "bg-emerald-500/15 text-emerald-300 ring-emerald-400/30"
              : "bg-amber-500/15 text-amber-300 ring-amber-400/30"
          }`}
        >
          {live ? "● Live API" : "● Demo data (bundled)"}
        </span>
      </header>

      {/* Stats */}
      <section className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat
          label="Solver"
          value={data.version.solver_status || data.status}
          sub={`seed ${data.version.seed}`}
        />
        <Stat label="Optimization score" value={String(data.score)} sub="explained below" />
        <Stat label="Conflicts" value="0" sub={`${data.placements.length} lessons placed`} />
        <Stat label="Teacher utilization" value={`${utilization}%`} sub="of available slots" />
      </section>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_320px]">
        {/* Timetable panel */}
        <section className="rounded-2xl bg-white/[0.02] p-4 ring-1 ring-white/10">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="inline-flex rounded-lg bg-white/5 p-1">
              {(["class", "teacher"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => {
                    setMode(m);
                    const list = m === "class" ? data.classes : data.teachers;
                    setEntityId(list[0]?.id ?? "");
                  }}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium capitalize transition ${
                    mode === m
                      ? "bg-sky-500 text-white"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {m} view
                </button>
              ))}
            </div>
            <select
              value={current}
              onChange={(e) => setEntityId(e.target.value)}
              className="rounded-lg border border-white/10 bg-[#0d1526] px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-sky-400"
            >
              {entities.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                </option>
              ))}
            </select>
          </div>
          <TimetableGrid data={data} mode={mode} entityId={current} />
          <p className="mt-3 text-xs text-slate-500">
            ⚗ = lab session · &ldquo;·&rdquo; = continuation of a double period · grey
            = break/assembly/lunch (hard-blocked)
          </p>
        </section>

        {/* Score panel */}
        <aside className="rounded-2xl bg-white/[0.02] p-5 ring-1 ring-white/10">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
            Why this score?
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Every soft rule contributes points — the engine maximizes the total.
          </p>
          <div className="mt-4">
            <ScoreBreakdown lines={data.score_breakdown} />
          </div>
          <div className="mt-6 rounded-lg bg-white/[0.03] p-3 text-xs leading-relaxed text-slate-400 ring-1 ring-white/5">
            Hard constraints (teacher/class/lab clashes, availability, breaks) are
            <span className="text-slate-200"> never violated</span>. Soft rules above
            are optimized within that feasible space.
          </div>
        </aside>
      </div>

      <footer className="mt-10 text-center text-xs text-slate-600">
        Vardiano Technologies · Phase 2 · point the UI at a live backend with
        <code className="mx-1 rounded bg-white/5 px-1.5 py-0.5 text-slate-400">
          NEXT_PUBLIC_API_URL
        </code>
      </footer>
    </div>
  );
}
