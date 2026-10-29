import type { BadgeTone } from "@eos/ui-kit";
import type { ApplicationStatus, DocumentType, OfferStatus, VerificationStatus } from "../api/client";

/** Every status is shown as a word with a tone, never by colour alone; an unknown value shows as itself. */
const STATUS: Record<ApplicationStatus, [string, BadgeTone]> = {
  submitted: ["Submitted", "neutral"],
  under_review: ["Under review", "info"],
  eligible: ["Eligible", "accent"],
  ineligible: ["Ineligible", "danger"],
  offered: ["Offer made", "warning"],
  accepted: ["Accepted", "success"],
  declined: ["Declined", "neutral"],
  rejected: ["Rejected", "danger"],
  withdrawn: ["Withdrawn", "neutral"],
};

export const statusLabel = (s: ApplicationStatus): string => STATUS[s]?.[0] ?? String(s);
export const statusTone = (s: ApplicationStatus): BadgeTone => STATUS[s]?.[1] ?? "neutral";

/** What the status means for the applicant, on the public Track page. */
const STATUS_EXPLAINED: Record<ApplicationStatus, string> = {
  submitted: "We have received your application. The admissions team will review it soon.",
  under_review: "The admissions team is reviewing your application and documents.",
  eligible: "You meet the requirements for this programme. Watch for an offer.",
  ineligible: "Your application does not meet the requirements for this programme.",
  offered: "You have an offer. Accept or decline it before it expires.",
  accepted: "You accepted your offer. The institution will contact you about the next steps.",
  declined: "You declined your offer.",
  rejected: "Your application was not successful.",
  withdrawn: "This application was withdrawn.",
};

export const statusExplained = (s: ApplicationStatus): string => STATUS_EXPLAINED[s] ?? "";

const DOCUMENT_TYPE: Record<DocumentType, string> = {
  identity_proof: "Identity proof",
  academic_record: "Academic record",
  portfolio_evidence: "Portfolio evidence",
  other: "Other document",
};

export const documentTypeLabel = (t: DocumentType): string => DOCUMENT_TYPE[t] ?? String(t);

const VERIFICATION: Record<VerificationStatus, [string, BadgeTone]> = {
  pending: ["Pending verification", "warning"],
  verified: ["Verified", "success"],
  rejected: ["Not accepted", "danger"],
};

export const verificationLabel = (v: VerificationStatus): string => VERIFICATION[v]?.[0] ?? String(v);
export const verificationTone = (v: VerificationStatus): BadgeTone => VERIFICATION[v]?.[1] ?? "neutral";

const OFFER: Record<OfferStatus, [string, BadgeTone]> = {
  open: ["Open", "warning"],
  accepted: ["Accepted", "success"],
  declined: ["Declined", "neutral"],
  expired: ["Expired", "danger"],
  withdrawn: ["Withdrawn", "neutral"],
};

export const offerLabel = (o: OfferStatus): string => OFFER[o]?.[0] ?? String(o);
export const offerTone = (o: OfferStatus): BadgeTone => OFFER[o]?.[1] ?? "neutral";

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

/** "3 days", "5 hours": how long something has been waiting. */
export function waitingFor(iso: string, now: Date = new Date()): string {
  const minutes = Math.max(0, Math.floor((now.getTime() - new Date(iso).getTime()) / 60000));
  if (minutes < 60) return minutes <= 1 ? "1 minute" : `${minutes} minutes`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return hours === 1 ? "1 hour" : `${hours} hours`;
  const days = Math.floor(hours / 24);
  return days === 1 ? "1 day" : `${days} days`;
}

export const percent = (part: number, whole: number): number => (whole ? Math.round((part / whole) * 1000) / 10 : 0);
