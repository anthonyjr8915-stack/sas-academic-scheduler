"use client";

import type { Placement, Timetable } from "@/lib/types";
import { subjectColor } from "@/lib/colors";

interface Cell {
  subject: string;
  detail: string;
  isLab: boolean;
  continuation: boolean;
}

interface Props {
  data: Timetable;
  mode: "class" | "teacher";
  entityId: string;
}

/** Renders the weekly grid for one class or one teacher. */
export default function TimetableGrid({ data, mode, entityId }: Props) {
  const { days, periods_per_day } = data.grid;
  const blocked = new Set(data.global_blocked_slots);

  const mine = data.placements.filter((p: Placement) =>
    mode === "class" ? p.class_id === entityId : p.teacher_id === entityId
  );

  const cells = new Map<number, Cell>();
  for (const p of mine) {
    for (let k = 0; k < p.length; k++) {
      const slot = p.start_slot + k;
      cells.set(slot, {
        subject: p.subject,
        detail: mode === "class" ? p.teacher_id : p.class_id,
        isLab: !!p.lab_kind,
        continuation: k > 0,
      });
    }
  }

  const slotOf = (day: number, period: number) => day * periods_per_day + period;

  return (
    <div className="overflow-x-auto rounded-xl ring-1 ring-white/10 bg-white/[0.02]">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            <th className="sticky left-0 bg-[#0d1526] px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">
              Period
            </th>
            {days.map((d) => (
              <th
                key={d}
                className="px-3 py-2.5 text-center text-xs font-semibold uppercase tracking-wide text-slate-300"
              >
                {d}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: periods_per_day }).map((_, period) => (
            <tr key={period} className="border-t border-white/5">
              <td className="sticky left-0 bg-[#0d1526] px-3 py-2 font-medium text-slate-400">
                P{period + 1}
              </td>
              {days.map((_, day) => {
                const slot = slotOf(day, period);
                const cell = cells.get(slot);
                if (blocked.has(slot)) {
                  return (
                    <td key={day} className="p-1.5">
                      <div className="flex h-11 items-center justify-center rounded-md bg-white/[0.03] text-[11px] text-slate-500">
                        break
                      </div>
                    </td>
                  );
                }
                if (!cell) {
                  return (
                    <td key={day} className="p-1.5">
                      <div className="h-11 rounded-md border border-dashed border-white/5" />
                    </td>
                  );
                }
                return (
                  <td key={day} className="p-1.5">
                    <div
                      className={`flex h-11 flex-col justify-center rounded-md px-2 ring-1 ${subjectColor(
                        cell.subject
                      )}`}
                    >
                      <span className="truncate text-[13px] font-semibold leading-tight">
                        {cell.subject}
                        {cell.continuation ? " ·" : ""}
                        {cell.isLab ? " ⚗" : ""}
                      </span>
                      <span className="truncate text-[11px] opacity-70">
                        {cell.detail}
                      </span>
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
