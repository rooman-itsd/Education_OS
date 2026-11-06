# video-conferencing: product requirements

Owner: Himanshu (@himanshu-rooman) · Backups: Faizan, Akshata · Kind: integration · Tier: common · Status: draft for review
Issue #144 · Depends on the integration-hub contracts (the meetings port).

## Purpose

Give a scheduled class, interview or mentoring session an online room on whichever service the institution already
uses, show each participant the right link, and bring back what happened: started, ended, who attended for how long,
and recordings. The calling module keeps the schedule; this adapter only manages rooms.

It implements the **meetings** port ([contracts/ports/meetings.yaml](../contracts/ports/meetings.yaml)) and the Adapter
contract ([contracts/ports/adapter.yaml](../contracts/ports/adapter.yaml)), both defined by `platform/integration-hub`.
Expected callers: lms or timetable-attendance for live classes (lms PRD question LQ8 decides which), selection-process
for interviews, alumni for mentoring sessions.

## What it is not

| Not this | That belongs to |
|---|---|
| The timetable, who is enrolled, who may join | the calling module |
| Marking attendance | timetable-attendance, from `integration-hub.meeting-attendance.received` if it chooses |
| Storing and showing recordings to students | the calling module, after `import_recording` into `platform/documents` |
| Hosting a video service | the institution's Zoom, Microsoft 365 or Webex, or its own Jitsi server |
| Calendar invitations | `platform/notification` (the port returns links; the caller tells people) |

## Providers in v1.0

| Provider | Auth (who authorises) | Create / change / cancel | Join links | Started / ended | Attendance | Recordings |
|---|---|---|---|---|---|---|
| **Zoom** | Rooman's Marketplace OAuth app, authorised by the institution's Zoom admin (account-level); or the institution's own Server-to-Server app | `POST /users/{userId}/meetings`, `PATCH` and `DELETE /meetings/{id}` | `join_url` for attendees, `start_url` for the host | Webhooks `meeting.started`, `meeting.ended` | `GET /past_meetings/{uuid}/participants` or the participants report; webhooks `meeting.participant_joined` / `_left` | `GET /meetings/{id}/recordings`, `recording.completed` |
| **Microsoft Teams** | Rooman's multi-tenant Entra app with **application** permissions, admin-consented per tenant, **plus an application access policy** the tenant admin grants | `POST /users/{organiserId}/onlineMeetings`, `PATCH`, `DELETE` | `joinWebUrl` (same link for everyone; roles by participants and lobby settings) | none in real time | `GET .../onlineMeetings/{id}/attendanceReports/{reportId}?$expand=attendanceRecords` after the meeting | `.../recordings` and `/transcripts`, with Graph change notifications |
| **Webex** | Rooman's Webex integration, authorised by a full org admin who is also a site admin (admin meeting scopes) | `POST /v1/meetings`, `PUT`, `DELETE` | `webLink`; host via host key | webhooks (meetings resource) | `/v1/meetingParticipants` | `/v1/recordings`, webhook on recordings created |
| **Jitsi (self-hosted)** | The institution's own server with token authentication (`app_id`, `app_secret`) | No API: a room is a name; the schedule is ours | Minted per person: a JWT (HS256) with `room`, `exp`, display name and moderator flag | not available | `unsupported` | `unsupported` (Jibri recordings stay on the institution's server) |

**Why Jitsi.** It is the self-hostable option: an institution that cannot or will not put classes on a US company's
service runs it on its own Indian server, and no class data leaves it. It costs nothing to test (Docker). The price is
no attendance and no recordings through the port; BigBlueButton, which has both (create and join with a checksum,
`meetingEndedURL`, a recording-ready callback signed as a JWT, and a webhooks service), is the alternative (open question 3).

### Sources

| Fact | Source |
|---|---|
| Zoom S2S OAuth (`grant_type=account_credentials`, 1-hour tokens, no refresh), internal to one account | https://developers.zoom.us/docs/internal-apps/s2s-oauth/, https://developers.zoom.us/docs/internal-apps/ |
| Zoom user-authorised and admin-managed OAuth apps for many accounts; publishing needs Zoom's review | https://developers.zoom.us/docs/integrations/end-user-auth/ |
| Zoom recordings API and `download_access_token` | https://developers.zoom.us/docs/api/meetings/ |
| Zoom webhook signature `x-zm-signature`, `endpoint.url_validation`, 3 s answer, revalidation every 72 h, retries at 5, 20 and 60 minutes on 5xx only | https://developers.zoom.us/docs/api/webhooks/ |
| Zoom event names (participant joined, recording archive, ...) | https://developers.zoom.us/docs/api/meetings/events/ |
| Zoom rate limits per account and plan; **meeting create/update: 100 requests per day per user** | https://developers.zoom.us/docs/api/rate-limits/ |
| Zoom data-centre routing (India selectable for meeting traffic on paid plans; storage in the home region) | Zoom support KB0066473 and KB0068382 (search excerpts) |
| Graph `POST /users/{id}/onlineMeetings` with `OnlineMeetings.ReadWrite.All` (application) | https://learn.microsoft.com/en-us/graph/api/application-post-onlinemeetings |
| Application access policy (`New-CsApplicationAccessPolicy`, `Grant-CsApplicationAccessPolicy`, up to 30 minutes to apply; 403 without it) | https://learn.microsoft.com/en-us/graph/cloud-communication-online-meeting-application-access-policy |
| Attendance reports (after the meeting; records with role, total seconds and intervals; no breakout rooms or channel meetings) | https://learn.microsoft.com/en-us/graph/api/meetingattendancereport-get |
| Recording and transcript change notifications (resources, `created`, 3-day maximum lifetime, lifecycle URL) | https://learn.microsoft.com/en-us/graph/teams-changenotifications-callrecording-and-calltranscript |
| Webhook delivery: `validationToken` echo within 10 s, `clientState`, 2xx within 3 s, retries for 4 h | https://learn.microsoft.com/en-us/graph/change-notifications-delivery-webhooks |
| Graph throttling (global 130,000 requests per 10 s per app; 2,000 meetings per user per month) | https://learn.microsoft.com/en-us/graph/throttling-limits |
| Microsoft 365 Developer Program sandbox now restricted (mainly Visual Studio subscribers) | https://learn.microsoft.com/en-us/office/developer-program/office-365-developer-program-faq (excerpt) |
| Webex Service Apps and admin-authorised integrations | https://developer.webex.com/blog/leveraging-service-apps-for-secure-and-scalable-api-calls-a-guide-for-admins-and-developers |
| Webex webhook secret: `X-Spark-Signature` HMAC-SHA1, newer `X-Webex-Signature` HMAC-SHA256 | https://developer.webex.com/blog/using-a-webhook-secret (excerpt) |
| Webex rate limits about 300 requests per minute, 429 with Retry-After | https://developer.webex.com/docs/rest-api-basics (excerpt) |
| Jitsi token claims (`iss`, `aud`, `sub`, `room`, `exp`, `context.user`), HS256 or RS256, Prosody token auth | https://github.com/jitsi/lib-jitsi-meet/blob/master/doc/tokens.md |
| BigBlueButton API checksum, create, join, `meetingEndedURL`, recording-ready callback; webhooks | https://docs.bigbluebutton.org/development/api/, https://docs.bigbluebutton.org/development/webhooks/ |

**Not verified** (developer pages rendered without content or were excerpts): Webex endpoint details and event names,
Zoom `meeting.started` / `meeting.ended` / `recording.completed` names (standard but outside the part we read),
whether a free Zoom account can build apps, Webex sandbox terms, and where Teams recordings land. Each is checked when
the adapter is built against the provider; none changes the port.

## Design

### Creating a meeting

1. The caller (say lms) calls `create_meeting` with `meeting_key` (its own class session id), title, start, duration,
   timezone, host (person id and email) and options.
2. The adapter resolves the host at the provider: Zoom user by email, Entra user by UPN, Webex host email. Jitsi needs
   none. A host who is not a licensed user answers `invalid_request` (`host_not_licensed`).
3. It creates the meeting and records `meeting_key` → provider meeting id, so the same key never creates a second
   meeting.
4. It returns `join_url`, `host_join_url` (none for Teams and Jitsi: same link, role at join), passcode and dial-in.

**Zoom's 100 create/update requests per host per day** matters for bulk timetabling: a term's classes for one teacher
can exceed it. The adapter spreads creation over days (create a week ahead, not a term), and a connection may name a
pool of host users. `capabilities.create_limit_per_host_per_day` tells the caller.

### Join links

`join_link` returns the stored link for Zoom, Teams and Webex. For Jitsi it mints a JWT per person: `room` is the
meeting's room name (random, not guessable), `exp` is `VIDEO_CONFERENCING_JITSI_TOKEN_TTL_S` after issue but no later
than the meeting's end plus an hour, the moderator flag only for hosts. Links are shown by the calling module to
enrolled participants only; the adapter never sends them.

### What comes back

| Port notification | Zoom | Teams | Webex | Jitsi |
|---|---|---|---|---|
| `meeting_started`, `meeting_ended` | webhooks | not available; `ended` inferred when the attendance report appears | webhooks | not available |
| `attendance_ready` → `fetch_attendance` | `meeting.ended` + `VIDEO_CONFERENCING_ATTENDANCE_DELAY_MIN` | polled after the scheduled end | after `ended` | unsupported |
| `recording_ready` | `recording.completed` | recording change notification (subscription renewed every < 3 days) | recordings webhook | unsupported |

Participants are matched to person ids by email (the institution's own domain), and through the identity the Jitsi
token carried. Unmatched participants are returned by display name to the caller and counted, not named, in the event.

### Connection (per organisation, in integration-hub)

| Provider | Settings | Secrets (hub secret store) | Platform credentials (env) |
|---|---|---|---|
| zoom | `account_id`, `host_resolution` (email or pool), `host_pool`, default options | OAuth tokens from authorisation; or, with the institution's own S2S app, `client_id`, `client_secret`, `webhook_secret_token` | Rooman Marketplace app id, secret, webhook secret token |
| teams | `tenant_id`, default lobby settings | none beyond consent; per-subscription `client_state` | Rooman Entra app id and secret |
| webex | `site_url` | OAuth tokens; `webhook_secret` | Rooman integration id and secret |
| jitsi | `base_url`, `app_id`, `room_prefix` | `app_secret` | none |

### Error mapping

| Provider answer | Port error | Retryable |
|---|---|---|
| Network error, timeout, TLS | `transport_unavailable` | yes |
| 5xx | `provider_error` | yes |
| 429 (Retry-After honoured; Zoom daily limits reset at 00:00 UTC) | `throttled` | yes |
| 401, invalid or revoked token, refresh refused | `auth_failed` | no |
| Graph 403 "No application access policy found for this app" | `auth_failed` (`access_policy_missing`, with the PowerShell the admin must run) | no |
| Host not a user, or not licensed | `invalid_request` (`host_not_licensed`) | no |
| Meeting not found (Zoom 3001, 404) | `not_found` | no |
| Cancel or change a live or ended meeting | `conflict` | no |
| Attendance or recordings on Jitsi | `unsupported` | no |

### Rate limits

| Provider | Published limit | What the adapter does |
|---|---|---|
| Zoom | Per account and plan (e.g. Pro: 30 light, 20 medium, 10 heavy requests per second); meeting create/update 100 per user per day | Create a week ahead; host pool; hold the queue on 429 |
| Microsoft Graph | 130,000 requests per 10 s per app; 2,000 meetings per user per month | Retry-After on 429 |
| Webex | About 300 requests per minute | Retry-After on 429 |
| Jitsi | Our own server | none |

## Sandbox and mock

| Provider | How it is tested in v1.0 |
|---|---|
| Zoom | Rooman's app in development mode against a Rooman Zoom developer account (webhooks to a staging URL); recorded fixtures for every call and event in CI |
| Teams | A Microsoft 365 tenant Rooman controls (the free developer sandbox is restricted now; a trial or a Visual Studio subscription), or a willing institution's test tenant; recorded fixtures in CI |
| Webex | Webex developer sandbox; recorded fixtures in CI |
| Jitsi | `docker-jitsi-meet` with token auth, locally and in CI; nothing recorded |

Webhook verification is tested with fixtures signed with known secrets, including wrong signatures, stale timestamps,
Zoom's url_validation, Graph's validationToken and lifecycle notifications.

## Data model (summary)

Own schema `video_conferencing`; every table has `organisation_id` with row-level security.

| Entity | Key fields |
|---|---|
| meeting | id, organisation_id, connection_id, meeting_key, caller_module, provider, provider_meeting_id, room_name (Jitsi), status, starts_at, duration_minutes, started_at, ended_at, join_url (encrypted), host_join_url (encrypted), passcode (encrypted) |
| attendance | organisation_id, meeting_id, person_id (nullable), display_name (nullable), role, total_seconds, intervals, complete |
| recording | organisation_id, meeting_id, provider_recording_id, kind, bytes, expires_at, document_id (once imported) |
| graph_subscription | organisation_id, connection_id, subscription_id, resource, client_state_ref, expires_at |

Join links and passcodes are stored encrypted: anyone holding one can enter the class.

## Personal data (DPDP Act 2023)

- Participants' names and emails go to the provider to create meetings and come back in attendance reports; the
  institution chose the provider and holds the contract with it.
- Recordings are personal data of everyone in them. They stay at the provider unless the caller asks to import one;
  importing stores it under the institution's own access rules and retention.
- **Where data is:** Zoom lets paid accounts choose meeting-traffic data centres including India, with storage in the
  home region; Microsoft offers India data residency for Teams under its Local or Advanced Data Residency offers;
  Webex is not verified; **Jitsi keeps everything on the institution's own server**. Each institution should be told
  this when it connects (open question 4).
- Unmatched participants are never named in events.

## Permissions and events

- `video-conferencing:meeting:read` (org-admin): `GET /meetings`.
- No events of its own: the hub publishes `integration-hub.meeting.started`, `.ended`,
  `integration-hub.meeting-attendance.received` and `integration-hub.meeting-recording.available`.

## External dependencies (what Rooman must apply for)

| What | With whom | How | Needed for |
|---|---|---|---|
| **Zoom Marketplace app** (general OAuth app, account-level, meeting, report and recording scopes, event subscription), published after **Zoom's app review** | Zoom | https://marketplace.zoom.us (developer account) | Institutions authorising Rooman's app. Until reviewed: each institution creates its own S2S app and enters its credentials |
| **Microsoft Entra multi-tenant app** with application permissions; Microsoft publisher verification recommended | Microsoft | Entra admin centre (https://entra.microsoft.com) | Teams. Each tenant admin consents and runs the application access policy commands |
| A Microsoft 365 tenant for development | Microsoft | Developer Program (restricted), a trial, or a Visual Studio subscription | Teams testing |
| **Webex integration** with admin meeting scopes | Cisco Webex | https://developer.webex.com | Webex |
| Nothing for Jitsi | — | The institution runs its own server | — |

## Out of scope (v1.0)

- BigBlueButton and Google Meet (open question 3).
- Breakout rooms, polls, chat transcripts, live streaming.
- Webinars and registration flows (Zoom limits registration calls to 3 per registrant per meeting per day).
- Calendar invitations from the provider (Graph `events` with `isOnlineMeeting` sends invitations that cannot be
  suppressed; the adapter uses `onlineMeetings` instead).

## Open questions (for review)

1. **lms or timetable-attendance (Himanshu, Shivani).** Who calls `create_meeting` for live classes (lms LQ8)? The port
   works for either.
2. **Rooman's apps or the institution's.** One Rooman app per provider that institutions authorise (proposed; needs
   Zoom's review and Microsoft publisher verification), or each institution's own app (no review, more setup)?
3. **Self-hosted choice.** Jitsi (proposed: simplest to run, no attendance or recordings through the port) or
   BigBlueButton (attendance and recordings, heavier to run)?
4. **Telling institutions where data goes.** A short notice per provider on the connection screen. Agreed?
5. **Attendance from meetings.** Should timetable-attendance mark attendance from the report automatically, or only
   show it to the teacher? Its owner decides; the event supports both.
