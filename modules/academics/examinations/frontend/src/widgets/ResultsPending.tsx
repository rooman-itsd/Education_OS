import type { WidgetProps } from "@eos/ui-kit";
import { getResultsPendingReport } from "../api/client";
import type { ResultsStage } from "../api/types";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** The contract's pipeline stages in order. Paper stages count papers; result stages count course offerings. */
export const STAGES: { stage: ResultsStage; label: string; unit: "paper" | "course offering" }[] = [
  { stage: "marks_entry", label: "Marks entry", unit: "paper" },
  { stage: "moderation", label: "Moderation", unit: "paper" },
  { stage: "awaiting_lock", label: "Awaiting lock", unit: "paper" },
  { stage: "awaiting_computation", label: "Awaiting computation", unit: "course offering" },
  { stage: "awaiting_approval", label: "Awaiting approval", unit: "course offering" },
  { stage: "awaiting_publication", label: "Awaiting publication", unit: "course offering" },
];

export function daysSince(iso: string, now = Date.now()): number {
  return Math.max(0, Math.floor((now - Date.parse(iso)) / 86_400_000));
}

/** examinations.results-pending: papers and results by pipeline stage (GET /reports/results-pending). */
export function ResultsPending(_props: WidgetProps) {
  const load = useWidgetData((signal) => getResultsPendingReport(signal));
  const report = load.state === "ready" ? load.data : null;
  const cycles = report?.items.filter((c) => c.stages.some((s) => s.count > 0)) ?? [];
  return (
    <WidgetStatus load={load} empty={report && cycles.length === 0 ? "No results pending." : null}>
      <div className="eos-exam">
        {cycles.map((c) => {
          const byStage = new Map(c.stages.map((s) => [s.stage, s]));
          return (
            <section key={c.exam_cycle_id} className="eos-exam__cycle" aria-label={c.exam_cycle_name ?? "Exam cycle"}>
              <h3 className="eos-exam__cycle-name">{c.exam_cycle_name ?? "Exam cycle"}</h3>
              <ol className="eos-exam__stages">
                {STAGES.map(({ stage, label, unit }) => {
                  const s = byStage.get(stage);
                  const count = s?.count ?? 0;
                  return (
                    <li key={stage} data-pending={count > 0 || undefined}>
                      <span className="eos-exam__stage-label">{label}</span>
                      <strong>{count}</strong>
                      <span className="eos-exam__muted">
                        {count > 0
                          ? `${unit}${count === 1 ? "" : "s"}${s?.oldest_since ? ` · oldest ${daysSince(s.oldest_since)} d` : ""}`
                          : "none"}
                      </span>
                    </li>
                  );
                })}
              </ol>
            </section>
          );
        })}
      </div>
    </WidgetStatus>
  );
}
