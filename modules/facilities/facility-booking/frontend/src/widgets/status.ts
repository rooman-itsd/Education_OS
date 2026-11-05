import type { BookingStatus } from "../api/client";

export type Tone = "danger" | "warning" | "info" | "success" | "neutral";

/** Statuses in words, and the tone of each; status always comes with a word, never colour alone. */
export const LABEL: Partial<Record<BookingStatus, string>> = {
  pending: "Awaiting approval",
  confirmed: "Confirmed",
  checked_in: "Checked in",
  completed: "Completed",
  no_show: "No-show",
};

export const TONE: Partial<Record<BookingStatus, Tone>> = {
  pending: "warning",
  confirmed: "info",
  checked_in: "success",
  completed: "neutral",
  no_show: "danger",
};
