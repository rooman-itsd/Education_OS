import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getLowStock, type LowStockLine, describeFailure, type Failure, qty } from "../api/client";

type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; data: LowStockLine[] };

/**
 * inventory-equipment.low-stock on the store staff and lead dashboards: items at or below their reorder level,
 * shortest first, with what is left and the reorder level (GET /low-stock). Out of stock is danger, low is warning;
 * status always comes with a word, never colour alone. The shell renders the panel and its title; this is the body.
 */
const SHOWN = 6;

export function LowStockWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    getLowStock(signal)
      .then((data) => setState({ kind: "ready", data }))
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") setState({ kind: "error", failure: describeFailure(e, "low stock") });
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
  if (state.data.length === 0) {
    return (
      <EmptyState icon={<Icons.Package />} title="Stock is healthy">
        Items that fall to their reorder level appear here.
      </EmptyState>
    );
  }

  return (
    <List divided label="Items low on stock">
      {state.data.slice(0, SHOWN).map((line, i) => {
        const out = line.available <= 0;
        return (
          <ListRow
            key={line.item_id}
            index={i}
            icon={out ? Icons.AlertTriangle : Icons.Package}
            tone={out ? "danger" : "warning"}
            title={line.item_name}
            meta={`Reorder level ${qty(line.reorder_level)} ${line.unit_of_measure}`}
            trailing={
              <Badge tone={out ? "danger" : "warning"}>
                {out ? "Out of stock" : `${qty(line.available)} ${line.unit_of_measure} left`}
              </Badge>
            }
          />
        );
      })}
      {state.data.length > SHOWN && <ListRow title={`${state.data.length - SHOWN} more`} tone="neutral" icon={Icons.Boxes} />}
    </List>
  );
}
