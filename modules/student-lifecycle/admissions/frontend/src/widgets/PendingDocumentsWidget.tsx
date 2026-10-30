import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { listMyApplications, type ApplicationDocument } from "../api/client";
import { documentTypeLabel, formatDate, verificationLabel, verificationTone, waitingFor } from "../components/labels";
import { useLoad } from "../components/useLoad";

const load = (signal?: AbortSignal) => listMyApplications(signal);

interface ApplicantDocumentItem extends ApplicationDocument {
  reference_number: string;
}

/**
 * admissions.pending-documents on the Applicant dashboard: lists the applicant's own documents that
 * are pending verification or rejected, with any rejection note.
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

  const items: ApplicantDocumentItem[] = (state.data.items || []).flatMap((app) =>
    (app.documents || [])
      .filter((d) => d.verification_status === "pending" || d.verification_status === "rejected")
      .map((d) => ({ ...d, reference_number: app.reference_number })),
  );

  if (items.length === 0) {
    return (
      <EmptyState icon={<Icons.FileCheck2 />} title="Nothing waiting for verification">
        Documents applicants upload appear here until someone verifies them.
      </EmptyState>
    );
  }

  return (
    <>
      <p className="eos-row__meta" aria-label="Documents waiting">
        {items.length} {items.length === 1 ? "document" : "documents"} waiting for verification
      </p>
      <List divided label="Documents waiting for verification">
        {items.map((d, i) => (
          <ListRow
            key={d.id}
            index={i}
            icon={Icons.FileText}
            tone={d.verification_status === "rejected" ? "danger" : "warning"}
            title={d.label ? `${documentTypeLabel(d.type)} · ${d.label}` : documentTypeLabel(d.type)}
            meta={
              d.verification_status === "rejected" && d.verification_note
                ? `Rejected: ${d.verification_note} · ${d.reference_number}`
                : `${d.reference_number} · Uploaded ${formatDate(d.uploaded_at)}`
            }
            trailing={
              d.verification_status === "rejected" ? (
                <Badge tone={verificationTone(d.verification_status)}>
                  {verificationLabel(d.verification_status)}
                </Badge>
              ) : (
                <Badge tone="warning">Waiting {waitingFor(d.uploaded_at)}</Badge>
              )
            }
          />
        ))}
      </List>
    </>
  );
}
