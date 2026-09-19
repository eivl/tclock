"""The "bricks" block font used for the big digits.

Each glyph is 6 columns by 5 rows at size 1. A row is described as run lengths that
alternate off/on starting with "off": ``(0, 6)`` is ``██████``, ``(2, 2)`` is ``  ██``,
``(0, 2, 2, 2)`` is ``██  ██``. Glyph table copied from clock-tui's BricksFont.
"""

GLYPH_WIDTH = 6
GLYPH_HEIGHT = 5
SPACING = 2
BLOCK = "█"

Runs = tuple[int, ...]

GLYPHS: dict[str, tuple[Runs, Runs, Runs, Runs, Runs]] = {
    "0": ((0, 6), (0, 2, 2, 2), (0, 2, 2, 2), (0, 2, 2, 2), (0, 6)),
    "1": ((0, 4), (2, 2), (2, 2), (2, 2), (0, 6)),
    "2": ((0, 6), (4, 2), (0, 6), (0, 2), (0, 6)),
    "3": ((0, 6), (4, 2), (0, 6), (4, 2), (0, 6)),
    "4": ((0, 2, 2, 2), (0, 2, 2, 2), (0, 6), (4, 2), (4, 2)),
    "5": ((0, 6), (0, 2), (0, 6), (4, 2), (0, 6)),
    "6": ((0, 6), (0, 2), (0, 6), (0, 2, 2, 2), (0, 6)),
    "7": ((0, 6), (4, 2), (4, 2), (4, 2), (4, 2)),
    "8": ((0, 6), (0, 2, 2, 2), (0, 6), (0, 2, 2, 2), (0, 6)),
    "9": ((0, 6), (0, 2, 2, 2), (0, 6), (4, 2), (0, 6)),
    ":": ((), (2, 2), (), (2, 2), ()),
    ".": ((), (), (), (), (2, 2)),
    "-": ((), (), (0, 6), (), ()),
}


def _row(runs: Runs, size: int) -> str:
    cells: list[str] = []
    on = False
    for length in runs:
        cells.append((BLOCK if on else " ") * (length * size))
        on = not on
    return "".join(cells).ljust(GLYPH_WIDTH * size)


def _glyph(ch: str, size: int) -> list[str]:
    runs = GLYPHS.get(ch)
    if runs is None:
        return [" " * (GLYPH_WIDTH * size)] * (GLYPH_HEIGHT * size)
    rows: list[str] = []
    for row_runs in runs:
        rows.extend([_row(row_runs, size)] * size)
    return rows


def text_width(text: str, size: int) -> int:
    """Total columns ``render(text, size)`` occupies."""
    if not text:
        return 0
    return len(text) * (GLYPH_WIDTH * size + SPACING) - SPACING


def render(text: str, size: int = 1) -> list[str]:
    """Render ``text`` as ``GLYPH_HEIGHT * size`` rows of block characters.

    Glyphs are separated by ``SPACING`` blank columns (not scaled). Characters without
    a glyph render as blank space of glyph width, so layout stays stable.
    """
    if size < 1:
        raise ValueError(f"size must be >= 1, got {size}")
    height = GLYPH_HEIGHT * size
    if not text:
        return [""] * height
    glyphs = [_glyph(ch, size) for ch in text]
    gap = " " * SPACING
    return [gap.join(glyph[i] for glyph in glyphs) for i in range(height)]
