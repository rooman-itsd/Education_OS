import type { ReactNode } from "react";

export interface Column<Row> {
  key: string;
  header: ReactNode;
  /** Renders the cell; defaults to the row's field named `key`. */
  cell?: (row: Row) => ReactNode;
  /** Right-aligned tabular numbers. */
  numeric?: boolean;
  /** This column names the row; it renders as a row header for screen readers. */
  primary?: boolean;
  width?: string | number;
}

export interface DataTableProps<Row> {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  /** Text under the table, e.g. "Showing 9 of 9". */
  caption?: ReactNode;
  /** Shown when there are no rows. */
  empty?: ReactNode;
  /** Accessible name of the table. */
  label?: string;
}

/** A plain data table with a tinted header row and hover rows. Wrap long tables in a Panel. */
export function DataTable<Row extends Record<string, unknown>>({ columns, rows, rowKey, caption, empty = "Nothing to show", label }: DataTableProps<Row>) {
  return (
    <div className="eos-table-wrap">
      <table className="eos-table" aria-label={label}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} scope="col" className={c.numeric ? "eos-num" : undefined} style={c.width ? { width: c.width } : undefined}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length}>
                <div className="eos-empty">{empty}</div>
              </td>
            </tr>
          )}
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((c) => {
                const content = c.cell ? c.cell(row) : (row[c.key] as ReactNode);
                return c.primary ? (
                  <th key={c.key} scope="row" className="eos-table__primary" style={{ textAlign: "left", fontWeight: 600 }}>
                    {content}
                  </th>
                ) : (
                  <td key={c.key} className={c.numeric ? "eos-num" : undefined}>
                    {content}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {caption && <div className="eos-table__caption">{caption}</div>}
    </div>
  );
}
