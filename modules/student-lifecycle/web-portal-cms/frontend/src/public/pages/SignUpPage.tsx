import { Fragment, useEffect, useState, type CSSProperties } from "react";
import { ErrorState, Icons, prefersReducedMotion } from "@eos/ui-kit";
import { APP_URL, ORG_SIGNUP_URL, type PublicRoute } from "../content";
import { BrandedLoader } from "../components/BrandedLoader";
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

type LoadState = "loading" | "error" | "ready";

function currencySymbol(currency: string): string {
  return currency === "INR" ? "₹" : `${currency} `;
}

function formatAmount(amount: number, currency: string): string {
  return amount.toLocaleString(currency === "INR" ? "en-IN" : undefined);
}

/** Short headline features with icons, from the plan's limits. */
function limitFeatures(plan: Plan): { text: string; icon: "Users" | "GraduationCap" | "Layers" }[] {
  const l = plan.limits ?? {};
  const out: { text: string; icon: "Users" | "GraduationCap" | "Layers" }[] = [];
  if (l.users != null) out.push({ text: `${l.users.toLocaleString("en-IN")} users`, icon: "Users" });
  if (l.students != null) out.push({ text: `${l.students.toLocaleString("en-IN")} students`, icon: "GraduationCap" });
  if (l.storage_gb != null) out.push({ text: `${l.storage_gb} GB storage`, icon: "Layers" });
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

  return (
    <div className="wpc-page wpc-pricing">
      <div className="wpc-container wpc-pricing__inner">
        <header className="wpc-pricing__head">
          <div className="wpc-pricing__intro">
            <p className="wpc-pricing__eyebrow">Get started</p>
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
          </div>
          {trial?.trial_days ? (
            <p className="wpc-pricing__pill">
              <Icons.Clock size={16} aria-hidden />
              Free for {trial.trial_days} days
            </p>
          ) : null}
        </header>

        {loadState === "loading" && <BrandedLoader label="Loading plans…" />}

        {loadState === "error" && (
          <ErrorState title="Couldn't reach the service" onRetry={loadPlans}>
            Plans couldn't be loaded right now. Please try again.
          </ErrorState>
        )}

        {loadState === "ready" && (
          <div className="wpc-pricing__tray" role="list" aria-label="Plans">
            {plans.map((plan, i) => (
              <PlanCard key={plan.id} plan={plan} index={i} featured={plan.id === "trial"} />
            ))}
          </div>
        )}

        <div className="wpc-pricing__foot">
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
        </div>
      </div>
    </div>
  );
}

function PlanCard({ plan, index, featured }: { plan: Plan; index: number; featured: boolean }) {
  const free = !plan.price_per_month;
  const price = useCountUp(plan.price_per_month || 0);
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
        <span className={featured ? "wpc-plan-card__tag is-live" : "wpc-plan-card__tag"}>
          {featured ? "Available now" : "After approval"}
        </span>

        <p className="wpc-plan-card__price">
          {free ? (
            <span className="wpc-plan-card__amount">Free</span>
          ) : (
            <>
              <span className="wpc-plan-card__amount">
                {currencySymbol(plan.currency)}
                {formatAmount(price, plan.currency)}
              </span>
              <span className="wpc-plan-card__per">/month</span>
            </>
          )}
        </p>
        {free && plan.trial_days ? <p className="wpc-plan-card__per">for {plan.trial_days} days</p> : null}

        <h2 id={`wpc-plan-${plan.id}`} className="wpc-plan-card__name">
          {plan.title}
        </h2>
        {plan.description && <p className="wpc-plan-card__desc">{plan.description}</p>}

        {features.length > 0 && (
          <ul className="wpc-plan-card__features">
            {features.map((f) => {
              const Icon = Icons[f.icon];
              return (
                <li key={f.text}>
                  <Icon size={18} aria-hidden />
                  {f.text}
                </li>
              );
            })}
          </ul>
        )}

        {includes.length > 0 && (
          <div className="wpc-plan-card__includes">
            <h3>Includes:</h3>
            <ul>
              {includes.map((item) => (
                <li key={item}>
                  <span className="wpc-plan-card__check" aria-hidden>
                    <Icons.Check size={13} />
                  </span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}

        {plan.after_trial && featured && <p className="wpc-plan-card__note">{plan.after_trial}</p>}
      </div>

      {featured ? (
        <a className="wpc-plan-card__cta" href={ORG_SIGNUP_URL}>
          Start free trial <Icons.ArrowRight size={18} className="wpc-btn-arrow" aria-hidden />
        </a>
      ) : (
        <span className="wpc-plan-card__cta is-locked" aria-disabled="true">
          <Icons.Lock size={16} aria-hidden /> Available after approval
        </span>
      )}
    </article>
  );
}

/** Counts a number up from 0 when it first renders (instant under reduced motion). */
function useCountUp(target: number, duration = 900): number {
  const [value, setValue] = useState(() => (prefersReducedMotion() ? target : 0));
  useEffect(() => {
    if (prefersReducedMotion() || target === 0) {
      setValue(target);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(target * eased));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);
  return value;
}
