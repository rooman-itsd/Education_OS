# Personal-data breach

Use this when personal data may have been seen, copied, changed, lost or made unavailable by someone who should not
have had that access, or by a fault. Suspected is enough: you start the clock on suspicion and stop it only with a
written reason. This is the legal side of a security incident; the technical side of each step is in the other
runbooks, linked below, and not repeated here.

**Not legal advice.** Every deadline, form and duty marked **(confirm with counsel)** is our reading of the Digital
Personal Data Protection Act, 2023 (the Act) and the Digital Personal Data Protection Rules, 2025 (the Rules), and
counsel has not reviewed it (DPDP gap D22, issue #148). Counsel's answers go in this file in a pull request.

**Who decides:** the lead (Faizan) decides whether to notify, and signs every notice. In his absence the Grievance
Officer decides. Nobody else sends anything to the Board, to an institution or to a person.

## The first hour (checklist for use under pressure)

1. **Write the time down, in UTC**, and keep a log from now on (section 3, "The incident log"). The 72 hours start
   when you became aware of the breach **(confirm with counsel)**.
2. **Call the incident lead and Faizan.** Severity 1 in [on-call.md](on-call.md). Name the incident lead in the team
   channel (section 1).
3. **Preserve first, then change things** (section 4): snapshot the database and copy the logs. Five minutes now
   saves the investigation.
4. **Contain** (section 5), the smallest step that stops it: one organisation, one user, one secret, then wider.
5. **Do not delete, purge or "tidy up"** anything: no prune, no restore over live data, no log truncation.
6. **Assess** (section 6): what data, whose, how many, which organisations, any children.
7. **Tell the institutions at once** if their data is involved (section 7.1). Do not wait for the full picture.
8. **Faizan decides on the Board and the people affected** (section 7), with counsel if reachable.
9. **Within 72 hours**, the detailed report to the Board **(confirm with counsel)** (section 7.2).
10. **Within two working days of containment**, the review (section 8).

## 0. What the law asks, in short

| Duty | Source | What it means for us |
|---|---|---|
| Intimate the Data Protection Board of India and each affected Data Principal of a personal data breach | Act s.8(6); Rules **(confirm with counsel: rule number, form and manner)** | Without delay, once we are aware. The Rules prescribe the content of both notices |
| Detailed report to the Board | Rules **(confirm with counsel)** | Within 72 hours of becoming aware, or a longer time the Board allows on request. The fields are in section 7.2 |
| Reasonable security safeguards | Act s.8(5) | The October [security review](../../docs/architecture/security-review-2026-10.md) is our record of them |
| Keep logs and the record of the breach | Rules **(confirm with counsel: period; the DPDP pass notes at least one year for some purposes)** | Section 8 |

**A personal data breach** is any unauthorised processing, or accidental disclosure, acquisition, sharing, use,
alteration, destruction or loss of access to personal data, that compromises its confidentiality, integrity or
availability **(confirm with counsel)**. A lost backup, a wrong email sent to the wrong people, an organisation
that could see another's rows and a stolen laptop with a token on it are all breaches. A failed attack that
reached no personal data is an incident, not a breach: log it and stop.

**Who is the Data Fiduciary.** It decides who must notify whom (the DPDP pass report, section 1, and section 5 of the
draft terms, #667):

| Data involved | Data Fiduciary | Education OS operator | So |
|---|---|---|---|
| What an institution keeps about its students, applicants, staff, parents, alumni, vendors, complainants and visitors (every feature module) | The institution | Data Processor | **Tell the institution at once.** It decides about and carries out the notice to the Board and to its people; we give it everything it needs to do so, in time. The terms ask the processor to inform the institution without undue delay |
| The organisation's account: its record, the first administrator's name, email and password hash, the consent record, the registration token | The operator | Data Fiduciary | We notify the Board and the people ourselves |
| Billing: subscription, GST invoices (recipient legal name, GSTIN, address), payment references | The operator | Data Fiduciary | The same |
| Platform emails, audit trail, event outbox, web server access logs | The operator for the platform's own purposes; the institution for the content | Fiduciary for the logs, Processor for the content | Treat as institution data when the content is the institution's, as ours when it is a log of who did what |

A breach often touches both: one stolen database dump holds both institution data and our account data. Notify
each Fiduciary for what is theirs. Whether we also report to the Board for institution data, as a courtesy or as
the terms require, is for counsel **(confirm with counsel)**.

## 1. Roles

| Role | Who | What they do |
|---|---|---|
| Incident lead | The on-call primary ([on-call.md](on-call.md): Srujan, then Himanshu), unless the lead names someone | Runs the technical response: preserve, contain, assess; keeps the incident log; reports to Faizan every hour |
| Decision maker | Faizan (lead) | Decides on notifying, on suspending a tenant, on taking the API offline, and signs the notices |
| Grievance Officer | `[Grievance Officer name, email]` (the same placeholder the DPDP pass report and the privacy notice use; Faizan to fill) | The contact the Board and the people affected write to; sends the notices to the people; keeps the record of requests that follow |
| Comms owner | Faizan, or whoever he names in writing | Writes and sends the notices; is the only voice to institutions and the public; answers press and social media with the approved text only |
| Institution's contact | The administrator the institution named at registration (`tenancy` organisation record; the first administrator's email) | Receives section 7.1 at once; tells us whom it wants for its own Board and people notices |
| Counsel | `[Counsel name, contact]` (Faizan to fill) | Confirms the **(confirm with counsel)** points before a notice goes, as far as time allows |

If the incident lead is the person who caused or may have caused the breach, someone else leads.

## 2. Detect: where a breach shows itself

Only what exists in this stack. Read these before you assume what happened.

| Source | What it shows | Where |
|---|---|---|
| The audit trail (`platform/audit`) | Who changed what, per organisation: tenancy lifecycle and super admin operations, identity users, billing, workflow decisions, documents, report runs and exports. Super admin operations also get a platform-level record, and a super admin reading across organisations is itself recorded. **Impersonation is a super admin action and is recorded.** It records changes, not reads: a stolen read is not in it | `GET /api/v1/audit/records` (filters in `platform/audit/contracts/openapi.yaml`); a super admin with `platform:audit:read` reads platform-level records, or one organisation's with `organisation_id`; `GET /api/v1/audit/entities/{type}/{id}/history`; the dashboard widgets `audit.recent-activity` and `audit.super-admin-actions` |
| API logs, one JSON line per request | `timestamp`, `request_id`, `organisation_id` (only from a verified token), `method`, `module`, `route`, `path` without the query string, `status`, `duration_ms`. A burst of `401` on `auth/login`, of `403`, of `404` on ids, or of one organisation's traffic at night is the usual trace. **No client IP and no user id are logged** | `$C logs --timestamps api`; `apps/backend/src/eos_backend/observability.py`; `apps/backend/README.md` ("Logs and errors") |
| Rate-limit refusals | `429` lines in the same log, by route. The limits are per IP, per user, per organisation, and tighter for `auth` and `login` (`infra/docker/.env.api.example`). Failed sign-ins are not recorded as events: they show only as `401` lines on the login route | The same log |
| `eos-monitor` (`infra/monitoring`) | Alerts on `errors` (5xx), `slow`, `containers`, `backup`, `disk`, `health`. It sees outages and floods, not data theft; alerts carry counts and paths, never log lines | `journalctl -t eos-monitor -g ALERT`; [on-call.md](on-call.md); `../monitoring/README.md` |
| Sentry (backend only, when `EOS_SENTRY_DSN` is set) | Unhandled errors with organisation and request ids, no personal data | The Sentry project |
| The event outbox and dead letters (`platform/event-bus`) | Every domain event, with its organisation; an event that failed all its attempts is dead-lettered. A dead letter for a consumer that mails or exports is worth reading. The outbox keeps 30 days (`EVENT_BUS_RETENTION_DAYS`) | `GET /api/v1/event-bus/events?state=dead_lettered`, `?name=<prefix>*`, `occurred_from`, `occurred_to` (a super admin with `platform:event-bus:admin` may pass `organisation_id`) |
| Scheduler runs | Which jobs ran and failed, and when | `GET /api/v1/scheduler/runs` |
| Backups | The nightly dumps in `/var/backups/eos/daily`: a comparison point for what the data looked like before | `../backup-dr/README.md`; [restore.md](restore.md) |
| Web server access logs | Client IPs and paths on the reverse proxy (`/var/log/nginx/educationos.access.log`, from `infra/docker/nginx.public-vhost.conf`). The only place client IPs are recorded. Rotation is not recorded in the repository (DPDP gap D23): check what is left before you rely on it | The proxy container |
| Reports from outside | A user, an institution, a researcher or the press writes in | The Grievance Officer's mailbox; the team channel. Treat a credible report as a detection and start the clock |

## 3. Declare, and keep the log

When you cannot rule a breach out within about an hour, **declare it**: tell Faizan, name the incident lead in the
team channel, and open the log.

**The incident log.** One private issue labelled `incident` and `security` in the repository, or, if the incident
may be public by that route, a document in the team's password manager's notes; ask Faizan. Never put personal data
or secrets in it. Each entry is: **the time in UTC** (`date -u +%Y-%m-%dT%H:%MZ`), who, what was seen or done, and the
command or screen. Include the moment you first became aware, the moment you declared, and every decision with who
made it.

## 4. Preserve the evidence first

Do this before containing, unless the data is leaving right now (then contain first and write why in the log).

```
cd /opt/education-os
C="docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api"
INC=/root/incident-$(date -u +%Y%m%dT%H%MZ); mkdir -p "$INC" && chmod 700 "$INC"; echo "$INC"
date -u > "$INC/started-utc.txt"
```

1. **A database snapshot, so the state at the time is kept.** Do not start a restore over the live database.
   ```
   systemctl start eos-db-backup.service; journalctl -u eos-db-backup.service -n 5 --no-pager
   cp -a /var/backups/eos/daily/$(ls -1 /var/backups/eos/daily | tail -1) "$INC/"
   ```
   The log ends in `ok`. The copy is kept for the review; keep older dumps from before the incident too (do not let
   the retention remove them: copy the oldest one that is plausibly clean).
2. **The logs.** Docker's logs are rotated and the oldest lines go; copy them now.
   ```
   for s in api relay scheduler db keycloak; do $C logs --no-color --timestamps $s > "$INC/$s.log" 2>&1; done
   journalctl --since "7 days ago" --no-pager > "$INC/journal.txt"
   cp /var/log/nginx/educationos.access.log* "$INC/" 2>/dev/null   # on the proxy container, if you have it
   ```
3. **The audit trail**, exported by its read route for the window you care about, per organisation, and the
   platform-level records (a super admin signs in as in [suspend-a-tenant.md](suspend-a-tenant.md)); the
   audit export route in the contract (`POST /api/v1/audit/records/export`) is for institutions' compliance exports, so
   check that it is live before you rely on it. Its own export is audited.
   ```
   curl -s -H "Authorization: Bearer $TOKEN" \
     "$BASE/audit/records?occurred_from=2026-11-01T00:00:00Z&limit=200" > "$INC/audit-platform.json"
   ```
   The audit table cannot be edited or deleted by the API's role (`platform/audit/README.md`), so it is itself
   evidence; the pruning job is paused below.
4. **The outbox**: `GET $BASE/event-bus/events?occurred_from=...` into the folder, dead letters included.
5. **A fingerprint, so you can show nothing changed after.** `sha256sum "$INC"/* > "$INC/SHA256SUMS"`, then copy the
   whole folder off the host (to the offsite backup location, by the same route as the backups) and record in the log
   who copied it, when, and to where. That is the chain of custody: write who held the evidence at each step.
6. **Pause what deletes.**
   - `audit.prune` (daily, 02:30 UTC, scheduler): the audit window is 7 years and the floor is 2555 days, so a
     routine run deletes nothing recent, but pause it for certainty: `AUDIT_RETENTION_ENABLED=false` in
     `infra/docker/.env.api`, then `$C up -d scheduler api`. Or disable its schedule: `PATCH $BASE/scheduler/schedules/{id}`
     with `{"enabled": false}` (find the id with `GET $BASE/scheduler/schedules`).
   - Outbox pruning runs in the relay and has no switch: set `EVENT_BUS_RETENTION_DAYS=3650` (its maximum) in
     `infra/docker/.env.api` and `$C up -d relay`. Dead-lettered and pending events are never pruned.
   - The scheduler's run history is pruned after `SCHEDULER_RUN_RETENTION_DAYS` (90): raise it the same way if the
     incident is older than that.
   - Notification history pruning (`NOTIFICATION_HISTORY_RETENTION_DAYS`) is not implemented yet (DPDP gap D14); if it
     has since been added, pause it here.
   - Do not run an organisation purge or a deletion request for an affected organisation: the 30-day hold stays.
   - Do not rotate the Docker log files by hand, and do not `docker compose down -v` (it deletes `eos-pgdata`,
     `eos-kcdata` and `eos-hub-secrets`).
7. Write it all in the log, in UTC, with the folder name.

## 5. Contain

Take the smallest step that stops the exposure, check it, then go wider only if you must. Each step is a decision;
write it in the log. Keep the commands in the runbooks they come from.

| Situation | Step | How |
|---|---|---|
| One organisation is the source or the victim | Suspend it: nobody of it can sign in, and signed-in users are refused at once | [suspend-a-tenant.md](suspend-a-tenant.md) (the lead decides; for a leak between organisations, suspend first and tell him straight after) |
| A person's account is taken over, or a staff member must lose access | End their sessions and block the account | **Keycloak (when `COMPOSE_PROFILES=oidc` is on):** in the organisation's realm, Users, the person, Sessions, "Sign out", then set the user disabled (admin console, on the LAN only: the public proxy answers `/auth/admin/` only from the LAN, `infra/docker/nginx.public-vhost.conf`); realm setup is `tools/scripts/keycloak-realm.sh` and `platform/identity/README.md`. **Platform tokens** last `EOS_JWT_TTL_MINUTES` (12 hours by default) and cannot be revoked one by one: to end them, rotate `EOS_JWT_SECRET` (next row). **Disable the identity user:** once the identity PR that adds `POST /api/v1/identity/users/{id}/disable` is merged, use it; until then identity has no route to disable a user (DPDP gap D10), so suspend the organisation if the account cannot wait |
| A token or the signing secret may be stolen, or any token may be forged | Rotate `EOS_JWT_SECRET`: every platform token stops working and every user is signed out | [rotate-secrets.md](rotate-secrets.md) section 1. In a leak, do it at once, not after hours. Super admin impersonation tokens die with it |
| The database login may be stolen | Rotate `EOS_APP_DB_PASSWORD` (the API's role `eos_app`, which cannot bypass row-level security) and, if the owner may be exposed, `EOS_DB_PASSWORD` (role `eos`, which can) | [rotate-secrets.md](rotate-secrets.md) sections 2 and 3. As the owner role, to stop `eos_app` at once while you work: `$C exec -T db psql -U eos -d eos -c "ALTER ROLE eos_app NOLOGIN"` (the API then cannot read the database; `infra/docker/db-roles.py` sets `LOGIN` again on the next deploy, so run no deploy until you mean it). Never grant `BYPASSRLS` or superuser to anyone to investigate: use the owner role on the host |
| Stored integration credentials (SBIePay, messaging providers, DigiLocker, video conferencing and so on) may be exposed, or the secret store volume was copied | Rotate the integration-hub key-encryption key (KEK), **and** rotate the credentials themselves at each provider: a new KEK protects what is stored from now, not what a thief already holds | `platform/integration-hub/README.md`, "Rotating the key": new `INTEGRATION_HUB_SECRET_KEK`, the old one in `INTEGRATION_HUB_SECRET_KEK_PREVIOUS`, restart, run `python -m eos_integration_hub.rotate_kek` once in the API's environment, and keep the previous key until it prints `"unreadable": 0`. Then change each provider's own key or password (SMTP: [rotate-secrets.md](rotate-secrets.md) section 4). The secret store is the volume `eos-hub-secrets`, outside the database and its backups |
| Other secrets (SMTP, Sentry DSN, alert bot, offsite backup key, Proxmox access) | Rotate | [rotate-secrets.md](rotate-secrets.md) sections 4 to 8 |
| Abusive traffic or one source address | Block it at the reverse proxy: add `deny <address>;` (or a `return 403;`) in the `location /api/` block of the public vhost, then `nginx -t && systemctl reload nginx` in the proxy container | `infra/docker/nginx.public-vhost.conf`. The API rate limits (`EOS_RATE_LIMIT_*`) already slow guessing; do not switch them off during an incident |
| The data is still leaving, the cause is unknown, or you cannot tell what is happening | Take the API offline: the site's static pages stay up, nothing reads the database | `$C stop api relay scheduler` (the database stays up, and Keycloak with it: stop `keycloak` too if its realm is involved). Faizan decides. Say so on the site's status channel in plain words. To return: `$C up -d`, after the cause is closed |
| The host cannot be trusted | Rebuild | `../backup-dr/DR.md`; take the evidence first (section 4) |

After each step: confirm it worked as the runbook says, and note the time. Containment is not the end: the way in
must be closed (a patched bug, a rotated secret, a removed key), or it will happen again.

## 6. Assess

Within the first day, and updated as you learn more. Write the answers in the log; the notices in section 7 are made
of them. **Say "unknown" where it is unknown**; do not guess in a notice.

1. **What happened and since when.** First and last time the unauthorised access or loss could have happened, in
   UTC. The audit trail, the `request` lines and the access logs set the window.
2. **Which data.** From the DPDP pass report's data map (section 3) for the modules involved: names, contact details,
   date of birth, identifiers (GSTIN, Aadhaar-like references), financial, health (sports-nutrition-health),
   location (transport), grievances, videos, credentials (password hashes, tokens), or only metadata. Say whether
   the data was **read, copied, changed or lost**.
3. **Whose, and how many.** Which organisations (`organisation_id`), which kinds of person (students, staff,
   parents, applicants, visitors), and how many of each. Count from the database as the owner role on the host,
   per organisation; never copy personal data into the log, only counts.
4. **Which Data Fiduciary** for each group (section 0): this decides who notifies.
5. **Children.** Whether any affected person is under 18. The platform does not flag minors (DPDP report, section 7:
   nothing computes an age or records guardian consent), so check dates of birth in the affected tables
   (`student_information_person.date_of_birth`, `admissions_application.applicant_date_of_birth`,
   `athlete_performance_athlete.date_of_birth`) and the guardians list. The dance, music, arts and theatre academies
   and the sports college are the likeliest. A breach of children's data is more serious: the notice goes to the
   parent or guardian, and counsel is told at once **(confirm with counsel)**.
6. **Likely harm.** Identity theft or fraud, discrimination, harassment, physical safety (location, health), loss of
   exam or grade integrity, financial loss, embarrassment. Whether the data was encrypted or hashed (passwords are
   PBKDF2 hashes; stored credentials are encrypted under the KEK).
7. **Cause.** Known, suspected or unknown, and whether it is still open.
8. **Severity.**

| Level | Meaning | Notify |
|---|---|---|
| Critical | Sensitive data (health, location, children's, grievances, credentials) of many people, or the cause is still open | The institutions at once; Board and people without delay, with the 72-hour report |
| High | Personal data of a defined group was read or copied | The same |
| Medium | Personal data was exposed to one authorised person who should not have seen it, or only internally, and is contained | Decide with counsel whether the Board and people must be told; always tell the institution |
| Low | No personal data was reached (an incident, not a breach) | Log it; no notice |

When unsure between two levels, take the higher.

## 7. Notify

Faizan decides, in writing in the log, with the time. The order is: the institution at once, then the Board, then the
people. Never tell the press, social media or a customer before the institution whose data it is.

Templates follow. Replace every `[...]`. Keep them plain, short and accurate; say what you know and what you do not.
Never include a secret, a password, one person's data or another institution's name in a notice.

### 7.1 To the institution (we are its processor)

Send at once, by email to the institution's administrator and by phone, and write down when and who answered. Update
every time something material changes, and at least daily until closed.

> **Subject: Personal data incident affecting [Institution name] on Education OS**
>
> We are writing as your data processor under the Education OS terms of service, section 5. We became aware at
> [time, date, UTC and IST] of an incident that may involve personal data held by [Institution name].
>
> **What happened:** [plain description; say if still being investigated].
> **Data involved:** [categories of data and of people; the number if known; "not yet known"].
> **When:** from [time] to [time], or "not yet known".
> **What we have done:** [steps taken, with times, for example: sessions ended, secrets rotated, the account
> suspended, evidence preserved].
> **What we are doing next:** [steps].
> **What you need to decide:** as the Data Fiduciary you decide whether and how to intimate the Data Protection Board
> of India and the people affected. The Rules set the time limits and content **(confirm with counsel)**, and we will
> give you the facts for each field within [hours]. We can send the draft notices below for you to adapt.
> **Contact:** [Incident lead name and phone], [Grievance Officer name, email].
>
> We will write again by [time] or sooner if something changes. Please do not forward this outside your
> organisation until we have confirmed the facts.

### 7.2 To the Board: the intimation, and the detailed report within 72 hours

**(confirm with counsel: the form, the portal or address, the exact fields, the deadline, and whether we or the
institution files for institution data.)** The Board's own form, when it is published, replaces this layout. Until it
is, keep to the content the Rules list as we understand it:

**A. The intimation (without delay)**

> To the Data Protection Board of India, from `[Company legal name]`, `[Registered address]`,
> `[Grievance Officer name, email]`. Date and time: [UTC and IST].
> We intimate a personal data breach. In brief: [two sentences: what happened and what it means for the people
> affected]. Details follow in the report. We are the Data [Fiduciary / Processor on behalf of Fiduciary
> `[Institution name]`].

**B. The detailed report (within 72 hours of becoming aware)**

| Field | What to write |
|---|---|
| 1. Nature of the breach | What happened, in plain words; the kind (unauthorised access, disclosure, loss, alteration); how it was found and when we became aware |
| 2. Extent | Which data, how many Data Principals, which organisations; whether children are included |
| 3. Timing | When it started, when it ended or "ongoing", when discovered, when contained (UTC and IST) |
| 4. Location | Which system, host, module or place (the production API host, the database, one module, a backup, a laptop); whether the data left India |
| 5. Likely impact | The harm to the people affected, from the assessment (section 6, item 6) |
| 6. Mitigation | What was done to limit harm, and when: containment steps from section 5 |
| 7. Findings about the cause | What led to it; the person or fault if known; "under investigation" with a date for the update |
| 8. Remedial measures | What is being changed so it cannot happen again, with owners and dates |
| 9. Intimation to Data Principals | When and how each affected person was told, what was said (attach the notice), how many were reached, and how many could not be |
| 10. Contact | The Grievance Officer, name and email |

If an item is not yet known, say so and give the date by which the Board will have it. Send an update when facts
change. Keep the filing receipt in the log.

### 7.3 To the people affected

Sent by the Data Fiduciary: the institution for its people, us for ours (account and billing contacts). When it is the
institution's, offer it this text and let it send under its own name, from its own channel, unless it asks us to
send. By email to the address on record; if there is none, by the institution's usual channel. To a child, send it to
the parent or guardian **(confirm with counsel)**. Do not link to a page that needs a sign-in. Translate it into the
language the person reads.

> **Subject: A security incident involving your personal data**
>
> Dear [name],
>
> **What happened.** On [date] we found that [plain description, for example "someone who should not have had access
> was able to see"] [the data below] held on Education OS, the system [Institution name] uses for [purpose].
>
> **What data was involved.** [Exactly which: name, email address, phone, date of birth, ...]. [Passwords, payment
> card or bank details were / were not involved.]
>
> **What this could mean for you.** [Likely consequences in plain words, for example "you may receive messages
> pretending to be from the institution".]
>
> **What we are doing.** [We have stopped the access, changed the keys, and are investigating. We have told the Data
> Protection Board of India.]
>
> **What you can do.** [Specific steps: be careful with messages asking for money or a password; change the password
> you use here and anywhere else you have used it; tell your bank if payment details were involved; do not reply to
> messages you did not expect.] We will never ask for your password by email or phone.
>
> **Who to contact.** [Name], `[Grievance Officer name, email]`, or [phone]. You may also complain to the Data
> Protection Board of India.
>
> [Name, role, `[Company legal name]`, date]

A person's reply is a request to the Fiduciary: pass it to the Grievance Officer, who logs it and answers within the
time the notice promises (30 days in the draft notice; counsel to check against the Rules).

### 7.4 Anyone else

- **Cyber-crime and the police, CERT-In:** a security incident may also have to be reported to CERT-In within the
  time its directions set (six hours, as we understand them) **(confirm with counsel; this is a separate duty from
  the Act)**. Counsel decides on a police complaint.
- **Hosting provider, payment provider (SBIePay), email provider:** tell them when their systems or credentials are
  involved, and when their contract asks for it.
- **Insurers:** if a policy exists, read its notice period today.
- **The public:** only text Faizan has approved.

## 8. Record and review

**The record.** Keep, per incident: the incident log, the evidence folder and its fingerprints (section 4), the
notices as sent with their delivery receipts, the Board's receipt, the decision to notify or not and why, and the
review. Keep it for at least `[retention period, counsel to confirm]`: until counsel says otherwise, **seven years**
(as long as the audit trail), in the password manager or on the offsite backup location, not in git. A decision not
to notify is recorded with its reasoning, as carefully as a notice.

**The review.** Within two working days of containment, with the people who worked on it, and without blame:

1. **The timeline in UTC:** first possible access, first sign, awareness, declaration, each containment step, each
   notice, closure.
2. **Root cause:** the one thing that, had it been different, would have stopped it; and why it was not caught
   earlier.
3. **Actions**, each with an owner and a date, as issues labelled `incident`; some will be code (a missing check, a
   route, a disabled-user route, redaction in the audit trail), some process.
4. **Was this runbook right?** Fix it in a pull request the same day (the convention of [README.md](README.md)): the
   slow step, the missing contact, the command that did not work, the answer counsel gave.
5. **The institutions and people:** what they have been told, what is still open, and when each will next hear from
   us.
6. Faizan closes the incident in the log, with the date, once the Board has what it asked for and the actions are
   issued.

## Open items for counsel and the lead

- Every **(confirm with counsel)** above: the rule numbers, the 72-hour start and the form, the notice content and
  channel, children's data, the CERT-In duty, who files for institution data, and the record's retention period.
- The placeholders `[Grievance Officer name, email]`, `[Company legal name]`, `[Registered address]` (also on the
  privacy notice and terms, #667) and `[Counsel name, contact]`.
- A drill: once, with the team, from a made-up incident to a drafted Board report, on staging, timed. The result goes
  in the review above.
