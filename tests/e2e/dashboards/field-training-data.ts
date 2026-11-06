import type { APIRequestContext } from "@playwright/test";
import type { DashboardUser } from "./organisation";
import { created, dayFromNow } from "./widgets";

/**
 * What the field-training data journeys set up through the API, as the roles of a clinical programme would
 * (the same setup serves the medical-student, clinical-supervisor and hospital-coordinator journeys; the agriculture
 * journeys pass their own `names`):
 * - the coordinator (field-training-coordinator) records a site, publishes an opening with two seats and assigns the
 *   trainee, which leaves one seat;
 * - with `start`, the coordinator starts the placement, the trainee logs hours for today and, with `verify`, the
 *   supervisor (field-training-supervisor, named on the site and the opening) verifies the entry.
 *
 * The placement began two days ago so the log date (today) falls inside it. Dates are plain days from now; the module
 * works in Asia/Kolkata, which is never behind the UTC day the helper takes.
 */
export const SITE = "City General Hospital";
export const OPENING = "Ward rotation";
export const REQUIRED_HOURS = 40;
export const LOGGED_HOURS = 4;

/** The words of one academy's setup: the site and its kind, the opening and its discipline, the trainee's log entry. */
export interface Names {
  site: string;
  siteKind: string;
  opening: string;
  discipline: string;
  activities: string;
}

const CLINICAL: Names = {
  site: SITE,
  siteKind: "Hospital",
  opening: OPENING,
  discipline: "Medicine",
  activities: "Observed ward rounds and assisted with patient intake",
};

/** The agriculture-college setup: a farm site and a rotation on it. */
export const FARM: Names = {
  site: "Demonstration Farm",
  siteKind: "Farm",
  opening: "Crop husbandry rotation",
  discipline: "Agronomy",
  activities: "Sowed a trial plot and recorded germination counts",
};

export interface Seeded {
  siteId: string;
  openingId: string;
  placementId: string;
  logId?: string;
}

interface Who {
  coordinator: DashboardUser;
  supervisor: DashboardUser;
  trainee: DashboardUser;
}

export async function seedPlacement(
  request: APIRequestContext,
  { coordinator, supervisor, trainee }: Who,
  {
    start = false,
    log = false,
    verify = false,
    names = CLINICAL,
  }: { start?: boolean; log?: boolean; verify?: boolean; names?: Names } = {},
): Promise<Seeded> {
  const site = await created<{ id: string }>(request, coordinator, "/field-training/sites", {
    name: names.site,
    kind: names.siteKind,
    supervisor_ids: [supervisor.id],
  });
  const opening = await created<{ id: string }>(request, coordinator, "/field-training/openings", {
    site_id: site.id,
    title: names.opening,
    discipline: names.discipline,
    starts_on: dayFromNow(-2),
    ends_on: dayFromNow(60),
    seats: 2,
    required_hours: REQUIRED_HOURS,
    supervisor_ids: [supervisor.id],
  });
  await created(request, coordinator, `/field-training/openings/${opening.id}/publish`, {});
  const placement = await created<{ id: string }>(request, coordinator, "/field-training/placements", {
    opening_id: opening.id,
    trainee_id: trainee.id,
  });
  const seeded: Seeded = { siteId: site.id, openingId: opening.id, placementId: placement.id };
  if (!start) return seeded;
  await created(request, coordinator, `/field-training/placements/${placement.id}/start`, {});
  if (!log) return seeded;
  const entry = await created<{ id: string }>(request, trainee, `/field-training/placements/${placement.id}/logs`, {
    date: dayFromNow(0),
    hours: LOGGED_HOURS,
    activities: names.activities,
  });
  seeded.logId = entry.id;
  if (verify) await created(request, supervisor, `/field-training/logs/${entry.id}/verify`, {});
  return seeded;
}
