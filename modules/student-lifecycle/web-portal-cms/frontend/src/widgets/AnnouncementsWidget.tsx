import { useCallback, useEffect, useState } from "react";
import { EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { describeFailure, isAbort, listAnnouncements, type Announcement, type AnnouncementPage, type Failure } from "../api/client";

const SHOWN = 5;
const EXCERPT = 140;

type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; page: AnnouncementPage };

/** The body as one line of plain text, cut at a word. Bodies are plain text: React escapes them; never HTML. */
export function excerpt(body: string, limit = EXCERPT): string {
  const text = body.replace(/\s+/g, " ").trim();
  if (text.length <= limit) return text;
  const cut = text.slice(0, limit);
  const space = cut.lastIndexOf(" ");
  return `${(space > limit * 0.6 ? cut.slice(0, space) : cut).trimEnd()}…`;
}

function when(a: Announcement): string {
  const iso = a.starts_at ?? a.published_at;
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

/**
 * web-portal-cms.announcements on the Applicant dashboard: the organisation's current announcements, newest first
 * (GET /announcements; only published ones inside their display window reach a member). The shell renders the
 * panel and its title; this is the body.
 */
export function AnnouncementsWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    listAnnouncements(SHOWN, signal)
      .then((page) => setState({ kind: "ready", page }))
      .catch((e: unknown) => {
        if (!isAbort(e)) setState({ kind: "error", failure: describeFailure(e, "announcements") });
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
  const { items, total } = state.page;
  if (total === 0) {
    return (
      <EmptyState icon={<Icons.ScrollText />} title="No announcements">
        Notices your organisation publishes appear here.
      </EmptyState>
    );
  }
  return (
    <List divided label="Announcements">
      {items.map((a, i) => (
        <ListRow
          key={a.id}
          index={i}
          icon={Icons.ScrollText}
          tone="accent"
          title={a.title}
          meta={[excerpt(a.body), when(a)].filter(Boolean).join(" · ")}
        />
      ))}
      {total > items.length && <ListRow title={`${total - items.length} more`} tone="neutral" icon={Icons.ClipboardList} />}
    </List>
  );
}
