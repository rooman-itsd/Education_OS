import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getSummary, listOpenTickets, type Priority, type Summary, type Ticket, type TicketStatus } from "../api/client";

type State = { kind: "loading" } | { kind: "error" } | { kind: "ready"; tickets: Ticket[]; total: number; summary: Summary };
type Tone = "danger" | "warning" | "info" | "neutral";

/** Words for priorities and statuses; status always comes with a word, never colour alone. */
const PRIORITY: Record<Priority, string> = { urgent: "Urgent", high: "High", medium: "Medium", low: "Low" };
const TONE: Record<Priority, Tone> = { urgent: "danger", high: "warning", medium: "info", low: "neutral" };
const STATUS: Partial<Record<TicketStatus, string>> = {
  open: "Unassigned",
  assigned: "Assigned",
  in_progress: "In progress",
  on_hold: "On hold",
};

const SHOWN = 5;

function who(t: Ticket): string {
  if (t.vendor) return `Vendor: ${t.vendor.name}`;
  return STATUS[t.status] ?? t.status;
}

/**
 * maintenance.tickets on the Facility / Inventory Staff, Equipment Manager and Lab In-charge dashboards: open
 * tickets in the organisation, SLA-breached and urgent first, with a line of counts on top
 * (GET /tickets?scope=managed&open=true and GET /summary). The shell renders the panel and its title; this is the body.
 */
export function TicketsWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    Promise.all([listOpenTickets(SHOWN, signal), getSummary(signal)])
      .then(([page, summary]) => setState({ kind: "ready", tickets: page.items, total: page.total, summary }))
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") setState({ kind: "error" });
      });
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  if (state.kind === "loading") return <SkeletonLines lines={4} />;
  if (state.kind === "error") {
    return (
      <ErrorState title="Could not load maintenance tickets" onRetry={() => load()}>
        Check your connection and try again.
      </ErrorState>
    );
  }
  if (state.total === 0) {
    return (
      <EmptyState icon={<Icons.Wrench />} title="No open tickets">
        Faults reported in your organisation appear here.
      </EmptyState>
    );
  }

  const { summary } = state;
  const counts = [
    `${summary.open} open`,
    `${summary.unassigned} unassigned`,
    `${summary.on_hold} on hold`,
    ...(summary.sla_breached_open ? [`${summary.sla_breached_open} past SLA`] : []),
  ].join(" · ");

  return (
    <>
      <p className="eos-row__meta" aria-label="Ticket counts">
        {counts}
      </p>
      <List divided label="Open maintenance tickets">
        {state.tickets.map((t, i) => {
          const breached = t.sla_breached.length > 0;
          return (
            <ListRow
              key={t.id}
              index={i}
              icon={breached ? Icons.AlertTriangle : t.kind === "corrective" ? Icons.Wrench : Icons.CalendarCheck2}
              tone={breached ? "danger" : TONE[t.priority]}
              title={`${t.number} · ${t.title}`}
              meta={`${t.target.label} · ${who(t)}${t.blocks_use ? " · Out of use" : ""}`}
              trailing={
                breached ? <Badge tone="danger">Past SLA</Badge> : <Badge tone={TONE[t.priority]}>{PRIORITY[t.priority]}</Badge>
              }
            />
          );
        })}
        {state.total > state.tickets.length && (
          <ListRow title={`${state.total - state.tickets.length} more open`} tone="neutral" icon={Icons.ClipboardList} />
        )}
      </List>
    </>
  );
}
