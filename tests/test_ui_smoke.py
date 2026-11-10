import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from pypdf import PdfReader, PdfWriter

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from pdfuser.ui.main_window import MainWindow
from pdfuser.ui.page_dialog import PageDialog, parse_page_ranges


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def make_pdf(path, pages):
    w = PdfWriter()
    for i in range(pages):
        w.add_blank_page(width=100 + i, height=200)
    with open(path, "wb") as f:
        w.write(f)


def row_names(win):
    return [e.name for e in win.entries()]


def test_import_folder_orders_and_reorders(app, tmp_path):
    for name, n in (("Chapter 10.pdf", 1), ("Chapter 2.pdf", 2), ("Chapter 1.pdf", 3)):
        make_pdf(tmp_path / name, n)
    win = MainWindow()
    win.add_paths([str(tmp_path)])
    assert row_names(win) == ["Chapter 1.pdf", "Chapter 2.pdf", "Chapter 10.pdf"]

    win.tree.topLevelItem(2).setSelected(True)
    win.move(-1)
    assert row_names(win) == ["Chapter 1.pdf", "Chapter 10.pdf", "Chapter 2.pdf"]
    win.resort()
    assert row_names(win) == ["Chapter 1.pdf", "Chapter 2.pdf", "Chapter 10.pdf"]

    win.tree.clearSelection()
    win.tree.topLevelItem(0).setSelected(True)
    win.remove_selected()
    assert row_names(win) == ["Chapter 2.pdf", "Chapter 10.pdf"]


def test_duplicates_and_non_pdf_ignored(app, tmp_path):
    make_pdf(tmp_path / "a.pdf", 1)
    (tmp_path / "notes.txt").write_text("hi")
    win = MainWindow()
    win.add_paths([str(tmp_path / "a.pdf"), str(tmp_path / "notes.txt")])
    win.add_paths([str(tmp_path / "a.pdf")])
    assert row_names(win) == ["a.pdf"]


def test_page_dialog_removal(app, tmp_path):
    make_pdf(tmp_path / "a.pdf", 5)
    win = MainWindow()
    win.add_paths([str(tmp_path / "a.pdf")])
    entry = win.entries()[0]
    dlg = PageDialog(entry, win)
    dlg._toggle(1)
    dlg.range_edit.setText("4-")
    dlg._apply_range()
    dlg._accept()
    assert entry.removed == {1, 3, 4}


def test_parse_page_ranges():
    assert parse_page_ranges("1-2, 5", 6) == {0, 1, 4}
    assert parse_page_ranges("5-", 6) == {4, 5}
    with pytest.raises(ValueError):
        parse_page_ranges("7", 6)
    with pytest.raises(ValueError):
        parse_page_ranges("abc", 6)


def test_end_to_end_merge(app, tmp_path):
    make_pdf(tmp_path / "1.pdf", 2)
    make_pdf(tmp_path / "2.pdf", 3)
    win = MainWindow()
    win.add_paths([str(tmp_path)])
    win.entries()[1].removed = {0}
    from pdfuser.core.pdfops import merge
    out = tmp_path / "out" / "merged.pdf"
    out.parent.mkdir()
    assert merge(win.entries(), out) == 4
    assert len(PdfReader(str(out)).pages) == 4
