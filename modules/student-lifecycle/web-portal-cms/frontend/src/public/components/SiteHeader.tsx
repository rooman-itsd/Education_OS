import { useEffect, useRef, useState, type MouseEvent } from "react";
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
 * Layout: logo left, links centred, actions right, on a plain bar in the page's paper colour. Once the
 * page scrolls past SCROLL_COMPACT the bar steps one tone darker and slightly shorter (no glass, no
 * shadow, no floating pill). A flat tone slides behind whichever link the pointer is over.
 *
 * Below MENU_BREAKPOINT the links move into a full-height menu sheet behind a menu button: large links,
 * "Start free trial" and "Sign in" as buttons, Escape to close, focus moved into it and the page held
 * still behind it. "Start free trial", the one primary action, stays in the bar at every width.
 */

/**
 * The bar condenses into the floating pill past SCROLL_COMPACT and only expands again back under
 * SCROLL_EXPAND. The gap between them (hysteresis) stops it flickering when the page rests near one line.
 */
const SCROLL_COMPACT = 80;
const SCROLL_EXPAND = 24;
/** Matches the navbar's `max-width: 860px` rule in public.css, where the links move into the menu. */
const MENU_BREAKPOINT = 860;

export function SiteHeader({
  route,
  onNavigate,
}: {
  route: PublicRoute;
  onNavigate: (route: PublicRoute) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const sheetRef = useRef<HTMLElement>(null);
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
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMenuOpen(false);
        toggleRef.current?.focus();
      }
    };
    // The sheet covers the page: hold the page still and move focus into the menu.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    sheetRef.current?.focus();
    window.addEventListener("resize", onResize);
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("resize", onResize);
      window.removeEventListener("keydown", onKey);
    };
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
          <Button variant="primary" onClick={() => onNavigate("signup")} className="wpc-header__cta">
            <span className="wpc-header__cta-long">Start free trial</span>
            <span className="wpc-header__cta-short">Free trial</span>
          </Button>
          <button
            ref={toggleRef}
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
        <nav id="wpc-mobile-nav" ref={sheetRef} className="wpc-mobile-nav" aria-label="Primary" tabIndex={-1}>
          <ul className="wpc-mobile-nav__list">
            {NAV.map((item) => (
              <li key={item.route}>
                <a
                  href={item.href}
                  onClick={go(item.route)}
                  className={item.route === route ? "wpc-mobile-nav__link is-active" : "wpc-mobile-nav__link"}
                  aria-current={item.route === route ? "page" : undefined}
                >
                  {item.label}
                  <Icons.ArrowRight size={20} aria-hidden />
                </a>
              </li>
            ))}
            <li>
              <a
                href="#/signup"
                onClick={go("signup")}
                className={route === "signup" ? "wpc-mobile-nav__link is-active" : "wpc-mobile-nav__link"}
                aria-current={route === "signup" ? "page" : undefined}
              >
                Plans &amp; pricing
                <Icons.ArrowRight size={20} aria-hidden />
              </a>
            </li>
          </ul>
          <div className="wpc-mobile-nav__actions">
            <Button variant="primary" onClick={() => onNavigate("signup")}>
              Start free trial
            </Button>
            <ButtonLink variant="secondary" href={APP_URL}>
              Sign in
            </ButtonLink>
          </div>
          <p className="wpc-mobile-nav__note">Every organisation starts on a free 30-day trial.</p>
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
