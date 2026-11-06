# iqac-accreditation — integration points

## Events published (contracts/events.yaml)

| Event | Published when | Consumers |
|---|---|---|
| `iqac-accreditation.cycle.status-changed` | every cycle status move, in the same transaction as the change and its audit entry | none yet |
| `iqac-accreditation.response.accepted` | a coordinator accepts a response | none yet; regulatory-reports might reuse accepted data (PRD open question 4) |

Payloads carry identifiers, the metric code, statuses and times only, never values, narratives, evidence or review comments.
They follow the convention on `main` (`organisation_id` in the payload, a file-level `version`); PRD open question 11 is
the question of the event-bus envelope. No consumer is assumed in this module's code.

## Events consumed

None. `module.yaml` keeps `consumes_events: []`.

## Platform services

| Service | Use today | When the SDK ships |
|---|---|---|
| identity | the token is verified with `eos_core` (`decode_token`, `permissions_for`) in `api/deps.py` | the identity SDK replaces that file; the permission keys stay |
| audit | an own table, `iqac_accreditation_audit_entry`, written on every change | audit through `packages/sdk`; the call sites are the `_audit` calls in `application/service.py` |
| notification | not called: owners are not told of an assignment, a return or a new action item | notices to the owner on `response.assigned`, `response.returned`, `action-item.created` and `action-item.reassigned`, which the audit entries already name |

## Other modules

- No code from any other module is imported, and no other module is called.
- Evidence may name a record in any module by `{module, entity, id}`. It is kept as given; the other module is not called
  and need not be enabled.
- Nothing here depends on another module being enabled.

## Dashboard

| Widget | Dashboard | Endpoint | Permission |
|---|---|---|---|
| `iqac-accreditation.action-items` | Governance (`platform/identity/config/dashboards/governance.yaml`) | `GET /stats/action-items` | `iqac-accreditation:stats:read` |

The Governance role holds `iqac-accreditation-coordinator` through `module_roles`, which grants the key. The module is not
enabled in `apps/*/config/modules.enabled.yaml` yet; that is a separate pull request after this one merges.
