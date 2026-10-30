# Role dashboard layouts

One file per role. The dashboard shell in `apps/frontend` reads the file for the signed-in user's
role and renders the listed widgets in order. Adding, removing or reordering a widget on a
dashboard is an edit here, not code.

```yaml
role: athlete            # must match a role id in packages/contracts/src/roles.ts
title: "Athlete"
extends: student         # optional: that role's widgets come first, and its permissions are inherited
module_roles:            # optional: the module roles this role holds (see below)
  - tournament-events-athlete
  - sports-nutrition-health-athlete
widgets:
  - athlete-performance.training-schedule   # <module>.<widget>, exported by that module
```

There is a layout for every role of every academy profile: the common roles, plus each academy's
learner (artist, musician, dancer, medical student, ...), instructor and field staff roles. Field
role layouts use the generic `practice/*` and `facilities/*` modules; the profile vocabulary names them.

Two layouts are platform-level rather than academy-level: `org-admin` (one per organisation,
created at registration) and `super-admin` (the operator, served by the admin screens in `apps/frontend`).

Rules
- A widget id must be exported by exactly one module's `frontend/src/widgets/index.ts`.
  Until the module ships it, the shell renders a "not built yet" card with the id, so a
  dashboard owner can see what is missing.
- The shell hides any widget whose permission key the viewer does not hold. Two roles may
  share a layout and still see different cards.
- `extends` is one level deep. Do not chain.
- `extends` also gives the role every permission key of the role it extends, on top of its own
  (`eos_core.config.permissions_for`, ADR-0004 "Role inheritance"). Extend only `student` or
  `faculty`-like roles: never `org-admin`, `super-admin` or `service` (a host test refuses it).
- `module_roles` says which roles of each module this profile role holds. A module grants its own roles
  (`projects-member`, `portfolio-reviewer`, `lms-instructor`, ...) and knows nothing of any academy's roles, so the
  layout maps the two: `research-scholar` lists `projects-member` and `portfolio-learner`, `research-supervisor`
  lists `projects-guide` and `portfolio-reviewer`. `eos_core.config.load_role_parents` returns them as extra
  parents of the layout's role, so `expand_roles` and `permissions_for` grant them; the `module_roles` of a role the
  layout `extends` are inherited too, so the `student` and `faculty` layouts list the roles every learner or
  teacher holds (`lms-student`, `library-member`, `lms-instructor`, ...) and an extending layout lists only its
  own. List a module role for each module whose widget is on the layout, chosen by the widget's meaning: learner
  layouts take the learner/student/member/trainee/athlete role, faculty layouts the guide/reviewer/supervisor/
  evaluator/coach role, staff layouts the coordinator/officer/responder role that fits. A learner layout never
  lists a manager or admin role. `selection-process` has only panelist and coordinator roles, so applicants are
  covered by no layout until that module grants one.
- Owner of this folder: Architecture and platform lead. A dashboard owner edits their own
  role's file in the same PR as the widgets.
