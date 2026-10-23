import { useCallback, useEffect, useState } from "react";
import { Badge, Button, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { AcademicManagementApiError, getMyOfferings, getRoster, type MyOffering, type RosterPage } from "../api/client";

type Load<T> = { kind: "loading" } | { kind: "error"; retry: boolean } | { kind: "ready"; data: T };

/** Retrying cannot fix a missing session (401) or a missing permission (403). */
function failed(e: unknown): { kind: "error"; retry: boolean } {
  const status = e instanceof AcademicManagementApiError ? e.status : 0;
  return { kind: "error", retry: status !== 401 && status !== 403 };
}

const aborted = (e: unknown) => (e as { name?: string })?.name === "AbortError";

const ROLE: Record<MyOffering["role"], string> = {
  primary: "Primary",
  co_instructor: "Co-instructor",
  teaching_assistant: "Teaching assistant",
};

/**
 * academic-management.course-roster on the Faculty dashboard: the offerings the caller teaches this term with their
 * enrolment (GET /me/offerings); choosing one lists its enrolled learners (GET /offerings/{id}/roster). The shell
 * renders the panel and its title; this is the body.
 */
export function CourseRoster(_props: WidgetProps) {
  const [offerings, setOfferings] = useState<Load<MyOffering[]>>({ kind: "loading" });
  const [chosen, setChosen] = useState<MyOffering | null>(null);

  const loadOfferings = useCallback((signal?: AbortSignal) => {
    setOfferings({ kind: "loading" });
    getMyOfferings(signal)
      .then((r) => setOfferings({ kind: "ready", data: r.items }))
      .catch((e: unknown) => {
        if (!aborted(e)) setOfferings(failed(e));
      });
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    loadOfferings(ctrl.signal);
    return () => ctrl.abort();
  }, [loadOfferings]);

  if (chosen) return <Roster offering={chosen} onBack={() => setChosen(null)} />;
  if (offerings.kind === "loading") return <SkeletonLines lines={3} />;
  if (offerings.kind === "error") {
    return (
      <ErrorState title="Could not load your courses" onRetry={offerings.retry ? () => loadOfferings() : undefined}>
        {offerings.retry ? "Check your connection and try again." : "You do not have access to course rosters."}
      </ErrorState>
    );
  }
  if (offerings.data.length === 0) {
    return (
      <EmptyState icon={<Icons.BookOpen />} title="No courses this term">
        Courses you are assigned to teach appear here.
      </EmptyState>
    );
  }
  return (
    <List divided label="Your courses this term">
      {offerings.data.map((o, i) => (
        <ListRow
          key={o.course_offering_id}
          index={i}
          title={`${o.course.code} · ${o.course.title}`}
          meta={
            <>
              {ROLE[o.role]}
              {o.sections.length > 0 && <> · {o.sections.map((s) => `${s.code} (${s.enrolled_count})`).join(", ")}</>}
            </>
          }
          trailing={<Badge tone="info">{`${o.enrolled_count} enrolled`}</Badge>}
          onClick={() => setChosen(o)}
        />
      ))}
    </List>
  );
}

function Roster({ offering, onBack }: { offering: MyOffering; onBack: () => void }) {
  const [roster, setRoster] = useState<Load<RosterPage>>({ kind: "loading" });

  const load = useCallback(
    (signal?: AbortSignal) => {
      setRoster({ kind: "loading" });
      getRoster(offering.course_offering_id, 200, signal)
        .then((data) => setRoster({ kind: "ready", data }))
        .catch((e: unknown) => {
          if (!aborted(e)) setRoster(failed(e));
        });
    },
    [offering.course_offering_id],
  );

  useEffect(() => {
    const ctrl = new AbortController();
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  const back = (
    <Button variant="ghost" size="sm" onClick={onBack}>
      All courses
    </Button>
  );
  const heading = `${offering.course.code} · ${offering.course.title}`;

  if (roster.kind === "loading") return <SkeletonLines lines={4} />;
  if (roster.kind === "error") {
    return (
      <ErrorState title={`Could not load the roster of ${heading}`} onRetry={roster.retry ? () => load() : undefined}>
        {back}
      </ErrorState>
    );
  }
  if (roster.data.items.length === 0) {
    return (
      <EmptyState icon={<Icons.Users />} title={`No learners enrolled in ${heading} yet`} action={back}>
        Learners appear here once their registration is confirmed.
      </EmptyState>
    );
  }
  return (
    <>
      {back}
      <List divided label={`Roster of ${heading}`}>
        {roster.data.items.map((e, i) => (
          <ListRow
            key={e.person_id + e.section_id}
            index={i}
            title={e.student_name ?? "Name not available"}
            meta={[e.roll_number, e.section_code && `Section ${e.section_code}`].filter(Boolean).join(" · ")}
          />
        ))}
      </List>
      {roster.data.total > roster.data.items.length && (
        <p className="eos-widget__status">{`Showing ${roster.data.items.length} of ${roster.data.total}`}</p>
      )}
    </>
  );
}
