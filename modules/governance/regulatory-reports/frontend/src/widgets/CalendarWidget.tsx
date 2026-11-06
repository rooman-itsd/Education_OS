import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getCalendar, type Calendar } from "../api/client";
import { describeFailure, filingMeta, statusLabel, type Failure } from "./shared";

type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; data: Calendar };

/** The calendar covers the next 90 days, well within REGULATORY_REPORTS_CALENDAR_MAX_DAYS. */
export const CALENDAR_DAYS = 90;

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** [from, to] for the calendar: today and CALENDAR_DAYS later, as local ISO dates. */
export function range(today: Date = new Date()): [string, string] {
  const end = new Date(today.getFullYear(), today.getMonth(), today.getDate() + CALENDAR_DAYS);
  return [iso(today), iso(end)];
}

/**
 * regulatory-reports.compliance-calendar on the Management dashboard: filings due in the next 90 days by due date,
 * each with its obligation, authority, period and status in words (GET /calendar). Needs regulatory-reports:data:read
 * and regulatory-reports:stats:read. The shell renders the panel and its title; this is the body.
 */
export function CalendarWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    const [from, to] = range();
    getCalendar(from, to, signal)
      .then((data) => setState({ kind: "ready", data }))
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") {
          setState({ kind: "error", failure: describeFailure(e, "the compliance calendar") });
        }
      });
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  if (state.kind === "loading") return <SkeletonLines lines={4} />;
  if (state.kind === "error") {
    const { title, detail, retry } = state.failure;
    return (
      <ErrorState title={title} onRetry={retry ? () => load() : undefined}>
        {detail}
      </ErrorState>
    );
  }
  if (state.data.items.length === 0) {
    return (
      <EmptyState icon={<Icons.CalendarRange />} title="No filings due">
        {`Filings due in the next ${CALENDAR_DAYS} days appear here.`}
      </EmptyState>
    );
  }
  return (
    <List divided label="Compliance calendar">
      {state.data.items.map((f, i) => {
        const status = statusLabel(f.status);
        return (
          <ListRow
            key={f.filing_id}
            index={i}
            date={f.due_on}
            tone={f.overdue ? "danger" : "info"}
            title={f.obligation_title}
            meta={filingMeta(f)}
            trailing={<Badge tone={f.overdue ? "danger" : status.tone}>{f.overdue ? "Overdue" : status.text}</Badge>}
          />
        );
      })}
    </List>
  );
}
