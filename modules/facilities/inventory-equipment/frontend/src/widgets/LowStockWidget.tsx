import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getLowStock, type LowStockLine } from "../api/client";

type State = { kind: "loading" } | { kind: "error" } | { kind: "ready"; data: LowStockLine[] };

/**
 * inventory-equipment.low-stock on the store staff and lead dashboards: items at or below their reorder level,
 * shortest first, with what is left and the reorder level (GET /low-stock). Out of stock is danger, low is warning;
 * status always comes with a word, never colour alone. The shell renders the panel and its title; this is the body.
 */
export function LowStockWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    getLowStock(signal)
      .then((data) => setState({ kind: "ready", data }))
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
      <ErrorState title="Could not load low stock" onRetry={() => load()}>
        Check your connection and try again.
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
      {state.data.map((line, i) => {
        const out = line.available <= 0;
        return (
          <ListRow
            key={line.item_id}
            index={i}
            icon={out ? Icons.AlertTriangle : Icons.Package}
            tone={out ? "danger" : "warning"}
            title={line.item_name}
            meta={`Reorder level ${line.reorder_level} ${line.unit_of_measure}`}
            trailing={
              <Badge tone={out ? "danger" : "warning"}>
                {out ? "Out of stock" : `${line.available} ${line.unit_of_measure} left`}
              </Badge>
            }
          />
        );
      })}
    </List>
  );
}
