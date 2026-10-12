# Skill Progress — Product Requirements

## 1. Purpose

The Skill Progress module records how learners' skills develop over time. Institutions define skill frameworks, skills and rubrics; evaluators record rubric-based assessments; learners and staff see each learner's current proficiency and a timeline of their progression.

It is a generic pattern used by every institution type whose academy profile includes `practice/skill-progress`: technique grades, practicum assessment, skills training and competency tracking (`docs/architecture/institution-types.md`).

## 2. Scope

### In scope
- Skill frameworks: competency frameworks with a code, title, description and status (active, draft, archived)
- Skills within a framework, optionally nested under a parent skill, with a category and a proficiency scale
- Proficiency scales: discrete stages, a numeric range or pass/fail, made of ranked performance levels
- Rubrics for a skill or a framework, made of weighted criteria with maximum points and optional performance levels
- Assessment records: a learner evaluated on a skill against a rubric, with criterion scores, an overall score, the level achieved, feedback and evidence links
- A learner's progress summary: the latest score and level for every evaluated skill
- A learner's progression timeline: assessments, milestones achieved and levels advanced, in date order

### Out of scope
- Defining who is a learner or an evaluator (identity and the student and staff modules; this module refers to them by id)
- Storing evidence files (this module keeps evidence URLs only)
- Course grades, examinations and results (academics/examinations)
- Athlete performance metrics and benchmarks (sports/athlete-performance)

## 3. Users

The contracts define three roles:

| Role | Who | Permissions |
|---|---|---|
| `skill-progress-admin` | Institution administrator for skill frameworks | Every key: framework read and write, assessment read, record, approve and delete, progress read and export |
| `skill-progress-evaluator` | Evaluators, instructors, mentors and supervisors | `framework:read`, `assessment:read`, `assessment:record`, `progress:read` |
| `skill-progress-viewer` | Learners and observers | `framework:read`, `assessment:read`, `progress:read` |

The role layouts in `platform/identity/config/dashboards/` place this module's widgets on:
- **Evaluators:** `skill-progress.assessments-due` on chef instructor, choreographer, clinical supervisor, mentor teacher, music teacher and project guide.
- **Learners:** `skill-progress.my-progress` on dancer, field trainee, hospitality trainee, medical student, musician and teacher trainee.
- **Coordinators:** `skill-progress.cohort-overview` on practicum coordinator.

## 4. Core Features

### Skill Frameworks
List frameworks by status, create a framework with a code and title, view it, and update its title, description or status (active, draft, archived).

### Skills
Add skills to a framework with a code, title, description, category and proficiency scale; nest a skill under a parent skill; list skills by framework, category or parent; view and update a skill's title, description, category and scale.

### Proficiency Scales
Each skill has a scale of type `discrete_stages`, `numeric_range` or `pass_fail`, with an optional minimum and maximum score and a list of performance levels. A performance level has a key, a label, a rank, a description and an optional minimum score (for example `level_3`, "Proficient", rank 3).

### Rubrics
Define a rubric for a skill or a framework with a title, description and criteria. Each criterion has a key, title, description, weight (default 1.0), maximum points and optional performance levels. List rubrics by skill or framework and view a rubric.

### Assessments
Record an assessment of a learner on a skill against a rubric: the evaluator, the assessment time, a score per criterion (points, level and notes), the overall score, the level achieved, feedback and evidence URLs. List assessments by learner, evaluator, skill and date range, and view one. An assessment record has a status of `submitted` (the default), `verified` or `voided`.

### Learner Progress Summary
For a learner, optionally within one framework: the number of skills evaluated and, for each skill, its title and category, the latest score and level, the number of evaluations and when it was last assessed.

### Progression Timeline
For a learner, optionally for one skill: a date-ordered list of entries of type `assessment`, `milestone_achieved` or `level_advanced`, each with a title, description, score and level.

## 5. Key Requirements

- Administrators must be able to create and maintain frameworks, skills and rubrics.
- Every skill must belong to a framework and have a proficiency scale with at least its type and levels.
- Every assessment must name the learner, evaluator, skill and rubric, and carry criterion scores, an overall score and the level achieved.
- Assessment history must be kept so that a learner's progress summary and timeline can be produced.
- Access must follow the permission keys in `contracts/permissions.yaml`.
- Every record must belong to the organisation (row-level security on `organisation_id`).

## 6. Interfaces

- **API:** `contracts/openapi.yaml` — under `/api/v1/skill-progress`:

  | Resource | Operations |
  |---|---|
  | `/frameworks` | list (filter by status), create |
  | `/frameworks/{framework_id}` | get, update |
  | `/skills` | list (filter by framework, category, parent skill), create |
  | `/skills/{skill_id}` | get, update |
  | `/rubrics` | list (filter by skill, framework), create |
  | `/rubrics/{rubric_id}` | get |
  | `/assessments` | list (filter by learner, evaluator, skill, date range), record |
  | `/assessments/{assessment_id}` | get |
  | `/learners/{learner_id}/progress` | progress summary (optionally for one framework) |
  | `/learners/{learner_id}/timeline` | progression timeline (optionally for one skill) |

- **Events:** `contracts/events.yaml` — `framework.created`, `skill.created`, `rubric.created`, `assessment.recorded`, `milestone.achieved` and `progress.updated`. Every event carries `organisation_id`.
- **Permissions:** `contracts/permissions.yaml` — `framework:read`, `framework:write`, `assessment:read`, `assessment:record`, `assessment:approve`, `assessment:delete`, `progress:read`, `progress:export`; roles as in section 3.
- **Platform services:** identity and audit (`module.yaml`). The module consumes no other module's events.

## 7. Module Boundary

This module owns skill frameworks, skills, rubrics, assessment records and learner progress.

It must not directly import code from other modules under `modules/`. Learners and evaluators are referenced by id. Other modules learn about assessments and progress from `skill-progress.assessment.recorded`, `skill-progress.milestone.achieved` and `skill-progress.progress.updated`.

Integration with other modules must happen through published API contracts and events.

## 8. Success Criteria

Any institution type can describe the skills it trains in its own frameworks and rubrics, record consistent rubric-based assessments, and show each learner and their evaluators an accurate, current picture of the learner's proficiency and how it has changed over time.

## 9. Not yet defined in the contracts

These are open questions. They are listed here so they are decided in a contract change, not assumed.

| # | Question |
|---|---|
| Q1 | **Permission per operation.** No operation in `openapi.yaml` names the permission key it requires. |
| Q2 | **Verifying and voiding assessments.** `assessment:approve` and `assessment:delete` exist, and an assessment's status can be `verified` or `voided`, but there is no operation to verify or void one. |
| Q3 | **Exporting progress.** `progress:export` exists, but there is no export operation. |
| Q4 | **Archiving.** A framework can be set to `archived` through its update. There is no archive or delete operation for skills or rubrics, and no rubric update. |
| Q5 | **Milestones.** `milestone.achieved` and the timeline's `milestone_achieved` and `level_advanced` entries exist, but the contracts do not say how a milestone is defined or when a learner reaches one or advances a level. |
| Q6 | **When progress is recomputed.** `progress.updated` says a learner's progress profile was recomputed, but not what triggers it. |
| Q7 | **Learners seeing only their own records.** The viewer role (learners and observers) holds `assessment:read` and `progress:read` with no own-records key or rule. |
| Q8 | **Scoring.** The contracts do not say how criterion points and weights produce `overall_score`, or how the overall score maps to `level_achieved`; both are supplied when an assessment is recorded. |
| Q9 | **Widget data.** The role layouts name `skill-progress.assessments-due`, `skill-progress.my-progress` and `skill-progress.cohort-overview`. `my-progress` can use the learner progress summary. The contracts define no due dates or assignment of assessments for `assessments-due`, and no cohort or group report for `cohort-overview`. |
| Q10 | **Role mapping.** The roles are named `skill-progress-admin`, `-evaluator` and `-viewer`. How they map to profile roles (for example music teacher or medical student) is not defined. |
| Q11 | **Update events.** Framework and skill updates publish no event; only creation does. |
