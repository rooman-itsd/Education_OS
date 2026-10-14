import { Fragment, useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { Button, Icons, useInView } from "@eos/ui-kit";
import {
  HOME_ADAPT,
  HOME_HERO,
  HOME_ONBOARDING,
  HOME_ONBOARDING_NOTE,
  HOME_SHOWCASE,
  HOME_TICKER,
  type IconItem,
  type PublicRoute,
  type ShowcaseItem,
  type TickerItem,
} from "../content";
import { Reveal, RevealGroup, stagger } from "../components/Reveal";

/**
 * Home page: centred hero over brand-coloured silk waves, with the capability ticker in the hero's
 * lower area; then the product showcase, how Education OS adapts to institution types, the onboarding
 * overview, which closes the page with its own call to action. Copy is from docs/features.md; nothing Specified/Planned is shown as
 * functional. Motion is restrained and reduced-motion safe.
 */
/** Hero headline, split so the first two lines reveal word by word and the last phrase rotates. */
const TITLE_LINE_1 = "Run your whole institution";
const TITLE_LINE_2 = "on";
const ROTATING_WORDS = ["one platform.", "one dashboard.", "one connected system.", "one source of truth."];

export function HomePage({ onNavigate }: { onNavigate: (route: PublicRoute) => void }) {
  return (
    <div className="wpc-page">
      {/* Hero */}
      <section className="wpc-herowrap">
        <HeroVideo />
        {/*
          Silk-wave background (inline SVG) — disabled in favour of the video above. To restore it,
          uncomment this block; its CSS (.wpc-herobg, .wpc-waves, .wpc-tone--*, .wpc-wave__line) is still
          in public.css.

        <div className="wpc-herobg" aria-hidden>
          <svg className="wpc-waves" viewBox="0 0 1440 900" preserveAspectRatio="none" focusable="false">
            <defs>
              <linearGradient id="wpc-grad-left" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" className="wpc-stop--3" />
                <stop offset="1" className="wpc-stop--6" />
              </linearGradient>
              <linearGradient id="wpc-grad-right" x1="1" y1="0" x2="0" y2="1">
                <stop offset="0" className="wpc-stop--3" />
                <stop offset="1" className="wpc-stop--6" />
              </linearGradient>
              <linearGradient id="wpc-grad-floor" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" className="wpc-stop--5" />
                <stop offset="1" className="wpc-stop--7" />
              </linearGradient>
              <linearGradient id="wpc-grad-deep" x1="0" y1="0" x2="1" y2="0.4">
                <stop offset="0" className="wpc-stop--7" />
                <stop offset="0.5" className="wpc-stop--8" />
                <stop offset="1" className="wpc-stop--6" />
              </linearGradient>
            </defs>
            <g className="wpc-waves__fill">
                <g className="wpc-layer" style={{ "--i": 0 } as CSSProperties}>
                  <path className="wpc-tone wpc-tone--2 wpc-sway wpc-sway--a" d="M-120,400 C150,462 330,586 430,710 C500,798 620,863 780,900 L-120,900 Z" />
                </g>
                <g className="wpc-layer" style={{ "--i": 1 } as CSSProperties}>
                  <path className="wpc-tone wpc-tone--2 wpc-sway wpc-sway--b" d="M1560,420 C1390,514 1260,617 1130,735 C1050,805 930,868 780,900 L1560,900 Z" />
                </g>
                <g className="wpc-layer" style={{ "--i": 2 } as CSSProperties}>
                  <path className="wpc-tone wpc-tone--3 wpc-sway wpc-sway--b" d="M-120,430 C100,488 260,588 335,696 C385,771 480,838 620,900 L-120,900 Z" />
                </g>
                <g className="wpc-layer" style={{ "--i": 3 } as CSSProperties}>
                  <path className="wpc-tone wpc-tone--3 wpc-sway wpc-sway--a" d="M1560,430 C1400,520 1300,610 1200,720 C1130,800 1040,860 930,900 L1560,900 Z" />
                </g>
                <g className="wpc-layer" style={{ "--i": 4 } as CSSProperties}>
                  <path className="wpc-tone wpc-tone--3 wpc-sway wpc-sway--a" d="M-120,565 C100,612 260,640 460,690 C660,740 770,722 960,702 C1160,682 1310,640 1560,560 L1560,900 L-120,900 Z" />
                </g>
                <g className="wpc-layer" style={{ "--i": 5 } as CSSProperties}>
                  <path className="wpc-tone wpc-tone--grad-left wpc-sway wpc-sway--a" d="M-120,470C60,525 185,610 235,725 C265,795 320,855 410,900 L-120,900 Z" />
                </g>
                <g className="wpc-layer" style={{ "--i": 6 } as CSSProperties}>
                  <path className="wpc-tone wpc-tone--grad-right wpc-sway wpc-sway--b" d="M1560,560C1430,612 1350,680 1285,772 C1250,815 1220,860 1170,900 L1560,900 Z" />
                </g>
                <g className="wpc-layer" style={{ "--i": 7 } as CSSProperties}>
                  <path className="wpc-tone wpc-tone--4 wpc-sway wpc-sway--b" d="M-120,640 C120,598 300,610 480,665 C700,730 825,792 1020,748 C1200,708 1360,650 1560,640 L1560,900 L-120,900 Z" />
                </g>
                <g className="wpc-layer" style={{ "--i": 8 } as CSSProperties}>
                  <path className="wpc-tone wpc-tone--5 wpc-sway wpc-sway--a" d="M-120,692 C140,650 305,700 525,762 C725,818 905,802 1105,762 C1265,730 1400,722 1560,700 L1560,900 L-120,900 Z" />
                </g>
                <g className="wpc-layer" style={{ "--i": 9 } as CSSProperties}>
                  <path className="wpc-tone wpc-tone--6 wpc-sway wpc-sway--b" d="M-120,742 C160,702 345,722 565,792 C765,852 945,832 1125,802 C1285,776 1425,792 1560,772 L1560,900 L-120,900 Z" />
                </g>
                <g className="wpc-layer" style={{ "--i": 10 } as CSSProperties}>
                  <path className="wpc-tone wpc-tone--grad-floor wpc-sway wpc-sway--a" d="M-120,802C200,772 385,802 605,836 C805,866 985,856 1165,842 C1305,830 1435,846 1560,832 L1560,900 L-120,900 Z" />
                </g>
                <g className="wpc-layer" style={{ "--i": 11 } as CSSProperties}>
                  <path className="wpc-tone wpc-tone--grad-deep wpc-sway wpc-sway--b" d="M-120,852C250,832 455,862 705,874 C955,886 1205,864 1560,882 L1560,900 L-120,900 Z" />
                </g>
            </g>
            <g className="wpc-waves__line">
              <path className="wpc-wave__line" pathLength={1} style={{ "--i": 0 } as CSSProperties} d="M-120,400 C150,462 330,586 430,710 C500,798 620,863 780,900" />
              <path className="wpc-wave__line" pathLength={1} style={{ "--i": 1 } as CSSProperties} d="M1560,420 C1390,514 1260,617 1130,735 C1050,805 930,868 780,900" />
              <path className="wpc-wave__line" pathLength={1} style={{ "--i": 2 } as CSSProperties} d="M-120,565 C100,612 260,640 460,690 C660,740 770,722 960,702 C1160,682 1310,640 1560,560" />
              <path className="wpc-wave__line" pathLength={1} style={{ "--i": 3 } as CSSProperties} d="M-120,692 C140,650 305,700 525,762 C725,818 905,802 1105,762 C1265,730 1400,722 1560,700" />
              <path className="wpc-wave__line" pathLength={1} style={{ "--i": 4 } as CSSProperties} d="M-120,640 C120,598 300,610 480,665 C700,730 825,792 1020,748 C1200,708 1360,650 1560,640" />
            </g>
          </svg>
        </div>
        */}
        <div className="wpc-container wpc-hero">
          <div className="wpc-hero__text eos-stagger">
            <p className="wpc-eyebrow wpc-eyebrow--pill">{HOME_HERO.eyebrow}</p>
            <h1 className="wpc-hero__title" aria-label={`${TITLE_LINE_1} ${TITLE_LINE_2} ${ROTATING_WORDS[0]}`}>
              <span className="wpc-title__line" aria-hidden>
                <TitleWords text={TITLE_LINE_1} start={0} />
              </span>
              <span className="wpc-title__line" aria-hidden>
                <TitleWords text={TITLE_LINE_2} start={TITLE_LINE_1.split(" ").length} />{" "}
                <RotatingWord words={ROTATING_WORDS} />
              </span>
            </h1>
            <p className="wpc-hero__subtitle">{HOME_HERO.subtitle}</p>
            <div className="wpc-hero__actions">
              <Button variant="primary" onClick={() => onNavigate("signup")}>
                <span className="wpc-btn-inner">
                  Get started <Icons.ArrowRight size={16} className="wpc-btn-arrow" />
                </span>
              </Button>
              <Button variant="secondary" onClick={() => onNavigate("features")}>
                Explore features
              </Button>
            </div>
            <ul className="wpc-trust" aria-label="At a glance">
              {HOME_HERO.trust.map((item) => (
                <li key={item} className="wpc-trust__item">
                  <Icons.Check size={15} aria-hidden /> {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
        {/* Capability ticker: in the hero's lower area, layered above the bottom waves. */}
        <div className="wpc-hero__ticker">
          <FeatureTicker items={HOME_TICKER} />
        </div>
      </section>

      {/* Product & module showcase */}
      <section className="wpc-container wpc-section">
        <Reveal className="wpc-section-intro">
          <p className="wpc-eyebrow">What's inside</p>
          <AnimatedHeading
            className="wpc-section__title wpc-section__title--xl"
            text="One platform. Every part of your institution."
          />
          <p className="wpc-section__lead">
            Explore the connected suites that bring admissions, teaching, campus operations, finance and
            governance into one place.
          </p>
        </Reveal>
        <Reveal>
          <ShowcaseCarousel items={HOME_SHOWCASE} onNavigate={onNavigate} />
        </Reveal>
      </section>

      {/* Adapts to institutions */}
      <FieldsSection>
        <Reveal className="wpc-adapt">
          <p className="wpc-eyebrow wpc-fieldsec__badge">{HOME_ADAPT.eyebrow}</p>
          <AnimatedHeading className="wpc-section__title" text={HOME_ADAPT.title} />
          <p className="wpc-section__lead">{HOME_ADAPT.lead}</p>
        </Reveal>
        <RevealGroup as="ul" ariaLabel="Academy types" className="wpc-fields">
          {HOME_ADAPT.academies.map((name, i) => (
            <li key={name} className="wpc-field" style={stagger(i)}>
              {name}
            </li>
          ))}
        </RevealGroup>
        <Reveal delay={150}>
          <p className="wpc-note">{HOME_ADAPT.note}</p>
        </Reveal>
      </FieldsSection>

      {/* Onboarding overview: navy band with drifting light and a pointer-following spotlight */}
      <OnboardSection>
        <div className="wpc-container wpc-onboard__inner">
          <Reveal className="wpc-onboard__head">
            <p className="wpc-eyebrow wpc-onboard__eyebrow">Getting started</p>
            <AnimatedHeading className="wpc-section__title wpc-onboard__title" text="From sign-up to signed in" />
          </Reveal>
          <RevealGroup as="ol" ariaLabel="Onboarding steps" className="wpc-steps wpc-onboard__steps">
            {HOME_ONBOARDING.map((item, i) => (
              <li key={item.title} className="wpc-step" style={stagger(i)}>
                <span className="wpc-step__num" aria-hidden>
                  {i + 1}
                </span>
                <span className="wpc-step__icon" aria-hidden>
                  <IconFor name={item.icon} size={22} />
                </span>
                <span className="wpc-step__body">
                  <span className="wpc-step__title">{item.title}</span>
                  <span className="wpc-step__text">{item.text}</span>
                </span>
              </li>
            ))}
          </RevealGroup>
          <Reveal className="wpc-onboard__foot" delay={200}>
            <div className="wpc-onboard__actions">
              <Button variant="primary" onClick={() => onNavigate("signup")}>
                <span className="wpc-btn-inner">
                  Get started <Icons.ArrowRight size={16} className="wpc-btn-arrow" />
                </span>
              </Button>
              <span className="wpc-onboard__divider" aria-hidden />
              <a
                className="wpc-onboard__link"
                href="#/features"
                onClick={(e) => {
                  e.preventDefault();
                  onNavigate("features");
                }}
              >
                Explore features <Icons.ArrowRight size={16} className="wpc-btn-arrow" aria-hidden />
              </a>
            </div>
            <p className="wpc-onboard__note">{HOME_ONBOARDING_NOTE}</p>
          </Reveal>
        </div>
      </OnboardSection>
    </div>
  );
}

/** Renders a named ui-kit icon. */
function IconFor({ name, size = 20 }: { name: IconItem["icon"]; size?: number }) {
  const Cmp = Icons[name];
  return <Cmp size={size} aria-hidden />;
}

/**
 * A continuous, right-to-left ticker of capability pills (reference: homepage feature strip). The
 * visible list announces each label once; an identical, `aria-hidden` second copy sits right after it
 * so the CSS animation (translating the whole track by exactly -50%) loops seamlessly. Keeps
 * scrolling on hover and pauses on keyboard focus; under reduced motion the loop stops and the track becomes a manually scrollable row
 * instead (see the reduced-motion rule in public.css), so no content is ever hidden.
 */
function FeatureTicker({ items }: { items: TickerItem[] }) {
  return (
    // Focusable so keyboard users can stop the motion (focus pauses it).
    <div className="wpc-ticker" role="region" aria-label="Platform capabilities" tabIndex={0}>
      <div className="wpc-ticker__track" role="list">
        {items.map((item) => (
          <TickerPill key={item.label} item={item} />
        ))}
        <div className="wpc-dup" aria-hidden="true">
          {items.map((item) => (
            <TickerPill key={`dup-${item.label}`} item={item} duplicate />
          ))}
        </div>
      </div>
    </div>
  );
}

function TickerPill({ item, duplicate = false }: { item: TickerItem; duplicate?: boolean }) {
  return (
    <span className="wpc-ticker__pill" role={duplicate ? undefined : "listitem"}>
      <span className="wpc-ticker__icon" aria-hidden>
        <IconFor name={item.icon} size={14} />
      </span>
      {item.label}
    </span>
  );
}

/** Auto-scroll speed for the showcase, in CSS pixels per second. */
const SHOWCASE_SPEED = 28;
/** How long the showcase waits after a manual scroll (swipe, trackpad, buttons) before drifting again. */
const SHOWCASE_IDLE_MS = 1500;

/**
 * A horizontally scrolling row of module showcase cards that drifts slowly on its own.
 *
 * The drift advances the track's real scrollLeft (not a CSS transform), so touch swipe, trackpad and the
 * previous/next buttons all act on the same position and never fight a separate animation. The card
 * list is rendered twice; when the drift passes the first set it jumps back by exactly one set's width,
 * which lands on identical content — so the loop never visibly snaps to the start. The duplicate set is
 * hidden from assistive technology and its links are out of the tab order.
 *
 * It pauses while the pointer is over it, while keyboard focus is inside it, and briefly after any
 * manual scroll. Under reduced motion there is no drift and no duplicate: it is a plain scrollable row
 * with scroll-snap and previous/next buttons that disable at each end.
 *
 * Real page screenshots of these modules don't exist in the repository, so each card shows a branded
 * icon illustration instead of a fabricated screenshot.
 */
function ShowcaseCarousel({ items, onNavigate }: { items: ShowcaseItem[]; onNavigate: (route: PublicRoute) => void }) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [loop] = useState(() => !prefersReducedMotion());
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(false);
  const hoverRef = useRef(false);
  const focusRef = useRef(false);
  const hoverTimer = useRef<ReturnType<typeof setTimeout>>();

  /** The width of one full set of cards: from the first card to the first duplicate. */
  const period = () => {
    const el = trackRef.current;
    const first = el?.querySelector<HTMLElement>('[data-card="0"]');
    const dup = el?.querySelector<HTMLElement>('[data-card="dup-0"]');
    return first && dup ? dup.offsetLeft - first.offsetLeft : 0;
  };

  const updateEdges = () => {
    const el = trackRef.current;
    if (loop || !el) return;
    setAtStart(el.scrollLeft <= 4);
    setAtEnd(el.scrollLeft >= el.scrollWidth - el.clientWidth - 4);
  };

  useEffect(() => {
    if (loop) return;
    updateEdges();
    window.addEventListener("resize", updateEdges);
    return () => window.removeEventListener("resize", updateEdges);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loop]);

  useEffect(() => {
    const el = trackRef.current;
    if (!loop || !el) return;
    let raf = 0;
    let last = performance.now();
    let pos = el.scrollLeft;
    let idleUntil = 0;
    const frame = (now: number) => {
      const dt = Math.min(now - last, 64);
      last = now;
      // The browser rounds scrollLeft, so `pos` keeps the precise value; a bigger gap means the user
      // scrolled it (swipe, trackpad, buttons), so adopt their position and wait before drifting again.
      if (Math.abs(el.scrollLeft - pos) > 2) {
        pos = el.scrollLeft;
        idleUntil = now + SHOWCASE_IDLE_MS;
      }
      if (!hoverRef.current && !focusRef.current && now >= idleUntil) {
        pos += (SHOWCASE_SPEED * dt) / 1000;
        const p = period();
        if (p > 0 && pos >= p) pos -= p;
        el.scrollLeft = pos;
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [loop]);

  useEffect(() => () => clearTimeout(hoverTimer.current), []);

  const scrollByCard = (dir: 1 | -1) => {
    const el = trackRef.current;
    if (!el) return;
    const card = el.querySelector<HTMLElement>(".wpc-showcase__card");
    const gap = parseFloat(getComputedStyle(el).columnGap) || 16;
    const amount = (card?.offsetWidth ?? 320) + gap;
    if (loop) {
      // Shift by one identical set first so there is always room to move either way — invisible,
      // because both sets look the same.
      const p = period();
      if (dir < 0 && el.scrollLeft < amount) el.scrollLeft += p;
      else if (dir > 0 && el.scrollLeft >= p) el.scrollLeft -= p;
    }
    el.scrollBy({ left: dir * amount, behavior: prefersReducedMotion() ? "auto" : "smooth" });
  };

  return (
    <div
      className="wpc-showcase"
      onPointerEnter={() => {
        clearTimeout(hoverTimer.current);
        hoverRef.current = true;
      }}
      onPointerLeave={() => {
        hoverTimer.current = setTimeout(() => {
          hoverRef.current = false;
        }, 400);
      }}
      onFocus={() => {
        focusRef.current = true;
      }}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) focusRef.current = false;
      }}
    >
      <div
        ref={trackRef}
        className={loop ? "wpc-showcase__track wpc-showcase__track--loop" : "wpc-showcase__track"}
        role="list"
        aria-label="Education OS suites"
        tabIndex={0}
        onScroll={updateEdges}
      >
        {items.map((item, i) => (
          <ShowcaseCard key={item.title} item={item} index={i} onNavigate={onNavigate} />
        ))}
        {loop && (
          <div className="wpc-dup" aria-hidden="true">
            {items.map((item, i) => (
              <ShowcaseCard key={`dup-${item.title}`} item={item} index={i} onNavigate={onNavigate} duplicate />
            ))}
          </div>
        )}
      </div>
      <div className="wpc-showcase__nav">
        <button
          type="button"
          className="wpc-showcase__arrow"
          onClick={() => scrollByCard(-1)}
          disabled={!loop && atStart}
          aria-label="Previous suites"
        >
          <Icons.ChevronLeft size={18} />
        </button>
        <button
          type="button"
          className="wpc-showcase__arrow"
          onClick={() => scrollByCard(1)}
          disabled={!loop && atEnd}
          aria-label="Next suites"
        >
          <Icons.ChevronRight size={18} />
        </button>
      </div>
    </div>
  );
}

function ShowcaseCard({
  item,
  index,
  onNavigate,
  duplicate = false,
}: {
  item: ShowcaseItem;
  index: number;
  onNavigate: (route: PublicRoute) => void;
  duplicate?: boolean;
}) {
  return (
    <article
      className="wpc-showcase__card"
      role={duplicate ? undefined : "listitem"}
      data-card={duplicate ? `dup-${index}` : String(index)}
    >
      <div className="wpc-showcase__visual" aria-hidden>
        <svg className="wpc-showcase__curves" viewBox="0 0 320 180" preserveAspectRatio="none" focusable="false">
          <path d="M-10,138 C70,108 140,160 220,128 C270,108 300,116 330,100" />
          <path d="M-10,162 C80,140 150,180 230,154 C280,140 305,146 330,132" />
        </svg>
        <span className="wpc-showcase__tile">
          <IconFor name={item.icon} size={32} />
        </span>
      </div>
      <div className="wpc-showcase__body">
        <p className="wpc-showcase__label">{item.title}</p>
        <h3 className="wpc-showcase__headline">{item.headline}</h3>
        <p className="wpc-showcase__text">{item.text}</p>
        <a
          className="wpc-showcase__link"
          href="#/features"
          tabIndex={duplicate ? -1 : undefined}
          onClick={(e) => {
            e.preventDefault();
            onNavigate("features");
          }}
        >
          Explore features <Icons.ArrowRight size={14} className="wpc-btn-arrow" />
        </a>
      </div>
    </article>
  );
}

const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Bundled by Vite as an asset URL (the `new URL(…, import.meta.url)` form needs no *.mp4 typing). */
const HERO_VIDEO = new URL("../components/video.mp4", import.meta.url).href;

/**
 * Decorative hero background video: muted, looping, inline, with no controls, and hidden from assistive
 * technology. Playback starts from the effect (with `muted` set on the element first, which browsers
 * require for autoplay). Under reduced motion it never plays and just shows its first frame.
 */
function HeroVideo() {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const video = ref.current;
    if (!video) return;
    video.muted = true;
    if (prefersReducedMotion()) {
      video.pause();
      return;
    }
    video.play().catch(() => {
      // Autoplay refused (e.g. data-saver modes): the first frame stays as a still background.
    });
  }, []);
  return (
    <div className="wpc-herovideo" aria-hidden>
      <video
        ref={ref}
        className="wpc-herovideo__media"
        src={HERO_VIDEO}
        muted
        loop
        playsInline
        preload="auto"
        tabIndex={-1}
      />
    </div>
  );
}

/**
 * Words that rise out of a mask one after another (CSS-driven; --w is the stagger index). The space
 * between words must sit outside each inline-block mask — inside it, trailing whitespace is dropped
 * and the words run together.
 */
function TitleWords({ text, start = 0 }: { text: string; start?: number }) {
  return (
    <>
      {text.split(" ").map((word, i) => (
        <Fragment key={`${word}-${i}`}>
          {i > 0 && " "}
          <span className="wpc-w">
            <span className="wpc-w__i" style={{ "--w": start + i } as CSSProperties}>
              {word}
            </span>
          </span>
        </Fragment>
      ))}
    </>
  );
}

/**
 * Cycles through key phrases in the brand colour. The first phrase rises in as part of the headline's
 * own reveal; every later phrase swaps in with a short, blur-free crossfade — deliberately a different,
 * quieter motion than the entrance — so it reads as the phrase changing, not the intro replaying.
 */
function RotatingWord({ words, interval = 3000 }: { words: string[]; interval?: number }) {
  // `cycled` (not `prev`) decides the class: `prev` clears 600ms after each swap, and keying the class on
  // it flipped the new phrase back to --first, replaying the entrance rise on every cycle.
  const [state, setState] = useState<{ cur: number; prev: number | null; cycled: boolean }>({
    cur: 0,
    prev: null,
    cycled: false,
  });
  useEffect(() => {
    if (prefersReducedMotion()) return;
    let clear: ReturnType<typeof setTimeout> | undefined;
    const tick = setInterval(() => {
      setState((s) => ({ cur: (s.cur + 1) % words.length, prev: s.cur, cycled: true }));
      clear = setTimeout(() => setState((s) => ({ ...s, prev: null })), 600);
    }, interval);
    return () => {
      clearInterval(tick);
      if (clear) clearTimeout(clear);
    };
  }, [words.length, interval]);
  return (
    <span className="wpc-rot">
      {/* Invisible copies of every phrase hold the slot at the widest one, so the line never resizes
          (and "on" never jumps) as phrases of different lengths swap in and out. */}
      {words.map((w) => (
        <span key={`size-${w}`} className="wpc-rot__sizer">
          {w}
        </span>
      ))}
      {state.prev != null && (
        <span key={`out-${state.prev}`} className="wpc-rot__word wpc-rot__word--out">
          {words[state.prev]}
        </span>
      )}
      <span
        key={`in-${state.cur}`}
        className={`wpc-rot__word${state.cycled ? " wpc-rot__word--in" : " wpc-rot__word--first"}`}
      >
        {words[state.cur]}
      </span>
    </span>
  );
}

/** A heading whose words rise in, one after another, the first time it scrolls into view. */
/**
 * "One platform, many fields": a full-bleed band whose background eases from white to pale lavender
 * as it enters the viewport, over a fine-line grid, with the content centred inside. `useInView`
 * reports in-view at once under reduced motion (and the CSS drops the transition), so the band simply
 * shows its final colour.
 */
function FieldsSection({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLElement>(null);
  // A low threshold: the band is tall, and on short screens 45% of it may never be visible at once.
  const inView = useInView(ref, 0.15);
  return (
    <section ref={ref} className={inView ? "wpc-fieldsec is-in" : "wpc-fieldsec"}>
      <div className="wpc-container wpc-section wpc-fieldsec__inner">{children}</div>
    </section>
  );
}

/**
 * "Getting started" band: the brand navy with slowly drifting light (CSS only, `.wpc-onboard__aura`)
 * and a soft spotlight that follows the pointer. The pointer position is written to CSS variables at
 * most once per frame; with reduced motion, or on touch input, the spotlight stays put and the drift
 * is switched off in CSS.
 */
function OnboardSection({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLElement>(null);
  const frame = useRef(0);

  useEffect(() => () => cancelAnimationFrame(frame.current), []);

  const onPointerMove = (e: { clientX: number; clientY: number; pointerType: string }) => {
    const el = ref.current;
    if (!el || e.pointerType !== "mouse" || prefersReducedMotion()) return;
    const { clientX, clientY } = e;
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      const box = el.getBoundingClientRect();
      el.style.setProperty("--spot-x", `${clientX - box.left}px`);
      el.style.setProperty("--spot-y", `${clientY - box.top}px`);
      el.classList.add("is-lit");
    });
  };

  const onPointerLeave = () => {
    cancelAnimationFrame(frame.current);
    ref.current?.classList.remove("is-lit");
  };

  return (
    <section ref={ref} className="wpc-onboard" onPointerMove={onPointerMove} onPointerLeave={onPointerLeave}>
      <div className="wpc-onboard__aura" aria-hidden>
        <span className="wpc-onboard__orb wpc-onboard__orb--a" />
        <span className="wpc-onboard__orb wpc-onboard__orb--b" />
        <span className="wpc-onboard__orb wpc-onboard__orb--c" />
      </div>
      {children}
    </section>
  );
}

function AnimatedHeading({ text, className }: { text: string; className: string }) {
  const ref = useRef<HTMLHeadingElement>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion() || typeof IntersectionObserver === "undefined") {
      setSeen(true);
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setSeen(true);
          io.disconnect();
        }
      },
      { threshold: 0.4 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <h2 ref={ref} className={`${className} wpc-ah${seen ? " is-in" : ""}`} aria-label={text}>
      <span aria-hidden>
        <TitleWords text={text} />
      </span>
    </h2>
  );
}
