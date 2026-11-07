"""Local Pillow renderer. Does not import AstrBot or modify game state."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .core import MAX_GUESSES, RESOURCE_DIR, Cell, IdiomGame, parse_word
from .hints import get_hint
from .pinyin_display import display_final, display_tone

FONT_PATH = RESOURCE_DIR / "fonts" / "NotoSansCJKsc-Regular.otf"
COLORS = {"exact": "#007a37", "misplaced": "#9a5b00", "none": "#626970"}
BACKGROUND_COLOR = "#fff8d6"
CELL_BACKGROUND_COLOR = "#eeeeee"
BORDER_COLOR = "#dfcf91"
PINYIN_FONT_SIZE = 28
TONE_FONT_SIZE = 20
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
            _draw_pinyin(draw, x + CELL_WIDTH / 2, y + 46, cell, pinyin_font)
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


def _draw_pinyin(draw, center_x, baseline, cell, font):
    initial, final, tone = cell.parts
    start = "?" if initial is None else initial
    end = display_final(initial, final)
    label = display_tone(tone)
    tone_font = font.font_variant(size=TONE_FONT_SIZE)
    start_width = draw.textlength(start, font=font)
    final_width = draw.textlength(end, font=font)
    tone_width = draw.textlength(label, font=tone_font)
    gap = 3
    x = center_x - (start_width + final_width + gap + tone_width) / 2
    draw.text(
        (x, baseline), start, anchor="ls", font=font, fill=COLORS[cell.matches[0]]
    )
    draw.text(
        (x + start_width, baseline),
        end,
        anchor="ls",
        font=font,
        fill=COLORS[cell.matches[1]],
    )
    draw.text(
        (x + start_width + final_width + gap, baseline - 12),
        label,
        anchor="ls",
        font=tone_font,
        fill=COLORS[cell.matches[2]],
    )
