import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { describeFailure, getMyLoans, type Failure, type Loan } from "../api/client";

type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; loans: Loan[] };

function longDate(day: string): string {
  const d = new Date(`${day}T00:00:00`);
  return Number.isNaN(d.getTime()) ? day : d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** "6.00" stays exact: the amount is shown as the API sent it, never parsed into a float. */
function hasFine(amount: string | undefined): amount is string {
  return !!amount && /[1-9]/.test(amount);
}

/**
 * library.loans on the Student dashboard: the student's active loans, earliest due first (GET /me/loans), with the
 * due date, an overdue badge and the fine accrued so far. The shell renders the panel and its title; this is the body.
 */
export function LoansWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    getMyLoans(signal)
      .then((loans) => setState({ kind: "ready", loans }))
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") setState({ kind: "error", failure: describeFailure(e, "your library loans") });
      });
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  if (state.kind === "loading") return <SkeletonLines lines={3} />;
  if (state.kind === "error") {
    const { title, detail, retry } = state.failure;
    return (
      <ErrorState title={title} onRetry={retry ? () => load() : undefined}>
        {detail}
      </ErrorState>
    );
  }
  if (state.loans.length === 0) {
    return (
      <EmptyState icon={<Icons.BookOpen />} title="No books on loan">
        Books you borrow from the library appear here with their due dates.
      </EmptyState>
    );
  }

  return (
    <List divided label="Library loans">
      {state.loans.map((loan, i) => (
        <ListRow
          key={loan.id}
          index={i}
          date={loan.due_on}
          tone={loan.overdue ? "danger" : "accent"}
          title={loan.title ?? "Untitled"}
          meta={
            <>
              {`Due ${longDate(loan.due_on)}`}
              {typeof loan.renewals_left === "number" && ` · ${loan.renewals_left} renewal${loan.renewals_left === 1 ? "" : "s"} left`}
            </>
          }
          trailing={
            loan.overdue ? (
              <Badge tone="danger">{hasFine(loan.fine_accrued) ? `Overdue · ${loan.fine_accrued}` : "Overdue"}</Badge>
            ) : undefined
          }
        />
      ))}
    </List>
  );
}
