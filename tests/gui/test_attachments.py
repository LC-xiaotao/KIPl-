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


def test_a_long_file_is_truncated(tmp_path):
    path = tmp_path / "long.txt"
    path.write_text("x" * (MAX_FILE_CHARS + 100), encoding="utf-8")
    attachment = extract_attachment(path)
    assert "已截断" in attachment.note
    assert attachment.text.endswith("已截断）")


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


def test_a_binary_file_is_refused(tmp_path):
    path = tmp_path / "data.bin"
    path.write_bytes(b"\x00\x01\x02")
    with pytest.raises(ValueError, match="不是可读取"):
        extract_attachment(path)
