"""Local Pillow renderer. Does not import AstrBot or modify game state."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .core import MAX_GUESSES, RESOURCE_DIR, Cell, IdiomGame, parse_word
from .hints import get_hint

FONT_PATH = RESOURCE_DIR / "fonts" / "NotoSansCJKsc-Regular.otf"
COLORS = {"exact": "#238653", "misplaced": "#b77916", "none": "#747c88"}
PADDING = 16
GAP = 12
CELL_WIDTH = 144
CELL_HEIGHT = 120


@dataclass(frozen=True)
class _Tile:
    char: str
    parts: tuple[str, str, str]
    matches: tuple[str, str, str]
    char_match: str


def _result_tile(cell: Cell) -> _Tile:
    syllable = cell.syllable
    return _Tile(
        cell.char,
        (syllable.initial, syllable.final.replace("v", "ü"), str(syllable.tone or 5)),
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
            cell.pinyin_parts,
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
    image = Image.new("RGB", (width, height), "#f6f7fb")
    draw = ImageDraw.Draw(image)
    char_font = ImageFont.truetype(str(font_path), 50)
    pinyin_font = ImageFont.truetype(str(font_path), 24)
    for row in range(rows):
        y = PADDING + row * (CELL_HEIGHT + GAP)
        for col in range(columns):
            x = PADDING + col * (CELL_WIDTH + GAP)
            draw.rounded_rectangle(
                (x, y, x + CELL_WIDTH - 1, y + CELL_HEIGHT - 1),
                radius=10,
                fill="white",
                outline="#d3d8e0",
            )
            if not board:
                continue
            cell = board[row][col]
            lengths = [draw.textlength(p, font=pinyin_font) for p in cell.parts]
            px = x + (CELL_WIDTH - sum(lengths) - 8) / 2
            for part, state, length in zip(cell.parts, cell.matches, lengths):
                draw.text((px, y + 10), part, font=pinyin_font, fill=COLORS[state])
                px += length + 4
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
