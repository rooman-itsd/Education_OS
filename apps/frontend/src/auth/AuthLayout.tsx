import type { ReactNode } from "react";
import { EduMark, Wordmark } from "@eos/ui-kit";

/** The split sign-in page: brand hero on the left, the form card on the right. */
export function AuthLayout({ children, footnote }: { children: ReactNode; footnote?: ReactNode }) {
  return (
    <div className="eos-auth">
      <aside className="eos-auth__hero" aria-hidden>
        <div style={{ position: "relative", display: "flex", alignItems: "center", gap: 12 }}>
          <EduMark size={44} />
          <Wordmark inverse size={22} />
        </div>
        <div style={{ position: "relative" }}>
          <h2>One platform for every institution</h2>
          <p>Configured for the way each institution teaches, trains, manages and supports its students.</p>
        </div>
        <div className="eos-auth__facts">
          <div className="eos-auth__fact"><b>15</b><span>Academy types</span></div>
          <div className="eos-auth__fact"><b>42</b><span>Feature modules</span></div>
          <div className="eos-auth__fact"><b>13</b><span>Platform services</span></div>
        </div>
      </aside>
      <main className="eos-auth__side">
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <EduMark size={40} />
          <Wordmark size={20} />
        </div>
        {children}
        {footnote && <p className="eos-auth__footnote">{footnote}</p>}
      </main>
    </div>
  );
}
