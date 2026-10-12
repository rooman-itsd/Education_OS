# web-portal-cms — integration points

## Events published (contracts/events.yaml)

| Event | Known/likely consumers |
|---|---|
| `web-portal-cms.page.published` / `.unpublished` | None required this week |
| `web-portal-cms.announcement.published` / `.unpublished` | Potentially surfaces to the `web-portal-cms.announcements` dashboard widget (already listed on the Applicant dashboard), though that widget reads live via the API rather than subscribing to this event |

## Events consumed

None. `module.yaml`'s `consumes_events: []` stays empty.

## Platform services used (via packages/sdk)

| Service | Use |
|---|---|
| `platform/audit` | Page/announcement publish, unpublish, create, update and delete are audited |
| `platform/notification` (not yet contracted) | Expected, once it exists, to send the sign-up verification email — sent by `platform/tenancy` as part of its own registration flow, not by this module |

## Cross-module API dependencies (frontend composition, not backend-to-backend)

This module's **frontend** calls two other modules' already-public endpoints directly to render
and submit the sign-up page. This is not a backend dependency of web-portal-cms's own API (its
`module.yaml` `depends_on` is unchanged — `platform: [identity, audit]`); it is the same kind of
composition `apps/frontend` already does across modules generally (ARCHITECTURE.md: "Access
channels ... Thin shells that compose module UIs").

| Call | Owner | Already public? |
|---|---|---|
| `GET /plans` | `platform/billing` | Yes (`security: []` in its existing contract) |
| `GET /academy-types` | `platform/tenancy` | Yes (`security: []` in its existing contract) |
| `POST /register` | `platform/tenancy` | Yes (`security: []` in its existing contract) |
| `POST /register/verify` | `platform/tenancy` | Yes (`security: []` in its existing contract) |

No change was made to either `platform/billing/contracts/openapi.yaml` or
`platform/tenancy/contracts/openapi.yaml` to support this — all four endpoints already existed,
already public, before this module's Week 1 work began.

## Explicitly not integrated

`student-information` and `admissions`: no call, no event, no shared id, in either direction.
Organisation sign-up is a different business process from both becoming a student and applying
for admission, and this module's contracts make no reference to either.
