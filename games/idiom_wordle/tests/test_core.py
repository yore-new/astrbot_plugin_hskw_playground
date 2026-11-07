import pytest

from games.idiom_wordle.core import (
    IdiomGame,
    evaluate,
    load_words,
    match_tokens,
    split_pinyin,
)


def game():
    return IdiomGame.create(now=0, answer="一心一意")


def test_dictionary_and_initialization():
    words = load_words()
    assert len(words) >= 30
    for word in words:
        assert all(c.char_match == "exact" for c in evaluate(word, word, words))
    assert game().deadline == 300
    with pytest.raises(ValueError):
        IdiomGame.create(now=0, words={})


def test_duplicate_tokens_reserve_exact_matches():
    assert match_tokens(list("一一一一"), list("一心一意")) == [
        "exact",
        "none",
        "exact",
        "none",
    ]
    assert match_tokens(list("心心一意"), list("一心一意")) == [
        "none",
        "exact",
        "exact",
        "exact",
    ]


def test_pinyin_parts_tones_and_polyphones():
    words = load_words()
    cells = evaluate("百发百中", "画蛇添足", words)
    assert cells[0].initial_match == "none"
    assert split_pinyin("er2").initial == ""
    assert split_pinyin("xue3").final == "ve"
    assert split_pinyin("ma5").tone == 0
    assert evaluate("重见天日", "重见天日", words)[0].syllable.initial == "ch"
    # Different characters can share pronunciation without winning.
    g = game()
    assert g.submit("衣心衣意", now=10) == "accepted"
    assert g.status == "playing"
    assert g.guesses[0].cells[0].char_match == "none"
    assert g.guesses[0].cells[0].tone_match == "exact"


def test_only_valid_new_guesses_reset_idle_deadline():
    g = game()
    assert g.submit("hello", now=100) == "invalid"
    assert g.deadline == 300
    assert g.submit("画蛇添足", now=299) == "accepted"
    assert g.deadline == 599
    assert g.submit("画蛇添足", now=400) == "duplicate"
    assert g.deadline == 599
    assert not g.expire(598.99)
    assert g.expire(599)
    assert g.submit("一心一意", now=600) == "ended"


def test_timeout_at_boundary_and_stop():
    g = game()
    assert g.submit("一心一意", now=300) == "ended"
    assert g.status == "timeout"
    g = game()
    g.stop()
    assert g.status == "stopped"
    assert not g.expire(1000)


def test_tenth_guess_wins_or_loses():
    choices = [w for w in load_words() if w != "一心一意"]
    for win in (True, False):
        g = game()
        for i, word in enumerate(choices[:9]):
            assert g.submit(word, now=i * 299) == "accepted"
        assert g.status == "playing"
        g.submit("一心一意" if win else choices[9], now=9 * 299)
        assert len(g.guesses) == 10
        assert g.status == ("won" if win else "lost")
        assert g.submit(choices[10], now=2700) == "ended"


def test_pinyin_parts_and_tones_consume_remaining_counts():
    cells = evaluate("衣衣衣衣", "一心一意", load_words())
    assert [c.initial_match for c in cells] == ["exact", "none", "exact", "exact"]
    assert [c.final_match for c in cells] == ["exact", "none", "exact", "exact"]
    assert [c.tone_match for c in cells] == ["exact", "exact", "exact", "none"]
    # The tone 4 exists in another position, but only one can be used.
    cells = evaluate("意意意衣", "一心一意", load_words())
    assert [c.tone_match for c in cells] == ["misplaced", "none", "none", "misplaced"]


def test_idle_interval_has_no_second_total_deadline(monkeypatch):
    import games.idiom_wordle.core as core

    # Temporarily lift the guess limit to make any hidden total timer observable.
    monkeypatch.setattr(core, "MAX_GUESSES", 100)
    g = game()
    choices = [w for w in load_words() if w != g.answer]
    for i, word in enumerate(choices[:12]):
        assert g.submit(word, now=(i + 1) * 299) == "accepted"
    assert g.status == "playing"
    assert g.deadline > 3600
