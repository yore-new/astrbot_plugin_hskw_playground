"""Local Pillow renderer. Does not import AstrBot or modify game state."""

import unicodedata
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .core import MAX_GUESSES, RESOURCE_DIR, Cell, IdiomGame, parse_word
from .hints import get_hint
from .pinyin_display import display_final, marked_final, tone_mark

FONT_PATH = RESOURCE_DIR / "fonts" / "NotoSansCJKsc-Regular.otf"
COLORS = {"exact": "#007f3d", "misplaced": "#9a5b00", "none": "#626970"}
BACKGROUND_COLOR = "#fff8d6"
CELL_BACKGROUND_COLOR = "#fffbed"
BORDER_COLOR = "#dfcf91"
PINYIN_FONT_SIZE = 28
PADDING = 16
GAP = 12
CELL_WIDTH = 144
CELL_HEIGHT = 120


@dataclass(frozen=True)
class _Tile:
    char: str
    parts: tuple[str | None, str | None, int | None]
    matches: tuple[str, str, str]
    char_match: str


def _result_tile(cell: Cell) -> _Tile:
    syllable = cell.syllable
    return _Tile(
        cell.char,
        (syllable.initial, syllable.final, syllable.tone),
        (cell.initial_match, cell.final_match, cell.tone_match),
        cell.char_match,
    )


def render_board(game: IdiomGame, font_path: Path = FONT_PATH) -> bytes:
    """Render guesses only; unsuccessful endings append a green answer row."""
    if len(game.guesses) > MAX_GUESSES:
        raise ValueError("Board exceeds ten guesses")
    board = [guess.cells for guess in game.guesses]
    if game.status in {"lost", "stopped", "timeout"}:
        board.append(
            tuple(
                Cell(char, syllable, "exact", "exact", "exact", "exact")
                for char, syllable in zip(
                    game.answer, parse_word(game.answer, game.words)
                )
            )
        )
    tiles = [tuple(_result_tile(cell) for cell in row) for row in board]
    return _render_rows(tiles, len(game.answer), font_path)


def render_hint(game: IdiomGame, font_path: Path = FONT_PATH) -> bytes:
    """One row of confirmed clues, with question marks for unknown components."""
    row = tuple(
        _Tile(
            cell.char or "?",
            (cell.initial, cell.final, cell.tone),
            tuple(
                "none" if value is None else "exact"
                for value in (cell.initial, cell.final, cell.tone)
            ),
            "none" if cell.char is None else "exact",
        )
        for cell in get_hint(game)
    )
    return _render_rows([row], len(row), font_path)


def _render_rows(
    board: list[tuple[_Tile, ...]], columns: int, font_path: Path
) -> bytes:
    rows = max(1, len(board))
    width = PADDING * 2 + columns * CELL_WIDTH + (columns - 1) * GAP
    height = PADDING * 2 + rows * CELL_HEIGHT + (rows - 1) * GAP
    image = Image.new("RGB", (width, height), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image)
    char_font = ImageFont.truetype(str(font_path), 50)
    pinyin_font = ImageFont.truetype(str(font_path), PINYIN_FONT_SIZE)
    for row in range(rows):
        y = PADDING + row * (CELL_HEIGHT + GAP)
        for col in range(columns):
            x = PADDING + col * (CELL_WIDTH + GAP)
            draw.rounded_rectangle(
                (x, y, x + CELL_WIDTH - 1, y + CELL_HEIGHT - 1),
                radius=10,
                fill=CELL_BACKGROUND_COLOR,
                outline=BORDER_COLOR,
            )
            if not board:
                continue
            cell = board[row][col]
            _draw_pinyin(image, draw, x + CELL_WIDTH / 2, y + 46, cell, pinyin_font)
            draw.text(
                (x + CELL_WIDTH / 2, y + 83),
                cell.char,
                anchor="mm",
                font=char_font,
                fill=COLORS[cell.char_match],
            )
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _graphemes(text: str) -> list[str]:
    result = []
    for char in text:
        if unicodedata.combining(char) and result:
            result[-1] += char
        else:
            result.append(char)
    return result


def _draw_pinyin(image, draw, center_x, baseline, cell, font):
    initial, final, tone = cell.parts
    start = "?" if initial is None else initial
    end = display_final(initial, final)
    letters = list(end)
    widths = [draw.textlength(letter, font=font) for letter in letters]
    start_width = draw.textlength(start, font=font)
    x = center_x - (start_width + sum(widths)) / 2
    draw.text(
        (x, baseline), start, anchor="ls", font=font, fill=COLORS[cell.matches[0]]
    )
    x += start_width
    accented = (
        _graphemes(marked_final(initial, final, tone))
        if final is not None and tone is not None
        else letters
    )
    positions = []
    for letter, marked, width in zip(letters, accented, widths):
        positions.append(x + width / 2)
        if marked != letter:
            # Paint the marked glyph, then restore the letter in its own color.
            draw.text(
                (x, baseline),
                marked,
                anchor="ls",
                font=font,
                fill=COLORS[cell.matches[2]],
            )
        if letter == "i" and marked != letter:
            # The bundled CJK font has no dotless-i glyph. Recolor the body of
            # the accented glyph below x-height, preserving the tone above it.
            left, _, right, bottom = font.getbbox(marked, anchor="ls")
            body_top = font.getbbox("x", anchor="ls")[1]
            mask = Image.new("L", (right - left, bottom - body_top))
            ImageDraw.Draw(mask).text(
                (-left, -body_top), marked, anchor="ls", font=font, fill=255
            )
            image.paste(
                COLORS[cell.matches[1]], (round(x) + left, baseline + body_top), mask
            )
        else:
            draw.text(
                (x, baseline),
                letter,
                anchor="ls",
                font=font,
                fill=COLORS[cell.matches[1]],
            )
        x += width
    if final is None or tone is None:
        mark = tone_mark(tone)
        if mark:
            # A missing vowel must not be inferred just to position a known tone.
            probe = _graphemes(marked_final(initial, final, 1)) if final else letters
            index = next(
                (
                    i
                    for i, (plain, marked) in enumerate(zip(letters, probe))
                    if plain != marked
                ),
                0,
            )
            draw.text(
                (positions[index], baseline - 21),
                mark,
                anchor="ms",
                font=font.font_variant(size=18),
                fill=COLORS[cell.matches[2]],
            )
