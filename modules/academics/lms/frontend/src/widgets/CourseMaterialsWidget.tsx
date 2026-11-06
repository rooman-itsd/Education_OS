import { useCallback } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type BadgeTone, type WidgetProps } from "@eos/ui-kit";
import { getMyCourseMaterials, type MaterialType } from "../api/client";
import { useWidgetData } from "./useWidgetData";

/** How many materials the dashboard card shows. */
export const MATERIAL_LIMIT = 5;

const TYPE: Record<MaterialType, { label: string; tone: BadgeTone }> = {
  document: { label: "Document", tone: "info" },
  link: { label: "Link", tone: "neutral" },
  page: { label: "Page", tone: "accent" },
};

/**
 * lms.course-materials on the Student dashboard and every layout extending it: materials recently published in the
 * caller's course spaces, newest first (GET /me/course-materials). The shell renders the panel and its title; this
 * is the body.
 */
export function CourseMaterialsWidget(_props: WidgetProps) {
  const fetcher = useCallback((signal?: AbortSignal) => getMyCourseMaterials(MATERIAL_LIMIT, signal), []);
  const { state, reload } = useWidgetData(fetcher, "course materials");

  if (state.kind === "loading") return <SkeletonLines lines={3} />;
  if (state.kind === "error") {
    const { title, detail, retry } = state.failure;
    return (
      <ErrorState title={title} onRetry={retry ? reload : undefined}>
        {detail}
      </ErrorState>
    );
  }
  const items = state.data.items;
  if (items.length === 0) {
    return (
      <EmptyState icon={<Icons.BookOpen />} title="No new course materials">
        Notes, links and documents your instructors publish appear here.
      </EmptyState>
    );
  }

  return (
    <List divided label="Course materials">
      {items.map((m, i) => {
        const type = TYPE[m.material_type] ?? TYPE.page;
        return (
          <ListRow
            key={m.material_id}
            index={i}
            date={m.published_at.slice(0, 10)}
            title={m.title}
            meta={m.course_title ?? "Course"}
            trailing={<Badge tone={type.tone}>{type.label}</Badge>}
          />
        );
      })}
    </List>
  );
}
