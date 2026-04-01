"""Split selected pages to separate PDFs (ZIP if multiple) or delete pages via pikepdf."""

from __future__ import annotations

import zipfile
from io import BytesIO

import pikepdf
from pikepdf import PasswordError, Pdf
import datetime


class PasswordRequiredError(Exception):
    """PDF terenkripsi dan belum ada kata sandi."""


def decrypt_if_needed(raw: bytes, password: str | None) -> bytes:
    """
    Buka PDF; jika terkunci tanpa password → PasswordRequiredError.
    Jika password salah → pikepdf.PdfError.
    """
    try:
        with Pdf.open(BytesIO(raw)):
            return raw
    except PasswordError:
        if not password:
            raise PasswordRequiredError from None
        buf = BytesIO()
        try:
            with Pdf.open(BytesIO(raw), password=password) as pdf:
                pdf.save(buf, encryption=None)
        except pikepdf.PdfError:
            raise
        return buf.getvalue()


def _normalize_indices_1based(pages: list[int], num_pages: int) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for p in pages:
        if not isinstance(p, int) or p < 1 or p > num_pages:
            continue
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def split_selected_pages(
    decrypted_pdf_bytes: bytes,
    pages_1based: list[int],
    *,
    base_stem: str = "document",
) -> tuple[bytes, str, str]:
    """
    Satu halaman terpilih → satu file PDF.
    Lebih dari satu → ZIP berisi satu PDF per halaman.

    Returns: (content, download_filename, media_type)
    """
    if not pages_1based:
        raise ValueError("Pilih minimal satu halaman untuk split.")

    with Pdf.open(BytesIO(decrypted_pdf_bytes)) as pdf:
        n = len(pdf.pages)
        indices = _normalize_indices_1based(pages_1based, n)
        if not indices:
            raise ValueError("Tidak ada nomor halaman yang valid.")

        if len(indices) == 1:
            p1 = indices[0]
            out_pdf = Pdf.new()
            out_pdf.pages.append(pdf.pages[p1 - 1])
            buf = BytesIO()
            out_pdf.save(buf)
            name = f"{base_stem}_page_{p1}.pdf"
            return buf.getvalue(), name, "application/pdf"

        zbuf = BytesIO()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as zf:
            for p1 in indices:
                part = Pdf.new()
                part.pages.append(pdf.pages[p1 - 1])
                pbuf = BytesIO()
                part.save(pbuf)
                zf.writestr(f"page({p1})-{timestamp}.pdf", pbuf.getvalue())
        return zbuf.getvalue(), f"{base_stem}_split_pages.zip", "application/zip"


def delete_selected_pages(
    decrypted_pdf_bytes: bytes,
    pages_1based: list[int],
    *,
    base_stem: str = "document",
) -> tuple[bytes, str]:
    """
    Hapus halaman yang dipilih; sisanya jadi satu PDF.

    Returns: (pdf_bytes, suggested_filename)
    """
    if not pages_1based:
        raise ValueError("Pilih minimal satu halaman untuk dihapus.")

    with Pdf.open(BytesIO(decrypted_pdf_bytes)) as pdf:
        n = len(pdf.pages)
        indices = _normalize_indices_1based(pages_1based, n)
        if not indices:
            raise ValueError("Tidak ada nomor halaman yang valid.")
        if len(indices) >= n:
            raise ValueError("Tidak boleh menghapus semua halaman.")

        # Hapus dari indeks terbesar agar indeks tidak bergeser
        for p1 in sorted(indices, reverse=True):
            del pdf.pages[p1 - 1]

        buf = BytesIO()
        pdf.save(buf)
        return buf.getvalue(), f"{base_stem}_tanpa_halaman_terpilih.pdf"
