import { useEffect, useMemo, useState } from "react";
import { Badge, Button, Icons, prefersReducedMotion } from "@eos/ui-kit";
import {
  STATUS_HINT,
  STATUS_LABEL,
  STATUS_TONE,
  type ImplStatus,
  type PublicRoute,
} from "../content";
import { FEATURE_CATEGORIES, type FeatureCategory, type FeatureModule } from "../features-data";
import { Reveal, RevealGroup, stagger } from "../components/Reveal";
import { Listbox } from "../components/Listbox";
import { ModuleWall, type WallModule } from "../components/ModuleWall";

const STATUS_ORDER: ImplStatus[] = ["implemented", "partial", "specified", "scaffold", "planned"];
type StatusFilter = ImplStatus | "all";

/** Project photographs (from the product's own image set), bundled by Vite. */
const PHOTO = {
  library: new URL("../assets/library.jpg", import.meta.url).href,
  lecture: new URL("../assets/lecture.jpg", import.meta.url).href,
  field: new URL("../assets/field-training.jpg", import.meta.url).href,
  campus: new URL("../assets/campus-walk.jpg", import.meta.url).href,
  students: new URL("../assets/students.jpg", import.meta.url).href,
};

const ALL_MODULES = FEATURE_CATEGORIES.flatMap((cat) => cat.modules);
const STATUS_COUNT = STATUS_ORDER.reduce(
  (acc, status) => ({ ...acc, [status]: ALL_MODULES.filter((m) => m.status === status).length }),
  {} as Record<ImplStatus, number>,
);
const WITH_CODE = STATUS_COUNT.implemented + STATUS_COUNT.partial;
/** Every module as one tile of the hero's wall, drawn with its product area's icon. */
const WALL_MODULES: WallModule[] = FEATURE_CATEGORIES.flatMap((cat) =>
  cat.modules.map((m) => ({ name: m.name, icon: cat.icon, status: m.status })),
);

/**
 * The "At a glance" summary: the ten product areas grouped into four pillars. Every area id appears in
 * exactly one pillar; the modules listed come straight from the catalogue (first few per pillar).
 */
interface Pillar {
  id: string;
  /** A photograph of that part of campus life, with its alt text. */
  photo: { src: string; alt: string };
  title: string;
  summary: string;
  categoryIds: string[];
}

const PILLARS: Pillar[] = [
  {
    id: "learning",
    photo: { src: PHOTO.lecture, alt: "A lecturer presenting to students in a lecture hall" },
    title: "Students & Learning",
    summary: "From first enquiry to enrolment, then teaching, assessment and attendance.",
    categoryIds: ["student-lifecycle", "academics"],
  },
  {
    id: "practice",
    photo: { src: PHOTO.field, alt: "Students and a teacher examining plants during field training" },
    title: "Practice & Campus Life",
    summary: "Field practice and portfolios, residential life and specialized suites.",
    categoryIds: ["practice", "campus-life", "sports"],
  },
  {
    id: "operations",
    photo: { src: PHOTO.campus, alt: "Students walking along a tree-lined campus path" },
    title: "Operations & Resources",
    summary: "Spaces, assets, money, people and the services that keep campus running.",
    categoryIds: ["facilities", "finance-operations", "support"],
  },
  {
    id: "governance",
    photo: { src: PHOTO.library, alt: "A student working in a sunlit university library" },
    title: "Governance & Platform",
    summary: "Compliance and grievance processes, and the shared core every deployment runs.",
    categoryIds: ["governance", "platform"],
  },
];

/** How many modules each pillar card lists before "View all". */
const PILLAR_PREVIEW = 5;

/**
 * Features page: the full Education OS catalogue, organised by product area. Each module card shows a
 * concise description, representative roles and its implementation status — using the five labels from
 * features.md so nothing Specified/Scaffold/Planned is presented as live.
 *
 * Layout (taste-skill house style: no ornaments, type and tone do the work): a large serif title with
 * three counts taken from the catalogue itself; a sticky product-area index (a sidebar on wide screens,
 * a wrapping row below 1100px) that highlights the area in view and scrolls to it on click (scrolling,
 * not changing the route hash); a status filter; and each area's modules as rows set on a tone step.
 * The four-pillar summary is a typographic list; the close is the one full green field. Reduced-motion
 * safe.
 */
export function FeaturesPage({ onNavigate }: { onNavigate: (route: PublicRoute) => void }) {
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [activeId, setActiveId] = useState(FEATURE_CATEGORIES[0]?.id ?? "");
  // Pointing at a count picks out its tiles on the wall behind the hero.
  const [wallFocus, setWallFocus] = useState<"code" | "modules" | null>(null);

  const visible = useMemo(
    () =>
      FEATURE_CATEGORIES.map((cat) => ({
        ...cat,
        modules: filter === "all" ? cat.modules : cat.modules.filter((m) => m.status === filter),
      })).filter((cat) => cat.modules.length > 0),
    [filter],
  );
  const visibleModules = visible.reduce((n, cat) => n + cat.modules.length, 0);

  // Highlight the product area currently in view.
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(
      (entries) => {
        const hit = entries.find((e) => e.isIntersecting);
        if (hit) setActiveId(hit.target.id.replace("wpc-cat-", ""));
      },
      { rootMargin: "-35% 0px -60% 0px" },
    );
    visible.forEach((cat) => {
      const el = document.getElementById(`wpc-cat-${cat.id}`);
      if (el) io.observe(el);
    });
    return () => io.disconnect();
  }, [visible]);

  const jumpTo = (id: string) => {
    const el = document.getElementById(`wpc-cat-${id}`);
    if (!el) return;
    setActiveId(id);
    el.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });
    // Move focus to the section so keyboard and screen-reader users land there too.
    el.focus({ preventScroll: true });
  };

  // From a pillar card: clear any status filter (so the area is shown), then scroll to it once rendered.
  const viewAll = (id: string) => {
    setFilter("all");
    window.setTimeout(() => requestAnimationFrame(() => jumpTo(id)), 0);
  };

  return (
    <div className="wpc-page wpc-fx">
      {/* Hero */}
      <header className="wpc-fx-hero">
        <ModuleWall modules={WALL_MODULES} highlight={wallFocus} />
        <div className="wpc-container wpc-fx-hero__inner">
          <h1 className="wpc-fx-hero__title">Everything in Education OS</h1>
          <p className="wpc-fx-hero__subtitle">
            Modules, platform capabilities and specialized solutions — grouped by what they do, with an honest
            status for each.
          </p>
          <dl className="wpc-fx-stats">
            <div className="wpc-fx-stat">
              <dt>Product areas</dt>
              <dd>{FEATURE_CATEGORIES.length}</dd>
            </div>
            <div
              className="wpc-fx-stat wpc-fx-stat--wall"
              onMouseEnter={() => setWallFocus("modules")}
              onMouseLeave={() => setWallFocus(null)}
            >
              <dt>Modules</dt>
              <dd>{ALL_MODULES.length}</dd>
            </div>
            <div
              className="wpc-fx-stat wpc-fx-stat--wall"
              onMouseEnter={() => setWallFocus("code")}
              onMouseLeave={() => setWallFocus(null)}
            >
              <dt>With working code</dt>
              <dd>{WITH_CODE}</dd>
            </div>
          </dl>
          <img
            className="wpc-fx-hero__photo"
            src={PHOTO.students}
            alt="Four students sitting together on campus steps, sharing a laptop and books"
            width={1068}
            height={768}
          />
          <div className="wpc-fx-hero__actions">
            <Button variant="primary" onClick={() => onNavigate("signup")}>
              Start free trial
            </Button>
            <button
              type="button"
              className="wpc-fx-hero__link"
              onClick={() => FEATURE_CATEGORIES[0] && jumpTo(FEATURE_CATEGORIES[0].id)}
            >
              Browse the catalogue <Icons.ChevronDown size={16} aria-hidden />
            </button>
          </div>
        </div>
      </header>

      {/* Catalogue */}
      <div className="wpc-container wpc-fx-body">
        <aside className="wpc-fx-index" aria-label="Product areas">
          {/* Small screens: one sticky dropdown that follows the area in view and jumps on choice. */}
          <div className="wpc-fx-jump">
            <Listbox
              label="Jump to a product area"
              hideLabel
              value={activeId}
              options={visible.map((cat) => ({
                value: cat.id,
                label: cat.title,
                hint: `${cat.modules.length} ${cat.modules.length === 1 ? "module" : "modules"}`,
              }))}
              onChange={jumpTo}
            />
          </div>
          <p className="wpc-fx-index__label">Product areas</p>
          <ul className="wpc-fx-index__list">
            {visible.map((cat) => (
              <li key={cat.id}>
                <button
                  type="button"
                  className={cat.id === activeId ? "wpc-fx-index__link is-active" : "wpc-fx-index__link"}
                  data-area={cat.id}
                  aria-current={cat.id === activeId ? "true" : undefined}
                  onClick={() => jumpTo(cat.id)}
                >
                  <span className="wpc-fx-index__name">{cat.title}</span>
                  <span className="wpc-fx-index__count">{cat.modules.length}</span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <div className="wpc-fx-main">
          {/* Status filter + legend */}
          <section className="wpc-fx-filter" aria-labelledby="wpc-fx-filter-h">
            <h2 id="wpc-fx-filter-h" className="wpc-fx-filter__title">
              Filter by status
            </h2>
            <div className="wpc-fx-filter__chips" role="group" aria-label="Filter modules by status">
              <FilterChip label="All" count={ALL_MODULES.length} active={filter === "all"} onClick={() => setFilter("all")} />
              {STATUS_ORDER.map((status) => (
                <FilterChip
                  key={status}
                  label={STATUS_LABEL[status]}
                  count={STATUS_COUNT[status]}
                  status={status}
                  active={filter === status}
                  disabled={STATUS_COUNT[status] === 0}
                  onClick={() => setFilter(status)}
                />
              ))}
            </div>
            <p className="wpc-fx-filter__result" aria-live="polite">
              Showing {visibleModules} {visibleModules === 1 ? "module" : "modules"} in {visible.length}{" "}
              {visible.length === 1 ? "area" : "areas"}
              {filter !== "all" && <> · {STATUS_HINT[filter as ImplStatus]}</>}
            </p>
            <details className="wpc-fx-legend">
              <summary>How to read the status labels</summary>
              <ul className="wpc-fx-legend__list">
                {STATUS_ORDER.map((status) => (
                  <li key={status}>
                    <Badge tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Badge>
                    <span>{STATUS_HINT[status]}</span>
                  </li>
                ))}
              </ul>
            </details>
          </section>

          {visible.map((cat) => (
            <CategorySection key={`${cat.id}-${filter}`} category={cat} />
          ))}
        </div>
      </div>

      {/* At a glance: the catalogue summarised into four pillars */}
      <section className="wpc-fx-sum" aria-labelledby="wpc-fx-sum-h">
        <div className="wpc-container wpc-fx-sum__inner">
          <Reveal className="wpc-fx-sum__head">
            <h2 id="wpc-fx-sum-h" className="wpc-fx-sum__title">
              The whole platform, in four pillars
            </h2>
            <p className="wpc-fx-sum__lead">
              A short tour of what each part of Education OS covers. Open any pillar to see every module in
              the catalogue above.
            </p>
          </Reveal>
          <RevealGroup className="wpc-fx-sum__grid">
            {PILLARS.map((pillar, i) => (
              <PillarCard key={pillar.id} pillar={pillar} index={i} onViewAll={viewAll} />
            ))}
          </RevealGroup>
        </div>
      </section>

      {/* Closing CTA */}
      <section className="wpc-fx-cta" aria-labelledby="wpc-fx-cta-h">
        <div className="wpc-container wpc-fx-cta__inner">
          <Reveal className="wpc-fx-cta__copy">
            <h2 id="wpc-fx-cta-h" className="wpc-fx-cta__title">
              Start with a free trial
            </h2>
            <p className="wpc-fx-cta__text">Register your organisation, pick your academy type, and go live after approval.</p>
          </Reveal>
          <Reveal className="wpc-fx-cta__actions" delay={120}>
            <Button variant="primary" onClick={() => onNavigate("signup")}>
              Start free trial
            </Button>
            <Button variant="ghost" onClick={() => onNavigate("home")}>
              Back to home
            </Button>
          </Reveal>
        </div>
      </section>
    </div>
  );
}

function FilterChip({
  label,
  count,
  status,
  active,
  disabled = false,
  onClick,
}: {
  label: string;
  count: number;
  status?: ImplStatus;
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={active ? "wpc-fx-chip is-active" : "wpc-fx-chip"}
      data-status={status}
      aria-pressed={active}
      disabled={disabled}
      title={status ? STATUS_HINT[status] : undefined}
      onClick={onClick}
    >
      {status && <span className="wpc-fx-chip__dot" aria-hidden />}
      {label}
      <span className="wpc-fx-chip__count">{count}</span>
    </button>
  );
}

/** One product area: a header, then its modules as rows. */
function CategorySection({ category }: { category: FeatureCategory }) {
  return (
    <section
      className="wpc-fx-cat"
      id={`wpc-cat-${category.id}`}
      tabIndex={-1}
      aria-labelledby={`wpc-cat-${category.id}-h`}
    >
      <Reveal className="wpc-fx-cat__head">
        <div className="wpc-fx-cat__heading">
          <h2 id={`wpc-cat-${category.id}-h`} className="wpc-fx-cat__title">
            {category.title}
          </h2>
          <p className="wpc-fx-cat__sub">{category.summary}</p>
        </div>
        <span className="wpc-fx-cat__count">
          {category.modules.length} {category.modules.length === 1 ? "module" : "modules"}
        </span>
      </Reveal>
      <RevealGroup className="wpc-fx-grid">
        {category.modules.map((mod, i) => (
          <ModuleCard key={mod.name} module={mod} index={i} />
        ))}
      </RevealGroup>
    </section>
  );
}

function ModuleCard({ module: mod, index }: { module: FeatureModule; index: number }) {
  return (
    <article className="wpc-fx-card" data-status={mod.status} style={stagger(index)}>
      <div className="wpc-fx-card__head">
        <h3 className="wpc-fx-card__title">{mod.name}</h3>
        <Badge tone={STATUS_TONE[mod.status]}>{STATUS_LABEL[mod.status]}</Badge>
      </div>
      <p className="wpc-fx-card__text">{mod.description}</p>
      {mod.roles.length > 0 && (
        <ul className="wpc-fx-card__roles" aria-label="Typical roles">
          {mod.roles.map((role) => (
            <li key={role}>{role}</li>
          ))}
        </ul>
      )}
    </article>
  );
}

/** One pillar of the summary: title, framing line, a few modules, and a link into the catalogue. */
function PillarCard({ pillar, index, onViewAll }: { pillar: Pillar; index: number; onViewAll: (id: string) => void }) {
  const categories = pillar.categoryIds
    .map((id) => FEATURE_CATEGORIES.find((cat) => cat.id === id))
    .filter((cat): cat is FeatureCategory => Boolean(cat));
  const modules = categories.flatMap((cat) => cat.modules);
  const preview = modules.slice(0, PILLAR_PREVIEW);
  const first = categories[0];

  return (
    <article className="wpc-fx-pillar" data-pillar={pillar.id} style={stagger(index)} aria-labelledby={`wpc-pillar-${pillar.id}`}>
      <h3 id={`wpc-pillar-${pillar.id}`} className="wpc-fx-pillar__title">
        {pillar.title}
      </h3>
      <p className="wpc-fx-pillar__summary">{pillar.summary}</p>
      <img className="wpc-fx-pillar__photo" src={pillar.photo.src} alt={pillar.photo.alt} loading="lazy" />
      <ul className="wpc-fx-pillar__list">
        {preview.map((mod) => (
          <li key={mod.name} className="wpc-fx-pillar__item">
            <span className="wpc-fx-pillar__body">
              <span className="wpc-fx-pillar__name">
                {mod.name}
                <span className="eos-sr-only"> ({STATUS_LABEL[mod.status]})</span>
              </span>
              <span className="wpc-fx-pillar__desc">{mod.description}</span>
            </span>
          </li>
        ))}
      </ul>
      {first && (
        <button type="button" className="wpc-fx-pillar__more" onClick={() => onViewAll(first.id)}>
          View all {modules.length} modules <Icons.ArrowRight size={16} className="wpc-link__arrow" aria-hidden />
        </button>
      )}
    </article>
  );
}
