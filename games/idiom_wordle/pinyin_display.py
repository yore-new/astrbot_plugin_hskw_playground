"""Format pinyin with numeric tone labels and superscript text fallbacks."""

TONE_LABELS = {0: "5", 1: "1", 2: "2", 3: "3", 4: "4", 5: "5"}
SUPERSCRIPT_TONES = str.maketrans("12345", "¹²³⁴⁵")


def display_tone(tone: int | None) -> str:
    """Use 5 for neutral tone and a question mark for an unknown tone."""
    return "?" if tone is None else TONE_LABELS[tone]


def display_final(initial: str | None, final: str | None) -> str:
    if final is None:
        return "?"
    # The internal matching representation expands ü after j/q/x/y.
    replacement = "u" if initial in {"j", "q", "x", "y"} else "ü"
    return final.replace("v", replacement)


def format_pinyin(initial: str | None, final: str | None, tone: int | None) -> str:
    """Represent the raised numeric label in plain-text hint fallbacks too."""
    start = "?" if initial is None else initial
    label = display_tone(tone).translate(SUPERSCRIPT_TONES)
    return start + display_final(initial, final) + label
