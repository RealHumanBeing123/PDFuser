"""Detect an existing order in a set of file names and sort by it.

Supported schemes (checked in this order):

* chapter  - "Chapter 1", "Ch2", "Part III", "Section four", "Vol 2" ...
* numeric  - 1, 2, 3 / 01_intro / report_10 (numbers compared as numbers, not text)
* alphabetic - a, b, c / "part a" / "appendix_B" (a single distinguishing letter)
* name     - fallback: natural (human) sort by file name

``detect_order`` returns the sorted paths and the kind of order that was found,
so the UI can tell the user whether it was confident or just sorted by name.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

KIND_CHAPTER = "chapter"
KIND_NUMERIC = "numeric"
KIND_ALPHA = "alphabetic"
KIND_NAME = "name"

_WORD_NUMBERS = {
    w: i
    for i, w in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve "
        "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split()
    )
}
_ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
_ROMAN_RE = re.compile(r"^(?=[ivxlcdm]+$)m{0,4}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$", re.I)

_CHAPTER_WORDS = (
    "chapter|chap|ch|part|pt|section|sec|lesson|unit|volume|vol|book|module|episode|ep|act|week|day|lecture"
)
_CHAPTER_RE = re.compile(
    rf"(?<![a-z])({_CHAPTER_WORDS})[\s_.\-#]*(\d+|[ivxlcdm]+|{'|'.join(_WORD_NUMBERS)})(?![a-z0-9])",
    re.I,
)
_NUM_RE = re.compile(r"\d+")
_SEP = r"[\s_.\-()\[\]]"
_ALPHA_START = re.compile(rf"^([a-z])(?={_SEP}|$)", re.I)
_ALPHA_END = re.compile(rf"(?:^|{_SEP})([a-z])$", re.I)


def roman_to_int(s: str) -> int | None:
    s = s.lower()
    if not _ROMAN_RE.match(s):
        return None
    total = 0
    for i, ch in enumerate(s):
        v = _ROMAN[ch]
        if i + 1 < len(s) and _ROMAN[s[i + 1]] > v:
            total -= v
        else:
            total += v
    return total


def natural_key(text: str) -> list:
    """Sort key that compares digit runs as numbers: file2 < file10."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


def _token_value(tok: str) -> int | None:
    tok = tok.lower()
    if tok.isdigit():
        return int(tok)
    if tok in _WORD_NUMBERS:
        return _WORD_NUMBERS[tok]
    return roman_to_int(tok)


def _chapter_values(stem: str) -> dict[str, int]:
    """keyword -> number for every chapter-like marker in ``stem`` (first hit per keyword)."""
    found: dict[str, int] = {}
    for m in _CHAPTER_RE.finditer(stem):
        value = _token_value(m.group(2))
        if value is not None:
            found.setdefault(m.group(1).lower(), value)
    return found


def _chapter_order(stems: Sequence[str]) -> list[int] | None:
    """Values for a keyword every file has and whose numbers all differ."""
    per_file = [_chapter_values(s) for s in stems]
    common = set(per_file[0]).intersection(*per_file[1:])
    for kw in sorted(common):
        vals = [d[kw] for d in per_file]
        if len(set(vals)) == len(vals):
            return vals
    return None


def _alpha_value(stem: str) -> tuple[str, str] | None:
    """Return (position, letter) if the name has a lone distinguishing letter."""
    m = _ALPHA_START.search(stem)
    if m:
        return "start", m.group(1).lower()
    m = _ALPHA_END.search(stem)
    if m:
        return "end", m.group(1).lower()
    return None


@dataclass
class OrderResult:
    paths: list[Path]
    kind: str  # one of the KIND_* constants

    @property
    def confident(self) -> bool:
        return self.kind != KIND_NAME

    def describe(self) -> str:
        return {
            KIND_CHAPTER: "Ordered by chapter/part number in the file names.",
            KIND_NUMERIC: "Ordered by the numbers in the file names.",
            KIND_ALPHA: "Ordered by the letters in the file names.",
            KIND_NAME: "No clear order found in the file names - sorted by name.",
        }[self.kind]


def detect_order(paths: Sequence[Path | str]) -> OrderResult:
    items = [Path(p) for p in paths]
    if len(items) < 2:
        return OrderResult(items, KIND_NAME if not items else KIND_NUMERIC)

    stems = [p.stem for p in items]

    # 1. chapter keywords
    vals = _chapter_order(stems)
    if vals is not None:
        order = sorted(range(len(items)), key=lambda i: (vals[i], natural_key(stems[i])))
        return OrderResult([items[i] for i in order], KIND_CHAPTER)

    # 2. numbers anywhere in the name (compare tuples of all numbers)
    nums = [tuple(int(n) for n in _NUM_RE.findall(s)) for s in stems]
    if all(nums) and len(set(nums)) == len(nums):
        order = sorted(range(len(items)), key=lambda i: (nums[i], natural_key(stems[i])))
        return OrderResult([items[i] for i in order], KIND_NUMERIC)

    # 3. single letters, all in the same position
    alphas = [_alpha_value(s) for s in stems]
    if all(a is not None for a in alphas):
        positions = {a[0] for a in alphas}  # type: ignore[index]
        letters = [a[1] for a in alphas]  # type: ignore[index]
        if len(positions) == 1 and len(set(letters)) == len(letters):
            order = sorted(range(len(items)), key=lambda i: letters[i])
            return OrderResult([items[i] for i in order], KIND_ALPHA)

    # 4. fallback
    return OrderResult(sorted(items, key=lambda p: natural_key(p.name)), KIND_NAME)


def list_pdfs(folder: Path | str) -> list[Path]:
    """PDF files directly inside ``folder`` (case-insensitive extension)."""
    return [p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() == ".pdf"]
