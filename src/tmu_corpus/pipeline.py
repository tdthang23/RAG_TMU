"""Offline corpus build, reproducible IDs, audit logs, quality summary."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from .pdf_reader import read_pdf
from .word_reader import read_docx
from .excel_reader import read_excel
from .metadata import extract_metadata, load_registry, merge_reviewed_metadata
from .structure import passages_from_units

EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xlsm", ".xls"}


def _sha256(path: Path) -> str:
    hash_ = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            hash_.update(block)
    return hash_.hexdigest()


def _id(value: str, size: int = 14) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:size]


def _write_jsonl(path: Path, records: list[dict]):
    with path.open("w", encoding="utf-8") as fh:
        for obj in records:
            fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=False) + "\n")


def build(cfg: dict) -> dict:
    input_dir = Path(cfg["input_dir"])
    output_dir = Path(cfg["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    if not input_dir.exists():
        raise FileNotFoundError(f"Thư mục đầu vào chưa tồn tại: {input_dir}")
    registry = load_registry(Path(cfg["metadata_registry"])) if cfg.get("metadata_registry") else {}
    docs = []
    passages = []
    errors = []
    warnings = []
    by_type: dict[str, int] = {}
    ocr_pages = 0
    files = sorted((p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS and not p.name.startswith("~$")), key=lambda p: p.as_posix())
    for path in files:
        rel = path.relative_to(input_dir).as_posix()
        try:
            digest = _sha256(path)
            doc_id = f"DOC_{_id(rel)}"
            version_id = f"VER_{digest[:16]}"
            ext = path.suffix.lower()
            if ext == ".pdf":
                extraction = read_pdf(path, cfg.get("pdf", {}))
            elif ext == ".docx":
                extraction = read_docx(path)
            else:
                extraction = read_excel(path, cfg.get("excel", {}))
            text = "\n".join(u.text for u in extraction.units)
            meta = extract_metadata(text) if ext not in (".xlsx", ".xlsm", ".xls") else extract_metadata("\n".join(u.text for u in extraction.units[:20]))
            meta = merge_reviewed_metadata(meta, registry, rel)
            doc_record = {
                "document_id": doc_id,
                "version_id": version_id,
                "source_file": rel,
                "source_sha256": digest,
                "file_type": ext.lstrip("."),
                "page_count": extraction.pages_total,
                "ocr_pages": extraction.ocr_pages,
                "native_pages": extraction.native_pages,
                "metadata": meta,
                "passage_count": 0,
                "warnings": extraction.warnings,
            }
            draft = passages_from_units(extraction.units, **{
                "max_chars": int(cfg.get("chunking", {}).get("max_chars", 950)),
                "overlap_chars": int(cfg.get("chunking", {}).get("overlap_chars", 120)),
            })
            seen = set()
            min_len = int(cfg.get("quality", {}).get("min_passage_chars", 12))
            for j, p in enumerate(draft, start=1):
                if len(p["raw_text"].strip()) < min_len:
                    continue
                source_locator = p.get("locators", [])
                passage_id = f"{doc_id}_P{j:05d}"
                if passage_id in seen:
                    raise AssertionError("Duplicate passage ID")
                seen.add(passage_id)
                passage = {
                    "passage_id": passage_id,
                    "document_id": doc_id,
                    "version_id": version_id,
                    "text": p.get("text", p["raw_text"]),
                    "raw_text": p["raw_text"],
                    "hierarchy": p["hierarchy"],
                    "source_locator": source_locator,
                    "extraction_methods": p["extraction_methods"],
                    "metadata": {
                        "document_number": meta.get("document_number"),
                        "issuer": meta.get("issuer"),
                        "effective_from": meta.get("effective_from"),
                        "effective_to": meta.get("effective_to"),
                        "effective_academic_year": meta.get("effective_academic_year"),
                        "applicable_cohorts": meta.get("applicable_cohorts", []),
                        "applicable_programs": meta.get("applicable_programs", []),
                        "verification_status": meta.get("verification_status", "unverified"),
                    },
                    "source_file": rel,
                    "source_sha256": digest,
                }
                passages.append(passage)
            doc_record["passage_count"] = len(seen)
            docs.append(doc_record)
            warnings.extend({"source_file": rel, "warning": w} for w in extraction.warnings)
            by_type[ext] = by_type.get(ext, 0) + 1
            ocr_pages += len(extraction.ocr_pages)
        except Exception as exc:
            errors.append({"source_file": rel, "error_type": type(exc).__name__, "message": str(exc)})

    _write_jsonl(output_dir / "documents.jsonl", docs)
    _write_jsonl(output_dir / "passages.jsonl", passages)
    (output_dir / "corpus.json").write_text(
        json.dumps({"schema_version": "1.0.0", "documents": docs, "passages": passages}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_jsonl(output_dir / "errors.jsonl", errors)
    _write_jsonl(output_dir / "warnings.jsonl", warnings)
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(input_dir),
        "files_discovered": len(files),
        "documents_ok": len(docs),
        "documents_failed": len(errors),
        "passages": len(passages),
        "pages_ocr": ocr_pages,
        "by_extension": by_type,
        "verified_metadata_docs": sum(d["metadata"].get("verification_status") == "verified" for d in docs),
        "documents_without_text": [d["source_file"] for d in docs if d["passage_count"] == 0],
        "error_files": [e["source_file"] for e in errors],
        "notes": [
            "Metadata auto-extracted must be manually verified before validity-sensitive retrieval.",
            "No gold answer/gold evidence is included in the online corpus.",
            "BM25/vector indexing is downstream: this pipeline only creates JSONL.",
        ],
    }
    (output_dir / "quality_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "manifest.json").write_text(json.dumps({
        "schema_version": "1.0.0", "created_at_utc": report["created_at_utc"],
        "files": [{"document_id": d["document_id"], "version_id": d["version_id"], "path": d["source_file"], "sha256": d["source_sha256"]} for d in docs],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
