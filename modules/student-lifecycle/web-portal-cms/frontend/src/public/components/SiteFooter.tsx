import { EduMark, Icons, Wordmark } from "@eos/ui-kit";
import { BRAND, FOOTER, FOOTER_TODO_HREF, type FooterLink, type PublicRoute } from "../content";

/**
 * Public footer: brand and tagline on the left, link columns (Product, Platform) across the rest of
 * the row, an oversized decorative "EDUCATION OS" wordmark behind the lower part, and a legal bar.
 * Only links to pages that exist are shown — any link still pointing at FOOTER_TODO_HREF is skipped
 * until its page ships (terms/privacy/contact are intentionally omitted until confirmed, features.md
 * §J). The year is read at render time, not hard-coded.
 */
export function SiteFooter({ onNavigate }: { onNavigate: (route: PublicRoute) => void }) {
  const renderLink = (link: FooterLink) => {
    const Icon = link.icon ? Icons[link.icon] : null;
    const content = (
      <>
        {Icon && (
          <span className="wpc-footer__icon" aria-hidden>
            <Icon size={15} />
          </span>
        )}
        <span>{link.label}</span>
      </>
    );
    if (link.route) {
      const route = link.route;
      return (
        <a
          className="wpc-footer__link"
          href={route === "home" ? "#/" : `#/${route}`}
          onClick={(e) => {
            e.preventDefault();
            onNavigate(route);
          }}
        >
          {content}
        </a>
      );
    }
    return (
      <a className="wpc-footer__link" href={link.href}>
        {content}
      </a>
    );
  };

  return (
    <footer className="wpc-footer">
      <div className="wpc-container wpc-footer__inner">
        <div className="wpc-footer__brand">
          <a
            className="wpc-brand wpc-footer__logo"
            href="#/"
            onClick={(e) => {
              e.preventDefault();
              onNavigate("home");
            }}
            aria-label={`${BRAND.name} home`}
          >
            <EduMark size={32} />
            <Wordmark size={18} />
          </a>
          <p className="wpc-footer__tagline">{BRAND.tagline}</p>
        </div>

        {FOOTER.map((col) => (
          <nav key={col.heading} className="wpc-footer__col" aria-label={col.heading}>
            <h2 className="wpc-footer__col-heading">{col.heading}</h2>
            <ul className="wpc-footer__links">
              {col.links
                .filter((link) => link.href !== FOOTER_TODO_HREF)
                .map((link) => (
                  <li key={link.label}>{renderLink(link)}</li>
                ))}
            </ul>
          </nav>
        ))}
      </div>

      <div className="wpc-container wpc-footer__legal">
        © {new Date().getFullYear()} {BRAND.name} · A {BRAND.parent} initiative
      </div>

      {/* Oversized brand signature behind the lower footer; purely decorative. */}
      <div className="wpc-footer__mark" aria-hidden="true">
        EDUCATION OS
      </div>
    </footer>
  );
}
