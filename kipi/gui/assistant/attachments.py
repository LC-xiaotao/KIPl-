"""Files the AI assistant can take as context: PDF, Word, Excel/CSV, text and HTML.

The text is extracted here and sent with the user's message, so every provider sees the
same plain text; nothing provider-specific is uploaded. Each file is capped and the
assistant panel caps the total, so one long PDF cannot fill the model's context by itself.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, List, Tuple

#: Characters sent with the message, and from all files in one message.
MAX_FILE_CHARS = 30_000
MAX_TOTAL_CHARS = 60_000
#: The full text kept for search/read tools; far more than one message carries.
MAX_FULL_CHARS = 1_000_000
MAX_PDF_PAGES = 200
MAX_TABLE_ROWS = 200

TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".log", ".py", ".json", ".yaml", ".yml", ".xml"}
TABLE_SUFFIXES = {".csv", ".tsv"}
HTML_SUFFIXES = {".html", ".htm"}


@dataclass
class Attachment:
    """One file: its opening text for the message, and the full text for the tools."""

    name: str
    text: str
    note: str
    full_text: str = ""
    pages: List[Tuple[int, str]] = field(default_factory=list)

    @property
    def chars(self) -> int:
        return len(self.full_text or self.text)

    @property
    def complete(self) -> bool:
        return self.chars <= len(self.text)


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: List[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in ("p", "br", "div", "tr", "li", "h1", "h2", "h3", "h4", "table"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    text = text.strip()
    if len(text) <= limit:
        return text, False
    return text[:limit].rstrip() + "\n…（内容过长，已截断）", True


def _table_text(rows: Iterable[Iterable[object]]) -> tuple[str, int]:
    lines: List[str] = []
    count = 0
    for row in rows:
        if count >= MAX_TABLE_ROWS:
            break
        lines.append(" | ".join("" if cell is None else str(cell) for cell in row))
        count += 1
    return "\n".join(lines), count


def _pdf(path: Path) -> tuple[str, str]:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:  # noqa: BLE001 - pypdf raises several types
            raise ValueError("PDF 已加密，无法读取") from exc
    total = len(reader.pages)
    pages = []
    for number, page in enumerate(reader.pages[:MAX_PDF_PAGES], 1):
        pages.append(f"[第 {number} 页]\n{page.extract_text() or ''}")
    note = f"PDF，{total} 页"
    if total > MAX_PDF_PAGES:
        note += f"，只读前 {MAX_PDF_PAGES} 页"
    return "\n\n".join(pages), note


def _docx(path: Path) -> tuple[str, str]:
    import docx
    document = docx.Document(str(path))
    parts = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        text, _rows = _table_text(
            ([cell.text.strip() for cell in row.cells] for row in table.rows))
        if text:
            parts.append(f"[表格]\n{text}")
    return "\n\n".join(parts), f"Word，{len(document.paragraphs)} 段"


def _xlsx(path: Path) -> tuple[str, str]:
    import openpyxl
    workbook = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    try:
        parts = []
        for sheet in workbook.worksheets:
            text, _rows = _table_text(sheet.iter_rows(values_only=True))
            parts.append(f"[工作表：{sheet.title}]\n{text}")
        return "\n\n".join(parts), f"Excel，{len(workbook.worksheets)} 个工作表"
    finally:
        workbook.close()


def _csv(path: Path) -> tuple[str, str]:
    text = _read_text(path)
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    table, rows = _table_text(csv.reader(io.StringIO(text), delimiter=delimiter))
    return table, f"表格，{rows} 行"


def _html(path: Path) -> tuple[str, str]:
    parser = _HTMLText()
    parser.feed(_read_text(path))
    lines = [line.strip() for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line), "HTML"


def _plain(path: Path) -> tuple[str, str]:
    text = _read_text(path)
    if path.suffix.lower() == ".json":
        try:
            text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
        except ValueError:
            pass
    if "\x00" in text:
        raise ValueError("不是可读取的文本或文档格式")
    return text, "文本"


def _pdf_pages(text: str) -> List[Tuple[int, str]]:
    parts = re.split(r"(?m)^\[第 (\d+) 页\]\s*$", text)
    return [(int(parts[i]), parts[i + 1].strip())
            for i in range(1, len(parts) - 1, 2)]


def extract_attachment(path: Path, limit: int = MAX_FILE_CHARS) -> Attachment:
    """Read one file: the opening text for the message, and the full text for tools."""
    path = Path(path)
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            full_text, note = _pdf(path)
        elif suffix == ".docx":
            full_text, note = _docx(path)
        elif suffix in (".xlsx", ".xlsm"):
            full_text, note = _xlsx(path)
        elif suffix in TABLE_SUFFIXES:
            full_text, note = _csv(path)
        elif suffix in HTML_SUFFIXES:
            full_text, note = _html(path)
        elif suffix in TEXT_SUFFIXES or suffix == "":
            full_text, note = _plain(path)
        elif suffix == ".xls":
            raise ValueError("旧版 .xls 暂不支持，请另存为 .xlsx 或 CSV")
        else:
            full_text, note = _plain(path)
    except ImportError as exc:
        raise ValueError(f"缺少读取该文件所需的库（{exc.name}），请先安装") from exc
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 - a damaged file becomes a message for the user
        raise ValueError(f"读取失败：{exc}") from exc
    full_text = (full_text or "").strip()
    if len(full_text) > MAX_FULL_CHARS:
        full_text = full_text[:MAX_FULL_CHARS].rstrip() + "\n…（文件过长，只保留前 100 万字）"
    digest, cut = _truncate(full_text, limit)
    if not digest:
        return Attachment(path.name, "（没有提取到文字；如果是扫描版 PDF，需要先做 OCR。）",
                          f"{note}，未提取到文字")
    pages = _pdf_pages(full_text) if suffix == ".pdf" else []
    chars = f"{len(full_text):,} 字"
    sent = f"，随消息发送前 {len(digest):,} 字" if cut else ""
    note = f"{note}，{chars}{sent}"
    return Attachment(path.name, digest, note, full_text, pages)
