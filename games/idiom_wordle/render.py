"""Local Pillow renderer. Does not import AstrBot or modify game state."""

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .core import MAX_GUESSES, RESOURCE_DIR, IdiomGame

FONT_PATH = RESOURCE_DIR / "fonts" / "NotoSansCJKsc-Regular.otf"
COLORS = {"exact": "#238653", "misplaced": "#b77916", "none": "#747c88"}
STATUS = {
    "playing": "继续猜词 · 每次有效猜词后有 5 分钟",
    "won": "恭喜猜中！",
    "lost": "机会已用完",
    "stopped": "本轮已结束",
    "timeout": "5 分钟没有有效猜词，本轮结束",
}


def render_board(game: IdiomGame, font_path: Path = FONT_PATH) -> bytes:
    """Return a PNG of all guesses, up to ten rows, with independently colored hints."""
    title_font = ImageFont.truetype(str(font_path), 28)
    char_font = ImageFont.truetype(str(font_path), 48)
    small_font = ImageFont.truetype(str(font_path), 19)
    pinyin_font = ImageFont.truetype(str(font_path), 23)
    rows = max(1, len(game.guesses))
    if rows > MAX_GUESSES:
        raise ValueError("Board exceeds ten rows")
    width, row_height = 720, 122
    image = Image.new("RGB", (width, 130 + rows * row_height + 148), "#f6f7fb")
    draw = ImageDraw.Draw(image)
    draw.text((28, 20), "猜成语 Wordle", font=title_font, fill="#202735")
    draw.text(
        (28, 68),
        f"已猜 {len(game.guesses)}/{MAX_GUESSES} 次 · {STATUS[game.status]}",
        font=small_font,
        fill="#343c48",
    )
    for row, guess in enumerate(game.guesses):
        y = 118 + row * row_height
        draw.text((18, y + 45), str(row + 1), font=small_font, fill="#747c88")
        for col, cell in enumerate(guess.cells):
            x = 55 + col * 163
            draw.rounded_rectangle(
                (x, y, x + 151, y + 110), radius=10, fill="white", outline="#d3d8e0"
            )
            syllable = cell.syllable
            parts = (
                syllable.initial,
                syllable.final.replace("v", "ü"),
                str(syllable.tone or 5),
            )
            matches = (cell.initial_match, cell.final_match, cell.tone_match)
            lengths = [draw.textlength(p, font=pinyin_font) for p in parts]
            px = x + (151 - sum(lengths) - 8) / 2
            for part, state, length in zip(parts, matches, lengths):
                draw.text((px, y + 8), part, font=pinyin_font, fill=COLORS[state])
                px += length + 4
            draw.text(
                (x + 75, y + 76),
                cell.char,
                anchor="mm",
                font=char_font,
                fill=COLORS[cell.char_match],
            )
    bottom = 130 + rows * row_height
    for i, (state, label) in enumerate(
        (("exact", "位置正确"), ("misplaced", "存在但错位"), ("none", "没有匹配项"))
    ):
        x = 28 + i * 228
        draw.rectangle((x, bottom, x + 16, bottom + 16), fill=COLORS[state])
        draw.text((x + 24, bottom - 5), label, font=small_font, fill="#343c48")
    draw.text(
        (28, bottom + 32),
        "拼音：声母 / 韵母 / 声调分别着色；5 表示轻声",
        font=small_font,
        fill="#343c48",
    )
    footer = (
        f"答案：{game.answer}  {game.words[game.answer]}"
        if game.status != "playing"
        else "发送四字汉字猜词，或 /猜成语结束"
    )
    draw.text((28, bottom + 75), footer, font=small_font, fill="#343c48")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
