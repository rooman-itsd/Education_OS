// The subset of the react-router-dom API the admin screens use, on top of the URL hash
// (`admin.html#/dashboard`). @eos/frontend does not depend on react-router-dom, and a hash router
// needs no server rewrite rule.

import {
  Children,
  createContext,
  isValidElement,
  useCallback,
  useContext,
  useLayoutEffect,
  useMemo,
  useSyncExternalStore,
  type AnchorHTMLAttributes,
  type MouseEvent,
  type ReactElement,
  type ReactNode,
} from "react";

export interface Location {
  pathname: string;
  search: string;
}

function readLocation(): Location {
  const raw = window.location.hash.replace(/^#/, "") || "/";
  const q = raw.indexOf("?");
  const pathname = (q === -1 ? raw : raw.slice(0, q)) || "/";
  return { pathname: pathname.startsWith("/") ? pathname : `/${pathname}`, search: q === -1 ? "" : raw.slice(q) };
}

let snapshot = readLocation();
let snapshotKey = window.location.hash;
function getSnapshot(): Location {
  if (window.location.hash !== snapshotKey) {
    snapshotKey = window.location.hash;
    snapshot = readLocation();
  }
  return snapshot;
}
function subscribe(onChange: () => void) {
  window.addEventListener("hashchange", onChange);
  return () => window.removeEventListener("hashchange", onChange);
}

function go(to: string, replace = false) {
  const url = new URL(window.location.href);
  url.hash = to;
  if (replace) window.history.replaceState(null, "", url);
  else window.history.pushState(null, "", url);
  window.dispatchEvent(new HashChangeEvent("hashchange"));
}

const LocationContext = createContext<Location | null>(null);
const RouteContext = createContext<{ params: Record<string, string>; outlet: ReactNode }>({ params: {}, outlet: null });

export function BrowserRouter({ children }: { children: ReactNode }) {
  const location = useSyncExternalStore(subscribe, getSnapshot);
  return <LocationContext.Provider value={location}>{children}</LocationContext.Provider>;
}

export function useLocation(): Location {
  const location = useContext(LocationContext);
  if (!location) throw new Error("useLocation() must be used inside <BrowserRouter>");
  return location;
}

export function useNavigate() {
  return useCallback((to: string, options?: { replace?: boolean }) => go(to, options?.replace), []);
}

export function useParams<T extends Record<string, string> = Record<string, string>>(): Partial<T> {
  return useContext(RouteContext).params as Partial<T>;
}

export function useSearchParams(): [URLSearchParams, (next: Record<string, string>) => void] {
  const { pathname, search } = useLocation();
  const params = useMemo(() => new URLSearchParams(search), [search]);
  const set = useCallback(
    (next: Record<string, string>) => go(`${pathname}?${new URLSearchParams(next).toString()}`),
    [pathname],
  );
  return [params, set];
}

export function Outlet() {
  return <>{useContext(RouteContext).outlet}</>;
}

export function Navigate({ to, replace }: { to: string; replace?: boolean }) {
  useLayoutEffect(() => go(to, replace), [to, replace]);
  return null;
}

interface RouteProps {
  path?: string;
  element?: ReactNode;
  children?: ReactNode;
}

export function Route(_props: RouteProps): ReactElement | null {
  return null; // configuration only; <Routes> reads its props
}

function matchPath(pattern: string, pathname: string): Record<string, string> | null {
  if (pattern === "*") return {};
  const want = pattern.split("/").filter(Boolean);
  const have = pathname.split("/").filter(Boolean);
  if (want.length !== have.length) return null;
  const params: Record<string, string> = {};
  for (let i = 0; i < want.length; i++) {
    const w = want[i]!;
    const h = decodeURIComponent(have[i]!);
    if (w.startsWith(":")) params[w.slice(1)] = h;
    else if (w !== h) return null;
  }
  return params;
}

function resolve(children: ReactNode, pathname: string): ReactNode | undefined {
  for (const child of Children.toArray(children)) {
    if (!isValidElement<RouteProps>(child)) continue;
    const { path, element, children: nested } = child.props;
    if (path === undefined) {
      const inner = resolve(nested, pathname);
      if (inner !== undefined) return <Layout element={element} outlet={inner} />;
      continue;
    }
    const params = matchPath(path, pathname);
    if (params) return <RouteContext.Provider value={{ params, outlet: null }}>{element}</RouteContext.Provider>;
  }
  return undefined;
}

function Layout({ element, outlet }: { element: ReactNode; outlet: ReactNode }) {
  const parent = useContext(RouteContext);
  return <RouteContext.Provider value={{ params: parent.params, outlet }}>{element}</RouteContext.Provider>;
}

export function Routes({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  return <>{resolve(children, pathname) ?? null}</>;
}

type LinkProps = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & { to: string; replace?: boolean };

export function Link({ to, replace, onClick, target, ...rest }: LinkProps) {
  const handle = (e: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(e);
    if (e.defaultPrevented || e.button !== 0 || target || e.metaKey || e.altKey || e.ctrlKey || e.shiftKey) return;
    e.preventDefault();
    go(to, replace);
  };
  return <a href={`#${to}`} onClick={handle} target={target} {...rest} />;
}

/** Like react-router's NavLink: adds `active` and `aria-current="page"` when the path matches. */
export function NavLink({ className, ...props }: LinkProps) {
  const { pathname } = useLocation();
  const target = props.to.split("?")[0]!;
  const active = pathname === target || (target !== "/" && pathname.startsWith(`${target}/`));
  const classes = active ? [className, "active"].filter(Boolean).join(" ") : className;
  return <Link aria-current={active ? "page" : undefined} className={classes} {...props} />;
}
