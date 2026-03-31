"""Lock PDF with password (AES) and user permissions via pikepdf."""

from __future__ import annotations

from io import BytesIO

from pikepdf import Encryption, Permissions, Pdf


def lock_pdf_bytes(
    data: bytes,
    password: str,
    *,
    allow_copy: bool = True,
    allow_print: bool = True,
) -> bytes:
    """
    Encrypt PDF bytes and set permissions for users who open with the user password.

    - allow_copy: PDF flag `extract` (copy text / extract content).
    - allow_print: both `print_lowres` and `print_highres`.
    """
    if not password or len(password) < 4:
        raise ValueError("Kata sandi minimal 4 karakter.")

    perms = Permissions(
        extract=allow_copy,
        print_lowres=allow_print,
        print_highres=allow_print,
    )
    enc = Encryption(
        owner=password,
        user=password,
        R=6,
        allow=perms,
        aes=True,
    )

    src = BytesIO(data)
    out = BytesIO()
    with Pdf.open(src) as pdf:
        pdf.save(out, encryption=enc)

    return out.getvalue()
