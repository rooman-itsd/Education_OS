import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { describeFailure, getMyProgress, shortDate, type Failure, type LearnerProgressSummary } from "../api/client";

type State =
  | { kind: "loading" }
  | { kind: "error"; failure: Failure }
  | { kind: "ready"; progress: LearnerProgressSummary };

const SHOWN = 6;

/**
 * skill-progress.my-progress on the learner dashboards: the viewer's latest level on each skill they were assessed
 * on, most recently assessed first (GET /me/progress). The shell renders the panel and its title; this is the body.
 */
export function MyProgressWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    getMyProgress(signal)
      .then((progress) => setState({ kind: "ready", progress }))
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") {
          setState({ kind: "error", failure: describeFailure(e, "your progress") });
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

  const skills = [...(state.progress.current_skills ?? [])].sort((a, b) =>
    (b.latest_assessed_at ?? "").localeCompare(a.latest_assessed_at ?? ""),
  );
  if (skills.length === 0) {
    return (
      <EmptyState icon={<Icons.Award />} title="No assessments yet">
        Your skill levels appear here once an instructor has assessed you.
      </EmptyState>
    );
  }
  const shown = skills.slice(0, SHOWN);
  return (
    <>
      <p className="eos-row__meta" aria-label="Progress summary">
        {skills.length === 1 ? "1 skill assessed" : `${skills.length} skills assessed`}
      </p>
      <List divided label="My skills">
        {shown.map((s, i) => (
          <ListRow
            key={s.skill_id}
            index={i}
            icon={Icons.Award}
            tone="info"
            title={s.skill_title}
            meta={[s.category, `assessed ${shortDate(s.latest_assessed_at)}`].filter(Boolean).join(" · ")}
            trailing={<Badge tone="info">{s.latest_level}</Badge>}
          />
        ))}
        {skills.length > shown.length && (
          <ListRow
            title={`${skills.length - shown.length} more ${skills.length - shown.length === 1 ? "skill" : "skills"}`}
            tone="neutral"
            icon={Icons.Layers}
          />
        )}
      </List>
    </>
  );
}
