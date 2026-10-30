# enrolment-registration — user stories

## Registration staff
- As registration staff, I can enrol a person in a programme from a starting term, and the module gives them a
  roll number, so every student has one identifier the whole institution uses.
- As registration staff, I can search enrolments by name, roll number, programme or status, so I find a student
  quickly.
- As registration staff, I can open and close a term's registration window, so regular registrations happen only
  when the academic calendar allows.
- As registration staff, I can register a student for a course offering and section, and I am told clearly when it
  is refused (not enrolled, already registered, offering or section closed, section full, window closed).
- As registration staff, I can register a whole batch for one offering and section in one go, and see which
  students succeeded and why the others did not, so one bad row does not stop the rest.
- As registration staff, I can register a student for a supplementary or backlog course outside the window, so
  examinations knows they are candidates.
- As registration staff, I can move a student to another section from a given date, so the timetable and roster
  follow the change.
- As registration staff, I can withdraw a registration or a whole enrolment, and the history is kept.

## Examination staff
- As examination staff, I can see how many candidates are registered this term and for which courses, including
  supplementary and backlog, so I can plan exams.

## Management, organisation admin, department admin
- As management, I can read enrolments and registrations, so I can answer "how many students are on each course"
  without asking the academic office.

## Other modules (consumers, not callers)
- As academic-management, I receive `course-registration.confirmed`, `.withdrawn` and `section-allocation.changed`
  and keep my roster from them, without calling this module.
- As examinations, I learn each registration's type (regular, supplementary, backlog) from the same events.
- As timetable-attendance, I learn when a section change takes effect.
