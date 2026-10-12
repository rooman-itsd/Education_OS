import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "dark";

interface ButtonBase {
  variant?: ButtonVariant;
  size?: "md" | "sm";
  /** Square button holding only an icon; pass `aria-label`. */
  icon?: boolean;
  children?: ReactNode;
  className?: string;
}

export type ButtonProps = ButtonBase & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className" | "children">;
export type ButtonLinkProps = ButtonBase & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "className" | "children">;

export function buttonClass({ variant = "secondary", size = "md", icon = false, className = "" }: ButtonBase): string {
  return ["eos-btn", `eos-btn--${variant}`, size === "sm" ? "eos-btn--sm" : "", icon ? "eos-btn--icon" : "", className]
    .filter(Boolean)
    .join(" ");
}

/** One primary (coral) button per screen; everything else is secondary or ghost. */
export function Button({ variant, size, icon, className, children, type = "button", ...rest }: ButtonProps) {
  return (
    <button type={type} className={buttonClass({ variant, size, icon, className })} {...rest}>
      {children}
    </button>
  );
}

/** A link styled as a button, for navigation. */
export function ButtonLink({ variant, size, icon, className, children, ...rest }: ButtonLinkProps) {
  return (
    <a className={buttonClass({ variant, size, icon, className })} {...rest}>
      {children}
    </a>
  );
}
