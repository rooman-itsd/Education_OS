import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getMyNotices, type Notice } from "../api/client";

/** How many notices the dashboard card shows. */
export const NOTICE_LIMIT = 5;

type State = { kind: "loading" } | { kind: "error" } | { kind: "ready"; notices: Notice[] };

function shortDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/**
 * hostel.notices on the Student dashboard: the notices for the student's hostel plus notices to every hostel,
 * newest first (GET /me/notices). The shell renders the panel and its title; this is the body.
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
      <ErrorState title="Could not load hostel notices" onRetry={() => load()}>
        Check your connection and try again.
      </ErrorState>
    );
  }
  if (state.notices.length === 0) {
    return (
      <EmptyState icon={<Icons.Megaphone />} title="No hostel notices right now">
        Notices from your warden appear here.
      </EmptyState>
    );
  }

  return (
    <List divided label="Hostel notices">
      {state.notices.map((n, i) => (
        <ListRow
          key={n.id}
          index={i}
          date={n.published_at.slice(0, 10)}
          title={n.title}
          meta={
            <>
              {n.body}
              {n.expires_at && <> · until {shortDate(n.expires_at)}</>}
            </>
          }
          trailing={n.hostel_id === null ? <Badge tone="info">All hostels</Badge> : undefined}
        />
      ))}
    </List>
  );
}
