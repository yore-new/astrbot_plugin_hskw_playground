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


def test_common_answer_pool_matches_reviewed_reference():
    from games.idiom_wordle.core import load_answers

    words = load_words()
    frequent = json.loads(
        (RESOURCE_DIR / "chinese_wordle" / "freq-idioms.json").read_text(
            encoding="utf-8"
        )
    )
    answers = load_answers(words)
    assert len(answers) == 1415
    assert set(answers) == set(frequent) & words.keys()
    assert "一心一意" in answers
    assert "全力以赴" in answers
    assert "一丁不识" not in answers
    assert "一不扭众" not in answers
    assert set(frequent) - words.keys() == {"追根溯源"}


def test_answer_generation_only_keeps_supported_frequent_candidates():
    from games.idiom_wordle.update_dictionary import build_answer_pool

    assert build_answer_pool(
        ["一心一意", "画蛇添足", "一心一意"], {"一心一意": "yi1 xin1 yi1 yi4"}
    ) == ["一心一意"]
    with pytest.raises(ValueError, match="empty"):
        build_answer_pool(["一心一意"], {})
    with pytest.raises(ValueError, match="four Chinese"):
        build_answer_pool(["abc"], {})


@pytest.mark.parametrize(
    "data", [[], {}, ["今天吃饭"], ["一心一意", "一心一意"], [None]]
)
def test_invalid_answer_resource_is_rejected(tmp_path, data):
    from games.idiom_wordle.core import load_answers

    path = tmp_path / "answers.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_answers({"一心一意": "yi1 xin1 yi1 yi4"}, path)
