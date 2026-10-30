import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { listRecentApplications } from "../api/client";
import { formatDate, statusLabel, statusTone } from "../components/labels";
import { useLoad } from "../components/useLoad";

const SHOWN = 6;
const load = (signal?: AbortSignal) => listRecentApplications(SHOWN, signal);

/**
 * admissions.application-status for admissions staff: the newest applications in the organisation with their status
 * in words, as the super admin console's applications table shows them (GET /applications, newest first).
 */
export function ApplicationStatusWidget(_props: WidgetProps) {
  const [state, reload] = useLoad(load, "applications");

  if (state.kind === "loading") return <SkeletonLines lines={4} />;
  if (state.kind === "error") {
    const { title, detail, retry } = state.failure;
    return (
      <ErrorState title={title} onRetry={retry ? reload : undefined}>
        {detail}
      </ErrorState>
    );
  }
  const { items, total } = state.data;
  if (total === 0) {
    return (
      <EmptyState icon={<Icons.GraduationCap />} title="No applications yet">
        New applications appear here as applicants submit them.
      </EmptyState>
    );
  }
  return (
    <List divided label="Latest applications">
      {items.map((a, i) => (
        <ListRow
          key={a.id}
          index={i}
          icon={Icons.GraduationCap}
          tone="accent"
          title={`${a.reference_number} · ${a.applicant.first_name} ${a.applicant.last_name}`}
          meta={`${a.academic_year} · Submitted ${formatDate(a.submitted_at)}`}
          trailing={
            <Badge tone={statusTone(a.status)} dot>
              {statusLabel(a.status)}
            </Badge>
          }
        />
      ))}
      {total > items.length && (
        <ListRow title={`${total - items.length} more`} tone="neutral" icon={Icons.ClipboardList} />
      )}
    </List>
  );
}
