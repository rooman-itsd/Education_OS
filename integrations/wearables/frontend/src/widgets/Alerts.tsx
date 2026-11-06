import { Badge, Icons, type WidgetProps } from "@eos/ui-kit";
import { getAlerts, type Alert, type AlertKind } from "../api/client";
import { athleteHandle, dayOf, KIND_LABEL, PROVIDER_LABEL } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

const EMPTY = {
  title: "No device problems",
  body: "Athletes whose watch link expired, was removed, stopped syncing or went quiet appear here.",
  icon: <Icons.Activity />,
};

/** The tone says how urgent, the label says what: neither carries the meaning alone. */
const TONE: Record<AlertKind, "danger" | "warning" | "neutral"> = {
  link_revoked: "danger",
  sync_failing: "danger",
  link_expired: "warning",
  no_recent_data: "warning",
  not_linked: "neutral",
};
const SHOWN = 8;

function Row({ alert }: { alert: Alert }) {
  const since = dayOf(alert.since);
  const provider = alert.provider ? (PROVIDER_LABEL[alert.provider] ?? alert.provider) : null;
  return (
    <li className="eos-wearables__row">
      <span className="eos-wearables__who">{athleteHandle(alert.person_id)}</span>
      <Badge tone={TONE[alert.kind]}>{KIND_LABEL[alert.kind] ?? alert.kind}</Badge>
      <span className="eos-wearables__muted">{[provider, since ? `since ${since}` : null].filter(Boolean).join(", ")}</span>
    </li>
  );
}

/**
 * wearables.alerts on the Coach dashboard: which athletes' device links expired or were removed, whose sync keeps failing, or
 * who sent no data for a while (GET /alerts). Statuses and dates only, never a reading, and nothing from Strava beyond
 * "linked". Read-only. The widget has no way to learn the coach's squad without importing another module, so it shows the
 * organisation's problems; the API takes a person_id filter for the day the shell can pass the squad.
 */
export function Alerts(_props: WidgetProps) {
  const load = useWidgetData((signal) => getAlerts({ limit: 50 }, signal));
  const page = load.state === "ready" ? load.data : null;
  const items = page?.items ?? [];

  return (
    <WidgetStatus load={load} empty={page && items.length === 0 ? EMPTY : null} lines={4}>
      {page && (
        <div className="eos-wearables">
          <h3 className="eos-wearables__heading">{items.length === 1 ? "1 athlete needs attention" : `${items.length}${page.next_cursor ? "+" : ""} athletes need attention`}</h3>
          <ul className="eos-wearables__list" aria-label="Device alerts">
            {items.slice(0, SHOWN).map((a) => (
              <Row key={`${a.person_id}:${a.kind}:${a.provider ?? ""}`} alert={a} />
            ))}
          </ul>
          {(items.length > SHOWN || page.next_cursor) && (
            <p className="eos-wearables__muted">{items.length > SHOWN ? `and ${items.length - SHOWN}${page.next_cursor ? "+" : ""} more` : "and more"}</p>
          )}
        </div>
      )}
    </WidgetStatus>
  );
}
