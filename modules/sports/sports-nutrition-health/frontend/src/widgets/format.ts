import type { BadgeTone } from "@eos/ui-kit";
import type { AppointmentStatus, AppointmentType, InjuryStatus, NutritionPlan, PlanGoal, Severity } from "../api/client";

const NUMBER = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 });

/**
 * How a row names an athlete: this module knows athletes by id only (athlete-performance owns their names) and
 * has no endpoint that names them, so the widgets show a short id rather than a made-up name.
 */
export function athleteLabel(id: string): string {
  return `Athlete ${id.slice(0, 8)}`;
}

/** A contract date (YYYY-MM-DD) as "5 Nov 2026", read as a local calendar date. */
export function day(date: string | null | undefined): string {
  if (!date) return "—";
  const d = new Date(`${date}T00:00:00`);
  if (Number.isNaN(d.getTime())) return date;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/** A contract date-time as the local time of day, "09:30". */
export function timeOf(instant: string): string {
  const d = new Date(instant);
  if (Number.isNaN(d.getTime())) return instant;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Today as YYYY-MM-DD in local time, and that date plus some days. */
export function isoDay(offsetDays = 0, now = new Date()): string {
  const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + offsetDays);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Whole days from today (local) to a contract date: 0 today, negative once it has passed. */
export function daysUntil(date: string, now = new Date()): number {
  const target = new Date(`${date}T00:00:00`);
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((target.getTime() - today.getTime()) / 86_400_000);
}

/** When a review is due, relative to today: the words and tone of its badge. */
export function due(date: string, now = new Date()): { label: string; tone: BadgeTone; overdue: boolean } {
  const n = daysUntil(date, now);
  if (n < 0) return { label: `Overdue by ${days(-n)}`, tone: "danger", overdue: true };
  if (n === 0) return { label: "Due today", tone: "warning", overdue: false };
  return { label: `Due in ${days(n)}`, tone: n <= 3 ? "warning" : "info", overdue: false };
}

/** The local day as an instant range [start, end), and the UTC calendar days it overlaps (one or two). */
export function localDay(now = new Date()): { start: Date; end: Date; utcDays: string[] } {
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const first = start.toISOString().slice(0, 10);
  const last = new Date(end.getTime() - 1).toISOString().slice(0, 10);
  return { start, end, utcDays: first === last ? [first] : [first, last] };
}

/** A plan's daily targets: "2,800 kcal · Protein 160 g · Carbs 350 g · Fat 80 g"; empty when none is set. */
export function targets(p: NutritionPlan): string {
  const parts: string[] = [];
  if (p.daily_calories != null) parts.push(`${NUMBER.format(p.daily_calories)} kcal`);
  if (p.protein_g != null) parts.push(`Protein ${NUMBER.format(p.protein_g)} g`);
  if (p.carbohydrate_g != null) parts.push(`Carbs ${NUMBER.format(p.carbohydrate_g)} g`);
  if (p.fat_g != null) parts.push(`Fat ${NUMBER.format(p.fat_g)} g`);
  return parts.join(" · ");
}

export const GOAL: Record<PlanGoal, string> = {
  performance: "Performance",
  weight_gain: "Weight gain",
  weight_loss: "Weight loss",
  recovery: "Recovery",
  maintenance: "Maintenance",
};

export const SEVERITY: Record<Severity, { label: string; tone: BadgeTone; rank: number }> = {
  severe: { label: "Severe", tone: "danger", rank: 0 },
  moderate: { label: "Moderate", tone: "warning", rank: 1 },
  minor: { label: "Minor", tone: "neutral", rank: 2 },
};

export const INJURY_STATUS: Record<InjuryStatus, { label: string; tone: BadgeTone }> = {
  active: { label: "Active", tone: "danger" },
  recovering: { label: "Recovering", tone: "info" },
  resolved: { label: "Resolved", tone: "success" },
};

export const APPOINTMENT_TYPE: Record<AppointmentType, string> = {
  physiotherapy: "Physiotherapy",
  medical: "Medical",
  nutrition: "Nutrition",
};

export const APPOINTMENT_STATUS: Record<AppointmentStatus, { label: string; tone: BadgeTone }> = {
  scheduled: { label: "Scheduled", tone: "info" },
  completed: { label: "Completed", tone: "success" },
  cancelled: { label: "Cancelled", tone: "neutral" },
  no_show: { label: "No show", tone: "warning" },
};

const plural = (one: string, many: string) => (n: number) => (n === 1 ? `1 ${one}` : `${n} ${many}`);

/** "1 day", "3 days". */
export const days = plural("day", "days");
/** "1 athlete", "3 athletes". */
export const athletes = plural("athlete", "athletes");
/** "1 plan", "3 plans". */
export const plans = plural("plan", "plans");
/** "1 injury", "3 injuries". */
export const injuries = plural("injury", "injuries");
/** "1 appointment", "3 appointments". */
export const appointments = plural("appointment", "appointments");
