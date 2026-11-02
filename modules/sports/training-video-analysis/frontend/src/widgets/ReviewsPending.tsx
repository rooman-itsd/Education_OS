import { Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { listVideos } from "../api/client";
import { dayOf, duration, videos } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** Rows listed, most recently recorded first (the server's order), before "and N more". */
export const SHOWN = 6;

const EMPTY = { title: "No videos waiting for review", body: "Training and match videos nobody has annotated yet appear here." };

/**
 * training-video-analysis.reviews-pending on the Coach dashboard: training videos waiting for the coach's review,
 * that is videos with no annotation yet (the contract has no review status). One request:
 * GET /videos?annotated=false, whose total counts every such video, not only the rows shown.
 */
export function ReviewsPending(_props: WidgetProps) {
  const load = useWidgetData((signal) => listVideos({ annotated: false, limit: SHOWN }, signal));
  const data = load.state === "ready" ? load.data : null;
  const rest = data ? data.total - data.items.length : 0;
  return (
    <WidgetStatus load={load} empty={data && data.total === 0 ? EMPTY : null} lines={4} icon={<Icons.MonitorPlay />}>
      {data && (
        <div className="eos-tva">
          <dl className="eos-tva__summary" aria-label="Review summary">
            <div className="eos-tva__headline" data-warn>
              <dt>Waiting for review</dt>
              <dd>{data.total}</dd>
            </div>
          </dl>
          <List divided label="Videos waiting for review">
            {data.items.map((v, i) => (
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
          {rest > 0 && <p className="eos-tva__muted">{`and ${videos(rest)} more`}</p>}
        </div>
      )}
    </WidgetStatus>
  );
}
