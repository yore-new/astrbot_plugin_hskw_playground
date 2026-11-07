from games.idiom_wordle.core import IdiomGame
from games.idiom_wordle.hints import HintCell, format_hint, get_hint


def game():
    return IdiomGame.create(now=0, answer="画蛇添足")


def test_no_guesses_reveals_nothing():
    g = game()
    assert get_hint(g) == (HintCell(),) * 4
    assert format_hint(g) == "\n".join(["?  ???"] * 4)
    assert g.deadline == 300
    assert not g.guesses


def test_hint_merges_all_history_without_consuming_turn_or_reading_answer():
    g = game()
    g.submit("画龙点睛", now=1)
    g.submit("一心一意", now=2)
    g.submit("海阔天空", now=3)
    before = (list(g.guesses), g.deadline, g.status)
    hint = get_hint(g)
    assert hint[0] == HintCell("画", "h", "ua", 4)
    assert hint[1].char is None
    assert hint[1].tone == 2  # An earlier guess provided this tone.
    assert hint[2] == HintCell(None, "t", "ian", 1)
    assert hint[3].char is None
    assert (g.guesses, g.deadline, g.status) == before
    assert get_hint(g) == hint
    # A summary must depend on recorded feedback, not hidden answer contents.
    g.answer = "守株待兔"
    assert get_hint(g) == hint


def test_yellow_and_automatic_empty_initial_do_not_reveal_answer():
    g = game()
    g.submit("掩耳盗铃", now=1)
    assert g.guesses[0].cells[1].initial_match == "exact"
    hint = get_hint(g)
    assert hint[1].initial is None
    assert hint[1].tone is None
    assert hint[1].char is None
    assert hint[1].pinyin_parts == ("?", "?", "?")
    g = IdiomGame.create(now=0, answer="一心一意")
    g.submit("画蛇添足", now=1)
    assert g.guesses[0].cells[0].tone_match == "misplaced"
    assert get_hint(g)[0].tone is None


def test_known_empty_initial_and_neutral_tone_are_not_question_marks():
    g = IdiomGame.create(
        now=0,
        answer="阿猫阿狗",
        words={"阿猫阿狗": "a1 mao5 a1 gou3"},
    )
    g.submit("阿猫阿狗", now=1)
    hint = get_hint(g)
    assert hint[0].initial == ""
    assert hint[0].pinyin_parts == ("", "a", "ˉ")
    assert hint[1].tone == 0
    assert hint[1].pinyin_parts == ("m", "ao", "")
