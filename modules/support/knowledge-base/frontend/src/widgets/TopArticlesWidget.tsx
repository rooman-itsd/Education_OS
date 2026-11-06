import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { KnowledgeBaseApiError, getTopArticles, type ArticleType, type TopArticle, type TopArticles } from "../api/client";

type Failure = { title: string; detail?: string; retry: boolean };
type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; data: TopArticles };

const PERIOD_DAYS: Record<TopArticles["period"], number> = { "7d": 7, "30d": 30, "90d": 90 };
const TYPE: Record<ArticleType, { label: string; icon: typeof Icons.BookOpen }> = {
  article: { label: "Article", icon: Icons.BookOpen },
  faq: { label: "FAQ", icon: Icons.HelpCircle },
  how_to: { label: "How-to", icon: Icons.ClipboardList },
};

/**
 * What the error state says, as the helpdesk and amc-vendor-support widgets do. A missing or unreachable service (404,
 * 502, 503, network failure) is "not available yet", not the user's connection; retrying cannot fix 401 or 403.
 */
export function describeFailure(e: unknown): Failure {
  if (!(e instanceof KnowledgeBaseApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Knowledge base data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: "Could not load top articles", detail: "Try again in a moment.", retry: true };
}

/** How readers rated an article, always in words: "85% found it helpful", or "No votes yet". */
export function helpfulLabel(a: Pick<TopArticle, "helpful_count" | "not_helpful_count" | "helpful_share">): string {
  const votes = a.helpful_count + a.not_helpful_count;
  if (votes === 0 || a.helpful_share == null) return "No votes yet";
  return `${Math.round(a.helpful_share * 100)}% found it helpful`;
}

function viewsLabel(views: number): string {
  return `${views} ${views === 1 ? "view" : "views"}`;
}

/**
 * knowledge-base.top-articles on the Support Staff dashboard: the published articles read most in the last 30 days,
 * with their type, how readers rated them and the view count (GET /stats/top-articles). Staff-only articles appear
 * only for callers who may read them; the server decides. The shell renders the panel and its title; this is the body.
 */
export function TopArticlesWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    getTopArticles({}, signal)
      .then((data) => setState({ kind: "ready", data }))
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") setState({ kind: "error", failure: describeFailure(e) });
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
  if (state.data.items.length === 0) {
    return (
      <EmptyState icon={<Icons.BookOpen />} title="No article views yet">
        {`The articles people read most in the last ${PERIOD_DAYS[state.data.period]} days appear here.`}
      </EmptyState>
    );
  }

  return (
    <List divided label="Top articles">
      {state.data.items.map((a, i) => {
        const type = TYPE[a.type] ?? TYPE.article;
        return (
          <ListRow
            key={a.article_id}
            index={i}
            icon={type.icon}
            tone="info"
            title={a.title}
            meta={`${type.label} · ${helpfulLabel(a)}`}
            trailing={<Badge tone="info">{viewsLabel(a.views)}</Badge>}
          />
        );
      })}
    </List>
  );
}
