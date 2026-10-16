import { useEffect, useState, type MouseEvent } from "react";
import { Button, ButtonLink, EduMark, Icons, Wordmark } from "@eos/ui-kit";
import { APP_URL, NAV, type NavItem, type PublicRoute } from "../content";
import { stagger } from "./Reveal";

/**
 * Public top bar: brand, primary navigation, and the "Sign in" / "Get started" actions.
 *
 * Nav links reveal a staggered letter swap on hover/focus — two stacked copies of each letter in a
 * clipped box, the top copy sliding up and a second (accent-coloured) copy sliding in behind it, each
 * letter a touch later than the one before (pure CSS transitions, no animation library; reduced motion
 * collapses it to an instant colour change via the media query below).
 *
 * Layout follows a "resizable" navbar: logo left, links centred, actions right. At the top of the page
 * it is a full-width frosted bar; once the page scrolls past SCROLL_COMPACT it shrinks into a
 * floating, rounded pill (CSS transitions on the `is-scrolled` class). A soft navy-tint pill slides
 * behind whichever link the pointer is over.
 *
 * Below MENU_BREAKPOINT the link list and "Sign in" move into a slide-down panel behind a menu button,
 * so the site stays fully navigable on a phone instead of just hiding the nav; "Get started" — the one
 * primary action per screen — stays visible at every width.
 */

/**
 * The bar condenses into the floating pill past SCROLL_COMPACT and only expands again back under
 * SCROLL_EXPAND. The gap between them (hysteresis) stops it flickering when the page rests near one line.
 */
const SCROLL_COMPACT = 80;
const SCROLL_EXPAND = 24;
/** Matches the navbar's `max-width: 820px` rule in public.css, where the links move into the menu. */
const MENU_BREAKPOINT = 820;

export function SiteHeader({
  route,
  onNavigate,
}: {
  route: PublicRoute;
  onNavigate: (route: PublicRoute) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [hoverPill, setHoverPill] = useState<{ left: number; width: number } | null>(null);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const y = window.scrollY;
      setScrolled((was) => (was ? y > SCROLL_EXPAND : y > SCROLL_COMPACT));
    };
    // At most one state check per animation frame, however fast scroll events arrive.
    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);

  useEffect(() => {
    setMenuOpen(false);
  }, [route]);

  useEffect(() => {
    if (!menuOpen) return;
    const onResize = () => {
      if (window.innerWidth > MENU_BREAKPOINT) setMenuOpen(false);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [menuOpen]);

  const go = (next: PublicRoute) => (e: { preventDefault: () => void }) => {
    e.preventDefault();
    onNavigate(next);
  };

  const showHoverPill = (e: MouseEvent<HTMLAnchorElement>) => {
    const link = e.currentTarget;
    setHoverPill({ left: link.offsetLeft, width: link.offsetWidth });
  };

  return (
    <header className={scrolled ? "wpc-header is-scrolled" : "wpc-header"}>
      <div className="wpc-header__bar">
        <a className="wpc-brand" href="#/" onClick={go("home")} aria-label="Education OS home">
          <EduMark size={30} />
          <Wordmark size={17} />
        </a>

        <nav className="wpc-nav" aria-label="Primary" onMouseLeave={() => setHoverPill(null)}>
          <span
            className={hoverPill ? "wpc-nav__pill is-visible" : "wpc-nav__pill"}
            style={hoverPill ? { transform: `translateX(${hoverPill.left}px)`, width: hoverPill.width } : undefined}
            aria-hidden
          />
          {NAV.map((item) => (
            <NavLink
              key={item.route}
              item={item}
              active={item.route === route}
              onClick={go(item.route)}
              onMouseEnter={showHoverPill}
            />
          ))}
        </nav>

        <div className="wpc-header__actions">
          <ButtonLink variant="ghost" href={APP_URL} className="wpc-header__signin">
            Sign in
          </ButtonLink>
          <Button variant="primary" onClick={() => onNavigate("signup")}>
            Get started
          </Button>
          <button
            type="button"
            className="wpc-nav-toggle"
            aria-expanded={menuOpen}
            aria-controls="wpc-mobile-nav"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            onClick={() => setMenuOpen((open) => !open)}
          >
            {menuOpen ? <Icons.X size={20} aria-hidden /> : <BurgerIcon />}
          </button>
        </div>
      </div>

      {menuOpen && (
        <nav id="wpc-mobile-nav" className="wpc-mobile-nav" aria-label="Primary">
          {NAV.map((item) => (
            <a
              key={item.route}
              href={item.href}
              onClick={go(item.route)}
              className={item.route === route ? "wpc-mobile-nav__link is-active" : "wpc-mobile-nav__link"}
              aria-current={item.route === route ? "page" : undefined}
            >
              {item.label}
            </a>
          ))}
          <a className="wpc-mobile-nav__link" href={APP_URL}>
            Sign in
          </a>
        </nav>
      )}
    </header>
  );
}

/** Menu icon whose three lines shorten in a stagger on hover (CSS: `.wpc-burger__line` in public.css). */
function BurgerIcon() {
  return (
    <svg
      width={20}
      height={20}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      aria-hidden
    >
      <path className="wpc-burger__line wpc-burger__line--1" d="M4 6h16" />
      <path className="wpc-burger__line wpc-burger__line--2" d="M4 12h16" />
      <path className="wpc-burger__line wpc-burger__line--3" d="M4 18h16" />
    </svg>
  );
}

/** One nav link whose letters swap in a staggered block on hover/focus (decorative; CSS-only). */
function NavLink({
  item,
  active,
  onClick,
  onMouseEnter,
}: {
  item: NavItem;
  active: boolean;
  onClick: (e: { preventDefault: () => void }) => void;
  onMouseEnter: (e: MouseEvent<HTMLAnchorElement>) => void;
}) {
  return (
    <a
      href={item.href}
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      className={active ? "wpc-nav__link is-active" : "wpc-nav__link"}
      aria-current={active ? "page" : undefined}
    >
      <span className="wpc-nav__swap" aria-hidden>
        {item.label.split("").map((ch, i) => (
          <span key={i} className="wpc-nav__letter" style={stagger(i)}>
            <span className="wpc-nav__letter-face wpc-nav__letter-face--base">{ch === " " ? " " : ch}</span>
            <span className="wpc-nav__letter-face wpc-nav__letter-face--alt">{ch === " " ? " " : ch}</span>
          </span>
        ))}
      </span>
      <span className="eos-sr-only">{item.label}</span>
    </a>
  );
}
