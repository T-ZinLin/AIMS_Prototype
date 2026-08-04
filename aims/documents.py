from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import fitz
from PIL import Image, ImageOps, UnidentifiedImageError


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}


class DocumentPreviewError(ValueError):
    """Raised when an uploaded submission cannot be rendered safely."""


@dataclass(frozen=True)
class DocumentPreview:
    image: Image.Image
    filename: str
    page_number: int
    page_count: int
    source_type: str


def _extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise DocumentPreviewError("Upload a JPG, JPEG, PNG, or PDF file.")
    return extension


def page_count(filename: str, payload: bytes) -> int:
    extension = _extension(filename)
    if not payload:
        raise DocumentPreviewError("The uploaded file is empty.")
    if extension != ".pdf":
        return 1

    try:
        with fitz.open(stream=payload, filetype="pdf") as document:
            if document.page_count < 1:
                raise DocumentPreviewError("The PDF does not contain any pages.")
            return document.page_count
    except DocumentPreviewError:
        raise
    except Exception as exc:
        raise DocumentPreviewError("The PDF could not be opened.") from exc


def render_preview(filename: str, payload: bytes, page_number: int = 1) -> DocumentPreview:
    extension = _extension(filename)
    total_pages = page_count(filename, payload)
    if page_number < 1 or page_number > total_pages:
        raise DocumentPreviewError(f"Choose a page between 1 and {total_pages}.")

    if extension == ".pdf":
        try:
            with fitz.open(stream=payload, filetype="pdf") as document:
                page = document.load_page(page_number - 1)
                pixels = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
                with Image.open(BytesIO(pixels.tobytes("png"))) as rendered:
                    image = rendered.convert("RGB").copy()
        except Exception as exc:
            raise DocumentPreviewError("The selected PDF page could not be rendered.") from exc
        source_type = "PDF"
    else:
        try:
            with Image.open(BytesIO(payload)) as uploaded_image:
                image = ImageOps.exif_transpose(uploaded_image).convert("RGB").copy()
        except (UnidentifiedImageError, OSError) as exc:
            raise DocumentPreviewError("The uploaded image could not be opened.") from exc
        source_type = "image"

    return DocumentPreview(
        image=image,
        filename=filename,
        page_number=page_number,
        page_count=total_pages,
        source_type=source_type,
    )

