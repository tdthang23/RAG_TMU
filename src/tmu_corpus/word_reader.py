"""DOCX paragraphs and tables in document-body order."""
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from .types import ExtractedDocument, Unit


def read_docx(path: Path) -> ExtractedDocument:
    doc = Document(str(path))
    result = ExtractedDocument()
    index = 0
    for element in doc.element.body.iterchildren():
        if element.tag == qn("w:p"):
            para = Paragraph(element, doc)
            if para.text.strip():
                index += 1
                for lno, line in enumerate(para.text.splitlines(), start=1):
                    if line.strip():
                        result.units.append(Unit(line, {"paragraph": index, "line": lno}, "docx"))
        elif element.tag == qn("w:tbl"):
            table = Table(element, doc)
            index += 1
            for ri, row in enumerate(table.rows, start=1):
                # Retain tabular content and row provenance.
                cells = [" ".join(c.text.split()) for c in row.cells]
                if any(cells):
                    result.units.append(Unit(" | ".join(cells), {"table": index, "row": ri}, "docx_table"))
    if not result.units:
        result.warnings.append("DOCX không có đoạn/tables text. Ảnh chèn trong Word chưa được OCR.")
    return result
