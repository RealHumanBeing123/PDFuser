from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from pdfuser.core.pdfops import PdfError, load_entry, merge


def make_pdf(path: Path, pages: int, label: str) -> Path:
    w = PdfWriter()
    for i in range(pages):
        w.add_blank_page(width=100 + i, height=200)  # width encodes the page index
    w.add_metadata({"/Title": label})
    with open(path, "wb") as f:
        w.write(f)
    return path


def widths(path):
    return [round(float(p.mediabox.width)) for p in PdfReader(str(path)).pages]


def test_merge_in_order(tmp_path):
    a = load_entry(make_pdf(tmp_path / "a.pdf", 2, "a"))
    b = load_entry(make_pdf(tmp_path / "b.pdf", 3, "b"))
    out = tmp_path / "out.pdf"
    assert merge([b, a], out) == 5
    assert widths(out) == [100, 101, 102, 100, 101]


def test_page_removal(tmp_path):
    a = load_entry(make_pdf(tmp_path / "a.pdf", 4, "a"))
    a.removed = {0, 2}
    b = load_entry(make_pdf(tmp_path / "b.pdf", 2, "b"))
    out = tmp_path / "out.pdf"
    assert merge([a, b], out) == 4
    assert widths(out) == [101, 103, 100, 101]


def test_file_with_all_pages_removed_is_skipped(tmp_path):
    a = load_entry(make_pdf(tmp_path / "a.pdf", 2, "a"))
    a.removed = {0, 1}
    b = load_entry(make_pdf(tmp_path / "b.pdf", 1, "b"))
    out = tmp_path / "out.pdf"
    assert merge([a, b], out) == 1


def test_nothing_to_merge(tmp_path):
    a = load_entry(make_pdf(tmp_path / "a.pdf", 1, "a"))
    a.removed = {0}
    with pytest.raises(PdfError):
        merge([a], tmp_path / "out.pdf")


def test_bookmarks(tmp_path):
    a = load_entry(make_pdf(tmp_path / "intro.pdf", 2, "a"))
    b = load_entry(make_pdf(tmp_path / "body.pdf", 2, "b"))
    out = tmp_path / "out.pdf"
    merge([a, b], out, bookmarks=True)
    outline = PdfReader(str(out)).outline
    assert [o.title for o in outline] == ["intro", "body"]
    merge([a, b], out, bookmarks=False)
    assert PdfReader(str(out)).outline == []


def test_output_cannot_overwrite_input(tmp_path):
    a = load_entry(make_pdf(tmp_path / "a.pdf", 1, "a"))
    with pytest.raises(PdfError):
        merge([a], tmp_path / "a.pdf")
    assert (tmp_path / "a.pdf").exists()


def test_corrupt_file(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    with pytest.raises(PdfError):
        load_entry(bad)


def test_encrypted_with_password_rejected(tmp_path):
    src = make_pdf(tmp_path / "plain.pdf", 1, "x")
    w = PdfWriter(clone_from=str(src))
    w.encrypt("secret")
    enc = tmp_path / "enc.pdf"
    with open(enc, "wb") as f:
        w.write(f)
    with pytest.raises(PdfError, match="password"):
        load_entry(enc)
