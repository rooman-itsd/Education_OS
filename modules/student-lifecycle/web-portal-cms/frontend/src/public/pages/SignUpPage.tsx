import { Fragment, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { ButtonLink, ErrorState, Icons, prefersReducedMotion } from "@eos/ui-kit";
import { APP_URL, ORG_SIGNUP_URL, type PublicRoute } from "../content";
import { BrandedLoader } from "../components/BrandedLoader";
import { TrialDial } from "../components/TrialDial";
import { RollingNumber } from "../components/RollingNumber";
import { Reveal, RevealGroup, stagger } from "../components/Reveal";
import { TrialJourney, type JourneyStep } from "../components/TrialJourney";
import { getPlans, type Plan } from "../../api/public-client";

/**
 * "Get started": plans and pricing, rendered from billing's public GET /billing/plans. Creating the
 * organisation and administrator account is not done here — the free-trial button hands off to the
 * app's own organisation sign-up (ORG_SIGNUP_URL), which owns registration and email verification.
 *
 * Honesty rules (features.md §H, §J):
 *  - Registration always starts the free trial — POST /register takes no plan — so only the trial is
 *    selectable; paid plans are shown with "Available after approval" and can't be chosen here.
 *  - Billing publishes monthly prices only, so there is no monthly/yearly switch or invented discount.
 *  - Plan features are derived from the plan's own data (limits, suites, integrations), nothing more.
 */

const TITLE = "Plans & pricing";

/**
 * Questions answered only with what the platform actually does: registration always starts the trial
 * (tenancy POST /register takes no plan), approval is by a platform administrator, the trial plan's
 * after_trial is read_only (billing plans.yaml), and every organisation is isolated by row-level security.
 */
const FAQ: { q: string; a: string }[] = [
  {
    q: "What does the free trial include?",
    a: "Every organisation starts on the trial plan shown above. Its users, students, storage, suites and integrations are listed on the card.",
  },
  {
    q: "Can I choose a paid plan when I sign up?",
    a: "Not yet. Registration always starts the free trial; Standard and Premium become available after your organisation is approved.",
  },
  {
    q: "What happens after I register?",
    a: "You confirm your email address, then a platform administrator reviews and approves your organisation. You can sign in once it is approved.",
  },
  {
    q: "What happens when the trial ends?",
    a: "On the trial plan, your organisation stays readable but can't be changed until a plan is active.",
  },
  {
    q: "Is our data kept separate from other institutions?",
    a: "Yes. Each organisation sees only its own records, enforced in the database with row-level security.",
  },
];

/** Plain-language meaning of billing's `after_trial` values (platform/billing/config/plans.yaml). */
const AFTER_TRIAL: Record<string, string> = {
  read_only: "When the trial ends, your organisation stays readable but can't be changed until a plan is active.",
  suspend: "When the trial ends, your organisation is paused until a plan is active.",
};

/** Trial length the dial shows until billing's plans arrive (the site's stated 30-day trial). */
const DEFAULT_TRIAL_DAYS = 30;

/**
 * From registration to a paid plan, using only what the platform does (see FAQ above): registration
 * starts the trial, the email is confirmed, a platform administrator approves, then the trial runs and
 * a plan is chosen. The trial length and what happens after it come from billing's trial plan.
 */
function journeySteps(trialDays: number, afterTrial: string | undefined): JourneyStep[] {
  return [
    {
      id: "register",
      title: "Register your organisation",
      text: "Add your organisation, its academy type and an administrator account. Registration always starts the free trial.",
    },
    {
      id: "confirm",
      title: "Confirm your email",
      text: "Open the link sent to the administrator's address to verify it.",
    },
    {
      id: "approve",
      title: "Get approved",
      text: "A platform administrator reviews your organisation. Once it is approved, you can sign in.",
    },
    {
      id: "trial",
      title: `Use it free for ${trialDays} days`,
      text: `Everything listed on the Trial card below, free for ${trialDays} days.`,
      dial: "count",
    },
    {
      id: "choose",
      title: "Choose a plan",
      text: `${(afterTrial && AFTER_TRIAL[afterTrial]) || "When the trial ends, choose a plan to keep working."} Standard and Premium become available once you're approved.`,
      dial: "end",
    },
  ];
}

const PHOTO = {
  campus: new URL("../assets/campus-walk.jpg", import.meta.url).href,
};

type LoadState = "loading" | "error" | "ready";

function currencySymbol(currency: string): string {
  return currency === "INR" ? "₹" : `${currency} `;
}

function formatAmount(amount: number, currency: string): string {
  return amount.toLocaleString(currency === "INR" ? "en-IN" : undefined);
}

/** Short headline limits, from the plan's own limits. */
function limitFeatures(plan: Plan): { text: string }[] {
  const l = plan.limits ?? {};
  const out: { text: string }[] = [];
  if (l.users != null) out.push({ text: `${l.users.toLocaleString("en-IN")} users` });
  if (l.students != null) out.push({ text: `${l.students.toLocaleString("en-IN")} students` });
  if (l.storage_gb != null) out.push({ text: `${l.storage_gb} GB storage` });
  return out;
}

/** The "includes" checklist, from the plan's suites, modules and integrations. */
function inclusions(plan: Plan): string[] {
  const out: string[] = [];
  if (plan.suites?.length) out.push(`${plan.suites.length} product ${plan.suites.length === 1 ? "suite" : "suites"}`);
  if (plan.modules?.length) out.push(`${plan.modules.length} ${plan.modules.length === 1 ? "module" : "modules"}`);
  if (plan.specialized_suites === "all") out.push("All specialized suites");
  else if (plan.specialized_suites > 0)
    out.push(`${plan.specialized_suites} specialized ${plan.specialized_suites === 1 ? "suite" : "suites"}`);
  if (plan.integrations?.length)
    out.push(`${plan.integrations.length} ${plan.integrations.length === 1 ? "integration" : "integrations"}`);
  return out;
}

export function SignUpPage({ onNavigate }: { onNavigate: (route: PublicRoute) => void }) {
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [plans, setPlans] = useState<Plan[]>([]);
  const headRef = useRef<HTMLElement>(null);
  const [dialDemo, setDialDemo] = useState<"count" | "end" | null>(null);

  const loadPlans = () => {
    setLoadState("loading");
    getPlans()
      .then((p) => {
        setPlans(p);
        setLoadState("ready");
      })
      .catch(() => setLoadState("error"));
  };

  useEffect(loadPlans, []);

  const trial = plans.find((p) => p.id === "trial");
  const trialDays = trial?.trial_days ?? DEFAULT_TRIAL_DAYS;
  const steps = useMemo(() => journeySteps(trialDays, trial?.after_trial), [trialDays, trial?.after_trial]);

  const toPlans = () => {
    const el = document.getElementById("wpc-plans");
    el?.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });
  };

  return (
    <div className="wpc-page wpc-pricing">
      <div className="wpc-container wpc-pricing__inner">
        <header ref={headRef} className="wpc-pricing__head">
          <div className="wpc-pricing__intro">
            <h1 className="wpc-pricing__title" aria-label={TITLE}>
              <span aria-hidden>
                {TITLE.split(" ").map((word, i) => (
                  <Fragment key={`${word}-${i}`}>
                    {i > 0 && " "}
                    <span className="wpc-pricing__word">
                      <span style={{ "--w": i } as CSSProperties}>{word}</span>
                    </span>
                  </Fragment>
                ))}
              </span>
            </h1>
            <p className="wpc-pricing__lead">
              Every organisation starts on the free trial. Paid plans activate after your organisation is
              approved — explore what each one includes.
            </p>
            <p className="wpc-tj__label">How the trial works</p>
            <TrialJourney steps={steps} label="How the trial works" onDial={setDialDemo} />
            <div className="wpc-pricing__actions">
              <ButtonLink variant="primary" href={ORG_SIGNUP_URL}>
                Start free trial
              </ButtonLink>
              <button type="button" className="wpc-pricing__compare" onClick={toPlans}>
                Compare plans <Icons.ChevronDown size={16} aria-hidden />
              </button>
            </div>
          </div>
          <div className="wpc-pricing__aside">
            <div className="wpc-pricing__dialwrap">
              <TrialDial days={trialDays} hostRef={headRef} demo={dialDemo} />
              <img
                className="wpc-pricing__photo"
                src={PHOTO.campus}
                alt="Students walking and talking along a tree-lined campus path"
                width={840}
                height={700}
              />
            </div>
            {trial?.trial_days ? (
              <p className="wpc-pricing__trial">
                Free for <strong>{trial.trial_days} days</strong>, then choose a plan.
              </p>
            ) : null}
          </div>
        </header>

        {loadState === "loading" && <BrandedLoader label="Loading plans…" />}

        {loadState === "error" && (
          <ErrorState title="Couldn't reach the service" onRetry={loadPlans}>
            Plans couldn't be loaded right now. Please try again.
          </ErrorState>
        )}

        {loadState === "ready" && (
          <div id="wpc-plans" className="wpc-pricing__tray" role="list" aria-label="Plans">
            {plans.map((plan, i) => (
              <PlanCard key={plan.id} plan={plan} index={i} featured={plan.id === "trial"} />
            ))}
          </div>
        )}

        <section className="wpc-faq" aria-labelledby="wpc-faq-h">
          <Reveal as="h2" id="wpc-faq-h" className="wpc-faq__title">
            Questions before you start
          </Reveal>
          <RevealGroup className="wpc-faq__list">
            {FAQ.map((item, i) => (
              <details key={item.q} className="wpc-faq__item" style={stagger(i)}>
                <summary>{item.q}</summary>
                <p>{item.a}</p>
              </details>
            ))}
          </RevealGroup>
        </section>

        <Reveal className="wpc-pricing__foot">
          <a className="wpc-pricing__link" href={APP_URL}>
            Already registered? <strong>Sign in</strong>
          </a>
          <a
            className="wpc-pricing__link"
            href="#/"
            onClick={(e) => {
              e.preventDefault();
              onNavigate("home");
            }}
          >
            Back to home
          </a>
        </Reveal>
      </div>
    </div>
  );
}

function PlanCard({ plan, index, featured }: { plan: Plan; index: number; featured: boolean }) {
  const free = !plan.price_per_month;
  const features = limitFeatures(plan);
  const includes = inclusions(plan);

  return (
    <article
      role="listitem"
      className={featured ? "wpc-plan-card is-featured" : "wpc-plan-card"}
      style={{ "--i": index } as CSSProperties}
      aria-labelledby={`wpc-plan-${plan.id}`}
    >
      <div className="wpc-plan-card__top">
        <h2 id={`wpc-plan-${plan.id}`} className="wpc-plan-card__name">
          {plan.title}
        </h2>
        {plan.description && <p className="wpc-plan-card__desc">{plan.description}</p>}

        <p className="wpc-plan-card__price">
          {free ? (
            <span className="wpc-plan-card__amount">Free</span>
          ) : (
            <>
              <span className="wpc-plan-card__amount">
                {currencySymbol(plan.currency)}
                {/* Rolls in as the card finishes its entrance (public.css: 0.35s + index × 0.14s). */}
                <RollingNumber text={formatAmount(plan.price_per_month, plan.currency)} delay={550 + index * 140} />
              </span>
              <span className="wpc-plan-card__per">/month</span>
            </>
          )}
        </p>
        {free && plan.trial_days ? <p className="wpc-plan-card__per">for {plan.trial_days} days</p> : null}

        {features.length > 0 && (
          <ul className="wpc-plan-card__features">
            {features.map((f) => (
              <li key={f.text}>{f.text}</li>
            ))}
          </ul>
        )}

        {includes.length > 0 && (
          <div className="wpc-plan-card__includes">
            <h3>Includes:</h3>
            <ul>
              {includes.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        {plan.after_trial && featured && AFTER_TRIAL[plan.after_trial] && (
          <p className="wpc-plan-card__note">{AFTER_TRIAL[plan.after_trial]}</p>
        )}
      </div>

      {featured ? (
        <a className="wpc-plan-card__cta" href={ORG_SIGNUP_URL}>
          Start free trial <Icons.ArrowRight size={18} className="wpc-btn-arrow" aria-hidden />
        </a>
      ) : (
        <span className="wpc-plan-card__cta is-locked" aria-disabled="true">
          Available after approval
        </span>
      )}
    </article>
  );
}

