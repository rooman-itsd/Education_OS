# iqac-accreditation — data model

One schema, owned entirely by this module: every table is named `iqac_accreditation_<entity>` and the Alembic chain
(`db/`, revision `iqac_accreditation_0001`) keeps its own version table, `iqac_accreditation_alembic_version`. No foreign
key leaves the module (module-standard rule 2): every person (owner, reviewer, actor) and every evidence reference to
another module's record is an id kept as given.

Every table carries `organisation_id` and the forced `tenant_isolation` row-level-security policy on
`app.organisation_id`; every query is also scoped in the repository, so SQLite tests enforce the same rule.

## Entities

### Framework (`iqac_accreditation_framework`)
An accreditation framework the organisation reports against. No accreditation content is built in.

| Field | Notes |
|---|---|
| id | uuid (text, 36), primary key |
| organisation_id, created_at, updated_at | |
| code | up to 40 characters; unique within the organisation |
| name | up to 200 |
| description | text, nullable, up to 10 000 characters on input |
| active | deactivated, never deleted; a framework used by a cycle that is not closed cannot be deactivated |

### Metric (`iqac_accreditation_metric`)

| Field | Notes |
|---|---|
| id, organisation_id, created_at, updated_at | |
| framework_id | within this module; indexed |
| code | up to 40; unique within the framework |
| title | up to 500 |
| criterion | up to 200, nullable: the label of the criterion the metric belongs to, matched whole and ignoring case by the `criterion` filter |
| kind | `quantitative` or `qualitative`; does not change after creation |
| unit | up to 40, nullable |
| guidance | text, nullable |
| active | deactivated, never deleted; existing responses keep their values |

### Cycle (`iqac_accreditation_cycle`)
A collection cycle of one framework for one period.

| Field | Notes |
|---|---|
| id, organisation_id, created_at, updated_at | |
| framework_id | indexed with status |
| name | up to 200 |
| period_start, period_end | dates from 1900-01-01 to 2199-12-31; the end is after the start |
| status | `planning`, `collecting`, `under_review`, `submitted`, `closed` |
| submitted_on | date, nullable: when the cycle was submitted to the accrediting body (needed for `submitted`) |
| closed_at | nullable |

### Response (`iqac_accreditation_response`)
The answer to one metric in one cycle, owned by one person. Unique on (cycle, metric).

| Field | Notes |
|---|---|
| id, organisation_id, created_at, updated_at | |
| cycle_id, metric_id | within this module |
| owner_id | person id from identity, by id only |
| due_on | date |
| status | `pending`, `submitted`, `returned`, `accepted` |
| value | double, nullable, finite, at most 1e15 in size; quantitative metrics only |
| narrative | text, nullable, up to 20 000 characters on input |
| review_comment | text, nullable |
| submitted_at, reviewed_at | nullable |
| reviewed_by | person id, nullable |

Overdue (`pending` or `returned` and `due_on` before today) is worked out when read, never stored.

### Evidence (`iqac_accreditation_evidence`)
A link or a reference to a record in another module. Stored as given; nothing is checked against the other module.

| Field | Notes |
|---|---|
| id, organisation_id | |
| response_id | within this module; indexed |
| title | up to 200 |
| kind | `link` (needs `url`) or `reference` (needs `reference`), never both |
| url | up to 2 000 characters, http or https only |
| reference | JSON `{module, entity, id}`, each up to 120 characters |
| note | text, nullable |
| added_by, added_at | |

Removed (the one hard delete) while the response is not accepted; the removal is audited.

### ActionItem (`iqac_accreditation_action_item`)

| Field | Notes |
|---|---|
| id, organisation_id, created_at, updated_at | |
| title | up to 200 |
| description | text, nullable |
| source | up to 120, nullable: free text such as an IQAC meeting, a peer team visit or an internal audit |
| cycle_id, metric_id | nullable, within this module |
| owner_id | person id, by id only |
| due_on | date |
| status | `open`, `in_progress`, `done`, `cancelled` |
| completed_at | nullable, set when it moves to `done` |

Overdue (`open` or `in_progress` and `due_on` before today) is worked out when read.

### AuditEntry (`iqac_accreditation_audit_entry`)
Stands in for the audit SDK, which does not exist yet; its rows are not in the platform audit trail.

| Field | Notes |
|---|---|
| id, organisation_id | |
| actor | person id, nullable |
| action | for example `cycle.status-changed`, `response.returned`, `evidence.removed`, `action-item.reassigned` |
| entity, entity_id | `framework`, `metric`, `cycle`, `response`, `evidence` or `action-item`, and its id |
| reason | a status move (`planning -> collecting`), a review comment or an action item note |
| occurred_at | |

Values, narratives, evidence content and links are never copied into an audit entry.

## Relationships

```
Framework (1) ──< Metric (many)
Framework (1) ──< Cycle (many)
Cycle (1) ──< Response (many)      one per metric in the cycle
Metric (1) ──< Response (many)
Response (1) ──< Evidence (many)
Cycle, Metric (0..1) ──< ActionItem (many)
```

All relationships are inside this module's schema. Person ids and evidence references are kept as given and never joined.

## Statuses

```
Cycle:       planning → collecting → under_review → submitted → closed
Response:    pending → submitted → accepted
             submitted → returned → submitted
ActionItem:  open → in_progress → done
             open | in_progress → cancelled
```
