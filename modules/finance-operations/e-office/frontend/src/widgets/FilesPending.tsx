import { Badge, Icons, List, ListRow, type BadgeTone, type WidgetProps } from "@eos/ui-kit";
import { getInbox, type FileSummary, type Inbox, type Priority } from "../api/client";
import { day, indianDay, PRIORITY_LABEL, sentence } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** How many of the files waiting longest the widget lists; the counts cover all of them. */
export const LIST_LIMIT = 5;

const EMPTY = {
  title: "No files pending",
  body: "Files sent to you for action appear here.",
  icon: <Icons.FolderOpen />,
};

/** Badge tone of a priority above normal. Normal files carry no priority badge. */
const PRIORITY_TONE: Record<Priority, BadgeTone | null> = {
  normal: null,
  urgent: "warning",
  immediate: "danger",
};

function isEmpty(inbox: Inbox | null): boolean {
  if (!inbox) return false;
  return (inbox.total ?? 0) === 0 && (inbox.items ?? []).length === 0 && (inbox.unattached_receipts ?? 0) === 0;
}

/** One figure of the summary. */
function Figure({ label, value, warn = false }: { label: string; value: number | undefined; warn?: boolean }) {
  return (
    <div data-warn={warn || undefined}>
      <dt>{label}</dt>
      <dd>{value ?? 0}</dd>
    </div>
  );
}

/** When the holding falls due, or, without a due date, when the file was received. */
function when(f: FileSummary): string {
  return f.due_on ? `Due ${day(f.due_on)}` : `Received ${indianDay(f.held_since)}`;
}

function FileRow({ file, index }: { file: FileSummary; index: number }) {
  const action = sentence(file.action_required);
  const priorityTone = PRIORITY_TONE[file.priority] ?? null;
  return (
    <ListRow
      index={index}
      icon={Icons.FileText}
      tone={file.overdue ? "danger" : "accent"}
      title={file.number}
      meta={
        <span className="eos-e-office__meta">
          <span className="eos-e-office__subject">{file.subject}</span>
          {action && <span>{action}</span>}
          <span>{when(file)}</span>
        </span>
      }
      trailing={
        (file.overdue || priorityTone) && (
          <span className="eos-e-office__trailing">
            {file.overdue && <Badge tone="danger">Overdue</Badge>}
            {priorityTone && <Badge tone={priorityTone}>{PRIORITY_LABEL[file.priority]}</Badge>}
          </span>
        )
      }
    />
  );
}

/**
 * e-office.files-pending on the HR Staff dashboard: how many open files the viewer holds, how many of them are
 * urgent and overdue, receipts still to attach to a file, and the files waiting longest with their subject, the
 * action asked for and the due date (GET /me/inbox).
 */
export function FilesPending(_props: WidgetProps) {
  const load = useWidgetData((signal) => getInbox(LIST_LIMIT, signal));
  const inbox = load.state === "ready" ? load.data : null;
  const overdue = inbox?.overdue ?? 0;
  const receipts = inbox?.unattached_receipts ?? 0;
  const items = inbox?.items ?? [];
  const total = inbox?.total ?? 0;

  return (
    <WidgetStatus load={load} empty={isEmpty(inbox) ? EMPTY : null} lines={5}>
      {inbox && (
        <div className="eos-e-office">
          <dl className="eos-e-office__summary">
            <Figure label="Pending" value={inbox.total} />
            <Figure label="Urgent" value={inbox.urgent} />
            <Figure label="Overdue" value={inbox.overdue} warn={overdue > 0} />
          </dl>
          {overdue > 0 && (
            <p className="eos-e-office__alert">
              <Badge tone="danger">{overdue === 1 ? "1 file overdue" : `${overdue} files overdue`}</Badge>
            </p>
          )}
          {receipts > 0 && (
            <p className="eos-e-office__muted">
              {receipts === 1 ? "1 letter received to attach to a file" : `${receipts} letters received to attach to a file`}
            </p>
          )}
          {items.length > 0 && (
            <section aria-label="Files waiting longest">
              <h3 className="eos-e-office__heading">Waiting longest</h3>
              <List divided label="Files waiting longest">
                {items.map((f, i) => (
                  <FileRow key={f.id} file={f} index={i} />
                ))}
              </List>
              {total > items.length && <p className="eos-e-office__muted">{`Showing ${items.length} of ${total} files`}</p>}
            </section>
          )}
        </div>
      )}
    </WidgetStatus>
  );
}
