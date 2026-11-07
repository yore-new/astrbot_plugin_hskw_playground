import json

import pytest

from games.idiom_wordle.core import RESOURCE_DIR, load_words, parse_word
from games.idiom_wordle.update_dictionary import build_dictionary


def test_dictionary_contains_every_upstream_word():
    source = RESOURCE_DIR / "handle"
    idioms = (source / "idioms.txt").read_text(encoding="utf-8").splitlines()
    polyphones = json.loads((source / "polyphones.json").read_text(encoding="utf-8"))
    words = load_words()
    assert len(words) == 29760
    assert set(words) == set(idioms) | polyphones.keys()
    assert words["一丁不识"] == "yi1 ding1 bu4 shi2"
    assert words["一心一意"] == "yi1 xin1 yi1 yi4"
    assert words["一丘之貉"] == "yi1 qiu1 zhi1 he2"
    assert words["一股脑儿"].endswith("er5")
    assert len(parse_word("一股脑儿", words)) == 4


def test_generator_priorities_neutral_tone_and_stable_order():
    words = build_dictionary(
        ["一心一意", "一股脑儿", "一丘之貉"],
        {"一丘之貉": "yi1 qiu1 zhi1 he2", "一股脑儿": "yi1 gu3 nao3 er"},
        {"一心一意": "yi1 xin1 yi1 yi4"},
    )
    assert list(words) == sorted(words)
    assert words["一股脑儿"] == "yi1 gu3 nao3 er5"
    assert words["一丘之貉"].endswith("he2")
    assert words["一心一意"].startswith("yi1")


@pytest.mark.parametrize(
    "idioms,polyphones,overrides",
    [
        ([], {}, {}),
        (["不对"], {}, {}),
        (["一心一意"], {"一心一意": "invalid"}, {}),
        (["一心一意"], {}, {"画蛇添足": "hua4 she2 tian1 zu2"}),
    ],
)
def test_invalid_sources_are_rejected(idioms, polyphones, overrides):
    with pytest.raises(ValueError):
        build_dictionary(idioms, polyphones, overrides)
