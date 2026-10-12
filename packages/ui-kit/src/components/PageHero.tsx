import type { ReactNode } from "react";

export interface PageHeroProps {
  title: ReactNode;
  subtitle?: ReactNode;
  /** Small line above the title, e.g. the suite a module belongs to. */
  eyebrow?: ReactNode;
  actions?: ReactNode;
  /** A photo behind the hero; the gradient fades over it from the left so the text stays readable. */
  image?: string;
  /** Heading level. */
  as?: "h1" | "h2";
}

/** The page header: the one gradient surface on a page. Buttons on it are white or glass. */
export function PageHero({ title, subtitle, eyebrow, actions, image, as: Heading = "h1" }: PageHeroProps) {
  return (
    <header className={image ? "eos-hero eos-hero--art" : "eos-hero"}>
      {image && (
        <div className="eos-hero__art" aria-hidden>
          <img src={image} alt="" />
        </div>
      )}
      <div className="eos-hero__text">
        {eyebrow && <div className="eos-hero__eyebrow">{eyebrow}</div>}
        <Heading className="eos-hero__title">{title}</Heading>
        {subtitle && <div className="eos-hero__subtitle">{subtitle}</div>}
        {image && actions && <div className="eos-hero__actions">{actions}</div>}
      </div>
      {!image && actions && <div className="eos-hero__actions">{actions}</div>}
    </header>
  );
}
