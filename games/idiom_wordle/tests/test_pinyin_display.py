import pytest

from games.idiom_wordle.pinyin_display import format_pinyin


@pytest.mark.parametrize(
    "initial,final,tone,expected",
    [
        ("h", "ua", 4, "hua⁴"),
        ("sh", "e", 2, "she²"),
        ("t", "ian", 1, "tian¹"),
        ("z", "u", 2, "zu²"),
        ("l", "iu", 2, "liu²"),
        ("g", "ui", 3, "gui³"),
        ("zh", "ou", 1, "zhou¹"),
        ("n", "v", 3, "nü³"),
        ("l", "ve", 4, "lüe⁴"),
        ("x", "ve", 3, "xue³"),
        ("j", "vn", 1, "jun¹"),
        ("y", "v", 2, "yu²"),
        ("", "er", 2, "er²"),
        ("", "ng", 2, "ng²"),
        ("m", "a", 0, "ma⁵"),
        ("m", "a", 5, "ma⁵"),
        (None, None, None, "???"),
        (None, "ian", 1, "?ian¹"),
        ("h", "ua", None, "hua?"),
        (None, None, 2, "??²"),
    ],
)
def test_superscript_tones_and_partial_pronunciation(initial, final, tone, expected):
    assert format_pinyin(initial, final, tone) == expected
    assert not any(char in "12345" for char in expected)
