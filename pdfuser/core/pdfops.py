"""PDF reading and merging (no GUI code here, so it is easy to test)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence

from pypdf import PdfReader, PdfWriter


class PdfError(Exception):
    """A PDF could not be read (corrupt, password protected, ...)."""


@dataclass
class PdfEntry:
    path: Path
    page_count: int
    removed: set[int] = field(default_factory=set)  # 0-based page indexes to drop

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def kept_pages(self) -> list[int]:
        return [i for i in range(self.page_count) if i not in self.removed]


def _open(path: Path) -> PdfReader:
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            # many "encrypted" PDFs only have an owner password; try empty user password
            if not reader.decrypt(""):
                raise PdfError(f"{path.name} is password protected.")
        return reader
    except PdfError:
        raise
    except Exception as exc:  # pypdf raises many different types
        raise PdfError(f"{path.name} could not be read ({exc}).") from exc


def load_entry(path: Path | str) -> PdfEntry:
    path = Path(path)
    reader = _open(path)
    try:
        count = len(reader.pages)
    except Exception as exc:
        raise PdfError(f"{path.name} could not be read ({exc}).") from exc
    if count == 0:
        raise PdfError(f"{path.name} has no pages.")
    return PdfEntry(path=path, page_count=count)


def merge(
    entries: Sequence[PdfEntry],
    output: Path | str,
    bookmarks: bool = True,
    progress: Optional[Callable[[int, int], None]] = None,
    cancelled: Optional[Callable[[], bool]] = None,
) -> int:
    """Merge ``entries`` in order into ``output``. Returns total pages written."""
    output = Path(output)
    out_resolved = output.resolve()
    for e in entries:
        if e.path.resolve() == out_resolved:
            raise PdfError("The output file can't be one of the files being merged.")
    usable = [e for e in entries if e.kept_pages]
    if not usable:
        raise PdfError("There are no pages left to merge.")

    writer = PdfWriter()
    total = 0
    for n, entry in enumerate(usable):
        if cancelled and cancelled():
            raise PdfError("Cancelled.")
        reader = _open(entry.path)
        first = len(writer.pages)
        for idx in entry.kept_pages:
            writer.add_page(reader.pages[idx])
            total += 1
        if bookmarks:
            writer.add_outline_item(entry.path.stem, first)
        if progress:
            progress(n + 1, len(usable))

    tmp = output.with_name(output.name + ".tmp")
    try:
        with open(tmp, "wb") as fh:
            writer.write(fh)
        tmp.replace(output)
    finally:
        if tmp.exists():
            tmp.unlink()
    return total
