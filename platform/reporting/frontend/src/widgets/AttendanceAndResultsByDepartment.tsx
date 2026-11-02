import { Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { getAttendanceAndResultsWidget } from "../api/client";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/**
 * reporting.attendance-and-results-by-department on Management dashboard:
 * Executive cross-department attendance & results comparison.
 */
export function AttendanceAndResultsByDepartment(_props: WidgetProps) {
  const load = useWidgetData((signal) => getAttendanceAndResultsWidget(signal), "attendance and results");
  const data = load.state === "ready" ? load.data : null;
  const empty =
    data && data.departments.length === 0
      ? { title: "No departmental metrics", body: "No departmental data available yet." }
      : null;

  return (
    <WidgetStatus load={load} empty={empty} icon={<Icons.Activity />} lines={5}>
      {data && (
        <div>
          <div className="flex gap-6 p-3 bg-muted/20 rounded-md mb-3 text-sm">
            <div>
              <span className="text-muted-foreground block text-xs">Avg Attendance</span>
              <span className="font-semibold">{data.institution_average_attendance}%</span>
            </div>
            <div>
              <span className="text-muted-foreground block text-xs">Avg Pass Rate</span>
              <span className="font-semibold">{data.institution_average_pass_rate}%</span>
            </div>
          </div>
          <List divided label="Department breakdown">
            {data.departments.map((d, i) => (
              <ListRow
                key={d.department_id}
                index={i}
                icon={d.is_attendance_low ? Icons.AlertTriangle : Icons.CheckCircle2}
                tone={d.is_attendance_low ? "warning" : "accent"}
                title={d.department_name}
                meta={`Attendance: ${d.attendance_rate}% · Pass: ${d.pass_rate}% · ${d.total_students} students`}
              />
            ))}
          </List>
        </div>
      )}
    </WidgetStatus>
  );
}
