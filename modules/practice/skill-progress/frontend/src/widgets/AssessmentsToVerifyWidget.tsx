import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import {
  describeFailure,
  listAssessmentsToVerify,
  listSkills,
  shortDate,
  type Assessment,
  type Failure,
  type Skill,
} from "../api/client";

type State =
  | { kind: "loading" }
  | { kind: "error"; failure: Failure }
  | { kind: "ready"; items: Assessment[]; total: number; skills: Map<string, string> };

const SHOWN = 6;

/**
 * skill-progress.assessments-due on the instructor dashboards: assessments recorded and not yet verified, newest
 * first (GET /assessments?status=submitted, with GET /skills for the skill titles). "Due" here means waiting for
 * verification; a due date is a later addition (#329). The shell renders the panel and its title; this is the body.
 */
export function AssessmentsToVerifyWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    Promise.all([listAssessmentsToVerify(SHOWN, signal), listSkills(signal).catch(() => ({ items: [] as Skill[] }))])
      .then(([page, skills]) =>
        setState({
          kind: "ready",
          items: page.items ?? [],
          total: page.total ?? (page.items ?? []).length,
          skills: new Map((skills.items ?? []).map((s) => [s.id, s.title])),
        }),
      )
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") {
          setState({ kind: "error", failure: describeFailure(e, "assessments to verify") });
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
  if (state.total === 0) {
    return (
      <EmptyState icon={<Icons.CheckCircle2 />} title="Nothing to verify">
        Assessments that are recorded and not yet verified appear here.
      </EmptyState>
    );
  }
  const more = state.total - state.items.length;
  return (
    <>
      <p className="eos-row__meta" aria-label="Verification summary">
        {state.total === 1 ? "1 assessment waiting" : `${state.total} assessments waiting`}
      </p>
      <List divided label="Assessments to verify">
        {state.items.map((a, i) => (
          <ListRow
            key={a.id}
            index={i}
            icon={Icons.ClipboardList}
            tone="warning"
            title={state.skills.get(a.skill_id) ?? "Skill"}
            meta={`Learner ${a.learner_id.slice(0, 8)} · assessed ${shortDate(a.assessed_at)}`}
            trailing={<Badge tone="warning">{a.level_achieved}</Badge>}
          />
        ))}
        {more > 0 && <ListRow title={`${more} more waiting`} tone="neutral" icon={Icons.Layers} />}
      </List>
    </>
  );
}
