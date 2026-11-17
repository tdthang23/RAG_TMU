"""Offline end-to-end smoke tests with artificial documents only."""
import csv
import json
import shutil
from pathlib import Path
import pytest
from tmu_corpus.pipeline import build
from tmu_corpus.structure import passages_from_units, split_long
from tmu_corpus.metadata import extract_metadata
from tmu_corpus.types import Unit


def test_metadata_no_hallucinated_applicability():
    txt = "TRƯỜNG ĐẠI HỌC THƯƠNG MẠI\nSố: 999/QĐ-DEMO\nHà Nội, ngày 10 tháng 11 năm 2026\nÁp dụng cho khóa 60."
    data = extract_metadata(txt)
    assert data["document_number"] == "999/QĐ-DEMO"
    assert data["issued_date"] == "2026-11-10"
    assert data["applicable_cohorts"] == []
    assert data["mentioned_cohorts"] == ["K60"]
    assert data["verification_status"] == "unverified"


def test_structure_split_and_overlap():
    items = [
        Unit("Chương I. QUY ĐỊNH", {"page": 1}),
        Unit("Điều 2. Quy định học vụ", {"page": 1}),
        Unit("1. Học viên đáp ứng điều kiện A.", {"page": 1}),
        Unit("2. Học viên đáp ứng điều kiện B.", {"page": 2}),
    ]
    chunks = passages_from_units(items, 200, 30)
    assert any(c["hierarchy"]["article"] == "2" and c["hierarchy"]["clause"] == "1" for c in chunks)
    assert any(c["hierarchy"]["clause"] == "2" for c in chunks)
    assert any("Điều 2" in c["text"] for c in chunks)
    assert len(split_long("Một câu thử nghiệm " * 200, 200, 30)) > 1


def test_end_to_end(tmp_path):
    from docx import Document
    from openpyxl import Workbook
    import fitz
    inp = tmp_path / "raw"
    out = tmp_path / "processed"
    inp.mkdir()
    d = Document()
    for line in ["TRƯỜNG ĐẠI HỌC THƯƠNG MẠI", "Số: 999/QĐ-DEMO", "Hà Nội, ngày 10 tháng 11 năm 2026", "Điều 1. Phạm vi", "1. Nội dung thử nghiệm thuộc khóa 60."]:
        d.add_paragraph(line)
    t = d.add_table(rows=1, cols=2)
    t.cell(0, 0).text = "Trường A"
    t.cell(0, 1).text = "Giá trị B"
    d.save(inp / "demo.docx")
    wb = Workbook()
    ws = wb.active
    ws.append(["Mã", "Nội dung"])
    ws.append(["1", "Thông tin minh họa Excel"])
    wb.save(inp / "data.xlsx")
    pdf = fitz.open()
    p = pdf.new_page()
    p.insert_text((50, 50), "Text native PDF for testing. More than thirty five characters.")
    pdf.save(inp / "text.pdf")
    pdf.close()
    registry = tmp_path / "registry.csv"
    with registry.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["filename", "applicable_cohorts", "verification_status"])
        w.writerow(["demo.docx", "K60", "verified"])
    cfg = {"input_dir": inp, "output_dir": out, "metadata_registry": registry,
           "pdf": {"ocr_mode": "never"}, "chunking": {"max_chars": 900, "overlap_chars": 100}, "quality": {"min_passage_chars": 4}}
    stats = build(cfg)
    assert stats["documents_ok"] == 3, stats
    assert stats["documents_failed"] == 0, stats
    assert stats["passages"] >= 4
    corpus = json.loads((out / "corpus.json").read_text(encoding="utf-8"))
    assert len(corpus["documents"]) == 3
    assert len(corpus["passages"]) == stats["passages"]
    docs = [json.loads(l) for l in (out / "documents.jsonl").read_text(encoding="utf-8").splitlines()]
    word = next(d for d in docs if d["file_type"] == "docx")
    assert word["metadata"]["applicable_cohorts"] == ["K60"]
    assert word["metadata"]["verification_status"] == "verified"
    assert word["metadata"]["document_number"] == "999/QĐ-DEMO"
    passages = [json.loads(l) for l in (out / "passages.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(p["extraction_methods"] == ["docx_table"] for p in passages)
    assert any(p["source_locator"][0].get("sheet") for p in passages)
    assert any(p["source_locator"][0].get("page") for p in passages)


@pytest.mark.skipif(not shutil.which("tesseract"), reason="OCR engine absent")
def test_scanned_pdf(tmp_path):
    import fitz
    from PIL import Image, ImageDraw, ImageFont
    from tmu_corpus.pdf_reader import read_pdf
    im = Image.new("RGB", (1400, 450), "white")
    draw = ImageDraw.Draw(im)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font = ImageFont.truetype(font_path, 40) if Path(font_path).exists() else ImageFont.load_default()
    draw.text((30, 40), "TEST OCR SCANNED PDF", font=font, fill="black")
    draw.text((30, 130), "Regulation text in a scanned page for retrieval.", font=font, fill="black")
    img = tmp_path / "scan.png"
    im.save(img)
    doc = fitz.open()
    page = doc.new_page(width=700, height=225)
    page.insert_image(page.rect, filename=str(img))
    path = tmp_path / "scan.pdf"
    doc.save(path)
    doc.close()
    res = read_pdf(path, {"ocr_mode": "auto", "ocr_language": "eng", "ocr_dpi": 220, "min_native_chars": 35})
    assert res.ocr_pages == [1], res.warnings
    assert "OCR" in " ".join(u.text for u in res.units)
