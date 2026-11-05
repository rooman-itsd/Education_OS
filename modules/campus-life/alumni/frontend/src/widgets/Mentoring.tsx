import { Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { getMyMentoring, type MentorCard, type MyAssignment, type MySession } from "../api/client";
import { day, duration, indianDate, indianDateTime, MODE_LABEL, role, telHref, upcoming, webUrl } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

export const EMPTY = {
  title: "No mentor assigned yet",
  body: "Your alumni mentor and upcoming sessions appear here once one is assigned.",
  icon: <Icons.GraduationCap />,
};

/** A link that opens outside the dashboard, saying so to screen readers. */
function ExternalLink({ href, children }: { href: string; children: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
      <span className="eos-sr-only"> (opens in a new tab)</span>
    </a>
  );
}

/** The mentor's contact details, as the contract gives them to the assigned student. Nothing when none is given. */
function Contacts({ mentor }: { mentor: MentorCard }) {
  const email = mentor.email?.trim();
  const phone = mentor.phone?.trim();
  const tel = telHref(phone);
  const linkedin = webUrl(mentor.linkedin_url);
  if (!email && !phone && !linkedin) return null;
  return (
    <dl className="eos-alumni__contacts" aria-label={`Contact ${mentor.full_name}`}>
      {email && (
        <div>
          <dt>
            <Icons.Mail aria-hidden="true" /> Email
          </dt>
          <dd>
            <a href={`mailto:${email}`}>{email}</a>
          </dd>
        </div>
      )}
      {phone && (
        <div>
          <dt>
            <Icons.Phone aria-hidden="true" /> Phone
          </dt>
          <dd>{tel ? <a href={tel}>{phone}</a> : phone}</dd>
        </div>
      )}
      {linkedin && (
        <div>
          <dt>
            <Icons.Globe aria-hidden="true" /> LinkedIn
          </dt>
          <dd>
            <ExternalLink href={linkedin}>LinkedIn profile</ExternalLink>
          </dd>
        </div>
      )}
    </dl>
  );
}

/** Who the mentor is, what the mentoring is about and since when. */
function Mentor({ assignment }: { assignment: MyAssignment }) {
  const m = assignment.mentor;
  const job = role(m.current_designation, m.current_company);
  const background = [`Class of ${m.graduation_year}`, m.programme?.trim(), m.industry?.trim(), m.city?.trim()].filter(Boolean).join(" · ");
  const focus = assignment.focus?.trim();
  return (
    <section aria-label="Your mentor" className="eos-alumni__mentor">
      <h3 className="eos-alumni__name">{m.full_name}</h3>
      {job && <p className="eos-alumni__role">{job}</p>}
      <p className="eos-alumni__muted">{background}</p>
      <dl className="eos-alumni__facts">
        {focus && (
          <div>
            <dt>Focus</dt>
            <dd>{focus}</dd>
          </div>
        )}
        <div>
          <dt>Mentoring since</dt>
          <dd>{day(assignment.started_on)}</dd>
        </div>
      </dl>
      <Contacts mentor={m} />
    </section>
  );
}

/** Where the session happens: the mode, then the room, address or meeting link. */
function Place({ session }: { session: MySession }) {
  const location = session.location?.trim();
  const link = webUrl(location);
  return (
    <span>
      {MODE_LABEL[session.mode] ?? session.mode}
      {location && (
        <>
          {" · "}
          {link ? <ExternalLink href={link}>Meeting link</ExternalLink> : location}
        </>
      )}
    </span>
  );
}

function Sessions({ sessions }: { sessions: MySession[] }) {
  return (
    <section aria-label="Upcoming sessions">
      <h3 className="eos-alumni__heading">Upcoming sessions</h3>
      {sessions.length === 0 ? (
        <p className="eos-alumni__muted">No sessions scheduled.</p>
      ) : (
        <List divided label="Upcoming mentoring sessions">
          {sessions.map((s, i) => {
            const length = duration(s.duration_minutes);
            const topic = s.topic?.trim();
            return (
              <ListRow
                key={s.id}
                index={i}
                date={indianDate(s.scheduled_at)}
                title={<time dateTime={s.scheduled_at}>{indianDateTime(s.scheduled_at)}</time>}
                meta={
                  <span className="eos-alumni__meta">
                    {topic && <span>{topic}</span>}
                    <Place session={s} />
                    {length && <span>{length}</span>}
                  </span>
                }
              />
            );
          })}
        </List>
      )}
    </section>
  );
}

/**
 * alumni.mentoring on the management-student dashboard: the student's active alumni mentor (name, current role and
 * company, background, focus, start date and contact details) and their next five upcoming sessions with date and
 * time in India, topic, mode and place (GET /me/mentoring). Without an active mentor it shows the empty state.
 */
export function Mentoring(_props: WidgetProps) {
  const load = useWidgetData((signal) => getMyMentoring(signal));
  const data = load.state === "ready" ? load.data : null;
  const assignment = data?.assignment ?? null;

  return (
    <WidgetStatus load={load} empty={data && !assignment ? EMPTY : null} lines={5}>
      {assignment && (
        <div className="eos-alumni">
          <Mentor assignment={assignment} />
          <Sessions sessions={upcoming(data?.upcoming_sessions)} />
        </div>
      )}
    </WidgetStatus>
  );
}
