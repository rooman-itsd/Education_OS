"""Status vocabularies from contracts/openapi.yaml and the transition table from docs/prd.md §6."""

from __future__ import annotations

SUBMITTED = "submitted"
UNDER_REVIEW = "under_review"
ELIGIBLE = "eligible"
INELIGIBLE = "ineligible"
OFFERED = "offered"
ACCEPTED = "accepted"
DECLINED = "declined"
REJECTED = "rejected"
WITHDRAWN = "withdrawn"

APPLICATION_STATUSES = (
    SUBMITTED,
    UNDER_REVIEW,
    ELIGIBLE,
    INELIGIBLE,
    OFFERED,
    ACCEPTED,
    DECLINED,
    REJECTED,
    WITHDRAWN,
)

TERMINAL = frozenset({INELIGIBLE, REJECTED, WITHDRAWN, ACCEPTED, DECLINED})

DOCUMENTS_OPEN = frozenset({SUBMITTED, UNDER_REVIEW})

# Targets reachable through the staff status endpoint. Offer, accept and decline have their own endpoints.
STAFF_TRANSITIONS: dict[str, frozenset[str]] = {
    SUBMITTED: frozenset({UNDER_REVIEW, REJECTED, WITHDRAWN}),
    UNDER_REVIEW: frozenset({UNDER_REVIEW, ELIGIBLE, INELIGIBLE, REJECTED, WITHDRAWN}),
    ELIGIBLE: frozenset({WITHDRAWN}),
    OFFERED: frozenset({WITHDRAWN}),
}

DOCUMENT_TYPES = ("identity_proof", "academic_record", "portfolio_evidence", "other")

PENDING = "pending"
VERIFIED = "verified"
VERIFICATION_STATUSES = (PENDING, VERIFIED, REJECTED)
VERIFICATION_DECISIONS = (VERIFIED, REJECTED)

OFFER_OPEN = "open"
OFFER_EXPIRED = "expired"
OFFER_STATUSES = (OFFER_OPEN, ACCEPTED, DECLINED, OFFER_EXPIRED, WITHDRAWN)

DRAFT = "draft"
PUBLISHED = "published"
MERIT_LIST_STATUSES = (DRAFT, PUBLISHED)
