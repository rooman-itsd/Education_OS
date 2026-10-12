# Sports Facilities — Product Requirements

## 1. Purpose

The Sports Facilities module keeps the registry of an institution's sports grounds, courts, pools, gyms and tracks, their availability, and how they are used.

## 2. Scope

### In scope
- A registry of sports facilities: type, sports, surface, indoor or outdoor, capacity and location
- Spaces within a facility that are used on their own (for example Court 2 or Lanes 1–4)
- Weekly operating hours
- Availability: operational, limited, closed or under maintenance, with a reason
- Usage records: who used a facility, when and for what
- Utilisation: hours used against hours open, by purpose

### Out of scope
- Booking and approving facility slots (facility-booking)
- Maintenance work orders (maintenance)
- Equipment and stock (inventory-equipment)
- Fixed asset register (asset-management)
- Classrooms, halls and other non-sports venues (facility-booking and other facilities modules)

## 3. Users

- Facility / Inventory Staff
- Coach
- Sports Staff
- Athlete
- Institution Administrator

## 4. Core Features

### Facility Registry
Register and update sports facilities with their type, sports, surface, indoor flag, capacity, location and description.

### Spaces
Divide a facility into spaces that can be used separately, each with its own capacity and sports.

### Operating Hours
Set opening and closing times for each day of the week.

### Availability
Open, limit or close a facility with a reason and an optional end time, for example for maintenance or weather.

### Usage Records
Record each use of a facility or space with its time, purpose (training, competition, physical education, recreation, event or maintenance), group and headcount, optionally linked to a facility-booking reference.

### Utilisation
Report hours used against hours open for a period, split by purpose.

## 5. Key Requirements

- Facility staff must be able to register facilities and keep their details, hours and availability current.
- Availability changes must be visible to coaches and athletes and announced to other modules.
- Coaches and facility staff must be able to record usage.
- Authorised users must be able to see utilisation for a facility and period.
- Every record must belong to the organisation (row-level security on `organisation_id`).

## 6. Interfaces

- **API:** `contracts/openapi.yaml` — facilities, spaces, operating hours, availability, usage records and utilisation under `/api/v1/sports-facilities`.
- **Events:** `contracts/events.yaml` — `facility.registered`, `facility.updated`, `availability.changed`, `usage.recorded`.
- **Permissions:** `contracts/permissions.yaml` — `facility:read`, `facility:write`, `facility:status`, `usage:read`, `usage:record`; default roles for admin, facility staff, coach and viewer.

## 7. Module Boundary

This module owns the sports facility registry, availability and usage records.

It must not directly import code from other modules under `modules/`. facility-booking references facilities by id and learns about them from `sports-facilities.facility.registered` and `sports-facilities.availability.changed`.

Integration with other modules must happen through published API contracts and events.

## 8. Success Criteria

The institution has one accurate, current list of its sports facilities, knows which are open, and can see how well they are used.
