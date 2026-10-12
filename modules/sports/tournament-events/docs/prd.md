# Tournament & Events — Product Requirements

## 1. Purpose

The Tournament & Events module manages the competitions an institution hosts or takes part in: tournaments, athlete and team entries, fixtures, results, officials and travel and event logistics.

## 2. Scope

### In scope
- Tournaments at intra-institution, inter-university, state, national and international level
- Publishing and cancelling tournaments
- Athlete and team entries per category
- Fixtures: matches, heats and rounds with time, venue and participants
- Results and placings per fixture
- Officials assigned to a tournament or fixture
- Travel and event logistics
- A calendar of tournaments and fixtures

### Out of scope
- Athlete profiles, performance metrics and benchmarks (athlete-performance)
- Training plans, sessions and video (training-video-analysis)
- Nutrition, medical and injury records (sports-nutrition-health)
- Facility registry and booking (sports-facilities, facility-booking)
- Ticketing, prize money and payments

## 3. Users

- Coach
- Sports Staff
- Athlete
- Management
- Institution Administrator

## 4. Core Features

### Tournaments
Create a tournament with discipline, level, format, dates, venue, hosting (home, away or neutral) and registration deadline; keep it as a draft until it is published, and cancel it with a reason if needed.

### Entries
Enter athletes or teams in a category; confirm or withdraw entries.

### Fixtures
Schedule matches, heats or rounds with their entries, time and venue; postpone, cancel or complete them.

### Results
Record placings, scores or marks for a fixture; recording a result completes the fixture.

### Officials
Assign referees, umpires, judges, timekeepers, technical officials and team managers to a tournament or a fixture.

### Logistics
Keep travel mode, departure and return times, accommodation, the number travelling and a contact person for each tournament.

### Calendar
Show published tournaments and their fixtures between two dates.

## 5. Key Requirements

- Authorised staff must be able to create tournaments, keep them as drafts and publish them.
- Draft tournaments must be visible only to organisers.
- Coaches must be able to enter athletes, follow fixtures and record results.
- Results must identify the athletes behind each entry so performance records can follow.
- Athletes must be able to see tournaments, their entries, fixtures, results and travel plans.
- Every record must belong to the organisation (row-level security on `organisation_id`).

## 6. Interfaces

- **API:** `contracts/openapi.yaml` — tournaments, entries, fixtures, results, officials, logistics and the calendar under `/api/v1/tournament-events`.
- **Events:** `contracts/events.yaml` — `tournament.created`, `tournament.published`, `tournament.cancelled`, `entry.confirmed`, `fixture.scheduled`, `result.recorded`, `official.assigned`.
- **Permissions:** `contracts/permissions.yaml` — keys for tournaments (read, write, publish), entries, fixtures, results, officials and logistics; default roles for admin, coach, athlete and viewer.
- **Dashboards:** supports the widgets named in the role layouts: `tournament-events.upcoming` (Athlete) and `tournament-events.calendar` (Coach).

## 7. Module Boundary

This module owns tournaments, entries, fixtures, results, officials and logistics.

It must not directly import code from other modules under `modules/`. Athletes are referenced by the athlete id published by athlete-performance; `tournament-events.result.recorded` lets athlete-performance record competition results.

Integration with other modules must happen through published API contracts and events.

## 8. Success Criteria

Staff can run a tournament from announcement to results in one place, and athletes and coaches always know what is coming up, where they are travelling and how they performed.
