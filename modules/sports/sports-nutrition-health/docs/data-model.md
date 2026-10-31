# sports-nutrition-health: data model

Every table is prefixed `sports_nutrition_health_`, carries `organisation_id` and has the `tenant_isolation`
row-level-security policy on Postgres. Foreign keys stay inside this module; athlete ids are athlete-performance's and
practitioner, nutritionist and user ids are platform/identity's, all plain values.

| Table | Holds | Notes |
|---|---|---|
| `plan` | A diet plan for one athlete | Goal, daily targets, meals, dates, `review_due_on`, status |
| `plan_review` | A nutritionist's review | Added, never changed; `end` completes the plan, a next date moves `review_due_on` |
| `health_record` | Confidential medical information | Medical roles only; never in events or audit values |
| `injury` | An injury from report to recovery | `resolved_on` set when resolved; `clinical_notes` medical roles only |
| `appointment` | Physiotherapy, medical or nutrition session | Optional `injury_id` of the same athlete; `completed_at` when completed |
| `athlete_link` | Which user is which athlete | From `athlete-performance.athlete.registered`; one per athlete |
| `audit_entry` | Who changed what | Interim until the audit SDK; shaped like platform/audit's Record |
