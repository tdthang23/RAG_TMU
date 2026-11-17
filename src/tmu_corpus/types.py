"""Tiny internal types, no external framework required."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Unit:
    text: str
    locator: dict[str, Any]
    extraction_method: str = "native"


@dataclass
class ExtractedDocument:
    units: list[Unit] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pages_total: int | None = None
    ocr_pages: list[int] = field(default_factory=list)
    native_pages: list[int] = field(default_factory=list)
