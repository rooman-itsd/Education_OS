import { Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { getDepartmentReportsWidget } from "../api/client";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/**
 * reporting.department-reports on Department Admin dashboard:
 * Departmental operational metrics and recent reports.
 */
export function DepartmentReports(_props: WidgetProps) {
  const load = useWidgetData((signal) => getDepartmentReportsWidget(undefined, signal), "department reports");
  const data = load.state === "ready" ? load.data : null;
  const empty =
    data && data.recent_reports.length === 0
      ? { title: "No department reports", body: "No recent reports generated for this department." }
      : null;

  return (
    <WidgetStatus load={load} empty={empty} icon={<Icons.FileText />} lines={5}>
      {data && (
        <div>
          <div className="flex gap-4 p-3 bg-muted/20 rounded-md mb-3 text-sm">
            <div>
              <span className="text-muted-foreground block text-xs">Attendance</span>
              <span className="font-semibold">{data.attendance_rate}%</span>
            </div>
            <div>
              <span className="text-muted-foreground block text-xs">Pass Rate</span>
              <span className="font-semibold">{data.exam_pass_rate}%</span>
            </div>
            <div>
              <span className="text-muted-foreground block text-xs">Faculty Load</span>
              <span className="font-semibold">{data.faculty_load_average} hrs</span>
            </div>
          </div>
          <List divided label="Recent department reports">
            {data.recent_reports.map((r, i) => (
              <ListRow
                key={r.id}
                index={i}
                icon={Icons.FileText}
                title={r.title}
                meta={data.department_name}
              />
            ))}
          </List>
        </div>
      )}
    </WidgetStatus>
  );
}

