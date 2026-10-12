# Frontend design system

Every screen of Education OS is built from `packages/ui-kit`: the role dashboards in
`apps/frontend`, the admin console, and every module's pages and widgets. The look is the admin
console design the team chose on 12 October 2026, turned into tokens and components so that ten
people building 59 dashboards produce one product. Nothing in a module invents its own colours,
fonts, spacing or shell.

## What you get

```
import "@eos/ui-kit/styles.css";          // once, in the app entry (apps/frontend already does)
import { Button, Panel, PanelHeader, PanelBody, StatGrid, PageHero, DataTable, List, ListRow,
         ProgressList, Badge, EmptyState, ErrorState, Skeleton, Segmented, ThemeScope,
         Figure, WidgetFrame, AppShell, Icons, BarChart, AreaChart } from "@eos/ui-kit";
```

| Layer | Where | What |
|---|---|---|
| Tokens | `src/styles/tokens.css` | Every colour, font, size, radius, shadow and easing as `--eos-*` variables. The page accent (`--accent`, `--accent-tint`, …) is what a suite recolours. |
| Base | `src/styles/base.css` | Reset, Inter, focus ring, button press and lift, entrance keyframes, reduced motion. |
| Components | `src/components/` | Button, Panel, StatCard and StatGrid, PageHero, Badge, DataTable, List and ListRow, ProgressBar and ProgressList, EmptyState, ErrorState, Skeleton, Segmented, Wordmark, ThemeScope. |
| Shell | `src/shell/` | AppShell: dark sidebar with folding suite groups, sticky top bar with breadcrumb, search (Ctrl K), notifications and account menu, notice bar, footer. |
| Widgets | `src/widget/` | The dashboard widget contract, `WidgetFrame`, `Figure`, `FigureStrip`, the registry. |
| Icons, charts, motion | `src/icons.tsx`, `src/charts.tsx`, `src/motion.ts` | Lucide icons as `Icons.Name`, bar and area charts with the Recharts API, `useInView`, `useElapsed`, `CountUp`. |

## The rules

1. **Tokens only.** No hex, rgb or named colour in a module. Use a component, a class from the kit,
   or `var(--eos-…)`. Status always comes with a word or an icon, never colour alone.
2. **One shell.** Pages render inside `AppShell`; `apps/frontend` provides it. A module page starts
   with `PageHero` (the only gradient on the page), then panels. Suites recolour their pages with
   `ThemeScope theme={themeForSuite("academics")}`.
3. **Not everything is a card.** Key numbers are `figure` widgets and join the strip at the top.
   Lists, tables and charts get a panel each. Prose and small facts can sit in a plain panel body
   with no extra boxes.
4. **One primary button per screen**, coral. Everything else is secondary, ghost or a link.
5. **Every async piece has four states:** loading (`Skeleton`), empty (`EmptyState` with what to do
   next), error (`ErrorState` with retry), ready. `WidgetFrame` does this for widgets.
6. **Tables are tables.** `DataTable` with a row header, right-aligned tabular numbers, a caption
   line. On phones it scrolls sideways; do not hide columns silently.
7. **Motion is restrained.** Entrance fades, count-ups and bar fills come from the kit and switch
   off under reduced motion. Do not add your own keyframes.
8. **Inter for text, Montserrat only in the wordmark.** Sizes 11 to 32 px from the token scale.
9. **Phone first.** Every page works at 390 px: the sidebar becomes a drawer, stat cards stack,
   tables scroll. Hit targets are 44 px on touch screens.

## Writing a widget

A widget is a `DashboardWidget` exported from `frontend/src/widgets/index.ts` of its module. The
shell lays it out by `kind`:

| kind | What it is | Component returns | Where it lands |
|---|---|---|---|
| `figure` | one key number | `<Figure label value delta … />` | the key-figure strip at the top |
| `list` | rows of items | `<List>…<ListRow …/></List>` | a panel, one third or two thirds wide |
| `table` | a data table | `<DataTable …/>` | a panel, flush, two thirds or full width |
| `chart` | a chart | `<ResponsiveContainer><BarChart …/></ResponsiveContainer>` | a panel |
| `panel` | anything else | any content | a panel |

```tsx
// modules/finance-operations/fees-accounts/frontend/src/widgets/OutstandingDues.tsx
import { Figure, Icons, type WidgetProps } from "@eos/ui-kit";
import { useOutstandingDues } from "../api";

export function OutstandingDues(_: WidgetProps) {
  const q = useOutstandingDues();
  if (q.isPending) return <Figure label="Outstanding dues" value="…" />;
  return <Figure label="Outstanding dues" value={q.data.total} prefix="₹" icon={Icons.IndianRupee} delta={`${q.data.overdue} overdue`} deltaTone={q.data.overdue ? "alert" : "up"} />;
}
```

```ts
// modules/finance-operations/fees-accounts/frontend/src/widgets/index.ts
export const widgets: DashboardWidget[] = [
  { id: "fees-accounts.outstanding-dues", title: "Outstanding dues", permission: "fees-accounts:invoice:read", size: "1x1", kind: "figure", component: OutstandingDues },
  { id: "fees-accounts.recent-payments", title: "Recent payments", subtitle: "Last 7 days", permission: "fees-accounts:payment:read", size: "2x1", kind: "list", component: RecentPayments },
];
```

Sizes: `1x1` a third of the grid, `2x1` two thirds, `full` the whole width. The grid is twelve
columns and folds to one on phones.

## Writing a module page

```tsx
import { Badge, Button, DataTable, PageHero, Panel, PanelBody, PanelHeader, StatGrid, ThemeScope, themeForSuite } from "@eos/ui-kit";

export function BookingsPage() {
  return (
    <ThemeScope theme={themeForSuite("facilities")} className="eos-dashboard">
      <PageHero eyebrow="D · Facilities" title="Bookings" subtitle="Rooms, grounds and equipment" actions={<Button variant="primary">New booking</Button>} />
      <StatGrid stats={[{ label: "Today", value: 14, icon: Icons.CalendarCheck2 }, { label: "Awaiting approval", value: 3, deltaTone: "alert", delta: "2 overdue" }]} />
      <Panel>
        <PanelHeader title="Upcoming bookings" subtitle="Next seven days" />
        <PanelBody flush>
          <DataTable … />
        </PanelBody>
      </Panel>
    </ThemeScope>
  );
}
```

## Preview it

```
pnpm --filter @eos/frontend dev
```

Open http://localhost:5173/?preview=1 and switch academy, role and plan in the top bar. The role
dashboard shows every widget from the role's layout file; the ones nobody has built yet show
"Not built yet" so the gap is visible. The admin console is at /admin.html.

## Changing the kit

The kit is owned by the architecture lead. A new component or token is a PR to `packages/ui-kit`
with a test in `packages/ui-kit/tests`. If a module needs something the kit lacks, ask in an issue
rather than styling around it; the next module will need it too.
