"""Unlock (decrypt) password-protected PDFs using pikepdf."""

from __future__ import annotations

from io import BytesIO

from pikepdf import Pdf


def unlock_pdf_bytes(data: bytes, password: str) -> bytes:
    """
    Remove password/encryption from a PDF.

    Raises pikepdf.PdfError if the password is salah atau PDF rusak.
    """
    if not password:
        raise ValueError("Kata sandi wajib diisi.")

    src = BytesIO(data)
    out = BytesIO()

    # Jika password salah, pikepdf akan melempar PdfError.
    with Pdf.open(src, password=password) as pdf:
        pdf.save(out, encryption=None)

    return out.getvalue()

