"""Convert PDF files to Word (.docx) using pdf2docx."""

from __future__ import annotations

import tempfile
import os
from pathlib import Path

from pdf2docx import Converter


def convert_pdf_to_docx(data: bytes) -> bytes:
    """
    Convert PDF bytes (already decrypted if needed) to DOCX bytes.

    Uses pdf2docx which works with file paths, so we write to temp files.
    Returns the DOCX content as bytes.

    Raises RuntimeError on conversion failure.
    """
    tmp_dir = tempfile.mkdtemp()
    pdf_path = os.path.join(tmp_dir, "input.pdf")
    docx_path = os.path.join(tmp_dir, "output.docx")

    try:
        # Write PDF bytes to temp file
        with open(pdf_path, "wb") as f:
            f.write(data)

        # Convert PDF → DOCX
        cv = Converter(pdf_path)
        cv.convert(docx_path)
        cv.close()

        # Read resulting DOCX
        with open(docx_path, "rb") as f:
            result = f.read()

        if not result:
            raise RuntimeError("Konversi menghasilkan file kosong.")

        return result

    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Gagal mengonversi PDF ke Word: {e}") from e
    finally:
        # Clean up temp files
        for p in (pdf_path, docx_path):
            try:
                os.unlink(p)
            except OSError:
                pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass
