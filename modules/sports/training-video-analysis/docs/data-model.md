# training-video-analysis — data model

Every table is prefixed `training_video_analysis_`, carries `organisation_id` and gets the `tenant_isolation`
row-level-security policy on Postgres (`db/migrations/versions/20261030_0001_initial.py`). Foreign keys stay inside
the module; ids of other modules and platform services are plain values.

| Table | Holds | References |
|---|---|---|
| `plan` | Title, description, dates, status, objectives | `coach_id`, `squad_id` (plain ids) |
| `drill` | The drill repository; `code` unique per organisation | — |
| `session` | Schedule (UTC), location, status, drill ids, notes, actual duration, `completed_at` | `plan_id` → plan; `coach_id`, `facility_id` (plain ids) |
| `session_attendee` | One row per athlete of a session, in the order given | `session_id` → session; `athlete_id` (athlete-performance's id) |
| `video` | Title, `video_url` and `thumbnail_url` (references to platform/documents), duration, resolution, `recorded_at` | `session_id` → session; `uploader_id`, `registered_by` (user ids) |
| `drill_tag` | A segment of a video's timeline | `video_id` → video; `drill_id` → drill |
| `annotation` | Time-coded content, category, drawing markup | `video_id` → video; `author_id` (user id) |
| `annotation_athlete` | One row per athlete an annotation is about | `annotation_id` → annotation; `athlete_id` |
| `athlete_link` | Which user is which athlete, with the time and id of the event that set it | `athlete_id`, `user_id` |
| `audit_entry` | Interim audit records shaped like platform/audit's `Record` | `entity_id` |

Attendees and tagged athletes are rows rather than JSON lists so that "the sessions and annotations of this athlete"
is an indexed query (`ix_..._athlete_id`) and lists load them for a whole page in one query.
