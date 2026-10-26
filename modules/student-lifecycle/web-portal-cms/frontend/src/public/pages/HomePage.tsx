import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Button, EduMark, Icons, prefersReducedMotion } from "@eos/ui-kit";
import {
  FIELD_VOCAB,
  HOME_ADAPT,
  HOME_HERO,
  HOME_ONBOARDING,
  HOME_ONBOARDING_LINES,
  HOME_ONBOARDING_NOTE,
  type FieldVocabulary,
  type PublicRoute,
} from "../content";
import { FEATURE_CATEGORIES } from "../features-data";
import { Reveal, RevealGroup, stagger } from "../components/Reveal";
import { Listbox, type ListboxOption } from "../components/Listbox";

/** Every academy type as a dropdown option, with how many of its own words the profile defines. */
const FIELD_OPTIONS: ListboxOption[] = FIELD_VOCAB.map((f) => ({
  value: f.id,
  label: f.title,
  hint: `${f.terms.length} own words`,
}));

/**
 * Home page. Its spine is the product's own idea: every academy type runs the same shared modules
 * under its own words (FIELD_VOCAB, copied from the institution profiles). One field choice, made in
 * the hero, re-speaks the page: the hero's workspace relabels its modules, the green chapter lists
 * every pair, and the module list names the practice suite in that vocabulary.
 *
 * Motion thesis (impeccable animate): the focal moment is the relabel itself, where each changed
 * word rolls in under a short logo-orange marker. Supporting motion explains state: the hero
 * composition assembles once on load, the onboarding steps light up along a growing line as they
 * reach the reading position, and the module photo follows the group under the pointer. Content is
 * visible by default; reduced motion keeps every state change without the travel.
 */

const PHOTO = {
  campus: new URL("../assets/campus-walk.jpg", import.meta.url).href,
  lecture: new URL("../assets/lecture.jpg", import.meta.url).href,
  field: new URL("../assets/field-training.jpg", import.meta.url).href,
  students: new URL("../assets/students.jpg", import.meta.url).href,
  library: new URL("../assets/library.jpg", import.meta.url).href,
};

/** Product areas, grouped; each group brings its own photograph to the list's picture slot. */
const AREA_GROUPS: { label: string; ids: string[]; photo: string; alt: string }[] = [
  {
    label: "Learning",
    ids: ["student-lifecycle", "academics"],
    photo: PHOTO.lecture,
    alt: "A lecturer presenting to students with laptops in a lecture hall",
  },
  {
    label: "Practice & campus",
    ids: ["practice", "campus-life", "sports"],
    photo: PHOTO.field,
    alt: "Students and a teacher examining plants during a field-training session",
  },
  {
    label: "Operations",
    ids: ["facilities", "finance-operations", "support"],
    photo: PHOTO.students,
    alt: "Four students sitting together on campus steps, sharing a laptop and books",
  },
  {
    label: "Governance & platform",
    ids: ["governance", "platform"],
    photo: PHOTO.library,
    alt: "A student working on a laptop in a sunlit university library",
  },
];

/** The registration states an organisation actually moves through (platform/tenancy). */
const ORG_STATES = ["Registered", "Email verified", "Awaiting approval", "Active"] as const;

/** Featured academy types shown as chips; the rest stay one choice away in the same select. */
const FEATURED_FIELDS = ["music-academy", "sports-college", "medical-college", "engineering-college", "law-college"];

const MODULE_COUNT = FEATURE_CATEGORIES.reduce((n, cat) => n + cat.modules.length, 0);

/** The field's word for a shared pattern, or the platform's word when the field keeps it. */
const wordFor = (field: FieldVocabulary, generic: string) =>
  field.terms.find((t) => t.generic === generic)?.word ?? generic;

export function HomePage({ onNavigate }: { onNavigate: (route: PublicRoute) => void }) {
  const [fieldId, setFieldId] = useState(FIELD_VOCAB[0]?.id ?? "");
  const [userPicked, setUserPicked] = useState(false);
  const field = FIELD_VOCAB.find((f) => f.id === fieldId) ?? FIELD_VOCAB[0];

  const pick = (id: string) => {
    setUserPicked(true);
    setFieldId(id);
  };

  const go = (route: PublicRoute) => (e: { preventDefault: () => void }) => {
    e.preventDefault();
    onNavigate(route);
  };

  if (!field) return null;

  return (
    <div className="wpc-page">
      <Hero
        field={field}
        onPick={pick}
        autoplay={!userPicked}
        onAutoAdvance={setFieldId}
        onTrial={() => onNavigate("signup")}
        onFeatures={go("features")}
      />
      <FieldChapter field={field} onPick={pick} />
      <Inside field={field} onFeatures={go("features")} />
      <Trust />
      <Steps onTrial={() => onNavigate("signup")} onFeatures={go("features")} />
    </div>
  );
}

/* ---------------------------------------------------------------- hero */

function Hero({
  field,
  onPick,
  autoplay,
  onAutoAdvance,
  onTrial,
  onFeatures,
}: {
  field: FieldVocabulary;
  onPick: (id: string) => void;
  autoplay: boolean;
  onAutoAdvance: (id: string) => void;
  onTrial: () => void;
  onFeatures: (e: { preventDefault: () => void }) => void;
}) {
  const ref = useRef<HTMLElement>(null);
  const glowFrame = useRef(0);
  const [paused, setPaused] = useState(false);
  useEffect(() => () => cancelAnimationFrame(glowFrame.current), []);
  const [inView, setInView] = useState(true);

  // Until the visitor picks a field, the workspace steps through a few fields on its own, only while
  // the hero is on screen and not hovered or focused, and never under reduced motion.
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(([e]) => setInView(Boolean(e?.isIntersecting)), { threshold: 0.3 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  useEffect(() => {
    if (!autoplay || paused || !inView || prefersReducedMotion()) return;
    const order = FEATURED_FIELDS.filter((id) => FIELD_VOCAB.some((f) => f.id === id));
    const t = window.setTimeout(() => {
      const next = order[(order.indexOf(field.id) + 1) % order.length] ?? order[0];
      if (next) onAutoAdvance(next);
    }, 3600);
    return () => window.clearTimeout(t);
  }, [autoplay, paused, inView, field.id, onAutoAdvance]);

  return (
    <section
      ref={ref}
      className="wpc-hx"
      aria-labelledby="wpc-hx-title"
      onPointerEnter={() => setPaused(true)}
      onPointerLeave={() => {
        setPaused(false);
        ref.current?.classList.remove("is-lit");
      }}
      onPointerMove={(e) => {
        // The dot field lights up around the pointer (mouse only; CSS reads --gx / --gy).
        const el = ref.current;
        if (!el || e.pointerType !== "mouse") return;
        const { clientX, clientY } = e;
        cancelAnimationFrame(glowFrame.current);
        glowFrame.current = requestAnimationFrame(() => {
          const box = el.getBoundingClientRect();
          el.style.setProperty("--gx", `${clientX - box.left}px`);
          el.style.setProperty("--gy", `${clientY - box.top}px`);
          el.classList.add("is-lit");
        });
      }}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div className="wpc-hx__bg" aria-hidden>
        <span className="wpc-hx__dots" />
        <span className="wpc-hx__dots wpc-hx__dots--lit" />
      </div>
      <div className="wpc-container wpc-hx__inner">
        <div className="wpc-hx__copy">
          <h1 id="wpc-hx-title" className="wpc-hx__title">
            {HOME_HERO.statement}
          </h1>
          <p className="wpc-hx__sub">{HOME_HERO.subtitle}</p>
          <div className="wpc-hx__actions">
            <Button variant="primary" onClick={onTrial}>
              Start free trial
            </Button>
            <a className="wpc-link" href="#/features" onClick={onFeatures}>
              See every module
            </a>
          </div>
          <p className="wpc-hx__fine">{HOME_ONBOARDING_NOTE}</p>
        </div>

        <div className="wpc-hx__picker">
          <FieldSelect field={field} onPick={onPick} label="Or choose any academy type" chips />
        </div>

        <div className="wpc-hx__stage">
          <Workspace field={field} photo={PHOTO.campus} />
          <p className="wpc-hx__caption">
            Illustration: an organisation admin's workspace. Module names follow the academy type.
          </p>
        </div>
      </div>
    </section>
  );
}

/** A word that rolls in, under a short marker, whenever its text changes. */
function Roll({ text }: { text: string }) {
  return (
    <span className="wpc-roll" key={text}>
      <span className="wpc-roll__text">{text}</span>
    </span>
  );
}

/**
 * The workspace an organisation admin sees, relabelled in the chosen field's words: navigation,
 * the module switches, the organisation's live status and a campus picture as one interface.
 */
function Workspace({ field, photo }: { field: FieldVocabulary; photo: string }) {
  const terms = field.terms.slice(0, 4);
  return (
    <div className="wpc-ws" data-ui aria-hidden>
      <div className="wpc-ws__bar">
        <EduMark size={20} />
        <span className="wpc-ws__org">
          <Roll text={field.title} />
        </span>
        <span className="wpc-ws__role">Organisation admin</span>
      </div>
      <div className="wpc-ws__body">
        <ul className="wpc-ws__nav">
          <li className="is-current">Dashboard</li>
          <li>Admissions</li>
          <li>Timetable</li>
          {terms.slice(0, 2).map((t) => (
            <li key={t.generic}>
              <Roll text={t.word} />
            </li>
          ))}
          <li>Fees &amp; accounts</li>
          <li>Governance</li>
        </ul>
        <div className="wpc-ws__main">
          <div className="wpc-ws__panel">
            <p className="wpc-ws__heading">Modules for your institution</p>
            <ul className="wpc-ws__rows">
              {terms.map((t) => (
                <li key={t.generic} className="wpc-ws__row">
                  <span className="wpc-ws__name">
                    <Roll text={t.word} />
                    <span className="wpc-ws__generic">{t.generic}</span>
                  </span>
                  <span className="wpc-ws__switch" />
                </li>
              ))}
            </ul>
          </div>
          <div className="wpc-ws__side">
            <StatusCard />
            <figure className="wpc-ws__photo">
              <img src={photo} alt="" width={840} height={700} />
              <figcaption>Campus</figcaption>
            </figure>
          </div>
        </div>
      </div>
    </div>
  );
}

/** A live status card stepping through the states an organisation really moves through. */
function StatusCard() {
  const [step, setStep] = useState(prefersReducedMotion() ? ORG_STATES.length - 1 : 0);
  useEffect(() => {
    if (prefersReducedMotion()) return;
    const t = window.setInterval(() => setStep((s) => (s + 1) % ORG_STATES.length), 1800);
    return () => window.clearInterval(t);
  }, []);
  return (
    <div className="wpc-sc">
      <p className="wpc-sc__label">Organisation status</p>
      <p className="wpc-sc__state">
        <span className={step === ORG_STATES.length - 1 ? "wpc-sc__dot is-live" : "wpc-sc__dot"} />
        <Roll text={ORG_STATES[step] ?? ""} />
      </p>
      <ol className="wpc-sc__track">
        {ORG_STATES.map((s, i) => (
          <li key={s} className={i <= step ? "is-done" : undefined} />
        ))}
      </ol>
    </div>
  );
}

/** Featured fields as buttons, every field in one select: the same control drives the whole page. */
function FieldSelect({
  field,
  onPick,
  label,
  chips = false,
}: {
  field: FieldVocabulary;
  onPick: (id: string) => void;
  label: string;
  chips?: boolean;
}) {
  return (
    <div className={chips ? "wpc-fs wpc-fs--chips" : "wpc-fs"}>
      {chips && (
        <div className="wpc-fs__chips" role="group" aria-label="Featured academy types">
          {FEATURED_FIELDS.map((id) => {
            const f = FIELD_VOCAB.find((v) => v.id === id);
            if (!f) return null;
            return (
              <button
                key={id}
                type="button"
                className="wpc-fs__chip"
                aria-pressed={f.id === field.id}
                onClick={() => onPick(f.id)}
              >
                {f.label}
              </button>
            );
          })}
        </div>
      )}
      <Listbox
        className="wpc-fs__select"
        label={label}
        value={field.id}
        options={FIELD_OPTIONS}
        onChange={onPick}
      />
    </div>
  );
}

/* ------------------------------------------------- the field's own words */

function FieldChapter({ field, onPick }: { field: FieldVocabulary; onPick: (id: string) => void }) {
  return (
    <section className="wpc-ch" aria-labelledby="wpc-ch-title">
      <div className="wpc-container wpc-ch__inner">
        <Reveal className="wpc-ch__head">
          <h2 id="wpc-ch-title" className="wpc-ch__title">
            Your field's own words
          </h2>
          <p className="wpc-ch__lead">{HOME_ADAPT.lead}</p>
          <FieldSelect field={field} onPick={onPick} label="Academy type" chips />
        </Reveal>
        <div className="wpc-ch__table" aria-live="polite">
          <RevealGroup as="ul" className="wpc-ch__rows">
            {field.terms.map((t, i) => (
              <li key={`${field.id}-${t.generic}`} className="wpc-ch__row" style={stagger(i)}>
                <span className="wpc-ch__generic">{t.generic}</span>
                <Icons.ArrowRight size={20} className="wpc-ch__arrow" aria-hidden />
                <span className="wpc-ch__word">{t.word}</span>
              </li>
            ))}
          </RevealGroup>
          <p className="wpc-ch__caption">
            Shown for a <strong>{field.title}</strong>, from its institution profile.
          </p>
          <p className="wpc-ch__note">{HOME_ADAPT.note}</p>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------- what's inside */

function Inside({ field, onFeatures }: { field: FieldVocabulary; onFeatures: (e: { preventDefault: () => void }) => void }) {
  const [active, setActive] = useState(0);
  const group = AREA_GROUPS[active] ?? AREA_GROUPS[0]!;
  const fieldWords = field.terms.map((t) => t.word).join(", ");

  return (
    <section className="wpc-in" aria-labelledby="wpc-in-title">
      <div className="wpc-container wpc-in__inner">
        <div className="wpc-in__col">
          <Reveal>
            <h2 id="wpc-in-title" className="wpc-in__title">
              Everything an institution runs
            </h2>
            <p className="wpc-in__lead">
              {MODULE_COUNT} modules in {FEATURE_CATEGORIES.length} product areas, built around one shared record
              of every person in your institution.
            </p>
          </Reveal>
          {AREA_GROUPS.map((g, gi) => (
            <div
              key={g.label}
              className={gi === active ? "wpc-in__group is-active" : "wpc-in__group"}
              onPointerEnter={() => setActive(gi)}
              onFocus={() => setActive(gi)}
            >
              <p className="wpc-in__group-label">{g.label}</p>
              <RevealGroup as="ul" className="wpc-in__rows" ariaLabel={g.label}>
                {g.ids.map((id, i) => {
                  const cat = FEATURE_CATEGORIES.find((c) => c.id === id);
                  if (!cat) return null;
                  return (
                    <li key={id} style={stagger(i)}>
                      <a className="wpc-in__row" href="#/features" onClick={onFeatures}>
                        <span className="wpc-in__name">
                          {cat.title}
                          <span className="wpc-in__summary">
                            {id === "practice" ? (
                              <>
                                For a {field.title}: <em>{fieldWords}</em>.
                              </>
                            ) : (
                              cat.summary
                            )}
                          </span>
                        </span>
                        <span className="wpc-in__value">
                          {cat.modules.length} modules
                          <Icons.ArrowRight size={16} aria-hidden className="wpc-in__arrow" />
                        </span>
                      </a>
                    </li>
                  );
                })}
              </RevealGroup>
            </div>
          ))}
        </div>
        <figure className="wpc-in__media">
          {AREA_GROUPS.map((g, gi) => (
            <img
              key={g.label}
              src={g.photo}
              alt={gi === active ? group.alt : ""}
              aria-hidden={gi === active ? undefined : true}
              className={gi === active ? "is-active" : undefined}
              loading="lazy"
            />
          ))}
          <figcaption>{group.label}</figcaption>
        </figure>
      </div>
    </section>
  );
}

/* --------------------------------------------------------------- trust */

/** Only claims the platform's own architecture and process back up (ADR-0005, platform/tenancy). */
const TRUST_POINTS = [
  {
    title: "Your data stays yours",
    text: "Every organisation sees only its own records, enforced in the database with row-level security.",
  },
  {
    title: "Reviewed before it goes live",
    text: "A platform administrator approves each organisation's academic package before anyone signs in.",
  },
  {
    title: "Configured, not customised",
    text: "Fifteen academy types run on the same platform, so updates reach every institution at once.",
  },
  {
    title: "A Rooman initiative",
    text: "Education OS is a Rooman initiative, and every organisation starts on a free 30-day trial.",
  },
];

function Trust() {
  return (
    <section className="wpc-tr" aria-labelledby="wpc-tr-title">
      <div className="wpc-container wpc-tr__inner">
        <Reveal as="h2" id="wpc-tr-title" className="wpc-tr__title">
          Built to be trusted with an institution
        </Reveal>
        <RevealGroup as="ul" className="wpc-tr__list">
          {TRUST_POINTS.map((p, i) => (
            <li key={p.title} style={stagger(i)}>
              <p className="wpc-tr__point">{p.title}</p>
              <p className="wpc-tr__text">{p.text}</p>
            </li>
          ))}
        </RevealGroup>
      </div>
    </section>
  );
}

/* --------------------------------------------------- getting started */

function Steps({ onTrial, onFeatures }: { onTrial: () => void; onFeatures: (e: { preventDefault: () => void }) => void }) {
  const listRef = useRef<HTMLOListElement>(null);
  const [reached, setReached] = useState(prefersReducedMotion() ? HOME_ONBOARDING_LINES.length : 0);

  // Each stage lights up as it reaches the reading line; the green line grows with them.
  useEffect(() => {
    const list = listRef.current;
    if (!list || prefersReducedMotion() || typeof IntersectionObserver === "undefined") {
      setReached(HOME_ONBOARDING_LINES.length);
      return;
    }
    const items: Element[] = Array.from(list.children);
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            const i = items.indexOf(e.target);
            setReached((r) => Math.max(r, i + 1));
          }
        });
      },
      { rootMargin: "0px 0px -45% 0px" },
    );
    items.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  return (
    <section className="wpc-st" aria-labelledby="wpc-st-title">
      <div className="wpc-container wpc-st__inner">
        <Reveal as="h2" id="wpc-st-title" className="wpc-st__title">
          From sign‑up to signed in
        </Reveal>
        <ol
          ref={listRef}
          className="wpc-st__steps"
          style={{ "--progress": reached / HOME_ONBOARDING_LINES.length } as CSSProperties}
        >
          {HOME_ONBOARDING_LINES.map((line, i) => (
            <li key={line} className={i < reached ? "wpc-st__step is-reached" : "wpc-st__step"}>
              <p className="wpc-st__line">{line}</p>
              <p className="wpc-st__text">{HOME_ONBOARDING[i]?.text}</p>
            </li>
          ))}
        </ol>
        <Reveal className="wpc-st__cta">
          <p className="wpc-st__cta-text">
            Start with the trial; your academy type, modules and words are set up for you.
          </p>
          <div className="wpc-st__actions">
            <Button variant="primary" onClick={onTrial}>
              Start free trial
            </Button>
            <a className="wpc-link" href="#/features" onClick={onFeatures}>
              See every module
            </a>
          </div>
          <p className="wpc-st__fine">{HOME_ONBOARDING_NOTE}</p>
        </Reveal>
      </div>
    </section>
  );
}
