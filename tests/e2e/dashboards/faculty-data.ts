import { expect, type APIRequestContext } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { addUser, type DashboardUser, type OrganisationAdmin } from "./organisation";

/**
 * The records behind the Faculty dashboard's data journey (faculty.spec.ts), created through the modules' own APIs, as
 * the roles that own them: a term, a course, an offering with one section taught by the faculty member, two students
 * enrolled and registered in it, an LMS course space with a published assignment both students submitted, and an exam
 * session and paper with an invigilation and an evaluation duty for the faculty member.
 *
 * Most of it depends on events between modules (an instructor reaches the LMS, a registration reaches the roster and
 * the course space), which the event-bus relay delivers a moment after the request that caused them: playwright's
 * warmup.ts starts it. A step that needs an earlier event retries until the event has arrived.
 */

export const COURSE = { code: "CS201", title: "Data Structures" };
export const SPACE_TITLE = "Data Structures 2026";
export const ASSIGNMENT = "Essay 1: Stacks and queues";
export const VENUE = "Hall A";
export const STUDENTS = ["Asha Rao", "Ben Okafor"] as const;

const AM = "/api/v1/academic-management";
const ER = "/api/v1/enrolment-registration";
const LMS = "/api/v1/lms";
const EX = "/api/v1/examinations";
const day = 24 * 3600 * 1000;
const iso = (offsetDays: number, hour?: number) => {
  const d = new Date(Date.now() + offsetDays * day);
  if (hour !== undefined) d.setUTCHours(hour, 0, 0, 0);
  return d.toISOString();
};

const as = (user: { token: string }) => ({ Authorization: `Bearer ${user.token}` });

async function body<T>(response: Awaited<ReturnType<APIRequestContext["post"]>>): Promise<T> {
  expect(response.ok(), `${response.url()} → ${response.status()} ${await response.text()}`).toBeTruthy();
  return (await response.json()) as T;
}
export const post = <T = Record<string, unknown>>(request: APIRequestContext, user: { token: string }, path: string, data: unknown = {}) =>
  request.post(path, { headers: as(user), data }).then((r) => body<T>(r));
const put = <T = Record<string, unknown>>(request: APIRequestContext, user: { token: string }, path: string, data: unknown) =>
  request.put(path, { headers: as(user), data }).then((r) => body<T>(r));
export const get = <T = Record<string, unknown>>(request: APIRequestContext, user: { token: string }, path: string) =>
  request.get(path, { headers: as(user) }).then((r) => body<T>(r));

/**
 * Retry a step that needs an event from an earlier one. Only the statuses an unarrived event explains are retried;
 * any other answer fails at once with what the API said.
 */
async function untilDelivered<T>(what: string, step: () => ReturnType<APIRequestContext["post"]>, retryOn = [403, 404, 409, 422]): Promise<T> {
  const deadline = Date.now() + 45_000;
  for (;;) {
    const response = await step();
    if (response.ok()) return (await response.json()) as T;
    if (!retryOn.includes(response.status()) || Date.now() > deadline) {
      throw new Error(`${what}: ${response.status()} ${await response.text()} (waited for the event relay)`);
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
}

export interface TeachingData {
  faculty: DashboardUser;
  /** A second faculty member who teaches nothing: whatever they see is not the first one's. */
  other: DashboardUser;
  hod: DashboardUser;
  students: DashboardUser[];
  term: { id: string };
  offering: { id: string; sections: { id: string; code: string }[] };
  space: { id: string };
  assignment: { id: string };
  paper: { id: string };
  session: { id: string };
}

export async function seedTeaching(request: APIRequestContext, admin: OrganisationAdmin, faculty: DashboardUser): Promise<TeachingData> {
  const hod = await addUser(request, admin, "department-admin");
  const other = await addUser(request, admin, "faculty", "faculty-two");
  const lmsAdmin = await addUser(request, admin, "lms-admin");
  const registrar = await addUser(request, admin, "registration-staff");
  const exams = await addUser(request, admin, "examination-staff");
  const students = [await addUser(request, admin, "student", "student-one"), await addUser(request, admin, "student", "student-two")];

  // academic-management: the term, the course and the offering that the faculty member teaches.
  const term = await post<{ id: string }>(request, admin, `${AM}/terms`, {
    code: "2026-ODD",
    name: "Odd term 2026",
    starts_on: iso(-30).slice(0, 10),
    ends_on: iso(120).slice(0, 10),
  });
  await post(request, admin, `${AM}/terms/${term.id}/activate`);
  const programme = await post<{ id: string }>(request, admin, `${AM}/programmes`, {
    code: "BTECH-CS",
    name: "B.Tech Computer Science",
    level: "undergraduate",
    department_id: randomUUID(),
    duration_terms: 8,
    credits_required: 160,
  });
  const course = await post<{ id: string }>(request, admin, `${AM}/courses`, {
    code: COURSE.code,
    title: COURSE.title,
    credits: 4,
    course_type: "theory",
    department_id: randomUUID(),
  });
  const created = await post<{ id: string }>(request, hod, `${AM}/offerings`, {
    course_id: course.id,
    academic_period_id: term.id,
    sections: [{ code: "A", capacity: 30 }],
  });
  await post(request, hod, `${AM}/offerings/${created.id}/faculty-assignments`, { faculty_id: faculty.id, role: "primary", contact_hours: 4 });
  await post(request, hod, `${AM}/offerings/${created.id}/status`, { status: "open" });
  const offering = await get<TeachingData["offering"]>(request, hod, `${AM}/offerings/${created.id}`);
  const section = offering.sections[0]!;

  // enrolment-registration: the students are enrolled in the programme and registered in the section.
  await put(request, registrar, `${ER}/terms/${term.id}/registration-window`, { opens_at: iso(-1), closes_at: iso(30) });
  for (const [i, name] of STUDENTS.entries()) {
    const enrolment = await post<{ id: string }>(request, registrar, `${ER}/programme-enrolments`, {
      person_id: students[i]!.id,
      student_name: name,
      programme_id: programme.id,
      start_academic_period_id: term.id,
    });
    await untilDelivered("registration", () =>
      request.post(`${ER}/registrations`, {
        headers: as(registrar),
        data: { programme_enrolment_id: enrolment.id, course_offering_id: offering.id, section_id: section.id, academic_period_id: term.id },
      }),
    );
  }

  // lms: a course space for the offering, an assignment the instructor publishes, a submission from each student.
  const space = await untilDelivered<{ id: string }>("course space", () =>
    request.post(`${LMS}/course-spaces`, { headers: as(lmsAdmin), data: { course_offering_id: offering.id, title: SPACE_TITLE } }),
  );
  await post(request, lmsAdmin, `${LMS}/course-spaces/${space.id}/status`, { status: "active" });
  const draft = await untilDelivered<{ id: string }>("assignment", () =>
    request.post(`${LMS}/course-spaces/${space.id}/assignments`, {
      headers: as(faculty),
      data: { title: ASSIGNMENT, due_at: iso(7), max_points: 10, submission_type: "text" },
    }),
  );
  await post(request, faculty, `${LMS}/assignments/${draft.id}/status`, { status: "published" });
  for (const [i, student] of students.entries()) {
    await untilDelivered("submission", () =>
      request.post(`${LMS}/assignments/${draft.id}/submissions`, { headers: as(student), data: { text: `Answer of ${STUDENTS[i]}` } }),
    );
  }

  // examinations: a cycle with one paper of the offering, a session in three days, and two duties of the faculty member.
  const scheme = await post<{ id: string }>(request, exams, `${EX}/grading-schemes`, {
    name: "Ten point",
    bands: [
      { min_percent: 0, max_percent: 40, grade: "F", grade_point: 0, is_pass: false },
      { min_percent: 40, max_percent: 100, grade: "P", grade_point: 6, is_pass: true },
    ],
  });
  await post(request, exams, `${EX}/grading-schemes/${scheme.id}/set-default`);
  const cycle = await post<{ id: string }>(request, exams, `${EX}/exam-cycles`, {
    academic_period_id: term.id,
    code: "2026-ODD-END",
    name: "Odd term end exams",
    cycle_type: "end_term",
    starts_on: iso(2).slice(0, 10),
    ends_on: iso(20).slice(0, 10),
    grading_scheme_id: scheme.id,
  });
  const assessment = await post<{ id: string }>(request, exams, `${EX}/assessment-schemes`, {
    course_offering_id: offering.id,
    pass_percent: 40,
    components: [{ code: "END", name: "End exam", kind: "written", weightage_percent: 100, max_marks: 100 }],
  });
  await post(request, exams, `${EX}/assessment-schemes/${assessment.id}/activate`);
  const papers = await post<{ items: { id: string }[] }>(request, exams, `${EX}/papers`, {
    exam_cycle_id: cycle.id,
    course_offering_id: offering.id,
    component_codes: ["END"],
  });
  const paper = papers.items[0]!;
  const session = await post<{ id: string }>(request, exams, `${EX}/sessions`, {
    exam_cycle_id: cycle.id,
    starts_at: iso(3, 9),
    ends_at: iso(3, 12),
    exam_paper_ids: [paper.id],
    venue_label: VENUE,
    invigilators_required: 1,
  });
  await post(request, exams, `${EX}/duties`, { staff_id: faculty.id, duty_type: "invigilation", exam_session_id: session.id });
  await post(request, exams, `${EX}/duties`, { staff_id: faculty.id, duty_type: "evaluation", exam_paper_id: paper.id });

  return { faculty, other, hod, students, term, offering, space, assignment: draft, paper, session };
}
