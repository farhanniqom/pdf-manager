"""PDF-related HTTP routes."""

from __future__ import annotations

import json
import re
from urllib.parse import quote
from io import BytesIO

import pikepdf
from pikepdf import Pdf, PasswordError
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.config import MAX_FILE_SIZE
from app.services.pdf_lock_service import lock_pdf_bytes
from app.services.pdf_unlock_service import unlock_pdf_bytes
from app.services.pdf_compress_service import compress_pdf_bytes
from app.services.pdf_to_word_service import convert_pdf_to_docx
from app.services.pdf_to_excel_service import convert_pdf_to_excel
from app.services.pdf_split_service import (
    PasswordRequiredError,
    decrypt_if_needed,
    delete_selected_pages,
    split_selected_pages,
)
from app.services.pdf_merge_service import merge_selected_pages

router = APIRouter(prefix="/pdf", tags=["pdf"])


def _safe_filename(name: str) -> str:
    base = re.sub(r'[^\w.\-]', "_", name, flags=re.ASCII) or "document.pdf"
    if not base.lower().endswith(".pdf"):
        base += ".pdf"
    return base


def _stem_from_filename(name: str) -> str:
    s = _safe_filename(name)
    return s[:-4] if s.lower().endswith(".pdf") else s


def _parse_pages_json(pages_str: str) -> list[int]:
    try:
        data = json.loads(pages_str)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail="Field pages harus berupa JSON array nomor halaman, contoh: [1,2,3].",
        ) from e
    if not isinstance(data, list) or not data:
        raise HTTPException(
            status_code=400,
            detail="pages harus array angka (1-based) dan tidak kosong.",
        )
    out: list[int] = []
    for x in data:
        if isinstance(x, bool) or not isinstance(x, int):
            raise HTTPException(
                status_code=400,
                detail="Setiap elemen pages harus bilangan bulat positif.",
            )
        if x < 1:
            raise HTTPException(
                status_code=400,
                detail="Nomor halaman minimal 1.",
            )
        out.append(x)
    return out


def _parse_json_object(s: str | None) -> dict:
    if not s:
        return {}
    try:
        val = json.loads(s)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="JSON tidak valid.") from e
    if not isinstance(val, dict):
        raise HTTPException(status_code=400, detail="Format JSON harus object.")
    return val


async def _read_and_validate_pdf(file: UploadFile) -> bytes:
    if not file.filename:
        raise HTTPException(status_code=400, detail="File PDF wajib diunggah.")
    ct = (file.content_type or "").lower()
    name_ok = (file.filename or "").lower().endswith(".pdf")
    if "pdf" not in ct and not name_ok:
        raise HTTPException(status_code=400, detail="Hanya file PDF yang didukung.")
    raw = await file.read()
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File melebihi batas ukuran.")
    if len(raw) < 8 or not raw.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Bukan file PDF yang valid.")
    return raw


@router.post("/lock")
async def lock_pdf(
    file: UploadFile = File(...),
    password: str = Form(...),
    allow_copy: str = Form("true"),
    allow_print: str = Form("true"),
):
    """
    Terima satu PDF, kunci dengan kata sandi, terapkan izin salin/cetak.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="File PDF wajib diunggah.")

    ct = (file.content_type or "").lower()
    name_ok = (file.filename or "").lower().endswith(".pdf")
    if "pdf" not in ct and not name_ok:
        raise HTTPException(status_code=400, detail="Hanya file PDF yang didukung.")

    raw = await file.read()
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File melebihi batas ukuran.")
    if len(raw) < 8 or not raw.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Bukan file PDF yang valid.")

    allow_copy_b = allow_copy.strip().lower() in ("1", "true", "yes", "on")
    allow_print_b = allow_print.strip().lower() in ("1", "true", "yes", "on")

    try:
        locked = lock_pdf_bytes(
            raw,
            password,
            allow_copy=allow_copy_b,
            allow_print=allow_print_b,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except pikepdf.PdfError as e:
        raise HTTPException(status_code=400, detail=f"PDF tidak valid atau rusak: {e}") from e

    fname = _safe_filename(file.filename)
    stem = fname[:-4] if fname.lower().endswith(".pdf") else fname
    out_name = f"{stem}_locked.pdf"
    cd = f'attachment; filename="{out_name}"; filename*=UTF-8\'\'{quote(out_name)}'

    return Response(
        content=locked,
        media_type="application/pdf",
        headers={"Content-Disposition": cd},
    )


@router.post("/unlock")
async def unlock_pdf(
    file: UploadFile = File(...),
    password: str = Form(...),
):
    """
    Terima satu PDF terkunci, buka dengan kata sandi, hilangkan enkripsi/izin.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="File PDF wajib diunggah.")

    ct = (file.content_type or "").lower()
    name_ok = (file.filename or "").lower().endswith(".pdf")
    if "pdf" not in ct and not name_ok:
        raise HTTPException(status_code=400, detail="Hanya file PDF yang didukung.")

    raw = await file.read()
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File melebihi batas ukuran.")
    if len(raw) < 8 or not raw.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Bukan file PDF yang valid.")

    try:
        unlocked = unlock_pdf_bytes(raw, password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except pikepdf.PdfError as e:
        # Salah password atau PDF korup/format tidak didukung.
        raise HTTPException(status_code=400, detail=f"Gagal membuka kunci PDF: {e}") from e

    fname = _safe_filename(file.filename)
    stem = fname[:-4] if fname.lower().endswith(".pdf") else fname
    out_name = f"{stem}_unlocked.pdf"
    cd = f'attachment; filename="{out_name}"; filename*=UTF-8\'\'{quote(out_name)}'

    return Response(
        content=unlocked,
        media_type="application/pdf",
        headers={"Content-Disposition": cd},
    )


@router.post("/compress")
async def compress_pdf(
    file: UploadFile = File(...),
    quality: str = Form("ebook"),
    password: str | None = Form(None),
):
    """
    Terima satu PDF, kompres dengan kualitas tertentu menggunakan Ghostscript.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="File PDF wajib diunggah.")

    ct = (file.content_type or "").lower()
    name_ok = (file.filename or "").lower().endswith(".pdf")
    if "pdf" not in ct and not name_ok:
        raise HTTPException(status_code=400, detail="Hanya file PDF yang didukung.")

    raw = await file.read()
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File melebihi batas ukuran.")
    if len(raw) < 8 or not raw.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Bukan file PDF yang valid.")

    # Deteksi PDF terenkripsi. Jika butuh password dan belum diberikan,
    # kembalikan kode khusus agar frontend bisa menampilkan pop-up.
    decrypted_bytes = raw
    try:
        # Coba buka tanpa password; jika sukses, file tidak diproteksi.
        with Pdf.open(BytesIO(raw)):
            pass
    except PasswordError:
        if not password:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "password_required",
                    "message": "PDF ini dilindungi kata sandi. Masukkan kata sandi untuk melanjutkan.",
                },
            )
        try:
            with Pdf.open(BytesIO(raw), password=password) as pdf:
                buf = BytesIO()
                # Simpan ulang tanpa enkripsi sehingga Ghostscript bisa memproses maksimal.
                pdf.save(buf, encryption=None)
                decrypted_bytes = buf.getvalue()
        except pikepdf.PdfError as e:
            raise HTTPException(
                status_code=400,
                detail="Kata sandi salah atau PDF tidak dapat dibuka.",
            ) from e
    except pikepdf.PdfError as e:
        raise HTTPException(
            status_code=400,
            detail=f"PDF tidak valid atau rusak: {e}",
        ) from e

    try:
        compressed = compress_pdf_bytes(decrypted_bytes, quality)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengompres PDF: {e}") from e

    fname = _safe_filename(file.filename)
    stem = fname[:-4] if fname.lower().endswith(".pdf") else fname
    out_name = f"{stem}_compressed.pdf"
    cd = f'attachment; filename="{out_name}"; filename*=UTF-8\'\'{quote(out_name)}'

    return Response(
        content=compressed,
        media_type="application/pdf",
        headers={"Content-Disposition": cd},
    )


def _decrypt_upload_for_tools(raw: bytes, password: str | None) -> bytes:
    try:
        return decrypt_if_needed(raw, password)
    except PasswordRequiredError:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "password_required",
                "message": "PDF ini dilindungi kata sandi. Masukkan kata sandi untuk melanjutkan.",
            },
        ) from None
    except pikepdf.PdfError as e:
        raise HTTPException(
            status_code=400,
            detail="Kata sandi salah atau PDF tidak dapat dibuka.",
        ) from e


@router.post("/split-pages")
async def split_pdf_pages(
    file: UploadFile = File(...),
    pages: str = Form(..., description='JSON array nomor halaman, contoh: [1,3,5]'),
    password: str | None = Form(None),
):
    """
    Ekstrak halaman terpilih: 1 halaman → satu PDF; lebih dari satu → ZIP berisi satu PDF per halaman.
    """
    raw = await _read_and_validate_pdf(file)
    clear = _decrypt_upload_for_tools(raw, password)
    page_list = _parse_pages_json(pages)
    stem = _stem_from_filename(file.filename or "document.pdf")
    try:
        content, out_name, media = split_selected_pages(
            clear, page_list, base_stem=stem
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except pikepdf.PdfError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Gagal memproses PDF: {e}",
        ) from e

    cd = f'attachment; filename="{out_name}"; filename*=UTF-8\'\'{quote(out_name)}'
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": cd},
    )


@router.post("/delete-pages")
async def delete_pdf_pages(
    file: UploadFile = File(...),
    pages: str = Form(..., description="JSON array nomor halaman yang akan dihapus (1-based)"),
    password: str | None = Form(None),
):
    """
    Hapus halaman terpilih; hasil satu PDF baru tanpa halaman tersebut.
    """
    raw = await _read_and_validate_pdf(file)
    clear = _decrypt_upload_for_tools(raw, password)
    page_list = _parse_pages_json(pages)
    stem = _stem_from_filename(file.filename or "document.pdf")
    try:
        content, out_name = delete_selected_pages(
            clear, page_list, base_stem=stem
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except pikepdf.PdfError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Gagal memproses PDF: {e}",
        ) from e

    cd = f'attachment; filename="{out_name}"; filename*=UTF-8\'\'{quote(out_name)}'
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": cd},
    )


@router.post("/to-word")
async def pdf_to_word(
    file: UploadFile = File(...),
    password: str | None = Form(None),
):
    """
    Konversi PDF ke format Word (.docx).
    Jika PDF terenkripsi dan password belum diberikan, kembalikan 401.
    """
    raw = await _read_and_validate_pdf(file)

    # Deteksi PDF terenkripsi
    decrypted_bytes = raw
    try:
        with Pdf.open(BytesIO(raw)):
            pass
    except PasswordError:
        if not password:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "password_required",
                    "message": "PDF ini dilindungi kata sandi. Masukkan kata sandi untuk melanjutkan.",
                },
            )
        try:
            with Pdf.open(BytesIO(raw), password=password) as pdf:
                buf = BytesIO()
                pdf.save(buf, encryption=None)
                decrypted_bytes = buf.getvalue()
        except (PasswordError, pikepdf.PdfError) as e:
            raise HTTPException(
                status_code=400,
                detail="Kata sandi salah atau PDF tidak dapat dibuka.",
            ) from e
    except pikepdf.PdfError as e:
        raise HTTPException(
            status_code=400,
            detail=f"PDF tidak valid atau rusak: {e}",
        ) from e

    try:
        docx_bytes = convert_pdf_to_docx(decrypted_bytes)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    stem = _stem_from_filename(file.filename or "document.pdf")
    out_name = f"{stem}.docx"
    cd = f'attachment; filename="{out_name}"; filename*=UTF-8\'\'{quote(out_name)}'

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": cd},
    )


@router.post("/to-excel")
async def pdf_to_excel(
    file: UploadFile = File(...),
    password: str | None = Form(None),
):
    """
    Konversi PDF ke format Excel (.xlsx).
    Fokus pada ekstraksi tabel agar baris & kolom tetap rapi.
    Jika PDF terenkripsi dan password belum diberikan, kembalikan 401.
    """
    raw = await _read_and_validate_pdf(file)

    # Deteksi PDF terenkripsi
    decrypted_bytes = raw
    try:
        with Pdf.open(BytesIO(raw)):
            pass
    except PasswordError:
        if not password:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "password_required",
                    "message": "PDF ini dilindungi kata sandi. Masukkan kata sandi untuk melanjutkan.",
                },
            )
        try:
            with Pdf.open(BytesIO(raw), password=password) as pdf:
                buf = BytesIO()
                pdf.save(buf, encryption=None)
                decrypted_bytes = buf.getvalue()
        except (PasswordError, pikepdf.PdfError) as e:
            raise HTTPException(
                status_code=400,
                detail="Kata sandi salah atau PDF tidak dapat dibuka.",
            ) from e
    except pikepdf.PdfError as e:
        raise HTTPException(
            status_code=400,
            detail=f"PDF tidak valid atau rusak: {e}",
        ) from e

    try:
        xlsx_bytes = convert_pdf_to_excel(decrypted_bytes)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    stem = _stem_from_filename(file.filename or "document.pdf")
    out_name = f"{stem}.xlsx"
    cd = f'attachment; filename="{out_name}"; filename*=UTF-8\'\'{quote(out_name)}'

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": cd},
    )


@router.post("/merge-pages")
async def merge_pdf_pages(
    files: list[UploadFile] = File(...),
    order: str = Form(..., description='JSON array: [{"file_index":0,"page":1}, ...]'),
    passwords: str | None = Form(None, description='JSON object, contoh: {"0":"pwdA","2":"pwdB"}'),
):
    """
    Gabungkan halaman terpilih dari banyak file sesuai urutan kustom.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Unggah minimal satu file PDF.")

    try:
        order_items = json.loads(order)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Field order harus JSON array.") from e
    if not isinstance(order_items, list) or not order_items:
        raise HTTPException(status_code=400, detail="Order harus array dan tidak boleh kosong.")

    pwd_map = _parse_json_object(passwords)

    raw_files: list[bytes] = []
    stems: list[str] = []
    for f in files:
        raw = await _read_and_validate_pdf(f)
        raw_files.append(raw)
        stems.append(_stem_from_filename(f.filename or "document.pdf"))

    clear_files: list[bytes] = []
    for idx, raw in enumerate(raw_files):
        pwd = pwd_map.get(str(idx))
        try:
            clear = decrypt_if_needed(raw, pwd)
        except PasswordRequiredError:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "password_required",
                    "file_index": idx,
                    "message": f"File ke-{idx + 1} membutuhkan kata sandi.",
                },
            ) from None
        except pikepdf.PdfError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Kata sandi salah atau file ke-{idx + 1} tidak dapat dibuka: {e}",
            ) from e
        clear_files.append(clear)

    merge_input: list[tuple[bytes, int]] = []
    for i, it in enumerate(order_items):
        if not isinstance(it, dict):
            raise HTTPException(status_code=400, detail=f"Item order ke-{i + 1} tidak valid.")
        if "file_index" not in it or "page" not in it:
            raise HTTPException(status_code=400, detail=f"Item order ke-{i + 1} wajib punya file_index dan page.")
        fi = it["file_index"]
        pg = it["page"]
        if isinstance(fi, bool) or not isinstance(fi, int):
            raise HTTPException(status_code=400, detail=f"file_index pada item ke-{i + 1} harus integer.")
        if isinstance(pg, bool) or not isinstance(pg, int):
            raise HTTPException(status_code=400, detail=f"page pada item ke-{i + 1} harus integer.")
        if fi < 0 or fi >= len(clear_files):
            raise HTTPException(status_code=400, detail=f"file_index pada item ke-{i + 1} di luar batas.")
        merge_input.append((clear_files[fi], pg))

    try:
        merged = merge_selected_pages(merge_input)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except pikepdf.PdfError as e:
        raise HTTPException(status_code=400, detail=f"Gagal merge PDF: {e}") from e

    out_name = f"{stems[0]}_merged.pdf" if stems else "merged.pdf"
    cd = f'attachment; filename="{out_name}"; filename*=UTF-8\'\'{quote(out_name)}'
    return Response(
        content=merged,
        media_type="application/pdf",
        headers={"Content-Disposition": cd},
    )

