"""Compress PDF using Ghostscript."""

import subprocess
import tempfile
from pathlib import Path


def compress_pdf_bytes(data: bytes, quality: str = "ebook") -> bytes:
    """
    Compress PDF bytes using Ghostscript with specified quality preset.

    quality: 'screen', 'ebook', 'printer', 'prepress'
    """
    if quality not in ["screen", "ebook", "printer", "prepress"]:
        raise ValueError(
            "Invalid quality preset. Use: screen, ebook, printer, prepress")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as input_file:
        input_file.write(data)
        input_path = input_file.name

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as output_file:
        output_path = output_file.name

    try:
        cmd = [
            "gs",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            f"-dPDFSETTINGS=/{quality}",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={output_path}",
            input_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Ghostscript error: {result.stderr}")

        with open(output_path, "rb") as f:
            compressed_data = f.read()

        return compressed_data

    finally:
        Path(input_path).unlink(missing_ok=True)
        Path(output_path).unlink(missing_ok=True)
