import { useState, type FormEvent } from "react";
import {
  Badge,
  Button,
  ErrorState,
  Icons,
  List,
  ListRow,
  SkeletonLines,
  type WidgetProps,
} from "@eos/ui-kit";
import {
  AdmissionsApiError,
  linkApplication,
  listMyApplications,
  type Application,
} from "../api/client";
import { formatDate, offerLabel, offerTone, statusLabel, statusTone } from "../components/labels";
import { useLoad } from "../components/useLoad";

const load = (signal?: AbortSignal) => listMyApplications(signal);

/**
 * admissions.application-status on the Applicant dashboard: shows the applicant's linked application,
 * with reference, status and any offer. When nothing is linked yet, it shows a form to link an application.
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
  const { items } = state.data;
  if (items.length === 0) {
    return <LinkForm onLinked={reload} />;
  }
  return <ApplicationList items={items} />;
}

function LinkForm({ onLinked }: { onLinked: () => void }) {
  const [reference, setReference] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!reference.trim() || !email.trim()) {
      setError("Enter your reference number and email.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await linkApplication(reference, email);
      onLinked();
    } catch (err: unknown) {
      if (err instanceof AdmissionsApiError) {
        if (err.status === 404) {
          setError("No application matches that reference number and email.");
        } else if (err.status === 409) {
          setError("This application is linked to another account.");
        } else {
          setError(err.message || "Could not link application.");
        }
      } else {
        setError("Could not link application.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <p className="eos-row__meta">Link your submitted application to track your status here.</p>
      <form
        onSubmit={onSubmit}
        noValidate
        aria-label="Link application"
        style={{ display: "flex", flexDirection: "column", gap: 8 }}
      >
        <label className="eos-field">
          Reference number
          <input
            className="eos-input"
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            placeholder="ADM-2026-A1B2C3"
            autoComplete="off"
            maxLength={32}
          />
        </label>
        <label className="eos-field">
          Email
          <input
            className="eos-input"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            maxLength={320}
          />
        </label>
        {error && (
          <p className="eos-form-error" role="alert">
            {error}
          </p>
        )}
        <Button variant="primary" type="submit" disabled={submitting}>
          {submitting ? "Linking…" : "Link application"}
        </Button>
      </form>
    </div>
  );
}

function ApplicationList({ items }: { items: Application[] }) {
  return (
    <List divided label="Latest applications">
      {items.map((a, i) => (
        <ListRow
          key={a.id}
          index={i}
          icon={Icons.GraduationCap}
          tone="accent"
          title={`${a.reference_number} · ${a.applicant.first_name} ${a.applicant.last_name}`}
          meta={
            a.offer
              ? `${a.academic_year} · Submitted ${formatDate(a.submitted_at)} · Offer: ${offerLabel(a.offer.status)}`
              : `${a.academic_year} · Submitted ${formatDate(a.submitted_at)}`
          }
          trailing={
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              {a.offer && <Badge tone={offerTone(a.offer.status)}>{offerLabel(a.offer.status)}</Badge>}
              <Badge tone={statusTone(a.status)} dot>
                {statusLabel(a.status)}
              </Badge>
            </div>
          }
        />
      ))}
    </List>
  );
}
