/**
 * Typed client for the parts of contracts/openapi.yaml the knowledge-base frontend uses. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the types below
 * must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the app shell
 * stores after sign-in.
 */

export type ArticleType = "article" | "faq" | "how_to";
export type Period = "7d" | "30d" | "90d";
export type Metric = "views" | "helpful";

/** One item of contract TopArticles.items. */
export interface TopArticle {
  article_id: string;
  slug: string;
  title: string;
  type: ArticleType;
  category_id: string;
  audience?: "everyone" | "staff";
  /** Views in the period */
  views: number;
  helpful_count: number;
  not_helpful_count: number;
  /** helpful / (helpful + not helpful), null with no votes */
  helpful_share?: number | null;
}

/** contract TopArticles */
export interface TopArticles {
  period: Period;
  metric: Metric;
  items: TopArticle[];
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class KnowledgeBaseApiError extends Error {
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
  const res = await fetch(`${API_BASE}/knowledge-base${path}`, { headers, signal });
  if (!res.ok) throw new KnowledgeBaseApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/**
 * GET /stats/top-articles: published articles ranked by views in the period (default 30d) or by helpful share.
 * Permission knowledge-base:stats:read.
 */
export function getTopArticles(
  options: { period?: Period; metric?: Metric; limit?: number } = {},
  signal?: AbortSignal,
): Promise<TopArticles> {
  const query = new URLSearchParams();
  if (options.period) query.set("period", options.period);
  if (options.metric) query.set("metric", options.metric);
  if (options.limit) query.set("limit", String(options.limit));
  const qs = query.toString();
  return get<TopArticles>(`/stats/top-articles${qs ? `?${qs}` : ""}`, signal);
}
