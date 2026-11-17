"""PDF: use text layer first, OCR *only* for scanned pages or when requested."""
from pathlib import Path
import os
from .types import ExtractedDocument, Unit


def read_pdf(path: Path, cfg: dict) -> ExtractedDocument:
    import fitz
    result = ExtractedDocument()
    mode = cfg.get("ocr_mode", "auto")
    threshold = int(cfg.get("min_native_chars", 35))
    ocr_language = cfg.get("ocr_language", "vie+eng")
    ocr_dpi = int(cfg.get("ocr_dpi", 220))

    with fitz.open(path) as pdf:
        result.pages_total = len(pdf)
        for i, page in enumerate(pdf):
            page_no = i + 1
            original_text = page.get_text("text", sort=True) or ""
            native_chars = sum(c.isalnum() for c in original_text)
            needs_ocr = mode == "always" or (mode == "auto" and native_chars < threshold)
            text = original_text
            method = "native"
            if needs_ocr:
                try:
                    import pytesseract
                    from PIL import Image
                    tess_path = cfg.get("tesseract_cmd") or os.getenv("TESSERACT_CMD")
                    if tess_path:
                        pytesseract.pytesseract.tesseract_cmd = tess_path
                    pix = page.get_pixmap(dpi=ocr_dpi, alpha=False)
                    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    ocr_text = pytesseract.image_to_string(image, lang=ocr_language, config="--psm 3")
                    if ocr_text.strip():
                        text = ocr_text
                        method = "ocr"
                        result.ocr_pages.append(page_no)
                    else:
                        result.warnings.append(f"Trang {page_no}: OCR không nhận được nội dung")
                except Exception as exc:
                    # If mixed PDF, keep native text even when OCR unavailable.
                    result.warnings.append(f"Trang {page_no}: OCR lỗi ({type(exc).__name__}: {exc})")
            if method == "native" and text.strip():
                result.native_pages.append(page_no)
            if text.strip():
                for line_no, line in enumerate(text.splitlines(), start=1):
                    if line.strip():
                        result.units.append(Unit(line, {"page": page_no, "line": line_no}, method))
            else:
                result.warnings.append(f"Trang {page_no}: Không có text để lập chỉ mục")
    return result
