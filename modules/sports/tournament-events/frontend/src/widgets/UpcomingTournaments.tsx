import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { listEntries, listFixtures, listTournaments, type Entry, type Fixture, type Tournament } from "../api/client";
import { dateTime, day, dayRange, ENTERED, isoDay, isoDayOf, LEVEL, tournaments } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** Tournaments listed, ongoing first and then by start date, before "and N more". */
export const SHOWN = 5;
/** The athlete's next fixtures listed. */
export const FIXTURES_SHOWN = 3;
/** Entries and fixtures read per tournament (the contract's maximum page). */
const PER_TOURNAMENT = 200;

const EMPTY = {
  title: "No upcoming tournaments",
  body: "Published tournaments appear here, with the ones you are entered in and your next fixtures.",
};

interface Row {
  tournament: Tournament;
  /** The athlete's own entries that are not withdrawn. */
  entries: Entry[];
  /** The athlete's fixtures still to be played (scheduled from now on, or in progress). */
  fixtures: Fixture[];
}

/** Whether the tournament still takes entries: until registration_closes_on (inclusive), and never after it ends. */
export function entriesOpen(t: Tournament, today: string): boolean {
  const closes = t.registration_closes_on && t.registration_closes_on < t.end_date ? t.registration_closes_on : t.end_date;
  return today <= closes;
}

function meta(r: Row, today: string): string {
  const t = r.tournament;
  const parts = [dayRange(t.start_date, t.end_date)];
  if (t.venue) parts.push(t.venue);
  parts.push(LEVEL[t.level] ?? t.level);
  if (r.entries.length > 0) parts.push(`Entered in ${[...new Set(r.entries.map((e) => e.category))].join(", ")}`);
  else if (entriesOpen(t, today) && t.registration_closes_on) parts.push(`Entries close on ${day(t.registration_closes_on)}`);
  return parts.join(" · ");
}

function EntryBadge({ r, today }: { r: Row; today: string }) {
  if (r.entries.length > 0) {
    const e = ENTERED[r.entries.some((x) => x.status === "confirmed") ? "confirmed" : "pending"];
    return <Badge tone={e.tone}>{e.label}</Badge>;
  }
  if (entriesOpen(r.tournament, today)) return <Badge tone="accent">Entries open</Badge>;
  return <Badge tone="neutral">Entries closed</Badge>;
}

/**
 * tournament-events.upcoming on the Athlete dashboard: the published tournaments that are on or still to come, with
 * whether the athlete is entered (their own entries: the backend narrows the entry list to the athlete's own) or can
 * still enter, and the athlete's next fixtures in the tournaments they are entered in.
 *
 * Requests: GET /tournaments?status=ongoing and ?status=published (effective status: published means not started
 * yet; drafts and cancelled ones are never listed), then for each tournament shown GET /tournaments/{id}/entries and,
 * where the athlete is entered, GET /tournaments/{id}/fixtures from today.
 */
export function UpcomingTournaments(_props: WidgetProps) {
  const load = useWidgetData(async (signal) => {
    const today = isoDay();
    const [ongoing, upcoming] = await Promise.all([
      listTournaments({ status: "ongoing", limit: SHOWN }, signal),
      listTournaments({ status: "published", limit: SHOWN }, signal),
    ]);
    // Ongoing ones started on or before today, published ones start after it: together they stay in date order.
    const shown = [...ongoing.items, ...upcoming.items].slice(0, SHOWN);
    const now = Date.now();
    const rows: Row[] = await Promise.all(
      shown.map(async (tournament) => {
        const entries = (await listEntries(tournament.id, { limit: PER_TOURNAMENT }, signal)).items.filter((e) => e.status !== "withdrawn");
        if (entries.length === 0) return { tournament, entries, fixtures: [] };
        const mine = new Set(entries.map((e) => e.id));
        const fixtures = (await listFixtures(tournament.id, { from: today, limit: PER_TOURNAMENT }, signal)).items.filter(
          (f) =>
            f.entry_ids.some((id) => mine.has(id)) &&
            (f.status === "in_progress" || (f.status === "scheduled" && new Date(f.scheduled_at).getTime() >= now)),
        );
        return { tournament, entries, fixtures };
      }),
    );
    return { today, rows, total: ongoing.total + upcoming.total };
  });
  const data = load.state === "ready" ? load.data : null;
  const next = (data?.rows ?? [])
    .flatMap((r) => r.fixtures.map((fixture) => ({ fixture, tournament: r.tournament })))
    .sort((a, b) => a.fixture.scheduled_at.localeCompare(b.fixture.scheduled_at))
    .slice(0, FIXTURES_SHOWN);
  const rest = data ? data.total - data.rows.length : 0;
  return (
    <WidgetStatus load={load} empty={data && data.total === 0 ? EMPTY : null} lines={5} icon={<Icons.Trophy />}>
      {data && (
        <div className="eos-te">
          <List divided label="Upcoming tournaments">
            {data.rows.map((r, i) => (
              <ListRow
                key={r.tournament.id}
                index={i}
                date={r.tournament.start_date}
                tone={r.entries.length > 0 ? "success" : "accent"}
                title={r.tournament.name}
                meta={meta(r, data.today)}
                trailing={
                  <span className="eos-te__trailing">
                    {r.tournament.status === "ongoing" && <Badge tone="info">Ongoing</Badge>}
                    <EntryBadge r={r} today={data.today} />
                  </span>
                }
              />
            ))}
          </List>
          {rest > 0 && <p className="eos-te__muted">{`and ${tournaments(rest)} more`}</p>}
          {next.length > 0 && (
            <section className="eos-te__section">
              <h3 className="eos-te__heading">Your next fixtures</h3>
              <List divided label="Your next fixtures">
                {next.map(({ fixture: f, tournament: t }, i) => (
                  <ListRow
                    key={f.id}
                    index={i}
                    date={isoDayOf(f.scheduled_at)}
                    tone="info"
                    title={f.category ? `${f.round} (${f.category})` : f.round}
                    meta={[t.name, dateTime(f.scheduled_at), f.venue ?? t.venue].filter(Boolean).join(" · ")}
                    trailing={f.status === "in_progress" ? <Badge tone="info">In progress</Badge> : undefined}
                  />
                ))}
              </List>
            </section>
          )}
        </div>
      )}
    </WidgetStatus>
  );
}
