"""Dialog for choosing which pages of one PDF to drop before merging."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit,
    QListView, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
)

import pypdfium2 as pdfium

from ..core.pdfops import PdfEntry

THUMB_W, THUMB_H = 130, 170


def parse_page_ranges(text: str, page_count: int) -> set[int]:
    """'1-3, 7, 10-' -> {0,1,2,6,9,...} (0-based). Raises ValueError on bad input."""
    result: set[int] = set()
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo_s, hi_s = (x.strip() for x in part.split("-", 1))
            lo = int(lo_s) if lo_s else 1
            hi = int(hi_s) if hi_s else page_count
        else:
            lo = hi = int(part)
        if lo < 1 or hi > page_count or lo > hi:
            raise ValueError(f"'{part}' is outside 1-{page_count}")
        result.update(range(lo - 1, hi))
    return result


class PageDialog(QDialog):
    def __init__(self, entry: PdfEntry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle(f"Pages - {entry.name}")
        self.resize(820, 600)
        self._removed: set[int] = set(entry.removed)
        self._next = 0

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Click pages to mark them for removal (Ctrl/Shift to select several, "
            "Space toggles the selection). Marked pages are left out of the merged file."
        ))

        self.list = QListWidget()
        self.list.setViewMode(QListView.IconMode)
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setIconSize(QSize(THUMB_W, THUMB_H))
        self.list.setGridSize(QSize(THUMB_W + 24, THUMB_H + 36))
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setUniformItemSizes(True)
        self.list.setWordWrap(False)
        layout.addWidget(self.list, 1)

        for i in range(entry.page_count):
            item = QListWidgetItem(f"Page {i + 1}")
            item.setTextAlignment(Qt.AlignHCenter)
            item.setIcon(self._placeholder(i))
            self.list.addItem(item)
        self._refresh_all()

        row = QHBoxLayout()
        self.range_edit = QLineEdit()
        self.range_edit.setPlaceholderText("Type pages to remove, e.g. 1-2, 5, 9-")
        self.range_edit.returnPressed.connect(self._apply_range)
        apply_btn = QPushButton("Mark")
        apply_btn.clicked.connect(self._apply_range)
        toggle_btn = QPushButton("Toggle selected")
        toggle_btn.clicked.connect(self._toggle_selected)
        restore_btn = QPushButton("Restore all")
        restore_btn.clicked.connect(self._restore_all)
        for w in (self.range_edit, apply_btn, toggle_btn, restore_btn):
            row.addWidget(w)
        layout.addLayout(row)

        self.summary = QLabel()
        layout.addWidget(self.summary)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.list.itemClicked.connect(self._on_click)
        self._update_summary()

        # render thumbnails a few at a time so the dialog opens instantly
        self._pdf = None
        try:
            self._pdf = pdfium.PdfDocument(str(entry.path))
        except Exception:
            self._pdf = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._render_some)
        if self._pdf is not None:
            self._timer.start(0)

    # ---- thumbnails -------------------------------------------------
    def _placeholder(self, index: int, removed: bool = False) -> QIcon:
        pm = QPixmap(THUMB_W, THUMB_H)
        pm.fill(QColor("#f2f2f2"))
        return QIcon(self._decorate(pm, index in self._removed))

    def _decorate(self, pm: QPixmap, removed: bool) -> QPixmap:
        pm = pm.copy()
        p = QPainter(pm)
        p.setPen(QColor("#bbbbbb"))
        p.drawRect(0, 0, pm.width() - 1, pm.height() - 1)
        if removed:
            p.fillRect(pm.rect(), QColor(255, 255, 255, 170))
            p.setPen(QColor("#d32f2f"))
            f = p.font()
            f.setPointSize(48)
            f.setBold(True)
            p.setFont(f)
            p.drawText(pm.rect(), Qt.AlignCenter, "✕")
            p.setPen(QColor("#d32f2f"))
            p.drawRect(1, 1, pm.width() - 3, pm.height() - 3)
        p.end()
        return pm

    def _render_some(self):
        for _ in range(3):
            if self._next >= self.entry.page_count:
                self._timer.stop()
                return
            i = self._next
            self._next += 1
            try:
                page = self._pdf[i]
                w, h = page.get_size()
                scale = min(THUMB_W / w, THUMB_H / h)
                bitmap = page.render(scale=scale)
                img = bitmap.to_pil().convert("RGBA")
                qimg = QImage(img.tobytes("raw", "RGBA"), img.width, img.height,
                              img.width * 4, QImage.Format_RGBA8888).copy()
                canvas = QPixmap(THUMB_W, THUMB_H)
                canvas.fill(QColor("white"))
                p = QPainter(canvas)
                p.drawImage((THUMB_W - qimg.width()) // 2, (THUMB_H - qimg.height()) // 2, qimg)
                p.end()
                self._thumbs[i] = canvas
            except Exception:
                pass
            self._refresh(i)

    @property
    def _thumbs(self) -> dict:
        if not hasattr(self, "_thumb_cache"):
            self._thumb_cache: dict[int, QPixmap] = {}
        return self._thumb_cache

    # ---- state ------------------------------------------------------
    def _refresh(self, i: int):
        base = self._thumbs.get(i)
        if base is None:
            base = QPixmap(THUMB_W, THUMB_H)
            base.fill(QColor("#f2f2f2"))
        item = self.list.item(i)
        item.setIcon(QIcon(self._decorate(base, i in self._removed)))
        item.setText(f"Page {i + 1}" + ("  (removed)" if i in self._removed else ""))

    def _refresh_all(self):
        for i in range(self.list.count()):
            self._refresh(i)

    def _update_summary(self):
        kept = self.entry.page_count - len(self._removed)
        self.summary.setText(f"{kept} of {self.entry.page_count} pages will be kept.")

    def _toggle(self, i: int):
        self._removed.symmetric_difference_update({i})
        self._refresh(i)
        self._update_summary()

    def _on_click(self, item: QListWidgetItem):
        # plain click toggles; with modifiers the user is building a selection instead
        from PySide6.QtWidgets import QApplication
        if QApplication.keyboardModifiers() == Qt.NoModifier:
            self._toggle(self.list.row(item))

    def _toggle_selected(self):
        for item in self.list.selectedItems():
            self._toggle(self.list.row(item))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Space and self.list.hasFocus():
            self._toggle_selected()
            return
        super().keyPressEvent(e)

    def _restore_all(self):
        self._removed.clear()
        self._refresh_all()
        self._update_summary()

    def _apply_range(self):
        try:
            pages = parse_page_ranges(self.range_edit.text(), self.entry.page_count)
        except ValueError as exc:
            self.summary.setText(f"Couldn't read that: {exc}")
            return
        self._removed |= pages
        self.range_edit.clear()
        self._refresh_all()
        self._update_summary()

    def _accept(self):
        self.entry.removed = set(self._removed)
        self.accept()

    def done(self, r):
        self._timer.stop()
        if self._pdf is not None:
            try:
                self._pdf.close()
            except Exception:
                pass
        super().done(r)
