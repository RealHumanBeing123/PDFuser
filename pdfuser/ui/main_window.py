"""PDFuser main window."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QMainWindow, QMessageBox, QProgressDialog, QPushButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ..core.ordering import detect_order, list_pdfs
from ..core.pdfops import PdfEntry, PdfError, load_entry, merge
from .page_dialog import PageDialog

ENTRY_ROLE = Qt.UserRole


class FileTree(QTreeWidget):
    """List that reorders by internal drag/drop and accepts files dropped from Explorer."""

    pathsDropped = Signal(list)
    orderChanged = Signal()

    def __init__(self):
        super().__init__()
        self.setColumnCount(3)
        self.setHeaderLabels(["#", "File", "Pages"])
        self.setRootIsDecorated(False)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setUniformRowHeights(True)
        h = self.header()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)

    @staticmethod
    def _local_paths(mime) -> list[str]:
        return [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            self.pathsDropped.emit(self._local_paths(e.mimeData()))
            e.acceptProposedAction()
            return
        super().dropEvent(e)
        self.orderChanged.emit()


class MergeWorker(QObject):
    progress = Signal(int, int)
    finished = Signal(int, str)  # pages, error

    def __init__(self, entries, output, bookmarks):
        super().__init__()
        self.entries, self.output, self.bookmarks = entries, output, bookmarks
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            pages = merge(self.entries, self.output, self.bookmarks,
                          progress=self.progress.emit, cancelled=lambda: self._cancel)
            self.finished.emit(pages, "")
        except Exception as exc:
            self.finished.emit(0, str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDFuser - merge PDFs")
        self.resize(820, 560)
        self.setAcceptDrops(True)
        self._last_dir = str(Path.home())
        self._thread: QThread | None = None
        self._dlg = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # --- top buttons
        top = QHBoxLayout()
        for text, slot in (("Add PDFs...", self.add_files),
                           ("Import folder...", self.import_folder)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            top.addWidget(b)
        top.addStretch(1)
        self.resort_btn = QPushButton("Re-detect order")
        self.resort_btn.setToolTip("Sort the list again using numbers, chapters or letters in the file names")
        self.resort_btn.clicked.connect(self.resort)
        top.addWidget(self.resort_btn)
        root.addLayout(top)

        # --- list + side buttons
        mid = QHBoxLayout()
        self.tree = FileTree()
        self.tree.pathsDropped.connect(self.handle_dropped)
        self.tree.orderChanged.connect(self._renumber)
        self.tree.itemDoubleClicked.connect(lambda *_: self.edit_pages())
        self.tree.itemSelectionChanged.connect(self._update_buttons)
        mid.addWidget(self.tree, 1)

        side = QVBoxLayout()
        self.up_btn = QPushButton("▲  Move up")
        self.down_btn = QPushButton("▼  Move down")
        self.pages_btn = QPushButton("Edit pages...")
        self.remove_btn = QPushButton("Remove from list")
        self.clear_btn = QPushButton("Clear list")
        self.up_btn.setToolTip("Alt+Up")
        self.down_btn.setToolTip("Alt+Down")
        self.pages_btn.setToolTip("Choose pages to leave out of the merged PDF (double-click a file)")
        self.up_btn.clicked.connect(lambda: self.move(-1))
        self.down_btn.clicked.connect(lambda: self.move(1))
        self.pages_btn.clicked.connect(self.edit_pages)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_btn.clicked.connect(self.clear)
        for b in (self.up_btn, self.down_btn, self.pages_btn, self.remove_btn, self.clear_btn):
            side.addWidget(b)
        side.addStretch(1)
        mid.addLayout(side)
        root.addLayout(mid, 1)

        self.hint = QLabel()
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

        # --- bottom
        bottom = QHBoxLayout()
        self.bookmarks = QCheckBox("Add a bookmark for each file")
        self.bookmarks.setChecked(True)
        bottom.addWidget(self.bookmarks)
        bottom.addStretch(1)
        self.merge_btn = QPushButton("Merge PDFs...")
        self.merge_btn.setDefault(True)
        self.merge_btn.setMinimumHeight(34)
        self.merge_btn.clicked.connect(self.start_merge)
        bottom.addWidget(self.merge_btn)
        root.addLayout(bottom)

        # --- shortcuts
        for seq, fn in (("Alt+Up", lambda: self.move(-1)), ("Alt+Down", lambda: self.move(1)),
                        ("Delete", self.remove_selected), ("Ctrl+O", self.add_files)):
            act = QAction(self)
            act.setShortcut(QKeySequence(seq))
            act.triggered.connect(fn)
            self.addAction(act)

        self._set_hint("Drag PDFs here from Explorer, add them with the buttons above, "
                       "or import a whole folder.")
        self._update_buttons()

    # ----- helpers --------------------------------------------------
    def _set_hint(self, text: str):
        self.hint.setText(text)

    def entries(self) -> list[PdfEntry]:
        return [self.tree.topLevelItem(i).data(0, ENTRY_ROLE) for i in range(self.tree.topLevelItemCount())]

    def _make_item(self, entry: PdfEntry) -> QTreeWidgetItem:
        item = QTreeWidgetItem(["", entry.name, ""])
        item.setData(0, ENTRY_ROLE, entry)
        item.setToolTip(1, str(entry.path))
        item.setFlags((item.flags() | Qt.ItemIsDragEnabled) & ~Qt.ItemIsDropEnabled)
        return item

    def _update_item(self, item: QTreeWidgetItem):
        e: PdfEntry = item.data(0, ENTRY_ROLE)
        kept = len(e.kept_pages)
        item.setText(2, str(e.page_count) if not e.removed else f"{kept} of {e.page_count}")

    def _renumber(self):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item.setText(0, str(i + 1))
            self._update_item(item)
        self._update_buttons()

    def _update_buttons(self):
        sel = self.tree.selectedItems()
        n = self.tree.topLevelItemCount()
        rows = sorted(self.tree.indexOfTopLevelItem(i) for i in sel)
        self.up_btn.setEnabled(bool(rows) and rows[0] > 0)
        self.down_btn.setEnabled(bool(rows) and rows[-1] < n - 1)
        self.pages_btn.setEnabled(len(sel) == 1)
        self.remove_btn.setEnabled(bool(sel))
        self.clear_btn.setEnabled(n > 0)
        self.resort_btn.setEnabled(n > 1)
        self.merge_btn.setEnabled(n > 0)

    # ----- adding files ---------------------------------------------
    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add PDFs", self._last_dir, "PDF files (*.pdf)")
        if files:
            self._last_dir = str(Path(files[0]).parent)
            self.add_paths(files)

    def import_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Import PDFs from folder", self._last_dir)
        if folder:
            self._last_dir = folder
            self.add_paths([folder])

    def handle_dropped(self, paths: list[str]):
        self.add_paths(paths)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.add_paths([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])
        e.acceptProposedAction()

    def add_paths(self, paths: list[str]):
        """Add PDFs and/or folders. Each folder is ordered on its own; loose files as one batch."""
        batches: list[list[Path]] = []
        loose: list[Path] = []
        for p in map(Path, paths):
            if p.is_dir():
                batches.append(list_pdfs(p))
            elif p.suffix.lower() == ".pdf" and p.is_file():
                loose.append(p)
        if loose:
            batches.append(loose)

        existing = {e.path.resolve() for e in self.entries()}
        problems: list[str] = []
        added = 0
        last_kind = None
        for batch in batches:
            result = detect_order(batch)
            last_kind = result
            for path in result.paths:
                if path.resolve() in existing:
                    continue
                try:
                    entry = load_entry(path)
                except PdfError as exc:
                    problems.append(str(exc))
                    continue
                self.tree.addTopLevelItem(self._make_item(entry))
                existing.add(path.resolve())
                added += 1
        self._renumber()

        if added == 0 and not problems:
            self._set_hint("No new PDF files found.")
        elif last_kind is not None:
            msg = f"Added {added} file(s). " + last_kind.describe()
            if last_kind.confident:
                msg += " Drag rows or use the arrows if you want a different order."
            else:
                msg += " Check the order below - drag rows or use the arrows to fix it."
            self._set_hint(msg)
        if problems:
            QMessageBox.warning(self, "Some files were skipped", "\n".join(problems))

    def resort(self):
        entries = self.entries()
        result = detect_order([e.path for e in entries])
        by_path = {e.path: e for e in entries}
        self.tree.clear()
        for p in result.paths:
            self.tree.addTopLevelItem(self._make_item(by_path[p]))
        self._renumber()
        self._set_hint(result.describe())

    # ----- editing the list -----------------------------------------
    def move(self, delta: int):
        items = self.tree.selectedItems()
        if not items:
            return
        rows = sorted(self.tree.indexOfTopLevelItem(i) for i in items)
        n = self.tree.topLevelItemCount()
        if (delta < 0 and rows[0] == 0) or (delta > 0 and rows[-1] == n - 1):
            return
        taken = [self.tree.takeTopLevelItem(r) for r in reversed(rows)][::-1]
        for item, r in zip(taken, rows):
            self.tree.insertTopLevelItem(r + delta, item)
        for item in taken:
            item.setSelected(True)
        self._renumber()
        self.tree.scrollToItem(taken[0])

    def remove_selected(self):
        for item in self.tree.selectedItems():
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(item))
        self._renumber()

    def clear(self):
        self.tree.clear()
        self._renumber()
        self._set_hint("List cleared.")

    def edit_pages(self):
        items = self.tree.selectedItems()
        if len(items) != 1:
            return
        entry: PdfEntry = items[0].data(0, ENTRY_ROLE)
        if PageDialog(entry, self).exec():
            self._update_item(items[0])

    # ----- merging --------------------------------------------------
    def start_merge(self):
        entries = self.entries()
        if not entries:
            return
        if not any(e.kept_pages for e in entries):
            QMessageBox.warning(self, "Nothing to merge", "Every page has been removed.")
            return
        default = Path(entries[0].path.parent) / "merged.pdf"
        out, _ = QFileDialog.getSaveFileName(self, "Save merged PDF", str(default), "PDF files (*.pdf)")
        if not out:
            return
        if not out.lower().endswith(".pdf"):
            out += ".pdf"

        self.merge_btn.setEnabled(False)
        self._merge_out = out
        self._merge_count = len(entries)

        self._dlg = QProgressDialog("Merging...", "Cancel", 0, len(entries), self)
        self._dlg.setWindowModality(Qt.WindowModal)
        self._dlg.setMinimumDuration(300)
        self._dlg.setAutoClose(False)
        self._dlg.setAutoReset(False)

        self._thread = QThread()
        self._worker = MergeWorker(entries, out, self.bookmarks.isChecked())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        # Slots are bound methods of this window, so Qt delivers them on the GUI thread.
        # (Plain lambdas would run on the worker thread and break the dialogs.)
        self._worker.progress.connect(self._on_merge_progress)
        self._worker.finished.connect(self._on_merge_finished)
        self._dlg.canceled.connect(self._worker.cancel)
        self._thread.start()

    def _on_merge_progress(self, n: int, total: int):
        if self._dlg is not None:
            self._dlg.setValue(n)

    def _on_merge_finished(self, pages: int, error: str):
        dlg, self._dlg = self._dlg, None
        if dlg is not None:
            dlg.canceled.disconnect()
            dlg.close()
            dlg.deleteLater()
        self._thread.quit()
        self._thread.wait()
        self._thread.deleteLater()
        self._worker.deleteLater()
        self._thread = None
        self._update_buttons()

        if error == "Cancelled.":
            self._set_hint("Merge cancelled.")
        elif error:
            self._set_hint("Merge failed.")
            QMessageBox.critical(self, "Merge failed", error)
        else:
            self._set_hint(f"Saved {pages} pages to {self._merge_out}")
            QMessageBox.information(
                self, "Done",
                f"Merged {self._merge_count} file(s) into {pages} pages.\n\n{self._merge_out}")
