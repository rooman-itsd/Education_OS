import type { ReactNode } from "react";
import { Lock } from "../icons";
import { Panel, PanelBody, PanelHeader } from "../components/Panel";
import { ErrorState, SkeletonLines } from "../components/States";
import type { WidgetKind, WidgetSize } from "./types";

export type WidgetState = "ready" | "loading" | "empty" | "error" | "locked";

export interface WidgetFrameProps {
  title: string;
  size: WidgetSize;
  kind?: WidgetKind;
  subtitle?: string;
  state?: WidgetState;
  /** Message for the empty, error or locked state. */
  message?: string;
  /** Top-right action, e.g. a "View all" link. */
  action?: ReactNode;
  children?: ReactNode;
}

/**
 * The panel every non-figure widget renders inside. Owns the header and the loading, empty,
 * error and locked states so individual widgets do not repeat them. Tables render flush.
 */
export function WidgetFrame({ title, size, kind = "panel", subtitle, state = "ready", message, action, children }: WidgetFrameProps) {
  return (
    <Panel className="eos-widget" data-state={state} data-span={size} data-kind={kind} aria-busy={state === "loading"} lift={state === "ready"}>
      <PanelHeader title={title} subtitle={subtitle} action={action} as="h2" icon={state === "locked" ? <Lock /> : undefined} />
      <PanelBody flush={kind === "table" && state === "ready"}>
        {state === "loading" && <SkeletonLines lines={kind === "figure" ? 1 : 3} />}
        {state === "empty" && <p className="eos-widget__status">{message ?? "Nothing to show"}</p>}
        {state === "locked" && <p className="eos-widget__status">{message ?? "Not in your plan"}</p>}
        {state === "error" && <ErrorState>{message}</ErrorState>}
        {state === "ready" && children}
      </PanelBody>
    </Panel>
  );
}
