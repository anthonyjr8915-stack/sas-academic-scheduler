export interface ScoreLine {
  rule: string;
  points: number;
  detail: string;
}

export interface Placement {
  lesson_id: string;
  class_id: string;
  subject: string;
  teacher_id: string;
  start_slot: number;
  day: number;
  period: number;
  length: number;
  lab_kind: string | null;
}

export interface Entity {
  id: string;
  name: string;
}

export interface Timetable {
  status: string;
  ok: boolean;
  solve_seconds: number;
  score: number;
  score_breakdown: ScoreLine[];
  diagnosis: string[];
  placements: Placement[];
  grid: { days: string[]; periods_per_day: number };
  classes: Entity[];
  teachers: Entity[];
  global_blocked_slots: number[];
  version: {
    label: string;
    status: string;
    seed: number;
    solver_status: string;
    score: number;
  };
}
