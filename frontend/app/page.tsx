import Dashboard from "@/components/Dashboard";
import { loadTimetable } from "@/lib/api";

// Revalidate periodically when pointed at a live backend; harmless for demo data.
export const revalidate = 30;

export default async function Home() {
  const { data, live } = await loadTimetable();
  return <Dashboard data={data} live={live} />;
}
