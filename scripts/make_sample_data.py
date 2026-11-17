"""Create 4 SYNTHETIC fixtures; not real university rules."""
from pathlib import Path
import csv
import sys

PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

from docx import Document
from openpyxl import Workbook

heading = "TÀI LIỆU GIẢ LẬP CHO KIỂM THỬ PHẦN MỀM"
content = [
    "TRƯỜNG ĐẠI HỌC THƯƠNG MẠI",
    "Số: 999/QĐ-DEMO",
    "Hà Nội, ngày 10 tháng 11 năm 2026",
    "QUYẾT ĐỊNH (GIẢ LẬP)",
    "Chương I. QUY ĐỊNH CHUNG",
    "Điều 1. Phạm vi áp dụng",
    "1. Quy định giả lập này chỉ dùng để kiểm thử hệ thống với sinh viên khóa 60.",
    "2. Không sử dụng các điều khoản giả lập để tư vấn cho người học.",
    "Điều 2. Điều kiện giả lập",
    "1. Sinh viên phải đáp ứng điều kiện A trong môi trường dữ liệu thử nghiệm.",
    "2. Trường hợp thuộc nhóm X được miễn điều kiện B trong bộ dữ liệu giả lập.",
    "Quyết định có hiệu lực kể từ ngày ký.",
]

# Word: paragraph and a table.
doc = Document()
for line in content:
    doc.add_paragraph(line)
table = doc.add_table(rows=2, cols=2)
table.cell(0, 0).text = "Trường"
table.cell(0, 1).text = "Giá trị"
table.cell(1, 0).text = "Ghi chú"
table.cell(1, 1).text = "Dữ liệu minh họa không có giá trị quy định"
doc.save(RAW / "decision_sample.docx")

# Excel: one row equals a retrievable passage.
wb = Workbook()
ws = wb.active
ws.title = "Thông tin"
ws.append(["Mã", "Nội dung", "Khóa"])
ws.append(["E01", "Hướng dẫn A, chỉ có giá trị minh họa", "K60"])
ws.append(["E02", "Hướng dẫn B, chỉ dùng thử nghiệm", "K59"])
wb.create_sheet("Sheet2")
wb["Sheet2"].append(["Mục", "Chi tiết"])
wb["Sheet2"].append(["M1", "Quy trình demo Excel"])
wb.save(RAW / "notes_sample.xlsx")

# PDF: rendered text, + a PDF with ONLY image pixels (scanned equivalent).
try:
    import fitz
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase import pdfmetrics
    from PIL import Image
    font_candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/tahoma.ttf"),
    ]
    font_path = next((p for p in font_candidates if p.exists()), None)
    if font_path:
        pdfmetrics.registerFont(TTFont("VN", str(font_path)))
    c = canvas.Canvas(str(RAW / "text_sample.pdf"), pagesize=(595, 842))
    c.setFont("VN" if font_path else "Helvetica", 11)
    for i, line in enumerate(content):
        c.drawString(50, 800 - i * 36, line)
    c.save()
    with fitz.open(RAW / "text_sample.pdf") as original:
        scanned = fitz.open()
        for page in original:
            pix = page.get_pixmap(dpi=220, alpha=False)
            dest_page = scanned.new_page(width=page.rect.width, height=page.rect.height)
            dest_page.insert_image(dest_page.rect, pixmap=pix)
        scanned.save(RAW / "scan_sample.pdf")
    print("Đã tạo: text_sample.pdf và scan_sample.pdf")
except ImportError:
    print("Thiếu reportlab/PyMuPDF để tạo PDF demo: pip install '.[test]'")

# CSV metadata registry is editable in Excel.
registry = PROJECT / "data" / "metadata" / "registry.csv"
with registry.open("w", newline="", encoding="utf-8-sig") as fh:
    writer = csv.DictWriter(fh, fieldnames=["filename", "document_number", "title", "issuer", "issued_date", "effective_from", "effective_to", "effective_academic_year", "applicable_cohorts", "applicable_programs", "replaces", "verification_status", "source_url"])
    writer.writeheader()
    writer.writerow({"filename": "decision_sample.docx", "document_number": "999/QĐ-DEMO", "title": "Quy định giả lập để thử chương trình", "applicable_cohorts": "K60", "applicable_programs": "chinh_quy", "verification_status": "verified"})
print("Đã tạo mẫu Word/Excel và registry tại", RAW)
print("LƯU Ý: TẤT CẢ DỮ LIỆU LÀ GIẢ LẬP. XÓA data/raw/* TRƯỚC KHI NẠP TÀI LIỆU THẬT.")
