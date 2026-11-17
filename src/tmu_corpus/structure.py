"""Structure-aware passage builder: chapters, articles, clauses, points."""
import re
from .types import Unit

CHAPTER = re.compile(r"^\s*Chương\s+([IVXLCDM]+|\d+)\b\s*[.\-:]?\s*(.*)$", re.I)
ARTICLE = re.compile(r"^\s*Điều\s+(\d+[a-z]?)\b\s*[.\-:]?\s*(.*)$", re.I)
CLAUSE = re.compile(r"^\s*(\d{1,2})\s*[.)]\s+(.*)$")
POINT = re.compile(r"^\s*([a-zđ])\)\s+(.*)$", re.I)


def split_long(text: str, max_chars: int, overlap: int) -> list[str]:
    """Chunk by char budget, word aware; bounded overlap, guaranteed progress."""
    if len(text) <= max_chars:
        return [text.strip()] if text.strip() else []
    out = []
    pos = 0
    while pos < len(text):
        end = min(pos + max_chars, len(text))
        if end < len(text):
            boundary = max(text.rfind("\n", pos + max_chars // 2, end), text.rfind(" ", pos + max_chars // 2, end))
            if boundary > pos:
                end = boundary
        piece = text[pos:end].strip()
        if piece:
            out.append(piece)
        if end >= len(text):
            break
        pos = max(pos + 1, end - overlap)
    return out


def passages_from_units(units: list[Unit], max_chars: int = 950, overlap_chars: int = 120) -> list[dict]:
    """Records of raw source text + structural context, without fabricated legal assertions."""
    if max_chars < 100 or not (0 <= overlap_chars < max_chars):
        raise ValueError("chunking: max_chars >= 100 và 0 <= overlap_chars < max_chars")
    if not units:
        return []
    if all(u.extraction_method == "excel" for u in units):
        out = []
        for u in units:
            for i, piece in enumerate(split_long(u.text, max_chars, overlap_chars)):
                out.append({"raw_text": piece, "hierarchy": {"chapter": None, "article": None, "article_title": None, "clause": None, "point": None},
                            "locators": [u.locator], "extraction_methods": [u.extraction_method], "part": i + 1})
        return out

    chapter = article = article_title = clause = point = None
    current_lines: list[str] = []
    current_locs: list[dict] = []
    current_methods: set[str] = set()
    current_hierarchy = {}
    result: list[dict] = []

    def snapshot():
        return {"chapter": chapter, "article": article, "article_title": article_title, "clause": clause, "point": point}

    def flush():
        nonlocal current_lines, current_locs, current_methods
        txt = "\n".join(current_lines).strip()
        if txt:
            for i, piece in enumerate(split_long(txt, max_chars, overlap_chars)):
                # Prefix indexable context without changing raw_text/provenance.
                parts = []
                if current_hierarchy.get("chapter"):
                    parts.append(f"Chương {current_hierarchy['chapter']}")
                if current_hierarchy.get("article"):
                    article_label = f"Điều {current_hierarchy['article']}"
                    if current_hierarchy.get("article_title"):
                        article_label += f". {current_hierarchy['article_title']}"
                    parts.append(article_label)
                content = "\n".join(parts + [piece]) if parts and not piece.startswith(parts[-1]) else piece
                result.append({"text": content, "raw_text": piece, "hierarchy": dict(current_hierarchy),
                               "locators": list(current_locs), "extraction_methods": sorted(current_methods), "part": i + 1})
        current_lines, current_locs, current_methods = [], [], set()

    for u in units:
        line = u.text.strip()
        if not line:
            continue
        if u.extraction_method == "docx_table" and current_lines and "docx_table" not in current_methods:
            flush()
        elif u.extraction_method != "docx_table" and "docx_table" in current_methods:
            flush()
        if m := CHAPTER.match(line):
            flush()
            chapter, article, article_title, clause, point = m.group(1), None, None, None, None
        elif m := ARTICLE.match(line):
            flush()
            article, article_title, clause, point = m.group(1), m.group(2), None, None
        elif article is not None and (m := CLAUSE.match(line)):
            flush()
            clause, point = m.group(1), None
        elif article is not None and (m := POINT.match(line)):
            flush()
            point = m.group(1)
        if not current_lines:
            current_hierarchy = snapshot()
        current_lines.append(line)
        if not current_locs or current_locs[-1] != u.locator:
            current_locs.append(u.locator)
        current_methods.add(u.extraction_method)
    flush()
    return result
