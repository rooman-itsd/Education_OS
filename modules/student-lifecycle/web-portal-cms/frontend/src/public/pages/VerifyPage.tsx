import { useEffect, useState } from "react";
import type { PublicRoute } from "../content";
import { RegistrationOutcome, VerifyEmail } from "../components/RegistrationSteps";
import type { VerifiedOrganisation } from "../../api/public-client";

/** The `token` query parameter of a `#/verify?token=…` link. */
export function tokenFromHash(hash: string): string {
  const query = hash.split("?")[1] ?? "";
  return new URLSearchParams(query).get("token") ?? "";
}

/**
 * `#/verify`: where the verification email's link lands (`#/verify?token=…`), and where a visitor
 * can type the code by hand. The token is read once, then removed from the address bar so it does
 * not stay in history or get shared by copying the URL; it is confirmed straight away with POST
 * /tenancy/register/verify.
 */
export function VerifyPage({ onNavigate }: { onNavigate: (route: PublicRoute) => void }) {
  // Read without side effects: React may run this initializer twice (StrictMode), so the address bar
  // is only cleaned afterwards, in an effect, once the token is safely in state.
  const [token] = useState(() => (typeof window === "undefined" ? "" : tokenFromHash(window.location.hash)));
  useEffect(() => {
    if (token) window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#/verify`);
  }, [token]);
  const [verified, setVerified] = useState<VerifiedOrganisation | null>(null);

  return (
    <div className="wpc-page wpc-reg">
      {verified ? (
        <RegistrationOutcome status={verified.status} onHome={() => onNavigate("home")} />
      ) : (
        <VerifyEmail initialToken={token} autoSubmit={Boolean(token)} onVerified={setVerified} />
      )}
    </div>
  );
}
