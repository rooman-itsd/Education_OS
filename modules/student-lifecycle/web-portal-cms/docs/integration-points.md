# web-portal-cms — integration points

Envelope rule: `organisation_id`, `actor` and `occurred_at` travel on the event envelope
(`platform/event-bus/contracts/events.yaml`), never in a payload.

## Events published (contracts/events.yaml)

| Event | Consumers |
|---|---|
| `web-portal-cms.page.published` / `.unpublished` | none required yet |
| `web-portal-cms.announcement.published` / `.unpublished` | none required yet; `platform/notification` could alert members once it consumes events. The widget reads the API live and does not subscribe |

## Events consumed

None. `module.yaml`'s `consumes_events` stays empty.

## Platform services

| Service | Use |
|---|---|
| `platform/identity` | Every organisation user holds the implicit `member` role (declared in `platform/tenancy/contracts/permissions.yaml`); this module grants it the two read keys and adds it in its own auth dependency, as identity does |
| `platform/audit` | Every CMS change; written to this module's `audit_entry` table until audit has a service |

## Frontend composition (the sign-up pages, built)

The public sign-up pages call two platform services' already-public endpoints directly. This is not a backend
dependency of web-portal-cms's API; neither contract was modified.

| Call | Owner | Public by its own contract |
|---|---|---|
| `GET /plans` | `platform/billing` | yes |
| `GET /academy-types` | `platform/tenancy` | yes |
| `POST /register` | `platform/tenancy` | yes |
| `POST /register/verify` | `platform/tenancy` | yes |

## What the host must provide

Registration in both `modules.enabled.yaml` files. For anonymous reads later (PRD §11 D1): the gateway letting
`/api/v1/web-portal-cms/public/{org_slug}/*` through after resolving the slug, the same request already open for
admissions.

## Explicitly not integrated

`student-information` and `admissions`: no call, no event, no shared id, in either direction.
