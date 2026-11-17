"""CLI entrypoint."""
import argparse
import json
from pathlib import Path
from .config import load_config
from .pipeline import build


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build an auditable JSONL corpus from PDF/DOCX/Excel")
    ap.add_argument("command", choices=["build", "report"], nargs="?", default="build")
    ap.add_argument("--config", default="config.yaml", help="Path to config YAML")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    if args.command == "build":
        report = build(cfg)
    else:
        p = Path(cfg["output_dir"]) / "quality_report.json"
        report = json.loads(p.read_text(encoding="utf-8"))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.command == "build" and report["documents_failed"]:
        print("CẢNH BÁO: Một số file lỗi. Xem data/processed/errors.jsonl")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
