"""Conservative rule-based metadata; never invent legal validity/applicability."""
import csv
import re
import unicodedata
from pathlib import Path
from datetime import datetime


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip()


def _iso(y: str, m: str, d: str) -> str | None:
    try:
        return datetime(int(y), int(m), int(d)).date().isoformat()
    except ValueError:
        return None


def _find_date(s: str) -> str | None:
    m = re.search(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", s, re.I)
    if m:
        return _iso(m.group(3), m.group(2), m.group(1))
    m = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", s)
    if m:
        return _iso(m.group(3), m.group(2), m.group(1))
    return None


def extract_metadata(text: str) -> dict:
    lines = [_norm(s) for s in text.splitlines() if s.strip()]
    head = "\n".join(lines[:30])
    number_m = re.search(r"\bSố\s*:\s*(\d{1,6}\s*/\s*[^\s,;]+)", head, re.I)
    number = re.sub(r"\s+", "", number_m.group(1)).rstrip(".") if number_m else None
    issuer = None
    # Conservative issuer extraction, only from document header.
    for line in lines[:14]:
        if re.search(r"(?:TRƯỜNG ĐẠI HỌC THƯƠNG MẠI|BỘ GIÁO DỤC VÀ ĐÀO TẠO)", line, re.I):
            issuer = line
            break
    types = ("QUYẾT ĐỊNH", "THÔNG TƯ", "CÔNG VĂN", "QUY CHẾ", "THÔNG BÁO", "HƯỚNG DẪN")
    doc_type = next((t.title() for t in types if any(t in line.upper() for line in lines[:35])), None)
    issued_date = None
    for line in lines[:35]:
        if re.search(r"(?:Hà Nội|ngày\s+\d{1,2}\s+tháng)", line, re.I):
            issued_date = _find_date(line)
            if issued_date:
                break
    effective_date = None
    effective_academic_year = None
    for line in lines:
        if re.search(r"(?:có hiệu lực|hiệu lực thi hành|áp dụng từ)", line, re.I):
            academic = re.search(r"năm học\s*(\d{4})\s*[–—-]\s*(\d{4})", line, re.I)
            if academic:
                effective_academic_year = f"{academic.group(1)}-{academic.group(2)}"
            effective_match = re.search(r"(?:từ|kể từ)\s+(ngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4}|ngày\s+\d{1,2}[./-]\d{1,2}[./-]\d{4})", line, re.I)
            if effective_match:
                effective_date = _find_date(effective_match.group(1))
            elif re.search(r"kể từ ngày ký", line, re.I) and issued_date:
                effective_date = issued_date
    cohorts = sorted({f"K{n}" for n in re.findall(r"\b(?:khóa|khoá)\s+(\d{1,3})\b", text, re.I)})
    # Cohorts mentioned anywhere are CANDIDATES, not proof of applicability.
    return {
        "document_number": number,
        "title": None,
        "document_type": doc_type,
        "issuer": issuer,
        "issued_date": issued_date,
        "effective_from": effective_date,
        "effective_to": None,
        "effective_academic_year": effective_academic_year,
        "applicable_cohorts": [],
        "mentioned_cohorts": cohorts,
        "applicable_programs": [],
        "replaces": [],
        "verification_status": "unverified",
    }


def _split_list(value: str) -> list[str]:
    return [_norm(x) for x in re.split(r"[;,|]", value) if x.strip()]


def load_registry(path: Path) -> dict[str, dict]:
    """CSV authored by human. Match on filename or document_number."""
    if not path.exists():
        return {}
    registry = {}
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
            key = row.get("filename") or row.get("document_number")
            if key:
                registry[key.casefold().replace("\\", "/")] = row
    return registry


def merge_reviewed_metadata(auto: dict, registry: dict[str, dict], relative_file: str) -> dict:
    merged = dict(auto)
    matched = registry.get(relative_file.casefold().replace("\\", "/"))
    if not matched:
        matched = registry.get(Path(relative_file).name.casefold())
    if not matched and auto.get("document_number"):
        matched = registry.get(auto["document_number"].casefold())
    if not matched:
        return merged
    allowed = {"document_number", "title", "issuer", "issued_date", "effective_from", "effective_to", "effective_academic_year", "applicable_cohorts", "applicable_programs", "replaces", "verification_status", "source_url"}
    for field, value in matched.items():
        if field in allowed and value:
            if field in ("applicable_cohorts", "applicable_programs", "replaces"):
                merged[field] = _split_list(value)
            else:
                merged[field] = value
    if merged.get("verification_status") not in ("verified", "unverified", "needs_review"):
        merged["verification_status"] = "unverified"
    return merged
