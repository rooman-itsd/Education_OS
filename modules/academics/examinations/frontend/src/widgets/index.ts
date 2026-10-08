import type { DashboardWidget } from "@eos/ui-kit";
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
 * Examination Staff widgets: data, endpoint and permission per the PRD, section 7 (PR #183).
 */
export const widgets: DashboardWidget[] = [
  {
    id: "examinations.schedule",
    title: "Exam schedule",
    permission: "examinations:session:read",
    size: "2x2",
    component: ExamSchedule,
  },
  {
    id: "examinations.hall-tickets-issued",
    title: "Hall tickets issued",
    permission: "examinations:hall-ticket:read-all",
    size: "2x1",
    component: HallTicketsIssued,
  },
  {
    id: "examinations.results-pending",
    title: "Results pending",
    permission: "examinations:report:read-all",
    size: "2x1",
    component: ResultsPending,
  },
];
