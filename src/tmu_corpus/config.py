"""Load config independent of the current working directory."""
from pathlib import Path
import yaml


def load_config(path: str | Path) -> dict:
    p = Path(path).resolve()
    with p.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    for name in ("input_dir", "output_dir", "metadata_registry"):
        raw = cfg.get(name)
        if raw:
            value = Path(raw)
            cfg[name] = (p.parent / value).resolve() if not value.is_absolute() else value
    pdf_cfg = cfg.setdefault("pdf", {})
    if pdf_cfg.get("ocr_mode", "auto") not in ("auto", "always", "never"):
        raise ValueError("pdf.ocr_mode chỉ nhận auto | always | never")
    return cfg
