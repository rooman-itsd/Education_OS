// The dashboard widgets each module exports from frontend/src/widgets/index.ts (the
// packages/ui-kit DashboardWidget contract), read from the repository. A layout id with no
// exported widget renders as "Not built yet", as in the role dashboard shell.

import type { DashboardWidget } from '@eos/ui-kit';

export type { DashboardWidget, WidgetSize } from '@eos/ui-kit';

const exports = import.meta.glob<{ widgets?: DashboardWidget[] }>('../../../../../modules/*/*/frontend/src/widgets/index.ts', {
  eager: true
});

/** Widgets per module id, exactly as each module exports them today. */
export const MODULE_WIDGETS: Record<string, DashboardWidget[]> = Object.fromEntries(
  Object.entries(exports).map(([path, mod]) => [path.split('/').slice(-5, -4)[0]!, mod.widgets ?? []])
);
