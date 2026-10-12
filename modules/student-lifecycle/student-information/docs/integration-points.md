# student-information — integration points

## Events published (contracts/events.yaml)

| Event | Likely consumers |
|---|---|
| `student-information.person.created` | Any module that caches a person's name/status against its own `person_id` reference once that reference starts being used (e.g. academics, finance-operations, campus-life — as their own contracts are written) |
| `student-information.person.updated` | Same consumers, to refresh cached name/contact fields |
| `student-information.person.status-changed` | Modules that gate behaviour on status (e.g. library loans, hostel allocation, fee waivers for withdrawn students) |
| `student-information.id-card.issued` / `.revoked` | `platform/notification` (card ready/revoked email), facilities access-control integrations, if/when they exist |

No consumer is hard-coded or assumed in this module's code or contracts; `module.yaml`'s
`consumes_events` for *other* modules is each consuming module's own declaration, not something
this module controls.

## Events consumed

None in this release. `module.yaml`'s `consumes_events: []` stays empty. Person records are
created directly by an authorised staff action (`POST /people`), not as a reaction to another
module's event — including `admissions`' application-accepted outcome, which (once admissions'
contract exists) is expected to be a staff-driven API call from an admissions user with the
`student-information:person:write` permission, not an automatic event subscription.

## Platform services used (via packages/sdk)

| Service | Use |
|---|---|
| `platform/identity` | Permission checks (`student-information:*` keys); optional link to a user account via `identity_user_id` |
| `platform/documents` | Storage for identity documents and generated ID card artifacts; this module stores only `document_id` references |
| `platform/audit` | Every create, update, status change, document action and card issue/revoke is audited |

## Cross-module API dependencies

None required to publish this module's own contract. This module does not call any other
module's API in this release, and no other module's published, reviewed contract currently
requires a synchronous call to this module either.

## Known future integration (not a dependency today)

`modules/student-lifecycle/admissions` is expected to call `POST /people` on this module once an
application is accepted, passing a `source` reference back to the application. As of this
writing, `admissions/contracts/openapi.yaml` does not yet exist as a reviewed contract, so this is
documented here as a forward-looking integration note, not implemented as a dependency
(`module.yaml`'s `depends_on` lists only `platform: [identity, audit]`, plus `documents` via the
SDK — no module-to-module dependency is declared).
