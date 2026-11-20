/*
 * DRAFT: REQUIRES LEGAL REVIEW BEFORE PUBLICATION (#148). The text is in ../legal.ts.
 */
import type { MouseEvent } from "react";
import { LEGAL_EFFECTIVE, LEGAL_VERSION, PRIVACY_NOTICE, TERMS_OF_SERVICE, type LegalDocument } from "../legal";
import type { PublicRoute } from "../content";

/**
 * One legal document of the public site: the Privacy Notice (#/privacy) or the Terms of Service (#/terms).
 * A title, the version and effective date, a contents list, then the numbered sections. The contents links
 * scroll to their section without touching the hash, which the site's router owns.
 */
function LegalPage({
  doc,
  self,
  other,
  onNavigate,
}: {
  doc: LegalDocument;
  self: PublicRoute;
  other: { route: PublicRoute; label: string };
  onNavigate: (route: PublicRoute) => void;
}) {
  const jump = (id: string) => (e: MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    document.getElementById(id)?.scrollIntoView({ block: "start" });
  };
  return (
    <div className="wpc-page wpc-legal">
      <div className="wpc-container wpc-legal__inner">
        <header className="wpc-legal__head">
          <h1 className="wpc-legal__title">{doc.title}</h1>
          <p className="wpc-legal__meta">
            Version {LEGAL_VERSION} · Effective {LEGAL_EFFECTIVE}
          </p>
          <p className="wpc-legal__lead">{doc.summary}</p>
        </header>

        <nav className="wpc-legal__toc" aria-label="Contents">
          <h2 className="wpc-legal__toc-title">Contents</h2>
          <ol>
            {doc.sections.map((s) => (
              <li key={s.id}>
                <a href={`#/${self}`} onClick={jump(`legal-${s.id}`)}>
                  {s.heading}
                </a>
              </li>
            ))}
          </ol>
        </nav>

        <div className="wpc-legal__body">
          {doc.sections.map((s) => (
            <section key={s.id} id={`legal-${s.id}`} className="wpc-legal__section" aria-labelledby={`legal-${s.id}-h`}>
              <h2 id={`legal-${s.id}-h`} className="wpc-legal__h2">
                {s.heading}
              </h2>
              {s.blocks.map((b, i) =>
                typeof b === "string" ? (
                  <p key={i}>{b}</p>
                ) : (
                  <ul key={i}>
                    {b.list.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ),
              )}
            </section>
          ))}
          <p className="wpc-legal__other">
            See also our{" "}
            <a
              className="wpc-link"
              href={`#/${other.route}`}
              onClick={(e) => {
                e.preventDefault();
                onNavigate(other.route);
              }}
            >
              {other.label}
            </a>
            .
          </p>
        </div>
      </div>
    </div>
  );
}

export function PrivacyPage({ onNavigate }: { onNavigate: (route: PublicRoute) => void }) {
  return <LegalPage doc={PRIVACY_NOTICE} self="privacy" other={{ route: "terms", label: "Terms of Service" }} onNavigate={onNavigate} />;
}

export function TermsPage({ onNavigate }: { onNavigate: (route: PublicRoute) => void }) {
  return <LegalPage doc={TERMS_OF_SERVICE} self="terms" other={{ route: "privacy", label: "Privacy Notice" }} onNavigate={onNavigate} />;
}
