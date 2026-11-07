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
        if self._image.mode == "RGB":
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
    assert [text for _, text, _ in drawn_text if text.isdigit()] == ["4", "2", "1", "2"]
    assert {"h", "ua", "sh", "e", "t", "ian", "z", "u"} <= {
        text for _, text, _ in drawn_text
    }
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
    answer_top = 16 + len(game.guesses) * 132
    answer_row = [call for call in drawn_text if call[0][1] >= answer_top]
    assert [text for _, text, _ in answer_row if text in "一心意"] == list(game.answer)
    assert all(color == COLORS["exact"] for _, _, color in answer_row)
    assert game.guesses == before
    assert game.status == ending
    # Same columns and spacing as previous guesses, directly below the last row.
    hanzi = [
        call
        for call in drawn_text
        if len(call[1]) == 1 and "\u4e00" <= call[1] <= "\u9fff"
    ]
    previous_y = hanzi[-5][0][1]
    answer_char_y = hanzi[-4][0][1]
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
    assert ("4", COLORS["exact"]) in [call[1:] for call in drawn_text]
    assert ("画", COLORS["exact"]) in [call[1:] for call in drawn_text]
    assert ("?", COLORS["none"]) in [call[1:] for call in drawn_text]
    assert "蛇" not in [text for _, text, _ in drawn_text]
    assert (game.guesses, game.deadline, game.status) == before


def test_superscript_tone_keeps_its_match_color_independent_of_the_vowel(drawn_text):
    game = IdiomGame.create(now=0, answer="一心一意")
    game.submit("画蛇添足", now=1)
    render_board(game)
    number = next(call for call in drawn_text if call[1] == "4")
    vowel = next(call for call in drawn_text if call[1] == "ua")
    assert number[2] == COLORS["misplaced"]
    assert vowel[2] == COLORS["none"]
    assert number[0][0] > vowel[0][0]
    assert number[0][1] < vowel[0][1]


@pytest.mark.parametrize(
    "tone,label", [(1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "5"), (0, "5")]
)
def test_all_tones_are_drawn_as_raised_digits(drawn_text, tone, label):
    game = IdiomGame.create(
        now=0,
        answer="一心一意",
        words={"一心一意": f"yi{tone} xin{tone} yi{tone} yi{tone}"},
    )
    game.submit(game.answer, now=1)
    render_board(game)
    digits = [call for call in drawn_text if call[1].isdigit()]
    assert [call[1] for call in digits] == [label] * 4
    for number in digits:
        letters = [
            call
            for call in drawn_text
            if call[0][0] < number[0][0] and call[1] in {"i", "in"}
        ]
        assert number[0][1] < letters[-1][0][1]
    assert not any(call[1] in {"ǐ", "ī", "ı"} for call in drawn_text)


@pytest.mark.parametrize("view", ["board", "hint", "answer"])
def test_all_views_use_pale_yellow_background_and_light_gray_cells(view):
    game = IdiomGame.create(now=0, answer="一心一意")
    if view == "answer":
        game.stop()
    png = render_hint(game) if view == "hint" else render_board(game)
    image = Image.open(BytesIO(png))
    assert image.getpixel((0, 0)) == (255, 248, 214)
    assert image.getpixel((20, 76)) == (238, 238, 238)


def test_feedback_colors_remain_readable_on_warm_backgrounds():
    from games.idiom_wordle.render import BACKGROUND_COLOR, CELL_BACKGROUND_COLOR

    def luminance(hex_color):
        rgb = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [
            v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb
        ]
        return sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

    for background in (BACKGROUND_COLOR, CELL_BACKGROUND_COLOR):
        for foreground in COLORS.values():
            light, dark = sorted(
                [luminance(background), luminance(foreground)], reverse=True
            )
            assert (light + 0.05) / (dark + 0.05) >= 4.5
    green = tuple(int(COLORS["exact"][i : i + 2], 16) for i in (1, 3, 5))
    assert green[1] > max(green[0], green[2])
    assert min(green) == 0  # Saturated green, rather than a muted gray-green.
