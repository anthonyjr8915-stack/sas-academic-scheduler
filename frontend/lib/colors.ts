// Stable, readable color per subject. Derived from the subject name so any
// subject (not just the demo set) gets a consistent chip color.
const PALETTE = [
  "bg-sky-500/20 text-sky-200 ring-sky-400/30",
  "bg-violet-500/20 text-violet-200 ring-violet-400/30",
  "bg-emerald-500/20 text-emerald-200 ring-emerald-400/30",
  "bg-amber-500/20 text-amber-200 ring-amber-400/30",
  "bg-rose-500/20 text-rose-200 ring-rose-400/30",
  "bg-cyan-500/20 text-cyan-200 ring-cyan-400/30",
  "bg-fuchsia-500/20 text-fuchsia-200 ring-fuchsia-400/30",
  "bg-lime-500/20 text-lime-200 ring-lime-400/30",
  "bg-indigo-500/20 text-indigo-200 ring-indigo-400/30",
];

export function subjectColor(subject: string): string {
  let hash = 0;
  for (let i = 0; i < subject.length; i++) {
    hash = (hash * 31 + subject.charCodeAt(i)) & 0xffffffff;
  }
  return PALETTE[Math.abs(hash) % PALETTE.length];
}
