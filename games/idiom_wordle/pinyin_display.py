"""Convert internal numbered pronunciations to standard visible tone marks."""

from pypinyin.contrib.tone_convert import to_tone

TONE_MARKS = {0: "", 1: "ˉ", 2: "ˊ", 3: "ˇ", 4: "ˋ", 5: ""}


def tone_mark(tone: int | None) -> str:
    return "?" if tone is None else TONE_MARKS[tone]


def display_final(initial: str | None, final: str | None) -> str:
    if final is None:
        return "?"
    # The internal matching representation expands ü after j/q/x/y.
    replacement = "u" if initial in {"j", "q", "x", "y"} else "ü"
    return final.replace("v", replacement)


def marked_final(initial: str | None, final: str, tone: int) -> str:
    return to_tone(display_final(initial, final) + str(tone or 5))


def format_pinyin(initial: str | None, final: str | None, tone: int | None) -> str:
    """Format known pronunciation; unknown components remain question marks."""
    start = "?" if initial is None else initial
    if final is None or tone is None:
        return start + display_final(initial, final) + tone_mark(tone)
    return start + marked_final(initial, final, tone)
