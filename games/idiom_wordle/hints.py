"""Summarize confirmed feedback without consulting the hidden answer."""

from dataclasses import dataclass, replace

from .core import IdiomGame
from .pinyin_display import display_final, format_pinyin, tone_mark


@dataclass(frozen=True)
class HintCell:
    char: str | None = None
    initial: str | None = None
    final: str | None = None
    tone: int | None = None

    @property
    def pinyin_parts(self) -> tuple[str, str, str]:
        return (
            "?" if self.initial is None else self.initial,
            display_final(self.initial, self.final),
            tone_mark(self.tone),
        )


def get_hint(game: IdiomGame) -> tuple[HintCell, ...]:
    """Combine green clues from every guess; missing and yellow clues stay unknown.

    An empty initial marked green is automatic in scoring, so it is only confirmed
    when the character itself is correct. Reading hints does not change the game.
    """
    known = [HintCell() for _ in game.answer]
    for guess in game.guesses:
        for i, cell in enumerate(guess.cells):
            syllable = cell.syllable
            if cell.char_match == "exact":
                known[i] = HintCell(
                    cell.char, syllable.initial, syllable.final, syllable.tone
                )
                continue
            updates = {}
            for name in ("initial", "final", "tone"):
                value = getattr(syllable, name)
                if (
                    getattr(known[i], name) is None
                    and getattr(cell, f"{name}_match") == "exact"
                    and (name == "tone" or value)
                ):
                    updates[name] = value
            known[i] = replace(known[i], **updates)
    return tuple(known)


def format_hint(game: IdiomGame) -> str:
    """Plain-text equivalent of the one-row hint image, also usable as a fallback."""
    cells = get_hint(game)
    return "\n".join(
        f"{cell.char or '?'}  {format_pinyin(cell.initial, cell.final, cell.tone)}"
        for cell in cells
    )
