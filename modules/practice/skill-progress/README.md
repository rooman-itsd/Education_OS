# skill-progress

**Domain:** practice
**Kind:** feature
**Status:** in-progress

Skill assessments and progression over time: technique, fitness, practicum, competencies.

## Scope
Responsible for: skill frameworks, the skills in them (optionally nested) with their proficiency scales, rubrics for a
skill or a whole framework, rubric-based assessments of learners with verification and voiding, each learner's
progress summary and progression timeline. It is a common module: nothing in it assumes a field; frameworks, scales
and rubrics carry the institution's own words.

Not responsible for: who is a learner or an evaluator (`platform/identity`, `student-information` and staff modules;
they are referenced by id), evidence files (only their URLs are kept), course grades and examinations
(`academics/examinations`) and athlete metrics (`sports/athlete-performance`).

Learners see only their own assessments, progress and timeline: a caller whose only skill-progress access comes from
a learner role (a role whose dashboard layout extends `student`, such as musician or medical-student) is narrowed to
the records whose `learner_id` is their user id. Evaluators, coordinators and administrators see their
organisation's learners (`application/service.py`, `api/deps.py`).

How it behaves (the contract's open questions in [docs/prd.md](docs/prd.md) section 9, decided here):
- **Permissions (Q1).** Every operation names its key in `x-permission`. `progress:export` has no operation yet (Q3).
- **Verifying and voiding (Q2).** `POST /assessments/{id}/verify` (`assessment:approve`) moves a submitted
  assessment to verified; whoever evaluated or recorded it cannot verify it. `POST /assessments/{id}/void`
  (`assessment:delete`) voids a submitted or verified one. Voided is final; a voided assessment stays on record but
  no longer counts towards progress or the timeline.
- **Frameworks.** Created active or draft. draft → active or archived; active → archived; archived → active. An
  archived framework takes no new skills or rubrics, and only an active framework's skills can be assessed.
- **Scales.** At least one level; keys, labels and ranks unique; `pass_fail` has two levels; `numeric_range` needs
  `min_score` below `max_score`; a level's `min_score` lies within the range and grows with the rank.
- **Rubrics.** For a skill (its framework is filled in) or for a framework, whose skills it then applies to. At least
  one criterion; keys unique; weight and max_points above 0.
- **Scores (Q8).** Every criterion of the rubric is scored once, with points from 0 to its max_points and a
  `level_key` among the criterion's levels. `overall_score` and `level_achieved` are the evaluator's: the score must
  lie within the skill's scale and reach the level's `min_score`; the level is named by key or label and returned as
  its label. The evaluator cannot be the learner; `assessed_at` defaults to now, must carry a timezone, is stored in
  UTC and cannot be in the future.
- **Milestones (Q5).** Per skill, the first counted assessment is the baseline; a later one whose level ranks above
  every earlier one is `level_advanced`; the first one at the scale's highest level is `milestone_achieved`. Each
  publishes `skill-progress.milestone.achieved` (`milestone_name` `level_advanced` or `highest_level_reached`). An
  assessment keeps the level rank it was given, so changing a skill's scale does not rewrite past progress.
- **Progress (Q6).** `skill-progress.progress.updated` is published when an assessment is recorded or voided. The
  summary shows, per skill, the latest counted assessment and how many there are; a learner with none has an empty
  summary (200), and an unknown `framework_id` is 404.
- **Timeline.** Assessments and the milestones derived from them, oldest first; `limit` keeps the most recent
  entries and `total` counts them all. A milestone entry's id is derived from its assessment's, so it is stable.
- **Audit.** Every change writes an entry to `skill_progress_audit_entry` (interim, until the audit SDK ships) with
  the changed fields, never feedback, notes, descriptions, evidence or criterion scores.

Requirements: [docs/prd.md](docs/prd.md).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. From the host it needs `packages/core` (database, tenant scoping, outbox, tokens, role layouts) and,
for its tests, `packages/testing`. The backend is `eos_skill_progress.api.router:router`; its Alembic chain is `db/`.
This module must not import code from any other module under `modules/`.

## Layout
| Path | Purpose |
|---|---|
| `docs/` | PRD, user stories, data model, screen list |
| `contracts/` | OpenAPI, event schemas, permission catalogue |
| `backend/` | Domain, application, infrastructure, API layers + unit tests |
| `frontend/` | Pages, components, API client + tests |
| `mobile/` | Mobile screens (optional) |
| `db/` | Migrations and seed data, own schema only |
| `config/` | `env.example`, feature flags |
| `tests/e2e` | End-to-end tests runnable in isolation |

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
