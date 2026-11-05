import { useCallback, useEffect, useState } from "react";
import { EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { describeFailure, getFrameworkSummary, type Failure, type FrameworkSummary } from "../api/client";

type State =
  | { kind: "loading" }
  | { kind: "error"; failure: Failure }
  | { kind: "ready"; frameworks: FrameworkSummary[] };

const SHOWN = 5;

/**
 * skill-progress.cohort-overview on the practicum coordinator dashboard: per framework, the learners assessed and
 * how many skills sit at each level (GET /reports/framework-summary). It is a summary of every assessed learner, not
 * of a cohort: skill-progress has no groups, and a real cohort would need a learner list fed by events (#329). The
 * shell renders the panel and its title; this is the body.
 */
export function CohortOverviewWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    getFrameworkSummary(signal)
      .then((report) => setState({ kind: "ready", frameworks: report.items ?? [] }))
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") {
          setState({ kind: "error", failure: describeFailure(e, "the skill summary") });
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
  if (state.frameworks.length === 0) {
    return (
      <EmptyState icon={<Icons.Users />} title="No assessments yet">
        Skill levels are summarised here once assessments are recorded.
      </EmptyState>
    );
  }
  const shown = state.frameworks.slice(0, SHOWN);
  const hidden = state.frameworks.length - shown.length;
  return (
    <List divided label="Skill levels by framework">
      {shown.map((f, i) => (
        <ListRow
          key={f.framework_id}
          index={i}
          icon={Icons.Layers}
          tone="info"
          title={f.framework_title}
          meta={f.levels.map((l) => `${l.level} ${l.count}`).join(" · ") || "No levels yet"}
          trailing={<span>{f.learners_assessed === 1 ? "1 learner" : `${f.learners_assessed} learners`}</span>}
        />
      ))}
      {hidden > 0 && (
        <ListRow title={`${hidden} more ${hidden === 1 ? "framework" : "frameworks"}`} tone="neutral" icon={Icons.Layers} />
      )}
    </List>
  );
}
