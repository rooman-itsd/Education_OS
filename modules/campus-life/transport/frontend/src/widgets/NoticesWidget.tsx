import { useCallback, useEffect, useState } from "react";
import {
  Badge,
  EmptyState,
  ErrorState,
  Icons,
  List,
  ListRow,
  SkeletonLines,
  type BadgeTone,
  type WidgetProps,
} from "@eos/ui-kit";
import { getMyNotices, type Notice, type NoticeKind } from "../api/client";

/** How many notices the dashboard card shows. */
export const NOTICE_LIMIT = 5;

type State = { kind: "loading" } | { kind: "error" } | { kind: "ready"; notices: Notice[] };

const KIND: Record<NoticeKind, { label: string; tone: BadgeTone }> = {
  delay: { label: "Delay", tone: "warning" },
  cancellation: { label: "Cancelled", tone: "danger" },
  "route-change": { label: "Route change", tone: "info" },
  general: { label: "Notice", tone: "neutral" },
};

function shortDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/**
 * transport.notices on the Student dashboard: notices for the routes of the student's passes plus notices to
 * every route, newest first (GET /me/notices). The shell renders the panel and its title; this is the body.
 */
export function NoticesWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    getMyNotices(NOTICE_LIMIT, signal)
      .then((notices) => setState({ kind: "ready", notices }))
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") setState({ kind: "error" });
      });
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  if (state.kind === "loading") return <SkeletonLines lines={3} />;
  if (state.kind === "error") {
    return (
      <ErrorState title="Could not load transport notices" onRetry={() => load()}>
        Check your connection and try again.
      </ErrorState>
    );
  }
  if (state.notices.length === 0) {
    return (
      <EmptyState icon={<Icons.Bus />} title="No transport notices right now">
        Delays, cancellations and route changes for your bus appear here.
      </EmptyState>
    );
  }

  return (
    <List divided label="Transport notices">
      {state.notices.map((n, i) => {
        const kind = KIND[n.kind] ?? KIND.general;
        return (
          <ListRow
            key={n.id}
            index={i}
            date={n.published_at.slice(0, 10)}
            title={n.title}
            meta={
              <>
                {n.route_id === null ? "All routes" : `Route ${n.route_code ?? ""}`.trim()} · {n.body}
                {n.expires_at && <> · until {shortDate(n.expires_at)}</>}
              </>
            }
            trailing={<Badge tone={kind.tone}>{kind.label}</Badge>}
          />
        );
      })}
    </List>
  );
}
