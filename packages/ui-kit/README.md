# packages/ui-kit

The Education OS design system: tokens, styles, components, the app shell and the **dashboard
widget contract**. React + TypeScript, plain CSS, no runtime dependency beyond React. Consumed by
`apps/frontend` and every module frontend. How to use it: [docs/architecture/frontend-design-system.md](../../docs/architecture/frontend-design-system.md).

```
import "@eos/ui-kit/styles.css";
import { AppShell, PageHero, StatGrid, Panel, DataTable, Figure, WidgetFrame, Icons } from "@eos/ui-kit";
```

| Export | Purpose |
|---|---|
| `styles.css` | Tokens (`--eos-*`), base styles, components and shell. Import once per app. |
| `Button`, `Badge`, `Panel`, `PanelHeader`, `PanelBody`, `PanelFooter`, `PanelLink` | Building blocks |
| `StatCard`, `StatGrid`, `CountUp` | Key figures that count up |
| `PageHero` | The page header, the one gradient surface on a page |
| `DataTable`, `List`, `ListRow`, `ProgressBar`, `ProgressList`, `Segmented` | Data display |
| `EmptyState`, `ErrorState`, `Skeleton`, `SkeletonLines` | The four states |
| `ThemeScope`, `themeForSuite`, `SUITE_THEMES`, `BRAND_THEME` | A suite's accent for its pages |
| `AppShell`, `Sidebar`, `Topbar`, `Notice` | The frame every signed-in screen shares |
| `Icons.*` | Lucide icons |
| `BarChart`, `AreaChart`, `ResponsiveContainer`, `XAxis`, `YAxis`, `CartesianGrid`, `Tooltip`, `Bar`, `Area` | Charts with the Recharts API |
| `useInView`, `useElapsed`, `easeOut`, `prefersReducedMotion` | Motion helpers |
| `DashboardWidget`, `WidgetProps`, `WidgetKind`, `WidgetSize`, `RoleLayout` | The widget contract |
| `WidgetRegistry`, `WidgetFrame`, `Figure`, `FigureStrip` | What the shell renders widgets with |

## Widget contract

A module exports its dashboard widgets from `frontend/src/widgets/index.ts`:

```ts
import type { DashboardWidget } from "@eos/ui-kit";

export const widgets: DashboardWidget[] = [
  { id: "fees-accounts.outstanding-dues", title: "Outstanding dues", permission: "fees-accounts:invoice:read", size: "1x1", kind: "figure", component: OutstandingDues },
  { id: "fees-accounts.recent-payments", title: "Recent payments", permission: "fees-accounts:payment:read", size: "2x1", kind: "list", component: RecentPayments },
];
```

`kind` decides the layout: `figure` widgets join the key-figure strip at the top of the dashboard;
`list`, `table`, `chart` and `panel` widgets get a panel on the twelve-column grid. A widget
imports only from its own module and `packages/`, fetches data through its module's generated API
client, and has a test. Widget ids are `<module>.<widget>` and unique across the repo.

```
pnpm --filter @eos/ui-kit test
pnpm --filter @eos/ui-kit typecheck
```
