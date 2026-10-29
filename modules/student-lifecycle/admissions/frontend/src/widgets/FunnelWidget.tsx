import { EmptyState, ErrorState, Icons, ProgressList, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getFunnel } from "../api/client";
import { percent } from "../components/labels";
import { useLoad } from "../components/useLoad";

/**
 * admissions.funnel on the Management (VC, Registrar) dashboard: how many applications reached each stage, each bar
 * measured against everyone who applied, like the super admin console's Admissions Funnel panel
 * (GET /reports/funnel, counts only). The shell renders the panel and its title; this is the body.
 */
export function FunnelWidget(_props: WidgetProps) {
  const [state, reload] = useLoad(getFunnel, "the admissions funnel");

  if (state.kind === "loading") return <SkeletonLines lines={4} />;
  if (state.kind === "error") {
    const { title, detail, retry } = state.failure;
    return (
      <ErrorState title={title} onRetry={retry ? reload : undefined}>
        {detail}
      </ErrorState>
    );
  }
  const { total, stages } = state.data;
  if (total === 0) {
    return (
      <EmptyState icon={<Icons.GraduationCap />} title="No applications yet">
        Applications submitted on your admissions page appear here, stage by stage.
      </EmptyState>
    );
  }
  return (
    <>
      <ProgressList
        relativeToFirst
        items={[
          { label: "Applied", count: stages.applied },
          { label: "Eligible", count: stages.eligible },
          { label: "Offered", count: stages.offered },
          { label: "Accepted", count: stages.accepted },
        ]}
      />
      <p className="eos-row__meta" aria-label="Funnel summary">
        Overall acceptance <strong>{percent(stages.accepted, stages.applied)}%</strong> · {total}{" "}
        {total === 1 ? "application" : "applications"}
      </p>
    </>
  );
}
