# Changelog — video-conferencing

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
### Security
- Default mode changed to `sandbox`; `mock` mode is refused for both environment configuration and per-connection
  calls unless `EOS_DEV_MODE=true`. Development data key and Jitsi app secret fallbacks are similarly disabled outside
  dev mode (security review, November 2026, N17, #681).
- Self-hosted Jitsi `base_url` requires `https` and refuses any host that is, or resolves to, an address that is not
  globally routable: loopback, private, link-local and cloud metadata addresses, shared address space `100.64.0.0/10`
  (Alibaba's metadata address `100.100.100.200` is in it), reserved and multicast ranges, and IPv6 forms that carry an IPv4
  address (mapped, NAT64, 6to4). The healthcheck no longer echoes the HTTP status code (security review, November 2026,
  N16, #680).
- `VIDEO_CONFERENCING_JITSI_ALLOWED_NETWORKS` (operator-set, comma-separated CIDRs, empty by default) lets an institution's
  own Jitsi on a private network be reached, which #692 refused outright. The connection's settings cannot widen it.
  Loopback, link-local, multicast and the cloud metadata addresses stay refused whatever is listed, and a list that opens
  one of those ranges, or is not a list of networks, is a configuration error. Azure's WireServer `168.63.129.16`, a
  public-looking address that passed the check, is now refused too, as is AWS's IPv6 metadata `fd00:ec2::254`.
- The Jitsi healthcheck resolves the host once and sends the request to the address that passed the check, with the host
  name kept as `Host` and as the TLS server name (so the certificate is still checked for the name), and never follows a
  redirect. A name that answered with a public address when checked can no longer be looked up again as an internal one
  (DNS rebinding).
- Zoom's `endpoint.url_validation` handshake answers only a `plainToken` made of base64url characters (`A-Z a-z 0-9 _ -`, 1
  to 256 long); anything else is refused, signed or not. Zoom's documentation does not say that the challenge is signed,
  so it is answered whether or not it carries `x-zm-signature`, and every other event still needs a valid signature and
  timestamp. The handshake answers HMAC(secret, `plainToken`), the same function as an event's signature
  HMAC(secret, `v0:<ts>:<body>`): a `plainToken` of `v0:<ts>:<forged event>` used to sign any event a caller wrote. A
  signed message always contains a `:`, a challenge token never does, so no answer can be an event signature (security
  review, November 2026, N13). Replaces the "handshake must be signed" rule of #670, which would have refused Zoom's own
  unsigned validation requests.

## [0.3.0] - 2026-11-05
Built on the draft contracts (0.2.0); no contract file changed.
- The meetings port and the Adapter contract for **Zoom** (account-level OAuth app or an institution's own Server-to-Server
  app; per-host daily create/update limit with an optional host pool), **Microsoft Teams** (Graph onlineMeetings, application
  permissions, access-policy error with the PowerShell hint, recordings subscription kept alive), **Webex** and **Jitsi**
  (random room names, per-person HS256 JWT join links).
- Webhooks: Zoom `x-zm-signature` and the `endpoint.url_validation` handshake, Graph `validationToken` and per-subscription
  `clientState` (derived from a stored nonce, never stored), Webex `X-Webex-Signature` / `X-Spark-Signature`.
- Own schema `video_conferencing` (meeting, attendance, recording, graph_subscription, host_quota, audit_entry), forced
  row-level security, Alembic chain `vc_0001` with its own version table. Join links and passcodes encrypted (Fernet).
- `GET /meetings` operator view with `video-conferencing:meeting:read`.
- Modes `mock` (default), `sandbox`, `live`; live refuses to start without its credentials.
- Deviations from the draft: `create_meeting` and `update_meeting` take an optional hub `meeting_id`; `fetch_attendance`
  takes an optional `roster` ([{person_id, email}]) because the adapter has no directory of people; `attendance_ready`
  carries `not_before`; Zoom `participant_joined/_left` are acknowledged but publish nothing (no person id to give);
  `verify_inbound` output adds `ack_status` (Graph wants 202); `due_attendance` and `renew_subscriptions` are added as
  scheduler jobs; new keys `MODE`, `DATA_KEY`, `PROVIDERS`, `PUBLIC_BASE_URL`, `ZOOM_CREATE_LIMIT_PER_HOST_PER_DAY`,
  `MAX_RECORDING_BYTES`.

## [0.2.0]
- Contracts proposed, no code: PRD for Zoom, Microsoft Teams (Graph), Webex and self-hosted Jitsi with sources;
  implements the meetings port (copies of the hub's port files in `contracts/ports/`); webhook verification for each
  provider and a read-only meetings view in `contracts/openapi.yaml`; no events of its own;
  `video-conferencing:meeting:read` for org-admin; `config/env.example`.
