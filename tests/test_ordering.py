from pathlib import Path

import pytest

from pdfuser.core.ordering import (
    KIND_ALPHA, KIND_CHAPTER, KIND_NAME, KIND_NUMERIC, detect_order, roman_to_int,
)


def names(result):
    return [p.name for p in result.paths]


def test_numeric_not_text_sorted():
    r = detect_order(["10.pdf", "2.pdf", "1.pdf", "3.pdf"])
    assert r.kind == KIND_NUMERIC
    assert names(r) == ["1.pdf", "2.pdf", "3.pdf", "10.pdf"]


def test_numeric_with_prefix_and_padding():
    r = detect_order(["scan_03.pdf", "scan_01.pdf", "scan_02.pdf"])
    assert r.kind == KIND_NUMERIC
    assert names(r) == ["scan_01.pdf", "scan_02.pdf", "scan_03.pdf"]


def test_chapters():
    r = detect_order(["Chapter 10 - End.pdf", "Chapter 2 - Middle.pdf", "Chapter 1 - Start.pdf"])
    assert r.kind == KIND_CHAPTER
    assert names(r) == ["Chapter 1 - Start.pdf", "Chapter 2 - Middle.pdf", "Chapter 10 - End.pdf"]


def test_chapter_beats_other_numbers():
    # the "2023" must not decide the order
    r = detect_order(["book 2023 ch3.pdf", "book 2023 ch1.pdf", "book 2023 ch2.pdf"])
    assert r.kind == KIND_CHAPTER
    assert names(r)[0] == "book 2023 ch1.pdf"


def test_roman_and_words():
    r = detect_order(["Part III.pdf", "Part I.pdf", "Part II.pdf"])
    assert r.kind == KIND_CHAPTER and names(r) == ["Part I.pdf", "Part II.pdf", "Part III.pdf"]
    r = detect_order(["Chapter Two.pdf", "Chapter One.pdf", "Chapter Three.pdf"])
    assert names(r) == ["Chapter One.pdf", "Chapter Two.pdf", "Chapter Three.pdf"]


def test_alphabetic_letters():
    r = detect_order(["c.pdf", "a.pdf", "b.pdf"])
    assert r.kind == KIND_ALPHA and names(r) == ["a.pdf", "b.pdf", "c.pdf"]
    r = detect_order(["Appendix_C.pdf", "Appendix_A.pdf", "Appendix_B.pdf"])
    assert r.kind == KIND_ALPHA and names(r)[0] == "Appendix_A.pdf"


def test_no_order_falls_back_to_name():
    r = detect_order(["zebra.pdf", "apple.pdf", "mango.pdf"])
    assert r.kind == KIND_NAME and not r.confident
    assert names(r) == ["apple.pdf", "mango.pdf", "zebra.pdf"]


def test_partial_numbers_fall_back():
    r = detect_order(["intro.pdf", "1.pdf", "2.pdf"])
    assert r.kind == KIND_NAME


def test_duplicate_numbers_not_confident():
    r = detect_order(["a1.pdf", "b1.pdf"])
    assert r.kind != KIND_NUMERIC


def test_multi_number_names():
    r = detect_order(["report_2024_02.pdf", "report_2024_10.pdf", "report_2024_01.pdf"])
    assert r.kind == KIND_NUMERIC
    assert names(r) == ["report_2024_01.pdf", "report_2024_02.pdf", "report_2024_10.pdf"]


def test_empty_and_single():
    assert detect_order([]).paths == []
    assert detect_order(["only.pdf"]).paths == [Path("only.pdf")]


@pytest.mark.parametrize("s,v", [("iv", 4), ("xiv", 14), ("mcmxc", 1990), ("abc", None)])
def test_roman(s, v):
    assert roman_to_int(s) == v
