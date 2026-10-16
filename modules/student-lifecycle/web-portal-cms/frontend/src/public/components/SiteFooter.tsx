import type { MouseEvent } from "react";
import { EduMark, Icons, Wordmark } from "@eos/ui-kit";
import {
  BRAND,
  FOOTER,
  FOOTER_LEGAL,
  FOOTER_SOCIAL,
  FOOTER_TODO_HREF,
  type FooterLink,
  type PublicRoute,
} from "../content";
import { SocialIcon } from "./SocialIcons";

/** A placeholder link (FOOTER_TODO_HREF) stays put instead of jumping the hash router to the top. */
const holdPlaceholder = (href: string | undefined) => (e: MouseEvent<HTMLAnchorElement>) => {
  if (href === FOOTER_TODO_HREF) e.preventDefault();
};

/**
 * Public footer, a designed close rather than a sitemap: ground and ink inverted. Across the top, the
 * brand with its tagline and social marks, then three link columns (Product, Company,
 * Contact); the name returns at full width along the bottom, above the legal line (copyright and the
 * legal links). Links still pointing at FOOTER_TODO_HREF render but do nothing until their real URL is
 * set in content.ts. Links underline on hover and press in when clicked; keyboard focus shows the
 * shared focus ring. The year is read at render time, not hard-coded.
 */
export function SiteFooter({ onNavigate }: { onNavigate: (route: PublicRoute) => void }) {
  const renderLink = (link: FooterLink, className = "wpc-footer__link") => {
    const Icon = link.icon ? Icons[link.icon] : null;
    const content = (
      <>
        {Icon && <Icon size={16} aria-hidden className="wpc-footer__icon" />}
        <span>{link.label}</span>
      </>
    );
    if (link.route) {
      const route = link.route;
      return (
        <a
          className={className}
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
      <a className={className} href={link.href} onClick={holdPlaceholder(link.href)}>
        {content}
      </a>
    );
  };

  return (
    <footer className="wpc-footer">
      <div className="wpc-container wpc-footer__top">
        <div className="wpc-footer__brand">
          <a
            className="wpc-footer__logo"
            href="#/"
            onClick={(e) => {
              e.preventDefault();
              onNavigate("home");
            }}
            aria-label={`${BRAND.name} home`}
          >
            <EduMark size={32} />
            <Wordmark size={18} inverse />
          </a>
          <p className="wpc-footer__tagline">{BRAND.tagline}</p>
          <ul className="wpc-footer__social" aria-label={`${BRAND.name} on social media`}>
            {FOOTER_SOCIAL.map((s) => (
              <li key={s.network}>
                <a
                  className="wpc-footer__social-link"
                  href={s.href}
                  onClick={holdPlaceholder(s.href)}
                  aria-label={`${BRAND.name} on ${s.label}`}
                  title={s.label}
                >
                  <SocialIcon network={s.network} />
                </a>
              </li>
            ))}
          </ul>
        </div>

        {FOOTER.map((col) => (
          <nav key={col.heading} className="wpc-footer__col" aria-label={col.heading}>
            <h2 className="wpc-footer__heading">{col.heading}</h2>
            <ul className="wpc-footer__links">
              {col.links.map((link) => (
                <li key={link.label}>{renderLink(link)}</li>
              ))}
            </ul>
          </nav>
        ))}
      </div>

      <div className="wpc-container wpc-footer__bottom">
        <p className="wpc-footer__mark" aria-hidden="true">
          Education OS
        </p>
        <div className="wpc-footer__legal">
          <p>
            © {new Date().getFullYear()} {BRAND.name} · A {BRAND.parent} initiative · All rights reserved
          </p>
          <nav aria-label="Legal">
            <ul className="wpc-footer__legal-links">
              {FOOTER_LEGAL.map((link) => (
                <li key={link.label}>{renderLink(link, "wpc-footer__legal-link")}</li>
              ))}
            </ul>
          </nav>
        </div>
      </div>
    </footer>
  );
}
