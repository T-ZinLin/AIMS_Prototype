from io import BytesIO

import fitz
from PIL import Image

from aims.documents import DocumentPreviewError, page_count, render_preview


def test_image_upload_is_rendered_locally():
    source = Image.new("RGB", (120, 80), "white")
    payload = BytesIO()
    source.save(payload, format="PNG")

    preview = render_preview("working.png", payload.getvalue())

    assert preview.source_type == "image"
    assert preview.page_count == 1
    assert preview.image.size == (120, 80)


def test_pdf_page_can_be_selected_and_rendered():
    document = fitz.open()
    document.new_page().insert_text((72, 72), "page one")
    document.new_page().insert_text((72, 72), "page two")
    payload = document.tobytes()
    document.close()

    assert page_count("submission.pdf", payload) == 2
    preview = render_preview("submission.pdf", payload, page_number=2)

    assert preview.source_type == "PDF"
    assert preview.page_number == 2
    assert preview.page_count == 2
    assert preview.image.width > 0


def test_unknown_upload_type_is_rejected():
    try:
        render_preview("submission.txt", b"not mathematics")
    except DocumentPreviewError as exc:
        assert "JPG" in str(exc)
    else:
        raise AssertionError("Unsupported upload type should be rejected")
