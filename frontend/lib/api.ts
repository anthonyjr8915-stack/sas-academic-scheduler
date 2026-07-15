import type { Timetable } from "./types";
import demo from "@/data/demo-timetable.json";

/**
 * Load a published timetable.
 *
 * If NEXT_PUBLIC_API_URL is configured, the frontend talks to the live FastAPI
 * backend (deploy it on Railway/Render/Fly — the OR-Tools solver can't run on
 * Vercel serverless). Otherwise it falls back to a real engine-generated demo
 * timetable bundled at build time, so the deployed site is always meaningful.
 */
export async function loadTimetable(): Promise<{ data: Timetable; live: boolean }> {
  const base = process.env.NEXT_PUBLIC_API_URL;
  if (!base) {
    return { data: demo as unknown as Timetable, live: false };
  }
  try {
    // Convention: backend exposes the demo school's published timetable here.
    const res = await fetch(`${base}/timetable/generate-demo`, {
      method: "POST",
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    const body = await res.json();
    // The live endpoint returns solver output; merge in grid/entity metadata
    // from the bundled demo so the UI has labels either way.
    const merged = { ...(demo as unknown as Timetable), ...body };
    return { data: merged, live: true };
  } catch {
    return { data: demo as unknown as Timetable, live: false };
  }
}
