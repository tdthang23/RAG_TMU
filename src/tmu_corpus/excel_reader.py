"""Excel row documents with sheet/row provenance."""
from pathlib import Path
from datetime import date, datetime
from .types import ExtractedDocument, Unit


def _text(v):
    if v is None:
        return ""
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return " ".join(str(v).split())


def _iter_xls(path: Path):
    try:
        import xlrd
    except ImportError as exc:
        raise RuntimeError("File .xls cần cài thêm: pip install '.[xls]' hoặc lưu lại dạng .xlsx") from exc
    wb = xlrd.open_workbook(str(path))
    for sheet in wb.sheets():
        def rows():
            for r in range(sheet.nrows):
                yield [sheet.cell_value(r, c) for c in range(sheet.ncols)]
        yield sheet.name, rows()


def _iter_xlsx(path: Path):
    import openpyxl
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    try:
        for sheet in wb.worksheets:
            yield sheet.title, sheet.iter_rows(values_only=True)
    finally:
        wb.close()


def read_excel(path: Path, cfg: dict) -> ExtractedDocument:
    result = ExtractedDocument()
    header_row = max(1, int(cfg.get("header_row", 1)))
    iterator = _iter_xls(path) if path.suffix.lower() == ".xls" else _iter_xlsx(path)
    for sheet_name, rows in iterator:
        headers = None
        for rno, row in enumerate(rows, start=1):
            values = [_text(v) for v in row]
            if rno < header_row:
                continue
            if rno == header_row:
                headers = [v if v else f"column_{i+1}" for i, v in enumerate(values)]
                continue
            if not any(values):
                continue
            if not headers:
                headers = [f"column_{i+1}" for i in range(len(values))]
            items = []
            for i, value in enumerate(values):
                if value:
                    col = headers[i] if i < len(headers) else f"column_{i+1}"
                    items.append(f"{col}: {value}")
            if items:
                result.units.append(Unit("; ".join(items), {"sheet": sheet_name, "row": rno}, "excel"))
    if not result.units:
        result.warnings.append("Excel không có dòng dữ liệu có nội dung sau hàng tiêu đề")
    return result
