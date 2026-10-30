# athlete-performance: data model

Every table is prefixed `athlete_performance_`, carries `organisation_id` and has the `tenant_isolation`
row-level-security policy on Postgres. Foreign keys stay inside this module; user, coach and student ids are plain
values owned by `platform/identity` and `student-information`.

| Table | Holds | Notes |
|---|---|---|
| `discipline` | Sports or event groups | Name unique per organisation |
| `metric` | Measurable things, unit and direction | Optional discipline; name unique per organisation |
| `athlete` | Sports profile | `discipline_ids` holds the primary first; `user_id` unique per organisation |
| `result` | One value for one athlete and metric | Corrections update the row; the audit entry keeps the old value |
| `fitness_test` | A battery of metrics | Name unique per organisation |
| `assessment` | One test for one athlete on one day | `measurements` is `[{metric_id, value}]` |
| `benchmark` | Target per metric, level, discipline, gender, age group | One per combination |
| `clearance` | Current fitness clearance per athlete | Status, validity and restrictions only; no clinical detail |
| `audit_entry` | Who changed what | Interim until the audit SDK; shaped like platform/audit's Record |

History and comparison read results and assessment measurements together; an assessment counts at the start of its
day (UTC).
