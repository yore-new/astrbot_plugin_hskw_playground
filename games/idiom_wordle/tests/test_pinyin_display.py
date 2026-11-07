import pytest

from games.idiom_wordle.pinyin_display import format_pinyin


@pytest.mark.parametrize(
    "initial,final,tone,expected",
    [
        ("h", "ua", 4, "huà"),
        ("sh", "e", 2, "shé"),
        ("t", "ian", 1, "tiān"),
        ("z", "u", 2, "zú"),
        ("l", "iu", 2, "liú"),
        ("g", "ui", 3, "guǐ"),
        ("zh", "ou", 1, "zhōu"),
        ("n", "v", 3, "nǚ"),
        ("l", "ve", 4, "lüè"),
        ("x", "ve", 3, "xuě"),
        ("j", "vn", 1, "jūn"),
        ("y", "v", 2, "yú"),
        ("", "er", 2, "ér"),
        ("", "ng", 2, "ńg"),
        ("m", "a", 0, "ma"),
        ("m", "a", 5, "ma"),
        (None, None, None, "???"),
        (None, "ian", 1, "?iān"),
        ("h", "ua", None, "hua?"),
        (None, None, 2, "??ˊ"),
    ],
)
def test_standard_tones_and_partial_pronunciation(initial, final, tone, expected):
    assert format_pinyin(initial, final, tone) == expected
    assert not any(char.isdigit() for char in expected)
