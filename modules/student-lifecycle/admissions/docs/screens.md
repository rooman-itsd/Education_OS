# admissions — screen inventory

The screens and widgets the contracts are designed to support.

## Public (web-portal-cms hosts the entry point; these are admissions' own pages)

Every public page is reached under the organisation's slug, e.g. `/apply/{org_slug}/track`.

| Screen | Purpose | Auth |
|---|---|---|
| Application form | Submit a new application | None (public) |
| Track application | Look up status and documents by reference number + email | None (public, email-verified) |
| Document upload | Attach a supporting document to an in-progress application | None (public, email-verified) |
| Offer decision | Accept or decline an offer | None (public, email-verified) |

Applicants have no account (`docs/prd.md` §6), so the Track application page is their view of
their own application — what an applicant dashboard would otherwise show.

## Staff (admissions dashboard / console)

| Screen | Purpose | Primary permission |
|---|---|---|
| Applications queue | List/search/filter applications | `admissions:application:read` |
| Application detail | Review one application, its documents, status history | `admissions:application:read` |
| Document verification | Verify/reject documents | `admissions:document:verify` |
| Status transition | Move an application through review/eligibility/rejection | `admissions:application:manage` |
| Merit lists | Generate (with optional scores) and publish merit lists | `admissions:merit-list:manage` |
| Offers | Extend an offer on an eligible application | `admissions:offer:manage` |

## Dashboard widgets

| Widget id | Kind | Permission | Data | Shows |
|---|---|---|---|---|
| `admissions.funnel` | chart | `admissions:report:read` | `GET /reports/funnel` | Applied → eligible → offered → accepted, with conversion between stages |
| `admissions.application-status` | list | `admissions:application:read` | `GET /applications` | Latest applications with their status |
| `admissions.pending-documents` | list | `admissions:document:verify` | `GET /documents?verification_status=pending` | Documents waiting for verification, oldest first |

`admissions.funnel` is on the Management (VC, Registrar) layout. `admissions.application-status`
and `admissions.pending-documents` are staff widgets: `platform/identity/config/dashboards/applicant.yaml`
still lists them, and the shell hides them there because an applicant holds no permission (and has
no session). Placing them on a staff layout is a change to the layout files, which the
Architecture lead owns; it is not made here.
