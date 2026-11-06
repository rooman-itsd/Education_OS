"""A minimal text-only PDF writer (PDF 1.4, Helvetica, no images, no compression) for the NIRF website copy.

No PDF library is on the approved stack, and the copy NIRF wants on the institution's website is a plain statement of
the submitted aggregate data, so a few lines of PDF syntax are enough. The output is byte-for-byte deterministic: no
creation date, no producer string, no random ids, which is what lets a golden file test it.
"""

from __future__ import annotations

LINES_PER_PAGE = 52
PAGE_W, PAGE_H, MARGIN, LEADING = 595, 842, 56, 14


def _escape(text: str) -> bytes:
    # Standard fonts are WinAnsi; anything outside Latin-1 is replaced rather than emitted as a broken glyph.
    raw = text.encode("latin-1", "replace")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def build_pdf(title: str, lines: list[str]) -> bytes:
    pages = [lines[i : i + LINES_PER_PAGE] for i in range(0, len(lines), LINES_PER_PAGE)] or [[]]
    objects: list[bytes] = []  # object n is objects[n - 1]

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    add(b"<< /Type /Catalog /Pages 2 0 R >>")  # 1
    page_ids = [4 + 2 * i for i in range(len(pages))]
    kids = b" ".join(b"%d 0 R" % pid for pid in page_ids)
    add(b"<< /Type /Pages /Kids [" + kids + b"] /Count %d >>" % len(pages))  # 2
    add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")  # 3
    for n, page in enumerate(pages):
        stream = bytearray(b"BT /F1 10 Tf %d TL %d %d Td " % (LEADING, MARGIN, PAGE_H - MARGIN))
        if n == 0:
            stream += b"/F1 14 Tf (" + _escape(title) + b") Tj /F1 10 Tf T* T* "
        for line in page:
            stream += b"(" + _escape(line) + b") Tj T* "
        stream += b"ET"
        add(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>"
            % (PAGE_W, PAGE_H, page_ids[n] + 1)
        )
        add(b"<< /Length %d >>\nstream\n" % len(stream) + bytes(stream) + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)
