import type { APIRequestContext } from "@playwright/test";
import type { DashboardUser } from "./organisation";
import { created, dayFromNow } from "./widgets";

/**
 * What the projects data journeys of the agriculture college set up through the API:
 * - a coordinator (projects:project:manage) creates an active research trial with the trainee as lead and the guide
 *   named, which needs no proposal and approval;
 * - with `milestone`, the guide (projects:milestone:manage, as a guide of the project) adds a milestone and, with
 *   `submit`, the trainee (projects:self:submit, as a member) submits it, which puts it in the guide's review queue.
 */
export const TRIAL = "Soil moisture trial";
export const MILESTONE = "Baseline soil sampling";

export interface SeededProject {
  projectId: string;
  milestoneId?: string;
}

interface Who {
  coordinator: DashboardUser;
  guide: DashboardUser;
  lead: DashboardUser;
}

export async function seedProject(
  request: APIRequestContext,
  { coordinator, guide, lead }: Who,
  { milestone = false, submit = false }: { milestone?: boolean; submit?: boolean } = {},
): Promise<SeededProject> {
  const project = await created<{ id: string }>(request, coordinator, "/projects/projects", {
    title: TRIAL,
    kind: "Research",
    starts_on: dayFromNow(0),
    ends_on: dayFromNow(90),
    lead_id: lead.id,
    guide_ids: [guide.id],
  });
  const seeded: SeededProject = { projectId: project.id };
  if (!milestone) return seeded;
  const added = await created<{ id: string }>(request, guide, `/projects/projects/${project.id}/milestones`, {
    title: MILESTONE,
    due_on: dayFromNow(30),
  });
  seeded.milestoneId = added.id;
  if (submit) await created(request, lead, `/projects/milestones/${added.id}/submissions`, { note: "Samples taken from all four plots" });
  return seeded;
}
