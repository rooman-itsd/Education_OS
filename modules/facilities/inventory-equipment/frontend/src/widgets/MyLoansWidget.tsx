import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { listLoans, loanItems, shortDate, type Loan, type LoanStatus } from "../api/client";

type State = { kind: "loading" } | { kind: "error" } | { kind: "ready"; data: Loan[]; total: number };
type Tone = "danger" | "warning" | "info" | "success" | "neutral";

/** Open loan statuses in words, and the tone of each; status always comes with a word, never colour alone. */
const LABEL: Partial<Record<LoanStatus, string>> = {
  requested: "Awaiting approval",
  approved: "Ready to collect",
  on_loan: "On loan",
  partially_returned: "Part returned",
  overdue: "Overdue",
};
const TONE: Partial<Record<LoanStatus, Tone>> = {
  requested: "info",
  approved: "success",
  on_loan: "neutral",
  partially_returned: "warning",
  overdue: "danger",
};

const SHOWN = 5;

/**
 * inventory-equipment.my-loans on learner and performer dashboards: the caller's open loans (requested, approved,
 * on loan, part returned, overdue), soonest due first, with what they hold and when it is due
 * (GET /loans?scope=mine&open=true). The shell renders the panel and its title; this is the body.
 */
export function MyLoansWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    listLoans({ scope: "mine", open: true, page_size: 50 }, signal)
      .then((page) => {
        const data = [...page.items].sort((a, b) => a.due_at.localeCompare(b.due_at));
        setState({ kind: "ready", data, total: page.total });
      })
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
      <ErrorState title="Could not load your loans" onRetry={() => load()}>
        Check your connection and try again.
      </ErrorState>
    );
  }
  if (state.data.length === 0) {
    return (
      <EmptyState icon={<Icons.Package />} title="Nothing on loan">
        Equipment you borrow appears here with its due date.
      </EmptyState>
    );
  }

  return (
    <List divided label="Your loans">
      {state.data.slice(0, SHOWN).map((loan, i) => (
        <ListRow
          key={loan.id}
          index={i}
          icon={loan.status === "overdue" ? Icons.AlertTriangle : Icons.Package}
          tone={TONE[loan.status] ?? "neutral"}
          title={loanItems(loan)}
          meta={
            loan.status === "overdue"
              ? `Was due ${shortDate(loan.due_at)} · ${loan.days_overdue} ${loan.days_overdue === 1 ? "day" : "days"} late`
              : `Due ${shortDate(loan.due_at)}`
          }
          trailing={<Badge tone={TONE[loan.status] ?? "neutral"}>{LABEL[loan.status] ?? loan.status}</Badge>}
        />
      ))}
      {state.total > SHOWN && <ListRow title={`${state.total - SHOWN} more`} tone="neutral" icon={Icons.Boxes} />}
    </List>
  );
}
