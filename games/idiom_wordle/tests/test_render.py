from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from games.idiom_wordle.core import IdiomGame, load_words
from games.idiom_wordle.render import COLORS, FONT_PATH, render_board, render_hint


@pytest.fixture
def drawn_text(monkeypatch):
    calls = []
    original = ImageDraw.ImageDraw.text

    def capture(self, xy, text, *args, **kwargs):
        calls.append((xy, text, kwargs.get("fill")))
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", capture)
    return calls


def test_png_rows_and_game_unchanged():
    game = IdiomGame.create(now=0, answer="一心一意")
    empty = Image.open(BytesIO(render_board(game)))
    assert empty.format == "PNG"
    assert empty.size == (644, 152)
    choices = [w for w in load_words() if w != game.answer]
    for i, word in enumerate(choices[:10]):
        game.submit(word, now=i)
    image = Image.open(BytesIO(render_board(game)))
    # Ten guesses plus a separate answer row; the answer is not an attempt.
    assert image.size == (644, 1472)
    assert game.status == "lost"
    assert len(game.guesses) == 10
    assert FONT_PATH.exists()


def test_board_contains_only_characters_and_pinyin(drawn_text):
    game = IdiomGame.create(now=0, answer="一心一意")
    game.submit("画蛇添足", now=1)
    render_board(game)
    assert [text for _, text, _ in drawn_text if text in "画蛇添足"] == list("画蛇添足")
    assert all(
        text
        in {
            "画",
            "蛇",
            "添",
            "足",
            "h",
            "ua",
            "4",
            "sh",
            "e",
            "2",
            "t",
            "ian",
            "1",
            "z",
            "u",
        }
        for _, text, _ in drawn_text
    )
    assert not any(text in "一心意" for _, text, _ in drawn_text)


@pytest.mark.parametrize("ending", ["stopped", "lost", "timeout"])
def test_unsuccessful_ending_appends_green_answer_without_mutation(ending, drawn_text):
    game = IdiomGame.create(now=0, answer="一心一意")
    choices = [w for w in load_words() if w != game.answer]
    for i, word in enumerate(choices[:10] if ending == "lost" else ["画蛇添足"]):
        game.submit(word, now=i)
    if ending == "stopped":
        game.stop()
    elif ending == "timeout":
        game.expire(game.deadline)
    before = list(game.guesses)
    render_board(game)
    answer_row = drawn_text[-16:]
    assert [text for _, text, _ in answer_row if text in "一心意"] == list(game.answer)
    assert all(color == COLORS["exact"] for _, _, color in answer_row)
    assert game.guesses == before
    assert game.status == ending
    # Same columns and spacing as previous guesses, directly below the last row.
    previous_y = drawn_text[-17][0][1]
    answer_char_y = answer_row[3][0][1]
    assert answer_char_y - previous_y == 132


def test_win_does_not_duplicate_correct_row(drawn_text):
    game = IdiomGame.create(now=0, answer="一心一意")
    game.submit(game.answer, now=1)
    image = Image.open(BytesIO(render_board(game)))
    assert image.size == (644, 152)
    assert [text for _, text, _ in drawn_text if text in "一心意"] == list(game.answer)


def test_stop_without_guesses_shows_only_answer(drawn_text):
    game = IdiomGame.create(now=0, answer="一心一意")
    game.stop()
    image = Image.open(BytesIO(render_board(game)))
    assert image.size == (644, 152)
    assert [text for _, text, _ in drawn_text if text in "一心意"] == list(game.answer)
    assert all(color == COLORS["exact"] for _, _, color in drawn_text)
    assert not game.guesses


def test_empty_hint_displays_only_question_marks(drawn_text):
    game = IdiomGame.create(now=0, answer="画蛇添足")
    image = Image.open(BytesIO(render_hint(game)))
    assert image.size == (644, 152)
    assert [text for _, text, _ in drawn_text] == ["?"] * 16
    assert all(color == COLORS["none"] for _, _, color in drawn_text)


def test_hint_draws_confirmed_clues_and_masks_the_rest(drawn_text):
    game = IdiomGame.create(now=0, answer="画蛇添足")
    game.submit("画龙点睛", now=1)
    before = (list(game.guesses), game.deadline, game.status)
    render_hint(game)
    assert [text for _, text, _ in drawn_text[:4]] == ["h", "ua", "4", "画"]
    assert all(color == COLORS["exact"] for _, _, color in drawn_text[:4])
    assert drawn_text[7][1:] == ("?", COLORS["none"])
    assert "蛇" not in [text for _, text, _ in drawn_text]
    assert (game.guesses, game.deadline, game.status) == before
