/**
 * Typed client for platform/documents API.
 */

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class DocumentsApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "DocumentsApiError";
  }
}

function token(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(options.headers as Record<string, string>),
  };
  const t = token();
  if (t) headers.Authorization = `Bearer ${t}`;
  if (options.body && typeof options.body === "string") headers["Content-Type"] = "application/json";

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) throw new DocumentsApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

export interface DocumentRecord {
  id: string;
  organisation_id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  status: "pending_upload" | "available" | "archived" | "deleted" | string;
  entity_type?: string | null;
  entity_id?: string | null;
  title?: string | null;
  client_token?: string | null;
  tags?: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface UploadIntentInput {
  filename: string;
  mime_type: string;
  size_bytes: number;
  title?: string;
  entity_type?: string;
  entity_id?: string;
  client_token?: string;
  tags?: string[];
}

export interface UploadIntentResponse {
  document: DocumentRecord;
  upload_url: string;
  method: string;
  expires_in_seconds: number;
}

export interface DownloadUrlResponse {
  download_url: string;
  filename: string;
  expires_in_seconds: number;
}

export interface DocumentListPage {
  items: DocumentRecord[];
  total: number;
}

export interface DeleteResponse {
  deleted: boolean;
  document_id: string;
}

export interface Failure {
  title: string;
  detail?: string;
  retry: boolean;
}

export function describeFailure(e: unknown, what: string): Failure {
  if (!(e instanceof DocumentsApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Document service is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to continue.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this document.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}

export function humanFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
}

export const requestUploadIntent = (input: UploadIntentInput, signal?: AbortSignal) =>
  request<UploadIntentResponse>("/documents/upload-intent", {
    method: "POST",
    body: JSON.stringify(input),
    signal,
  });

export const confirmUpload = (id: string, signal?: AbortSignal) =>
  request<DocumentRecord>(`/documents/${id}/confirm`, {
    method: "POST",
    signal,
  });

export const getDocument = (id: string, signal?: AbortSignal) =>
  request<DocumentRecord>(`/documents/${id}`, { signal });

export const getDownloadUrl = (id: string, signal?: AbortSignal) =>
  request<DownloadUrlResponse>(`/documents/${id}/download-url`, { signal });

export const listDocuments = (
  params?: {
    status?: string;
    entity_type?: string;
    entity_id?: string;
    limit?: number;
    offset?: number;
  },
  signal?: AbortSignal,
) => {
  const q = new URLSearchParams();
  if (params?.status) q.set("status", params.status);
  if (params?.entity_type) q.set("entity_type", params.entity_type);
  if (params?.entity_id) q.set("entity_id", params.entity_id);
  if (params?.limit !== undefined) q.set("limit", String(params.limit));
  if (params?.offset !== undefined) q.set("offset", String(params.offset));
  const queryStr = q.toString();
  return request<DocumentListPage>(`/documents/${queryStr ? `?${queryStr}` : ""}`, { signal });
};

export const deleteDocument = (id: string, signal?: AbortSignal) =>
  request<DeleteResponse>(`/documents/${id}`, {
    method: "DELETE",
    signal,
  });
