# Sports Nutrition & Health — Product Requirements

## 1. Purpose

The Sports Nutrition & Health module manages athletes' diet plans, confidential health records, injuries and physiotherapy, medical and nutrition appointments, so that nutritionists, medical staff and coaches can keep athletes healthy and available to train.

## 2. Scope

### In scope
- Nutrition (diet) plans per athlete, with goals, daily targets and meals
- Scheduled reviews of nutrition plans
- Confidential health records: medical history, allergies, medication, screenings, vaccinations
- Injury tracking from report to recovery
- Physiotherapy, medical and nutrition appointments

### Out of scope
- Athlete profiles, performance metrics, fitness testing, benchmarks and fitness clearance (athlete-performance)
- Training plans, sessions and video (training-video-analysis)
- Tournament and fixture management (tournament-events)
- Hospital, pharmacy or insurance systems
- Payments and billing

## 3. Users

- Nutritionist
- Medical Staff (Doctor / Physio)
- Coach
- Athlete
- Institution Administrator

## 4. Core Features

### Nutrition Plans
Create a plan for an athlete with a goal (performance, weight gain, weight loss, recovery or maintenance), daily calorie and macronutrient targets, meals, dates and a review date.

### Plan Reviews
Record a review with the outcome (continue, adjust or end), body weight and the next review date, so plans due for review are visible.

### Health Records
Keep confidential medical information for an athlete, readable only by medical roles.

### Injury Tracking
Report an injury with body part, type, severity and context; follow it through active, recovering and resolved, with an expected return date.

### Appointments
Schedule physiotherapy, medical and nutrition appointments with a practitioner, optionally linked to an injury, and mark them completed, cancelled or missed.

## 5. Key Requirements

- Nutritionists must be able to create, update and review nutrition plans.
- Medical staff must be able to keep health records, report and update injuries, and schedule appointments.
- Health records must be visible only to medical roles; coaches see injury status and expected return, not clinical notes or records.
- Athletes must see only their own plans, injuries and appointments.
- Events must carry ids, status and dates only, never clinical detail.
- Every record must belong to the organisation (row-level security on `organisation_id`).

## 6. Interfaces

- **API:** `contracts/openapi.yaml` — nutrition plans and their reviews, health records, injuries and appointments under `/api/v1/sports-nutrition-health`.
- **Events:** `contracts/events.yaml` — `plan.created`, `plan.reviewed`, `injury.reported`, `injury.resolved`, `appointment.scheduled`, `appointment.completed`.
- **Permissions:** `contracts/permissions.yaml` — keys for plans, plan reviews, health records, injuries and appointments; default roles for admin, medical staff, nutritionist, coach and athlete.
- **Dashboards:** supports the widgets named in the role layouts: `injured-athletes` and `appointments-today` (Medical Staff), `athletes-on-plans` and `plan-reviews-due` (Nutritionist), `nutrition-plan` (Athlete).

## 7. Module Boundary

This module owns nutrition plans, plan reviews, health records, injuries and appointments.

It must not directly import code from other modules under `modules/`. Athletes are referenced by the athlete id published by athlete-performance.

Integration with other modules must happen through published API contracts and events.

## 8. Success Criteria

Nutritionists, medical staff and coaches share one accurate, confidential view of each athlete's nutrition, injuries and treatment, so decisions about training and selection are based on current health information.
