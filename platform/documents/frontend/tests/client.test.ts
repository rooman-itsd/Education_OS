import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  requestUploadIntent,
  confirmUpload,
  getDocument,
  getDownloadUrl,
  listDocuments,
  deleteDocument,
  humanFileSize,
  describeFailure,
  DocumentsApiError,
} from "../src/api/client";

describe("Documents API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("formats human-readable file sizes correctly", () => {
    expect(humanFileSize(500)).toBe("500 B");
    expect(humanFileSize(1024)).toBe("1.0 KB");
    expect(humanFileSize(1024 * 1024)).toBe("1.0 MB");
    expect(humanFileSize(2.5 * 1024 * 1024)).toBe("2.5 MB");
    expect(humanFileSize(1024 * 1024 * 1024)).toBe("1.0 GB");
  });

  it("handles failure descriptions properly", () => {
    expect(describeFailure(new DocumentsApiError(401, "Unauthorized"), "doc").retry).toBe(false);
    expect(describeFailure(new DocumentsApiError(403, "Forbidden"), "doc").retry).toBe(false);
    expect(describeFailure(new DocumentsApiError(404, "Not Found"), "doc").retry).toBe(true);
    expect(describeFailure(new DocumentsApiError(500, "Server Error"), "doc").retry).toBe(true);
  });

  it("requests upload intent with auth token and body", async () => {
    localStorage.setItem("eos.token", "test-token");
    const mockResponse = {
      document: {
        id: "doc-1",
        organisation_id: "org-1",
        filename: "syllabus.pdf",
        mime_type: "application/pdf",
        size_bytes: 1024,
        status: "pending_upload",
        created_at: "2026-10-30T10:00:00Z",
        updated_at: "2026-10-30T10:00:00Z",
      },
      upload_url: "http://storage.local/upload",
      method: "PUT",
      expires_in_seconds: 900,
    };

    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    });
    vi.stubGlobal("fetch", fetchSpy);

    const res = await requestUploadIntent({
      filename: "syllabus.pdf",
      mime_type: "application/pdf",
      size_bytes: 1024,
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/documents/upload-intent",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer test-token",
          "Content-Type": "application/json",
        }),
      }),
    );
    expect(res.document.id).toBe("doc-1");
    expect(res.upload_url).toBe("http://storage.local/upload");
  });

  it("confirms upload successfully", async () => {
    const mockDoc = {
      id: "doc-1",
      organisation_id: "org-1",
      filename: "syllabus.pdf",
      mime_type: "application/pdf",
      size_bytes: 1024,
      status: "available",
      created_at: "2026-10-30T10:00:00Z",
      updated_at: "2026-10-30T10:01:00Z",
    };

    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockDoc,
    });
    vi.stubGlobal("fetch", fetchSpy);

    const res = await confirmUpload("doc-1");
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/documents/doc-1/confirm",
      expect.objectContaining({ method: "POST" }),
    );
    expect(res.status).toBe("available");
  });

  it("gets document metadata and download url", async () => {
    const mockDoc = {
      id: "doc-1",
      organisation_id: "org-1",
      filename: "syllabus.pdf",
      mime_type: "application/pdf",
      size_bytes: 1024,
      status: "available",
      created_at: "2026-10-30T10:00:00Z",
      updated_at: "2026-10-30T10:00:00Z",
    };
    const mockDownload = {
      download_url: "http://storage.local/download",
      filename: "syllabus.pdf",
      expires_in_seconds: 900,
    };

    const fetchSpy = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => mockDoc })
      .mockResolvedValueOnce({ ok: true, json: async () => mockDownload });
    vi.stubGlobal("fetch", fetchSpy);

    const doc = await getDocument("doc-1");
    expect(doc.id).toBe("doc-1");

    const dl = await getDownloadUrl("doc-1");
    expect(dl.download_url).toBe("http://storage.local/download");
  });

  it("lists documents with query filters", async () => {
    const mockList = {
      items: [
        {
          id: "doc-1",
          organisation_id: "org-1",
          filename: "syllabus.pdf",
          mime_type: "application/pdf",
          size_bytes: 1024,
          status: "available",
          created_at: "2026-10-30T10:00:00Z",
          updated_at: "2026-10-30T10:00:00Z",
        },
      ],
      total: 1,
    };

    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockList,
    });
    vi.stubGlobal("fetch", fetchSpy);

    const res = await listDocuments({
      status: "available",
      entity_type: "course",
      limit: 10,
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/documents/?status=available&entity_type=course&limit=10",
      expect.anything(),
    );
    expect(res.total).toBe(1);
    expect(res.items.length).toBe(1);
  });

  it("deletes a document", async () => {
    const mockDelete = { deleted: true, document_id: "doc-1" };
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockDelete,
    });
    vi.stubGlobal("fetch", fetchSpy);

    const res = await deleteDocument("doc-1");
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/documents/doc-1",
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(res.deleted).toBe(true);
  });

  it("throws DocumentsApiError on HTTP error status", async () => {
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
    });
    vi.stubGlobal("fetch", fetchSpy);

    await expect(getDocument("non-existent")).rejects.toThrow(DocumentsApiError);
  });
});
