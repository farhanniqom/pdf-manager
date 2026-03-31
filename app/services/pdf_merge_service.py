"""Merge selected pages from multiple PDFs in custom order."""

from __future__ import annotations

from io import BytesIO

from pikepdf import Pdf


def merge_selected_pages(
    files_in_order: list[tuple[bytes, int]],
) -> bytes:
    """
    Merge pages in exact order.

    files_in_order item: (pdf_bytes, page_number_1_based)
    """
    if not files_in_order:
        raise ValueError("Pilih minimal satu halaman untuk digabung.")

    out = Pdf.new()
    opened: list[Pdf] = []
    try:
        for pdf_bytes, page_1 in files_in_order:
            src = Pdf.open(BytesIO(pdf_bytes))
            opened.append(src)
            if page_1 < 1 or page_1 > len(src.pages):
                raise ValueError(f"Nomor halaman tidak valid: {page_1}.")
            out.pages.append(src.pages[page_1 - 1])

        buf = BytesIO()
        out.save(buf)
        return buf.getvalue()
    finally:
        for p in opened:
            p.close()

