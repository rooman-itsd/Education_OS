import type { DashboardWidget } from "@eos/ui-kit";
import { ExamDuties } from "./ExamDuties";
import { ExamSchedule } from "./ExamSchedule";
import { HallTicketsIssued } from "./HallTicketsIssued";
import { ResultsPending } from "./ResultsPending";
import "./widgets.css";

/**
 * Dashboard widgets exported by examinations.
 * Ids are "examinations.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 *
 * Data, endpoint and permission per the PRD, section 7 (PR #183): the three Examination Staff widgets, and
 * examinations.exam-duties for the Faculty dashboard.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "examinations.schedule",
    title: "Exam schedule",
    permission: "examinations:session:read",
    kind: "list",
    size: "2x2",
    component: ExamSchedule,
  },
  {
    id: "examinations.hall-tickets-issued",
    title: "Hall tickets issued",
    permission: "examinations:hall-ticket:read-all",
    kind: "panel",
    size: "2x1",
    component: HallTicketsIssued,
  },
  {
    id: "examinations.results-pending",
    title: "Results pending",
    permission: "examinations:report:read-all",
    kind: "panel",
    size: "2x1",
    component: ResultsPending,
  },
  {
    id: "examinations.exam-duties",
    title: "My exam duties",
    permission: "examinations:duty:read-own",
    kind: "list",
    size: "2x1",
    component: ExamDuties,
  },
];
