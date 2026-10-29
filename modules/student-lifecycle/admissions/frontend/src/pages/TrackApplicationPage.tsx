import { useRef, useState, type FormEvent } from "react";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Icons,
  List,
  ListRow,
  PageHero,
  Panel,
  PanelBody,
  PanelHeader,
  SkeletonLines,
  ThemeScope,
  themeForSuite,
} from "@eos/ui-kit";
import { AdmissionsApiError, describeFailure, isAbort, trackApplication, type Application, type Failure } from "../api/client";
import {
  documentTypeLabel,
  formatDate,
  offerLabel,
  offerTone,
  statusExplained,
  statusLabel,
  statusTone,
  verificationLabel,
  verificationTone,
} from "../components/labels";

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "not-found" }
  | { kind: "error"; failure: Failure }
  | { kind: "ready"; application: Application };

/**
 * The applicant's view of their own application, with no account: reference number and email, both required to
 * match (GET /public/{org_slug}/applications/track). A wrong reference and a wrong email get the same answer, so the
 * page reveals nothing about other applications. The host mounts it on the public site for one organisation.
 */
export function TrackApplicationPage({ orgSlug }: { orgSlug: string }) {
  const [reference, setReference] = useState("");
  const [email, setEmail] = useState("");
  const [missing, setMissing] = useState(false);
  const [state, setState] = useState<State>({ kind: "idle" });
  const inflight = useRef<AbortController | null>(null);

  const track = () => {
    if (!reference.trim() || !email.trim()) {
      setMissing(true);
      return;
    }
    setMissing(false);
    inflight.current?.abort();
    const ctrl = new AbortController();
    inflight.current = ctrl;
    setState({ kind: "loading" });
    trackApplication(orgSlug, reference, email, ctrl.signal)
      .then((application) => setState({ kind: "ready", application }))
      .catch((e: unknown) => {
        if (isAbort(e)) return;
        if (e instanceof AdmissionsApiError && e.status === 404) setState({ kind: "not-found" });
        else setState({ kind: "error", failure: describeFailure(e, "your application") });
      });
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    track();
  };

  return (
    <ThemeScope theme={themeForSuite("student-lifecycle")} className="eos-dashboard">
      <PageHero
        eyebrow="Admissions"
        title="Track your application"
        subtitle="Enter the reference number from your confirmation and the email you applied with."
      />

      <Panel lift={false}>
        <PanelBody>
          <form
            onSubmit={onSubmit}
            noValidate
            aria-label="Track your application"
            style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 480 }}
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
            {missing && (
              <p className="eos-form-error" role="alert">
                Enter your reference number and email.
              </p>
            )}
            <Button variant="primary" type="submit" disabled={state.kind === "loading"}>
              {state.kind === "loading" ? "Looking up…" : "Track application"}
            </Button>
          </form>
        </PanelBody>
      </Panel>

      {state.kind === "loading" && (
        <Panel lift={false}>
          <PanelBody>
            <SkeletonLines lines={5} />
          </PanelBody>
        </Panel>
      )}
      {state.kind === "not-found" && (
        <Panel lift={false}>
          <PanelBody>
            <EmptyState icon={<Icons.Search />} title="No application found">
              Check the reference number and use the email you applied with.
            </EmptyState>
          </PanelBody>
        </Panel>
      )}
      {state.kind === "error" && (
        <Panel lift={false}>
          <PanelBody>
            <ErrorState title={state.failure.title} onRetry={state.failure.retry ? track : undefined}>
              {state.failure.detail}
            </ErrorState>
          </PanelBody>
        </Panel>
      )}
      {state.kind === "ready" && <ApplicationView application={state.application} />}
    </ThemeScope>
  );
}

function ApplicationView({ application: a }: { application: Application }) {
  return (
    <>
      <Panel lift={false}>
        <PanelHeader
          title={a.reference_number}
          subtitle={`${a.applicant.first_name} ${a.applicant.last_name} · ${a.academic_year}`}
          action={
            <Badge tone={statusTone(a.status)} dot>
              {statusLabel(a.status)}
            </Badge>
          }
        />
        <PanelBody>
          <p>{statusExplained(a.status)}</p>
          <p className="eos-row__meta">Submitted {formatDate(a.submitted_at)}</p>
        </PanelBody>
      </Panel>

      {a.offer && (
        <Panel lift={false}>
          <PanelHeader
            title="Your offer"
            action={<Badge tone={offerTone(a.offer.status)}>{offerLabel(a.offer.status)}</Badge>}
          />
          <PanelBody>
            {a.offer.note && <p>{a.offer.note}</p>}
            <p className="eos-row__meta">
              Offered {formatDate(a.offer.offered_at)}
              {a.offer.expires_at ? ` · Respond by ${formatDate(a.offer.expires_at)}` : ""}
            </p>
          </PanelBody>
        </Panel>
      )}

      <Panel lift={false}>
        <PanelHeader title="Documents" subtitle={`${a.documents.length} uploaded`} />
        <PanelBody>
          {a.documents.length === 0 ? (
            <EmptyState icon={<Icons.FileText />} title="No documents yet">
              Documents you upload for this application appear here with their verification status.
            </EmptyState>
          ) : (
            <List divided label="Your documents">
              {a.documents.map((d, i) => (
                <ListRow
                  key={d.id}
                  index={i}
                  icon={Icons.FileText}
                  tone={d.verification_status === "verified" ? "success" : d.verification_status === "rejected" ? "danger" : "warning"}
                  title={d.label || documentTypeLabel(d.type)}
                  meta={`${documentTypeLabel(d.type)} · Uploaded ${formatDate(d.uploaded_at)}`}
                  trailing={<Badge tone={verificationTone(d.verification_status)}>{verificationLabel(d.verification_status)}</Badge>}
                />
              ))}
            </List>
          )}
        </PanelBody>
      </Panel>
    </>
  );
}
