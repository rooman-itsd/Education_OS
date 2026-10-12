# Training & Video Analysis — Product Requirements

## 1. Purpose

The Training & Video Analysis module lets coaches plan training, schedule sessions, keep a repository of drills, and review training and competition video with athletes through drill tags and time-coded annotations.

## 2. Scope

### In scope
- Training plans for a squad or group over a period (for example a pre-season block)
- Training sessions within a plan: scheduling, location, status and completion
- A drill repository that sessions and video tags refer to
- Registering training and performance videos against a session
- Tagging drills or phases on a video timeline
- Time-coded coaching annotations on a video
- Athlete access to their assigned plans, sessions and reviewed videos

### Out of scope
- Athlete profiles, performance metrics, fitness testing and benchmarks (athlete-performance)
- Tournament and fixture management (tournament-events)
- Nutrition, medical and injury records (sports-nutrition-health)
- Facility registry and booking (sports-facilities, facility-booking)
- Storing the video files themselves (platform/documents; this module keeps the video's reference and metadata)

## 3. Users

- Coach
- Sports Staff
- Athlete
- Institution Administrator

## 4. Core Features

### Training Plans
Create and update a training plan with a title, coach, start and end dates and a status (draft, active, completed, archived).

### Training Sessions
Schedule sessions inside a plan with a coach, start time and location; move them through scheduled, in progress, completed or cancelled; find sessions by plan, coach, date range or status.

### Drill Repository
Keep a catalogue of drills that coaches reuse across sessions and refer to when tagging video.

### Video Registration
Register a training or performance video against a session with its title, duration and the location of the file.

### Drill Tagging
Mark the start and end of a drill or tactical phase on a video's timeline, linked to a drill in the repository.

### Coaching Annotations
Add, update and remove time-coded technical or tactical annotations on a video, with a category, so athletes can review feedback at the exact moment it applies.

## 5. Key Requirements

- Coaches must be able to create plans and schedule sessions within them.
- Every session, video, tag and annotation must belong to the organisation and to its parent plan, session or video.
- Videos must be registered with a reference to the stored file; this module does not store media itself.
- Drill tags must refer to a drill in the repository.
- Annotations must be time-coded and attributed to their author.
- Athletes must be able to view their assigned plans, sessions and reviewed videos without being able to change them.
- Access must follow the permission keys in `contracts/permissions.yaml` and the organisation boundary.

## 6. Interfaces

- **API:** `contracts/openapi.yaml` — plans, sessions, drills, videos, video annotations and drill tags under `/api/v1/training-video-analysis`.
- **Events:** `contracts/events.yaml` — `plan.created`, `session.scheduled`, `session.completed`, `video.uploaded`, `video.tagged`, `annotation.added`.
- **Permissions:** `contracts/permissions.yaml` — read and write keys per resource, plus `video:upload`, `video:tag` and `annotation:write`; default roles for admin, coach and athlete.

## 7. Module Boundary

This module owns training plans, sessions, drills, video metadata, drill tags and annotations.

It must not directly import code from other modules under `modules/`.

Integration with other modules must happen through published API contracts and events.

## 8. Success Criteria

Coaches can plan and run training and give athletes precise, time-coded video feedback, with every record scoped to the organisation and protected by permission keys.
