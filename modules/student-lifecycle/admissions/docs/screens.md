# Screens and UI — admissions

This module owns no full-page staff screens in this release; staff work through the super admin
console's applications queue and detail views, which call this module's `/applications`,
`/merit-lists` and `/reports` endpoints directly.

The public Track Application page is exported by this module's frontend as `<TrackApplicationPage
orgSlug="..." />` for the host to mount at a public URL (e.g. `#/apply/{org_slug}/track`).

## Staff actions (mounted in the super admin console)

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
| `admissions.application-status` | list | `admissions:self:read` | `GET /me/applications` | The applicant's linked application, its status and any offer (or link form if unlinked) |
| `admissions.pending-documents` | list | `admissions:self:read` | `GET /me/applications` | Documents waiting for verification or rejected, with rejection notes |

`admissions.funnel` is on the Management (VC, Registrar) layout. `admissions.application-status`
and `admissions.pending-documents` are on the Applicant dashboard (`platform/identity/config/dashboards/applicant.yaml`).
Applicants sign in with their identity account, hold `admissions:self:read`, and see their own applications and documents.
