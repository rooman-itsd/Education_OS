# admissions — screen inventory

Week 1 scope is contracts and PRD only; no frontend code is built yet. This is the planned screen
list the contracts above are designed to support.

## Public (web-portal-cms hosts the entry point; these are admissions' own pages)

| Screen | Purpose | Auth |
|---|---|---|
| Application form | Submit a new application | None (public) |
| Track application | Look up status and pending documents by reference number + email | None (public) |
| Document upload | Attach a supporting document to an in-progress application | None (public, email-verified) |
| Offer decision | Accept or decline an offer | None (public, email-verified) |

## Staff (admissions dashboard / console)

| Screen | Purpose | Primary permission |
|---|---|---|
| Applications queue | List/search/filter applications | `admissions:application:read` |
| Application detail | Review one application, its documents, status history | `admissions:application:read` |
| Document verification | Verify/reject documents | `admissions:document:verify` |
| Status transition | Move an application through review/eligibility/rejection | `admissions:application:manage` |
| Merit lists | Generate and publish merit lists | `admissions:merit-list:manage` |
| Offers | Extend an offer on an eligible application | `admissions:offer:manage` |

## Dashboard widgets

`platform/identity/config/dashboards/applicant.yaml` already lists
`admissions.application-status` and `admissions.pending-documents` as widget ids for the
Applicant role. Since this release has no applicant account/session, these widgets cannot be
built as session-scoped "my application" widgets this week; they remain "not built yet" on that
dashboard until an authenticated applicant experience is decided (see `docs/prd.md` §6). This is
a known, flagged gap, not an oversight — the dashboard layout file itself is owned by the
Architecture lead and is not changed here.
