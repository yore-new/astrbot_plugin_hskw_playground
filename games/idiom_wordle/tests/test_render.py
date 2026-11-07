from io import BytesIO

from PIL import Image

from games.idiom_wordle.core import IdiomGame, load_words
from games.idiom_wordle.render import FONT_PATH, render_board


def test_png_rows_and_game_unchanged():
    game = IdiomGame.create(now=0, answer="一心一意")
    empty = Image.open(BytesIO(render_board(game)))
    assert empty.format == "PNG"
    choices = [w for w in load_words() if w != game.answer]
    for i, word in enumerate(choices[:10]):
        game.submit(word, now=i)
    image = Image.open(BytesIO(render_board(game)))
    assert image.size == (720, 1498)
    assert game.status == "lost"
    assert len(game.guesses) == 10
    assert FONT_PATH.exists()


def test_playing_board_does_not_include_answer(monkeypatch):
    from PIL import ImageDraw

    texts = []
    original = ImageDraw.ImageDraw.text

    def capture(self, xy, text, *args, **kwargs):
        texts.append(text)
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", capture)
    game = IdiomGame.create(now=0, answer="一心一意")
    render_board(game)
    assert all(game.answer not in t for t in texts)
    game.stop()
    render_board(game)
    assert any("答案：一心一意" in t for t in texts)
