import pytest

from tclock import font

ZERO = [
    "██████",
    "██  ██",
    "██  ██",
    "██  ██",
    "██████",
]
ONE = [
    "████  ",
    "  ██  ",
    "  ██  ",
    "  ██  ",
    "██████",
]
COLON = [
    "      ",
    "  ██  ",
    "      ",
    "  ██  ",
    "      ",
]


def test_zero_glyph() -> None:
    assert font.render("0") == ZERO


def test_one_and_colon_glyphs() -> None:
    assert font.render("1") == ONE
    assert font.render(":") == COLON


def test_all_glyphs_are_6_by_5_at_size_1() -> None:
    for ch in "0123456789:.-":
        rows = font.render(ch)
        assert len(rows) == 5, ch
        assert all(len(r) == 6 for r in rows), ch


def test_size_2_scales_both_axes() -> None:
    rows = font.render("1", 2)
    assert len(rows) == 10
    assert all(len(r) == 12 for r in rows)
    assert rows[0] == "████████    "
    assert rows[1] == rows[0]
    assert rows[2] == "    ████    "


def test_glyphs_separated_by_two_spaces_not_scaled() -> None:
    rows = font.render("00")
    assert len(rows[0]) == 6 + 2 + 6
    assert rows[0] == "██████  ██████"
    rows2 = font.render("00", 2)
    assert len(rows2[0]) == 12 + 2 + 12


def test_unknown_char_renders_blank_glyph() -> None:
    rows = font.render("x")
    assert rows == ["      "] * 5


def test_empty_text_keeps_height() -> None:
    assert font.render("", 1) == [""] * 5
    assert font.render("", 3) == [""] * 15


def test_text_width_matches_render() -> None:
    for text in ["0", "12:34", "1:02:03.4", ""]:
        for size in (1, 2, 3):
            rows = font.render(text, size)
            assert len(rows[0]) == font.text_width(text, size)


def test_size_below_one_rejected() -> None:
    with pytest.raises(ValueError):
        font.render("0", 0)
