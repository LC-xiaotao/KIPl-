"""Files the AI assistant can take as context: PDF, Word, Excel/CSV, text, HTML and images.

Text is extracted here and sent with the user's message, so every provider sees the same
text. Images are resized and encoded here, then sent as image blocks by the provider
adapters; their base64 never goes to disk. Each file is capped and the assistant panel caps
the total, so one long PDF or a pile of screenshots cannot fill the model's context.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import math
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

#: Images: longest edge sent to the model, source/encoded byte caps, per-message count.
MAX_IMAGE_DIM = 1568
MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGES_PER_MESSAGE = 4

TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".log", ".py", ".json", ".yaml", ".yml", ".xml"}
TABLE_SUFFIXES = {".csv", ".tsv"}
HTML_SUFFIXES = {".html", ".htm"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


@dataclass
class Attachment:
    """One file: its opening text for the message, and the full text for the tools."""

    name: str
    text: str
    note: str
    full_text: str = ""
    pages: List[Tuple[int, str]] = field(default_factory=list)
    # Images carry their encoded bytes and metadata; text files leave these defaults.
    kind: str = "text"              # "text" | "image"
    mime: str = ""                  # image/png, image/jpeg
    data: str = ""                  # base64; memory only, never persisted
    width: int = 0
    height: int = 0
    byte_size: int = 0              # encoded bytes

    @property
    def chars(self) -> int:
        return 0 if self.is_image else len(self.full_text or self.text)

    @property
    def is_image(self) -> bool:
        return self.kind == "image"

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


def _fit_image(image, max_edge: int = MAX_IMAGE_DIM):
    """Scale down so the longest edge is at most ``max_edge``; never enlarge."""
    from qtpy.QtCore import Qt
    width, height = image.width(), image.height()
    long_edge = max(width, height)
    if long_edge <= max_edge or long_edge <= 0:
        return image
    scale = max_edge / float(long_edge)
    return image.scaled(max(1, round(width * scale)), max(1, round(height * scale)),
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)


def _encode_image(image, fmt: str, quality: int = 85) -> bytes:
    """Encode a QImage in memory; JPEG has no alpha, so composite it onto white."""
    from qtpy.QtCore import QBuffer, QIODevice, Qt
    from qtpy.QtGui import QImage, QPainter
    if fmt.upper() == "JPEG":
        rgb = QImage(image.size(), QImage.Format.Format_RGB32)
        rgb.fill(Qt.GlobalColor.white)
        painter = QPainter(rgb)
        try:
            painter.drawImage(0, 0, image)
        finally:
            painter.end()
        image = rgb
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    try:
        ok = image.save(buffer, fmt, quality) if fmt.upper() == "JPEG" \
            else image.save(buffer, fmt)
        if not ok:
            raise ValueError("图片编码失败")
        return bytes(buffer.data())
    finally:
        buffer.close()


def _image_attachment(path: Path, name: str) -> Attachment:
    """Load, orient, bound, encode and base64 one image for the model."""
    from qtpy.QtCore import Qt
    from qtpy.QtGui import QImageReader

    if path.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError(
            f"图片超过 {MAX_IMAGE_BYTES // (1024 * 1024)} MB 上限")
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and max(size.width(), size.height()) > MAX_IMAGE_DIM:
        # Bound the decoded size before reading, so a decompression bomb cannot allocate
        # a huge buffer just to be scaled down afterwards.
        reader.setScaledSize(size.scaled(MAX_IMAGE_DIM, MAX_IMAGE_DIM,
                                         Qt.AspectRatioMode.KeepAspectRatio))
    frames = reader.imageCount()
    image = reader.read()
    if image.isNull():
        raise ValueError(f"无法读取图片：{reader.errorString() or '格式不支持'}")
    image = _fit_image(image)

    fmt = "JPEG" if path.suffix.lower() in (".jpg", ".jpeg") else "PNG"
    mime = "image/jpeg" if fmt == "JPEG" else "image/png"
    raw = _encode_image(image, fmt)
    attempts = 0
    while len(raw) > MAX_IMAGE_BYTES and attempts < 4:
        attempts += 1
        if fmt != "JPEG":
            fmt, mime = "JPEG", "image/jpeg"
            raw = _encode_image(image, fmt)
            continue
        ratio = math.sqrt(MAX_IMAGE_BYTES / float(len(raw))) * 0.95
        ratio = max(0.25, min(0.75, ratio))
        edge = max(1, int(max(image.width(), image.height()) * ratio))
        image = _fit_image(image, edge)
        raw = _encode_image(image, fmt)
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError(
            f"图片压缩后仍超过 {MAX_IMAGE_BYTES // (1024 * 1024)} MB 上限")

    data = base64.b64encode(raw).decode("ascii")
    width, height = image.width(), image.height()
    note = f"图片，{width}×{height}，{max(1, math.ceil(len(raw) / 1024))} KB"
    if frames and frames > 1:
        note += "，只取第一帧"
    text = f"（图片：{name}，{width}×{height}）"
    return Attachment(name, text, note, kind="image", mime=mime, data=data,
                      width=width, height=height, byte_size=len(raw))


def extract_attachment(path: Path, limit: int = MAX_FILE_CHARS,
                       *, display_name: str = "") -> Attachment:
    """Read one file: the opening text for the message, and the full text for tools."""
    path = Path(path)
    suffix = path.suffix.lower()
    name = display_name or path.name
    try:
        if suffix in IMAGE_SUFFIXES:
            return _image_attachment(path, name)
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
        return Attachment(name, "（没有提取到文字；如果是扫描版 PDF，需要先做 OCR。）",
                          f"{note}，未提取到文字")
    pages = _pdf_pages(full_text) if suffix == ".pdf" else []
    chars = f"{len(full_text):,} 字"
    sent = f"，随消息发送前 {len(digest):,} 字" if cut else ""
    note = f"{note}，{chars}{sent}"
    return Attachment(name, digest, note, full_text, pages)

