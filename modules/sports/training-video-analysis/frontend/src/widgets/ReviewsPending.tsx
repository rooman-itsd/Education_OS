import { Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { listAnnotations, listVideos, type TrainingVideo } from "../api/client";
import { dayOf, duration, videos } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/**
 * Most recent videos checked for annotations. The contract has no review status and no annotation count on a video,
 * so finding the ones waiting takes one GET /videos/{id}/annotations per video; this caps those requests.
 */
export const CHECKED = 20;
/** Rows listed before "and N more". */
export const SHOWN = 6;

const NO_VIDEOS = { title: "No training videos yet", body: "Uploaded training and match videos waiting for your review appear here." };
const ALL_REVIEWED = { title: "All videos reviewed", body: "Every recent video has at least one annotation." };

export interface ReviewQueue {
  /** Videos with no annotation yet, newest recording first (the server's order). */
  pending: TrainingVideo[];
  /** How many of the most recent videos were checked (at most CHECKED). */
  checked: number;
  /** Every video the caller can see. */
  total: number;
}

/** The most recent CHECKED videos, and which of them nobody has annotated yet. */
export async function loadReviewQueue(signal: AbortSignal): Promise<ReviewQueue> {
  const page = await listVideos(CHECKED, signal);
  const recent = page.items.slice(0, CHECKED);
  const annotations = await Promise.all(recent.map((v) => listAnnotations(v.id, signal)));
  return {
    pending: recent.filter((_, i) => annotations[i]!.length === 0),
    checked: recent.length,
    total: page.total,
  };
}

/**
 * training-video-analysis.reviews-pending on the Coach dashboard: training videos waiting for the coach's review,
 * that is videos with no annotation yet (the contract has no review status). GET /videos gives the most recent
 * CHECKED videos, then GET /videos/{id}/annotations for each; older videos are not checked, and the widget says so.
 */
export function ReviewsPending(_props: WidgetProps) {
  const load = useWidgetData(loadReviewQueue);
  const data = load.state === "ready" ? load.data : null;
  const empty = !data ? null : data.total === 0 ? NO_VIDEOS : data.pending.length === 0 && data.total <= data.checked ? ALL_REVIEWED : null;
  const shown = data ? data.pending.slice(0, SHOWN) : [];
  const rest = data ? data.pending.length - shown.length : 0;
  return (
    <WidgetStatus load={load} empty={empty} lines={4} icon={<Icons.MonitorPlay />}>
      {data && (
        <div className="eos-tva">
          <dl className="eos-tva__summary" aria-label="Review summary">
            <div className="eos-tva__headline" data-warn={data.pending.length > 0 || undefined}>
              <dt>Waiting for review</dt>
              <dd>{data.pending.length}</dd>
            </div>
            <div>
              <dt>Reviewed</dt>
              <dd>{data.checked - data.pending.length}</dd>
            </div>
          </dl>
          {shown.length > 0 ? (
            <List divided label="Videos waiting for review">
              {shown.map((v, i) => (
                <ListRow
                  key={v.id}
                  index={i}
                  icon={Icons.MonitorPlay}
                  tone="warning"
                  title={v.title}
                  meta={`Recorded ${dayOf(v.recorded_at)}`}
                  trailing={<span className="eos-tva__duration">{duration(v.duration_seconds)}</span>}
                />
              ))}
            </List>
          ) : (
            <p className="eos-tva__muted">{`None of the ${videos(data.checked)} checked is waiting for review.`}</p>
          )}
          {rest > 0 && <p className="eos-tva__muted">{`and ${videos(rest)} more`}</p>}
          {data.total > data.checked && (
            <p className="eos-tva__muted">{`Checked the ${data.checked} most recent of ${videos(data.total)}.`}</p>
          )}
        </div>
      )}
    </WidgetStatus>
  );
}
