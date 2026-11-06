/** A contract date-time as the local calendar day, "5 Nov 2026". */
export function dayOf(instant: string): string {
  const d = new Date(instant);
  if (Number.isNaN(d.getTime())) return instant;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/** A video's length as "4:05" or "1:02:09"; "—" when there is none. */
export function duration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return "—";
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

/** "1 video", "3 videos". */
export const videos = (n: number) => (n === 1 ? "1 video" : `${n} videos`);

/** A session's start as "Wed 5 Nov, 06:30" in the viewer's time; the raw value when it is not a date. */
export function sessionStart(instant: string): string {
  const d = new Date(instant);
  if (Number.isNaN(d.getTime())) return instant;
  const day = d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
  const time = d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });
  return `${day}, ${time}`;
}

/** "1 session", "3 sessions". */
export const sessions = (n: number) => (n === 1 ? "1 session" : `${n} sessions`);

/** Today as a local calendar day, "2026-11-05", for the `from_date` of a session query. */
export function localToday(now = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}
