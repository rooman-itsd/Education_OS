# grievance: integration points

## Publishes (`contracts/events.yaml`)
| Event | When | Payload |
|---|---|---|
| `grievance.case.filed` | A case is filed, in the same transaction as the case and its audit entry | `organisation_id`, `case_id`, `number`, `track`, `committee_id`, `filed_at` |
| `grievance.case.closed` | A case reaches a final state: closed (`closure: decided`), withdrawn, or not admitted | `organisation_id`, `case_id`, `number`, `track`, `committee_id`, `closure`, `appealed`, `closed_at` |

Payloads carry identifiers and metadata only: never the complainant, respondent, category, description, proceedings,
updates, decision outcome or findings. `committee_id` in the closed event is the committee the case was filed with or
transferred to. No module consumes them yet (PRD open question 6).

## Consumes
Nothing.

## Platform services
| Service | Use | How today |
|---|---|---|
| identity | Who is calling and their permission keys | The token is verified with `eos_core.security` and the keys come from `eos_core.config.permissions_for` (`api/deps.py`), until the identity SDK ships. Committee membership is the module's own data. |
| audit | One entry per change and per read of case content | `grievance_audit_entry`, until the audit SDK ships. |
| notification | Generic notices: "There is an update on case GRV-000123." | `infrastructure/notifier.py` logs the notice and keeps the last ones in memory, until the notification SDK ships. Recipients: committee members on filing, a message, a withdrawal, a transfer and an appeal; the complainant on a status change, a message from the committee, a decision and an appeal decision. |

## Dashboard widgets
| Widget id | Dashboard | Endpoint | Permission |
|---|---|---|---|
| `grievance.open-by-committee` | Governance | `GET /stats/open-by-committee` | `grievance:stats:read` |
| `grievance.open` | Management | `GET /stats/open` | `grievance:stats:read` |

## Boundaries
Grievances are not helpdesk tickets and hostel discipline records stay in hostel; ragging complaints come here. No
code, table or foreign key reaches another module.
