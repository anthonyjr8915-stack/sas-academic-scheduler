import type { ScoreLine } from "@/lib/types";

/** The explainable optimization score — why the timetable scored what it did. */
export default function ScoreBreakdown({ lines }: { lines: ScoreLine[] }) {
  const max = Math.max(1, ...lines.map((l) => Math.abs(l.points)));
  return (
    <div className="space-y-2.5">
      {lines.map((l) => {
        const positive = l.points >= 0;
        return (
          <div key={l.rule} className="group">
            <div className="flex items-center justify-between gap-3">
              <span className="truncate text-sm text-slate-300" title={l.detail}>
                {l.rule.replace(/_/g, " ")}
              </span>
              <span
                className={`shrink-0 font-mono text-sm font-semibold ${
                  positive ? "text-emerald-300" : "text-rose-300"
                }`}
              >
                {positive ? "+" : ""}
                {l.points}
              </span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/5">
              <div
                className={`h-full rounded-full ${
                  positive ? "bg-emerald-400/70" : "bg-rose-400/70"
                }`}
                style={{ width: `${(Math.abs(l.points) / max) * 100}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
