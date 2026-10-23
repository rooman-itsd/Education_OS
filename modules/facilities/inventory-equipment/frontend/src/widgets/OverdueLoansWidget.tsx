import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { listLoans, loanItems, shortDate, type Loan } from "../api/client";

type State = { kind: "loading" } | { kind: "error" } | { kind: "ready"; data: Loan[]; total: number };

const SHOWN = 6;

/**
 * inventory-equipment.overdue-loans on the Equipment Manager dashboard: every overdue loan in the organisation,
 * longest late first, with what is out and how late it is (GET /loans?scope=managed&status=overdue; the
 * scheduler sweep marks loans overdue). The shell renders the panel and its title; this is the body.
 */
export function OverdueLoansWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    listLoans({ scope: "managed", status: ["overdue"], page_size: 50 }, signal)
      .then((page) => {
        const data = [...page.items].sort((a, b) => b.days_overdue - a.days_overdue);
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
      <ErrorState title="Could not load overdue loans" onRetry={() => load()}>
        Check your connection and try again.
      </ErrorState>
    );
  }
  if (state.data.length === 0) {
    return (
      <EmptyState icon={<Icons.CheckCircle2 />} title="No overdue loans">
        Loans not back by their due date appear here.
      </EmptyState>
    );
  }

  return (
    <List divided label="Overdue loans">
      {state.data.slice(0, SHOWN).map((loan, i) => (
        <ListRow
          key={loan.id}
          index={i}
          icon={Icons.Clock}
          tone="danger"
          title={loanItems(loan)}
          meta={`Due ${shortDate(loan.due_at)}`}
          trailing={<Badge tone="danger">{`${loan.days_overdue} ${loan.days_overdue === 1 ? "day" : "days"} late`}</Badge>}
        />
      ))}
      {state.total > SHOWN && <ListRow title={`${state.total - SHOWN} more overdue`} tone="neutral" icon={Icons.Boxes} />}
    </List>
  );
}
