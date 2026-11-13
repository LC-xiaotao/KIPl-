"""Text extraction for the files attached to an assistant message."""

import pytest

from kipi.gui.assistant.attachments import MAX_FILE_CHARS, extract_attachment


def test_text_csv_and_html(tmp_path):
    markdown = tmp_path / "notes.md"
    markdown.write_text("# 标题\n内容", encoding="utf-8")
    attachment = extract_attachment(markdown)
    assert attachment.name == "notes.md"
    assert "标题" in attachment.text and "文本" in attachment.note

    table = tmp_path / "nets.csv"
    table.write_text("net,mv\n3V3,6.5\nGND,0.2\n", encoding="utf-8")
    attachment = extract_attachment(table)
    assert "net | mv" in attachment.text
    assert "3V3 | 6.5" in attachment.text

    page = tmp_path / "page.html"
    page.write_text("<h1>Title</h1><script>secret()</script><p>Body</p>",
                    encoding="utf-8")
    attachment = extract_attachment(page)
    assert "Title" in attachment.text and "Body" in attachment.text
    assert "secret" not in attachment.text


def test_a_long_file_keeps_the_full_text(tmp_path):
    path = tmp_path / "long.txt"
    path.write_text("x" * (MAX_FILE_CHARS + 100), encoding="utf-8")
    attachment = extract_attachment(path)
    assert len(attachment.full_text) > len(attachment.text)
    assert attachment.text.endswith("已截断）")
    assert "随消息发送前" in attachment.note
    assert not attachment.complete


def test_docx_and_xlsx(tmp_path):
    docx = pytest.importorskip("docx")
    openpyxl = pytest.importorskip("openpyxl")

    document = docx.Document()
    document.add_paragraph("Hello doc")
    document.save(tmp_path / "a.docx")
    attachment = extract_attachment(tmp_path / "a.docx")
    assert "Hello doc" in attachment.text and "Word" in attachment.note

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "S1"
    sheet.append(["net", "mv"])
    sheet.append(["3V3", 6.5])
    workbook.save(tmp_path / "a.xlsx")
    attachment = extract_attachment(tmp_path / "a.xlsx")
    assert "S1" in attachment.text and "3V3 | 6.5" in attachment.text


def test_pdf_page_count(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(tmp_path / "blank.pdf")
    attachment = extract_attachment(tmp_path / "blank.pdf")
    assert "PDF，1 页" in attachment.note
    assert len(attachment.pages) == 1 and attachment.pages[0][0] == 1


def test_a_binary_file_is_refused(tmp_path):
    path = tmp_path / "data.bin"
    path.write_bytes(b"\x00\x01\x02")
    with pytest.raises(ValueError, match="不是可读取"):
        extract_attachment(path)


import base64
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("qtpy")
    from qtpy.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_image_is_resized_and_encoded(tmp_path, qapp):
    from qtpy.QtGui import QImage

    path = tmp_path / "big.png"
    image = QImage(2400, 1200, QImage.Format.Format_RGB32)
    image.fill(0xff112233)
    assert image.save(str(path), "PNG")

    attachment = extract_attachment(path)
    assert attachment.is_image
    assert attachment.mime == "image/png"
    assert max(attachment.width, attachment.height) == 1568
    assert attachment.chars == 0 and attachment.complete
    assert attachment.data
    assert base64.b64decode(attachment.data).startswith(b"\x89PNG")
    assert "（图片：" in attachment.text and "图片" in attachment.note

    named = extract_attachment(path, display_name="截图-当前视图.png")
    assert named.name == "截图-当前视图.png"


def test_jpeg_is_sent_as_jpeg(tmp_path, qapp):
    from qtpy.QtGui import QImage

    path = tmp_path / "photo.jpg"
    image = QImage(120, 80, QImage.Format.Format_RGB32)
    image.fill(0xffabcdef)
    assert image.save(str(path), "JPG")
    attachment = extract_attachment(path)
    assert attachment.mime == "image/jpeg"
    assert base64.b64decode(attachment.data).startswith(b"\xff\xd8")


def test_a_corrupt_image_is_reported(tmp_path, qapp):
    path = tmp_path / "bad.png"
    path.write_bytes(b"not an image")
    with pytest.raises(ValueError, match="无法读取图片"):
        extract_attachment(path)


def test_an_oversize_image_file_is_rejected(tmp_path, qapp):
    from kipi.gui.assistant.attachments import MAX_IMAGE_BYTES

    path = tmp_path / "huge.png"
    path.write_bytes(b"\0" * (MAX_IMAGE_BYTES + 1))
    with pytest.raises(ValueError, match="MB 上限"):
        extract_attachment(path)
