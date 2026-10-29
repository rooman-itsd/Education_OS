import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { listPendingDocuments } from "../api/client";
import { documentTypeLabel, waitingFor } from "../components/labels";
import { useLoad } from "../components/useLoad";

const SHOWN = 6;
const load = (signal?: AbortSignal) => listPendingDocuments(SHOWN, signal);

/**
 * admissions.pending-documents for staff who verify documents: what applicants uploaded that nobody has verified,
 * longest waiting first (GET /documents?verification_status=pending).
 */
export function PendingDocumentsWidget(_props: WidgetProps) {
  const [state, reload] = useLoad(load, "documents waiting for verification");

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
      <EmptyState icon={<Icons.FileCheck2 />} title="Nothing waiting for verification">
        Documents applicants upload appear here until someone verifies them.
      </EmptyState>
    );
  }
  return (
    <>
      <p className="eos-row__meta" aria-label="Documents waiting">
        {total} {total === 1 ? "document" : "documents"} waiting for verification
      </p>
      <List divided label="Documents waiting for verification">
        {items.map((d, i) => (
          <ListRow
            key={d.id}
            index={i}
            icon={Icons.FileText}
            tone="warning"
            title={`${d.reference_number} · ${d.applicant_name}`}
            meta={d.label ? `${documentTypeLabel(d.type)} · ${d.label}` : documentTypeLabel(d.type)}
            trailing={<Badge tone="warning">Waiting {waitingFor(d.uploaded_at)}</Badge>}
          />
        ))}
        {total > items.length && (
          <ListRow title={`${total - items.length} more waiting`} tone="neutral" icon={Icons.ClipboardList} />
        )}
      </List>
    </>
  );
}
