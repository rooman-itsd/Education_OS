/**
 * Typed client for portfolio API endpoints consumed by frontend widgets.
 */

export type ItemStatus = "draft" | "submitted" | "under_review" | "approved" | "changes_requested" | "withdrawn";

export interface ItemMedia {
  id: string;
  item_id: string;
  document_id: string;
  caption?: string | null;
  sort_order: number;
}

export interface Review {
  id: string;
  item_id: string;
  organisation_id: string;
  reviewer_person_id: string;
  decision: "approved" | "changes_requested";
  score?: number | null;
  comments?: string | null;
  reviewed_at: string;
}

export interface Item {
  id: string;
  organisation_id: string;
  type_id: string;
  owner_person_id: string;
  title: string;
  description?: string | null;
  tags: string[];
  attributes: Record<string, string>;
  status: ItemStatus;
  media: ItemMedia[];
  reviews: Review[];
  submitted_at?: string | null;
  decided_at?: string | null;
  created_at: string;
  updated_at: string;
  can: string[];
}

export interface ItemPage {
  items: Item[];
  total: number;
  page: number;
  page_size: number;
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class PortfolioApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function token(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const t = token();
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`${API_BASE}/portfolio${path}`, { headers, signal });
  if (!res.ok) throw new PortfolioApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

export async function listMyItems(pageSize = 6, signal?: AbortSignal): Promise<ItemPage> {
  return get<ItemPage>(`/items?scope=mine&page_size=${pageSize}`, signal);
}

export async function listReviewsPending(pageSize = 6, signal?: AbortSignal): Promise<ItemPage> {
  return get<ItemPage>(`/items?scope=managed&status=submitted,under_review&page_size=${pageSize}`, signal);
}

