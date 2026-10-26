# notification

**Domain:** platform
**Kind:** platform
**Status:** in progress — backend foundation only (see "What this release does NOT do")

**Email delivery**, plus an in-app inbox, with templates and per-recipient preferences. Replaces the
in-memory `eos_core.notify` stub as the way Education OS tells a person something.

Email is the only channel this release delivers on. SMS, WhatsApp and push are named in the contract so
other modules can be written against them, but **no template declares them and no provider implements
them**, so a request for one is refused — see "Channels" below.

## Architecture

```
caller (HTTP POST /messages, or a service call)
  └─ accept_message   validate -> render once -> record `queued`   (no send, no commit)
       └─ COMMIT      the message row is durable before anything leaves the process
            └─ dispatch   claim (guarded UPDATE, leased, fenced by attempt number)
                 └─ transport   memory | adapter -> OutboundMessaging port -> provider
                      └─ record  sent | failed, provider id or a reason code, event to the outbox
```

Accept, then commit, then send: a message is never sent before the row describing it exists, and a crash
mid-send leaves a row that `recover_stuck()` can re-drive rather than a mail nobody can account for.

**Not outbox-driven yet.** The module publishes its own events to the outbox, but nothing consumes events to
*trigger* a notification, because no relay exists — see "Known dependencies and limitations".

## Channels

| Channel | State in this release |
|---|---|
| `email` | **Delivered.** The only channel that leaves the process |
| `in_app` | **Stored and readable** through `GET /inbox`. Nothing is transmitted |
| `sms`, `whatsapp`, `push` | **Contracted, not implemented.** Refused with 422 |

`NOTIFICATION_CHANNELS_ENABLED` defaults to `email,in_app`. The refusal is structural rather than a
configuration flag: no platform template declares `sms`, `whatsapp` or `push`, so a request naming one is
refused with "channel is not available for this template" before anything is written. The provider registry
has no implementation for them either, so even an enabled channel could not send.

**Known contract/implementation gap, needs a decision (contract owner).** `contracts/openapi.yaml` declares
`enum: [email, sms, whatsapp, push, in_app]` for `Channel`, and `domain/models.py` mirrors it. Three of those
five values cannot be used. Narrowing the enum would be a breaking change to a merged contract and would
contradict issue #79 ("email first, SMS and WhatsApp later"), so the enum is **left as is** and the gap is
documented here instead. **Not changed unilaterally — narrowing a merged contract needs the contract
owner's decision, which has not yet been sought.**

## The four templates issue #79 requires

Platform templates live in code, never in the database: category, placeholders and secret handling decide what
may be stored and overridden, so an organisation cannot edit them. Organisations may override **wording** only.

| Purpose | Key | Variables | Channels | Notes |
|---|---|---|---|---|
| **Verification** | `tenancy.organisation.verify` | `organisation_name`, `token`, `token_id` | email | **Secret-bearing**, not overridable, never in-app |
| **Approval** | `tenancy.organisation.approved` | `organisation_name` | email, in_app | |
| **Trial reminder** | `billing.trial.reminder` | `organisation_name`, `trial_ends_on`, `days_left` | email, in_app | |
| **Invoice** | `billing.invoice.issued` | `organisation_name`, `invoice_number`, `amount`, `due_on` | email, in_app | |

Two more ship alongside: `tenancy.organisation.verified` and `billing.trial.expired`.

All four are covered end to end by `tests/test_required_templates.py`: each sends, renders every supplied
value, refuses a missing variable by name, drops undeclared variables, refuses an oversized or non-scalar
value, and cannot have a newline injected into its subject through a variable. A subject override containing
CR or LF is refused when the template is saved, and a rendered subject is folded to one line whether the break
came from a value or from the override's own text. **Nothing yet calls three of the four** — see the
limitations below.

## What this release provides

| Piece | State |
|---|---|
| Message record (`notification_message`), per organisation, `organisation_id NOT NULL` + RLS policy | built; tested on SQLite **and on PostgreSQL 16.15 with RLS enforced as a non-superuser** |
| Send a message by a direct call or `POST /messages`: validate, render, record `queued`, send once | built |
| Idempotency on `client_token` as the **only** key; an event-linked send derives its token from the event, template, channel and recipient | built (see "Idempotency"); contract awaiting Faizan's approval |
| Secret-bearing templates (verification token): secret rendered in memory, **never stored, logged or published** | built |
| Platform templates in code (verification, approval, trial reminder, trial expired, invoice) + per-organisation overrides | built |
| A message is sent with the wording chosen when it was accepted (template text snapshot, never values) | built |
| Preferences, transactional mail that cannot be switched off, in-app inbox | built |
| Memory transport (dev and tests), refused outside dev mode | built |
| `recover_stuck()` for abandoned messages and due retries, with a bounded recovery-failure policy | built as a **function**, nothing calls it |
| Alembic chain `db/` with RLS, fresh and existing-database paths | built |

## What this release does NOT do

Do not read this module as a finished notification workflow. Missing, and blocking production use:

1. **No real email by default.** `NOTIFICATION_TRANSPORT=memory` sends nothing.
   `NOTIFICATION_TRANSPORT=adapter` now works and hands the message to an installed implementation of the
   OutboundMessaging port — see "The adapter transport" below. Delivery through a commercial relay is still
   unproven; the adapter has only been exercised against MailHog.
2. **No automatic recovery or retries.** A retryable failure leaves the message `queued` with a
   `next_attempt_at`; a crash leaves it `queued` or `sending`. Nothing re-drives it until
   `recover_stuck()` is run, because the scheduler (#82) does not exist. There is no operator route
   to unstick a message (by decision); recovery is internal.
3. **No events consumed.** There is no event consumer mechanism or relay (#83). `accept_message(...,
   source_event_id=..., channel=...)` is the dedupe-safe entry a future handler can call; nothing calls it yet.
   The single-key contract that says how an event-linked send derives its key **is implemented** here, with
   tests, and is documented in [docs/idempotency.md](docs/idempotency.md) — but it is **not yet approved** by
   Faizan, so it may still change. Nothing consumes events regardless.
4. **No tenancy integration.** `platform/tenancy` still calls `eos_core.notify.send_email` before its
   commit (service.py:93 vs :100). Replacing that call, and issuing `client_token` + `secret_ref`, is
   Faizan's change. There is also no route to re-issue an expired verification token.
5. **No audit.** `platform/audit` has no backend. Structured logs (ids only) are **not** durable audit
   records. For that reason **`POST /messages/{id}/resend` is not implemented**: the contract promises
   it is audited.
6. **Quiet hours are stored, not enforced.** Deferring a message needs the scheduler. A future
   `send_after` is rejected (422) for the same reason.
7. **No receipts.** Nothing records `delivered` or `bounced` from a provider (messaging-providers
   webhooks and the consumer are unbuilt), and a hard bounce does not suppress an address yet.
8. **Email and in-app only; no attachments.** SMS, WhatsApp and push are contracted but not
   implemented, and attachments are not supported. All are rejected (422) rather than silently dropped.
9. **No router mounted.** Mounting `eos_notification.api.router` in `apps/backend` is Srujan's change.
10. **Would fail the route-coverage test in PR #214 once mounted.** That test needs every route to name a
    catalogue key that some role grants. `GET/PUT /preferences/{user_id}`, `GET /inbox` and
    `POST /inbox/{id}/read` have no key yet, and no role grants `notification:message:send`. The keys and
    least-privilege grants are proposed in the contract draft, pending Faizan's approval.
11. **Unresolved shared tenant-isolation dependency.** On PostgreSQL, database-level row-level security
    is not currently effective for authenticated requests. A separate, unresolved tenant-isolation dependency exists in shared identity/`eos_core` code. It is outside this module, is not fixed here, and requires restricted coordination with that code's owner.
    **This module does not rely on RLS alone** — every query is filtered by `organisation_id` in code,
    and that filtering is verified on PostgreSQL with row-level security enforced.

### Delivery guarantees (what is and is not claimed)

- Retries are recognised before anything that can change is read (see "Idempotency today").
- `recover_stuck()` handles each message on its own and the sweep always continues (see "Recovery policy").
- At-least-once to the provider. The provider port (`integrations/messaging-providers/contracts/port.yaml`)
  has no idempotency key, so a crash after a provider accepted a message and before it was recorded can
  send a duplicate. **Exactly-once is not claimed.**
- A message is claimed with one guarded `UPDATE` (status + lease); a second worker changes nothing, and a
  worker that outlives its lease cannot overwrite a newer attempt (it is fenced by the attempt number).
- Attempts are bounded by `NOTIFICATION_MAX_ATTEMPTS`; the failure event is published once.
- A secret-bearing message cannot be retried or recovered: its secret was never stored. It is failed
  (`secret_unavailable` if never sent, `outcome_unknown` if a provider call may have succeeded) and the
  sender must issue a new secret with a **new `client_token` and a new `secret_ref`**.

### Idempotency (implemented behaviour)

`client_token` is the **only** idempotency key. The full contract, and the reasoning, is in
[docs/idempotency.md](docs/idempotency.md); it is **awaiting Faizan's approval**, so the rules below may still
change, but the code, the tests and this section already match each other.

- **API and direct calls:** the same token with the same request returns the original (HTTP 200) even if the
  recipient's preferences or account changed since. The same token with a different request is a 422. "Same
  request" compares the template, the requested channel, the template's own category (an explicit category may
  only repeat it), the recipient as given (`user_id`, lower-cased address, locale with blank treated as missing)
  and the non-secret variables as text. An omitted channel and an explicit one are **different requests**,
  because an omitted channel means "let preferences decide".
- **Event-linked messages** (`source_event_id`, only through the service, not the HTTP API): `channel` is
  **required** (422 without it), and the token is **derived**, not supplied:
  `"evt:" + sha256("<event>|<template>|<channel>|<recipient as asked>")`. A caller that supplies a *different*
  `client_token` alongside an event gets a 422. One event still produces one message per channel and per
  recipient.
- **A redelivery whose variables changed is a 422**, not a silent return of the original: same event, same
  template, same recipient but different content means the relay or the producer is broken.
- **`source_event_id` is stored and keeps its unique constraint, as a safety net only.** Nothing reads it to
  decide whether a send is a repeat; it is read only to recover the existing row if that constraint fires.
- **Known limit:** a handler that works out its recipients at handling time (for example "all org admins") can
  send to a newly added member on a redelivery. The fix is a per-handler event receipt keyed
  `(organisation, event, handler)`, deferred to the **#83** handler design review.

### Recovery policy (implemented)

Recovery failures (a bug or a database error while recovering a message, not a provider failure) are counted in
`recovery_failures`, separate from `attempts`, which only counts provider calls. The exception class of the last one
is kept in `last_recovery_error`; its text never is, because it can carry addresses or SQL parameters.

- Each recorded failure defers the message: a queued message by `next_attempt_at`, a sending one by its lease. The
  delay doubles from `NOTIFICATION_RETRY_BACKOFF_S` and is capped at `NOTIFICATION_RECOVERY_MAX_DELAY_S`,
  whose own bounds are in [Retry-delay bounds](#retry-delay-bounds).
- At `NOTIFICATION_RECOVERY_MAX_FAILURES` the message becomes `failed`. Its delivery `last_error` is kept (or set
  to `recovery_exhausted` if it had none), and `notification.message.failed` is published with
  `last_error: "recovery_exhausted"`. The status change and the outbox row are added in one session and committed
  together; `eos_core.events.publish` itself only adds the row and never commits.
- Every recovery write is one `UPDATE` guarded on the status, attempts and recovery-failure count the sweep saw.
  A worker that claimed the message meanwhile, or another worker that already recorded the same failure, makes it
  a no-op, so a failure is counted once and the terminal event is published once.
- Logging: one warning per failure, with the message id and exception class only, so at most
  `NOTIFICATION_RECOVERY_MAX_FAILURES` such warnings per message. If the failure **cannot be recorded** (for
  example the database is unavailable), nothing is counted, the message stays eligible and the next sweep warns
  again: that repetition is bounded only by how often recovery runs and its `limit`, not by the counter.
- Recovery itself is still not triggered by anything (blocker 2).

### Secret-bearing templates (`tenancy.organisation.verify`)

Callers must send `client_token` and a non-secret issuance id (`token_id` for verification) that is
**unique per secret**. A retry (same `client_token`, same `token_id`) returns the original and sends
nothing. The same `client_token` with a different `token_id` is a 422. The service cannot check that a
caller never reuses a `token_id` with a different secret; that is the caller's obligation.

The secret reaches the provider only inside the rendered body, which is the mail itself. It is never put in
the provider `metadata` (the port echoes metadata back on receipts) and is kept out of `repr()` of the
outbound message. Only the in-process memory transport receives it separately (`dev_secrets`), so that
`eos_testing` can read a verification token.

### The adapter transport (packaging and discovery)

`NOTIFICATION_TRANSPORT=adapter` resolves an implementation of the OutboundMessaging port
(`integrations/messaging-providers/contracts/port.yaml`) **by entry point**. This module never imports an
adapter package, which keeps "changing provider is configuration, not code" true and keeps notification inside
its module boundary.

An adapter declares itself in its own `pyproject.toml`:

```toml
[project.entry-points."eos.outbound_messaging"]
messaging-providers = "eos_messaging_providers.application.registry:get_provider"
```

The value is a callable `channel -> provider`, where the provider implements `send`, `capabilities` and
`healthcheck` as `port.yaml` defines them. The name is the **adapter**, not the vendor: which vendor serves a
channel is the adapter's own business (for messaging-providers, `MESSAGING_PROVIDERS_EMAIL`).

**Runtime requirements**, in order of how often they are missed:

1. **The adapter package must be installed in the running environment** — `pip install -e
   integrations/messaging-providers`. Entry points are registered at install time, so editing `pyproject.toml`
   without reinstalling changes nothing.
2. **`NOTIFICATION_ADAPTER` must name it**, matching the entry-point name exactly. Default
   `messaging-providers`.
3. **`apps/backend` must depend on the adapter package** for it to be installed in the deployed app (Srujan).

Every failure is a **503 raised before a message row is written**, never a silent fallback:

| Situation | Result |
|---|---|
| `NOTIFICATION_ADAPTER` empty | 503, "no messaging adapter configured" |
| nothing installed in the group | 503, "none installed" |
| name not among those installed | 503, listing what *is* installed |
| two distributions claim one name | 503, refuses to guess which |
| entry point fails to import | 503, and the import error's text is **not** echoed to the caller |

`reply_to` is passed **only** when the provider advertises `supports_reply_to` and an address is configured;
otherwise the argument is omitted entirely rather than passed as `None`, so an adapter written before
`reply_to` existed keeps working. `dev_secrets` has no counterpart in the port and is never forwarded: the
fields are mapped one by one and the message object is never serialised whole.

## Public surface

- API: [contracts/openapi.yaml](contracts/openapi.yaml) (0.1.0, merged). The code presents the internal
  `sent` status as `sending` until the contract change adding `sent` is approved
  (`api/schemas.py: EXPOSE_SENT_STATUS`).
- Events: [contracts/events.yaml](contracts/events.yaml). Published here: `notification.message.sent|failed`,
  `notification.preferences.changed`. `bounced` is not published (no receipts).
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml). No role in the merged catalogue holds
  `notification:message:send`, so no person can call `POST /messages` until a grant is approved.

## Configuration

See [config/env.example](config/env.example). `NOTIFICATION_TRANSPORT=memory` is refused unless
`EOS_DEV_MODE` is true, and `EOS_DEV_MODE` defaults to true when unset, so production must set it to
false explicitly.

### Retry-delay bounds

`NOTIFICATION_RECOVERY_MAX_DELAY_S` has a valid range of **1 to 86,400 seconds (24 hours)**, default 3,600.

| Configured | Effective | What an operator sees |
|---|---|---|
| unset, or unparseable | 3,600 | nothing; the default applies |
| 1 – 86,400 | as given | nothing |
| above 86,400 | **86,400** | the value is reduced, and the first out-of-range value for this setting is logged once |
| 0 or negative | **1** | same |

`NOTIFICATION_SENDING_LEASE_S` (default 120) carries its own `1..86,400` range, for a different reason: it is
added to the clock when a message is claimed and subtracted from it when recovery sweeps, with no cap in
between, so an unbounded value raises mid-claim rather than merely scheduling a silly retry. Its ceiling is a
separate constant (`MAX_SENDING_LEASE_S`) that happens to hold the same number, because a lease is not a retry
delay and the recovery policy should not decide it.

**The lease's lower bound is the part that matters, and this module cannot enforce it.** A lease must outlast
the whole provider call, or a send still in flight loses its claim and recovery dispatches it a second time.
`MESSAGING_PROVIDERS_SMTP_TIMEOUT_S` (default 10) is a **socket** timeout applied to each blocking operation,
and one SMTP send performs roughly ten of them — connect, EHLO, STARTTLS, EHLO, AUTH, MAIL FROM, RCPT TO,
DATA, body, QUIT — so the worst case is about **ten times** the timeout, roughly 100s against a 120s lease.
That margin is thin, and raising the provider timeout breaks the relationship silently: the two settings live
in different modules, notification must not import the adapter (the port is resolved by entry point), and
nothing correlates them. **Raise the lease whenever you raise the provider timeout.** Today the consequence is
latent rather than live, because nothing triggers `recover_stuck` in this release (**#82**) and the default
transport is `memory`.

The 24-hour figure is an **operational ceiling on one configured delay**, not a promise that every message is
delivered within a day: `NOTIFICATION_MAX_ATTEMPTS` still bounds the attempts, and a message that exhausts
them becomes `failed`. The ceiling is enforced because this value is also the only bound on a provider's own
`retry_after` hint. Left unbounded, a hostile hint would push `next_attempt_at` past the end of the calendar,
and that overflow is raised *after* the message has been claimed — stranding it in `sending` until recovery
finds it. `NOTIFICATION_RETRY_BACKOFF_S` is likewise never negative; zero is allowed and means "retry on the
next sweep".

The bounds are enforced on the configuration object itself, not only when it is read from the environment, so
a caller that constructs a `NotificationConfig` directly — the scheduler in **#82**, the relay in **#83** —
gets the same guarantees. Out-of-range **integers** are clamped; a bool, string or float for an integer
setting is a caller bug rather than operator error, and raises a field-specific `TypeError` instead of being
coerced. `True` in particular is never accepted as `1`.

## Database and deployment order

Schema changes are an Alembic chain in [db/](db/) (own version table `notification_alembic_version`):

```
cd platform/notification/db && alembic upgrade head          # fresh database
```

`apps/backend` still runs `init_db()` (`create_all`) at startup for every model it has imported, and
`create_all` neither alters existing tables nor records an Alembic version. So **the order matters**:

1. Merge this module and its chain. Do **not** mount the router yet.
2. On each environment run `alembic upgrade head` for notification.
3. Check `alembic current` is `notification_0001` and that the schema matches the models.
4. Only then merge the router mount (Srujan). After it, every schema change is a new revision.

If the tables already exist (the router was mounted first and `init_db()` created them), do **not** run
`upgrade` (it fails with "already exists") and do **not** stamp blindly: first verify the live schema
equals the models (the compare used in `test_notification_migrations.py`), and only then
`alembic stamp head`. A database that has drifted must not be stamped.

## Tests

```
. .venv/bin/activate
python -m pytest platform/notification/backend/tests -q
tools/scripts/precheck.sh
```

These run on SQLite by default and import only `eos_core`, `eos_identity` (a declared dependency),
`eos_testing` and this module. They pass on Python 3.13 and 3.12. On SQLite alone they **are not evidence of
row-level security, of real concurrency, or of transaction rollback**: with the SQLite driver's default
settings (`eos_core.db`), a savepoint opened after only a read is not inside a transaction and its release
commits, so code here never relies on a rollback to undo a write (the transport check runs before the insert).

### The same suite on PostgreSQL

The whole suite also runs against PostgreSQL, with row-level security enforced, as a role that is neither a
superuser nor `BYPASSRLS` — so it exercises the **service**, not only the schema. Passing on
PostgreSQL 16.15 (14 Oct 2026).

```
docker run -d --name eos-pg -e POSTGRES_PASSWORD=pg -p 5433:5432 postgres:16
docker exec eos-pg psql -U postgres \
  -c "CREATE ROLE eos_app LOGIN PASSWORD 'eos_app_test' NOSUPERUSER NOBYPASSRLS" \
  -c "CREATE DATABASE eos_nsuite OWNER eos_app"
cd platform/notification/backend
NOTIFICATION_PG_SUITE_URL=postgresql+psycopg://eos_app:eos_app_test@localhost:5433/eos_nsuite \
  python -m pytest tests -q --ignore=tests/test_postgres.py
```

Opt-in on purpose, and refused for any database not named `eos_nsuite`: these tests delete rows between tests
and `EOS_DATABASE_URL` may point somewhere real. Running this way found two things SQLite hid — a replay
returning an ORM object with every attribute expired (fixed in `send_message`), and test fixtures writing rows
with no tenant scope, which RLS correctly refuses.

### PostgreSQL tests: RUN, on PostgreSQL 16.15

`backend/tests/test_postgres.py`: **16 passed** on PostgreSQL 16.15 (Docker, local).
They skip unless `EOS_PG_ADMIN_URL` is set, and **no CI job runs them yet** (Srujan).

    docker run -d --name eos-pg -e POSTGRES_PASSWORD=pg -p 5433:5432 postgres:16
    EOS_PG_ADMIN_URL=postgresql+psycopg://postgres:pg@localhost:5433/postgres pytest tests/test_postgres.py -q

The file creates the two databases (`eos_nmig`, `eos_ntest`) and an `eos_app` role that is explicitly
`NOSUPERUSER NOBYPASSRLS`, and asserts that before anything else — a superuser passes every RLS check
vacuously. The admin URL is used only for that setup; every assertion runs as `eos_app`.

What the file covers, and what it does not: it verifies what the **database** guarantees (schema, policies,
cross-tenant reads and writes, the bypass, per-tenant uniqueness, two-connection races, column lengths,
savepoint rollback) through real connections and real SQL — all of that now **passes**. It does **not**
exercise the service layer against PostgreSQL; that needs the application bound to a PostgreSQL engine and is
still outstanding, as is the same check driven through HTTP.

#### Unresolved: shared tenant-isolation dependency

Database-level row-level security is not currently effective for authenticated requests on PostgreSQL.
A separate, unresolved tenant-isolation dependency exists in shared identity/`eos_core` code. It is outside this module, is not fixed here, and requires restricted coordination with that code's owner. Details are deliberately not reproduced here. The original list:

- RLS enabled and forced, `tenant_isolation` policy present on all three tables.
- Cross-tenant read and write, including `WITH CHECK` and an `UPDATE` that tries to change `organisation_id`.
- No-organisation context sees nothing; an insert with `''` or NULL is rejected.
- Tenant switching: a new transaction sees only the new organisation; a switch inside an open transaction
  does not change visibility (the setting is applied once per transaction); pooled connections do not leak it.
- Per-tenant uniqueness of `client_token` and the event key.
- Two real connections claiming one message: exactly one wins.
- Two racing inserts of the same event: one row.
- `String(36)` length enforcement (SQLite does not enforce lengths).
- Two real connections recording the same recovery failure, or both reaching the limit: one increment, one
  terminal outbox row; and that the terminal status change and its outbox row commit or roll back together.
- Through HTTP, not only the service: that a cross-tenant read through `GET /messages` returns nothing
  even if the code filter were removed.
- That an `accept_message` followed by a rollback leaves no row (savepoint inside a real transaction).

## Known dependencies and limitations

What #79 cannot finish inside this module, with the owner and the smallest change needed:

| Blocker | Owner | Smallest change | #79 criterion affected |
|---|---|---|---|
| **No outbox relay.** `packages/core` writes `outbox_event` rows and nothing anywhere sets `published = true`; `platform/event-bus/` has **0 Python files**. So no event can *trigger* a notification, and approval, trial-reminder and invoice mails have no caller. | Himanshu, **issue #83** | the relay itself — a separate issue, deliberately not built here | **outbox-driven**, "visible on staging" |
| **No scheduler**, so nothing calls `recover_stuck()` and nothing emits trial reminders. `platform/scheduler/` has 0 Python files. | Himanshu, **issue #82** | the scheduler itself | retries in practice |
| **Adapter not installed in the deployed app.** Entry points register at *install* time. `apps/backend/pyproject.toml` lists neither `eos-notification` nor `eos-messaging-providers`, and `py-setup.sh` installs neither — so in CI and staging the group is empty and the adapter transport is a 503. | **Srujan** | add both to `apps/backend` dependencies and `py-setup.sh` | delivery, staging |
| **Router not mounted.** `PLATFORM_ROUTERS` in `apps/backend/src/eos_backend/main.py` lists identity, tenancy, billing only. | **Srujan** | add notification, **after** `alembic upgrade head` | staging |
| **No migration runs** in CI or any deploy script. | **Srujan** | `cd platform/notification/db && alembic upgrade head` before start | staging |
| **Tenancy still calls the stub.** `platform/tenancy/.../service.py:93` calls `eos_core.notify.send_email`, before its own commit at line 100. | **Faizan** | replace with a notification send carrying `client_token` and `token_id` | **replace `eos_core.notify`** |
| **`eos_testing` reads `notify.sent`.** `packages/testing/.../tenancy.py:31` pulls the verification token out of the stub, so the stub cannot be deleted without breaking every module's `register_and_login`. | **Srujan** | read the token from the notification inbox or the API instead | **replace `eos_core.notify`** |
| **No role grants any notification permission.** Real users receive only `org-admin` or `super-admin`; `permissions_for(["org-admin"])` returns no notification keys, and `notification:message:send` is granted by no role at all. The six administrative routes are unreachable. | **Faizan** (B3) | grant the keys to `org-admin`; give `message:send` a service-only holder | tested/usable |
| **Unresolved shared tenant-isolation dependency** (outside this module; requires restricted coordination with that code's owner). | **Faizan** | shared-code fix | tenant isolation |
| **`check-boundaries.py` ignores `depends_on.integrations`.** Worked around by entry-point discovery; blocks any module that imports an integration directly. | **Srujan/Faizan** | read that manifest key too | — |

Also incomplete by decision, not blockage: channels beyond email and in-app are contracted but not
implemented (422, not silently dropped); no attachments; no provider receipts, so nothing records
`delivered`/`bounced` and a hard bounce does not suppress an address; no resend route until audit (#81)
exists; quiet hours stored but not enforced.

## Layout

| Path | Purpose |
|---|---|
| `docs/` | PRD, user stories, data model, screen list |
| `contracts/` | OpenAPI, event schemas, permission catalogue |
| `backend/` | `domain/` models and errors, `application/` services, `infrastructure/` config, templates, transport, `api/` router |
| `frontend/` | Pages, components, API client + tests |
| `mobile/` | Mobile screens (optional) |
| `db/` | Alembic chain (own tables, own version table) |
| `config/` | `env.example`, feature flags |
| `tests/e2e` | End-to-end tests runnable in isolation |

## Dependencies

See `module.yaml`. This module must not import code from any other module under `modules/`. It imports
`eos_core`, `eos_identity` (recipient lookup and route guards) and, in tests, `eos_testing`.

Importing `eos_identity` directly, instead of through `packages/sdk`, departs from module-standard rule 4
(`docs/architecture/module-standard.md`). `packages/sdk` is not installable yet, so `eos-sdk` was replaced by
`eos-identity` in `backend/pyproject.toml`. This needs a written exception from the architecture lead and is
**pending**; the module stays `portable: false`.

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../docs/architecture/module-standard.md#portability-checklist).
