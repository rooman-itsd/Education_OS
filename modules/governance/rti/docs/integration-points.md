# rti: integration points

## Publishes
Both events are written to the `eos_core` outbox (`outbox_event`) in the same transaction as the change and its audit
entry, so a failure stores none of them. Payloads carry identifiers and metadata only (`contracts/events.yaml`).

| Event | When | Payload |
|---|---|---|
| `rti.request.received` | `POST /requests` | `organisation_id`, `request_id`, `number`, `received_via`, `received_on` |
| `rti.request.closed` | `POST /requests/{id}/close`, `POST /requests/{id}/transfer` | `organisation_id`, `request_id`, `number`, `closure` (`responded`, `appeal_decided`, `transferred`), `response_type` (null for a transfer), `appealed`, `closed_at` |

No module consumes them yet; `regulatory-reports` may want counts (PRD open questions 8 and 11).

## Consumes
Nothing. The module has no dependency on another module being enabled.

## Platform services
| Service | How it is used today |
|---|---|
| identity | The token is verified with `eos_core` (`decode_token`) and permission keys come from `permissions_for`, which follows the `module_roles` of the caller's dashboard layouts. Person ids (applicant, officer, custodian, appellate authority) are held by id only. Swap for the identity SDK when it ships. |
| audit | `packages/sdk` is empty, so every change and every read of a request writes a row in the module's own `rti_audit_entry` until the audit SDK exists. |
| notification | Not called: `packages/sdk` has no notification client. Assignments, referrals and replies are audited and name the person to notify; the notices (request number and a generic message, never applicant data) can be added in `application/service.py`. |

## Dashboard
| Widget | Layout | Endpoint | Permission |
|---|---|---|---|
| `rti.nearing-deadline` | Governance (`platform/identity/config/dashboards/governance.yaml`, role `rti-officer`) | `GET /stats/nearing-deadline` | `rti:stats:read` |

## Not integrated in v1
fees-accounts (fees are metadata), web-portal-cms (no public form), platform/documents (no attachments), scheduler (no
timers or reminders), regulatory-reports, grievance, helpdesk, incident-management.
