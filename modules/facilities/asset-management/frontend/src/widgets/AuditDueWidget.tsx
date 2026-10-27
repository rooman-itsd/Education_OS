import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { describeFailure, getVerificationDue, shortDate, type Failure, type VerificationDue } from "../api/client";

type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; data: VerificationDue };

const SHOWN = 5;

/**
 * asset-management.audit-due on the Facility / Inventory Staff dashboard: assets overdue or due soon for physical
 * verification, overdue first, with a counts line and the open verification cycles and their progress
 * (GET /verifications/due). Overdue is danger, due soon is warning; status always comes with a word, never colour
 * alone. The shell renders the panel and its title; this is the body.
 */
export function AuditDueWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    getVerificationDue(signal)
      .then((data) => setState({ kind: "ready", data }))
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") {
          setState({ kind: "error", failure: describeFailure(e, "assets due for verification") });
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

  const { data } = state;
  const assets = data.assets ?? [];
  const cycles = (data.open_cycles ?? []).filter((c) => c.status !== "closed");
  if (assets.length === 0 && cycles.length === 0) {
    return (
      <EmptyState icon={<Icons.CheckCircle2 />} title="Nothing due for verification">
        {`Assets due within ${data.within_days} days appear here.`}
      </EmptyState>
    );
  }

  return (
    <>
      <p className="eos-row__meta" aria-label="Verification counts">
        {`${data.overdue_count} overdue · ${data.due_soon_count} due in ${data.within_days} days`}
      </p>
      <List divided label="Assets due for verification">
        {cycles.map((c, i) => {
          const total = c.counts?.total ?? 0;
          const done = total - (c.counts?.pending ?? 0);
          return (
            <ListRow
              key={`cycle-${c.id}`}
              index={i}
              icon={Icons.ClipboardList}
              tone="info"
              title={c.name}
              meta={c.status === "planned" ? `Planned · due ${shortDate(c.due_on)}` : `${done} of ${total} checked · due ${shortDate(c.due_on)}`}
              trailing={<Badge tone="info">{c.status === "planned" ? "Planned" : "In progress"}</Badge>}
            />
          );
        })}
        {assets.slice(0, SHOWN).map((a, i) => (
          <ListRow
            key={a.asset_id}
            index={cycles.length + i}
            icon={a.overdue ? Icons.AlertTriangle : Icons.Clock}
            tone={a.overdue ? "danger" : "warning"}
            title={`${a.tag} · ${a.name}`}
            meta={`${a.location || "No location"} · due ${shortDate(a.next_verification_due)}`}
            trailing={<Badge tone={a.overdue ? "danger" : "warning"}>{a.overdue ? "Overdue" : "Due soon"}</Badge>}
          />
        ))}
        {assets.length > SHOWN && <ListRow title={`${assets.length - SHOWN} more`} tone="neutral" icon={Icons.Boxes} />}
      </List>
    </>
  );
}
