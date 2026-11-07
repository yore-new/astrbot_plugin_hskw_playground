# Pinyin matching adapted from antfu/handle, Copyright Anthony Fu.
# See LICENSE.Handle for the original MIT license.

"""Framework-free game state. All times are monotonic seconds."""

from __future__ import annotations

import json
import math
import random
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pypinyin import Style, pinyin

IDLE_SECONDS = 300
MAX_GUESSES = 10
RESOURCE_DIR = Path(__file__).parent / "resources"
INITIALS = ("zh", "ch", "sh", *"bpmfdtnlgkhjqxrzcsyw")
HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U000323af]+\Z")


@dataclass(frozen=True)
class Syllable:
    initial: str
    final: str
    tone: int

    @property
    def parts(self) -> tuple[str, ...]:
        return tuple(p for p in (self.initial, self.final) if p)


def split_pinyin(value: str) -> Syllable:
    value = value.lower().replace("ü", "v").replace("u:", "v")
    if not re.fullmatch(r"[a-zv]+[0-5]", value):
        raise ValueError(f"Invalid numbered pinyin: {value}")
    base, tone = value[:-1], int(value[-1]) % 5
    # Match Handle's explicit ü normalization, including yu/ju/qu/xu.
    base = re.sub(r"^([yjqx])u", r"\1v", base)
    initial = next((i for i in INITIALS if base.startswith(i)), "")
    final = base[len(initial) :]
    if not final:
        initial, final = "", base
    return Syllable(initial, final, tone)


def is_candidate(text: str, length: int = 4) -> bool:
    return len(text) == length and HAN.fullmatch(text) is not None


def load_words(path: Path = RESOURCE_DIR / "idioms.json") -> dict[str, str]:
    words = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(words, dict) or not words:
        raise ValueError("Idiom dictionary must be a nonempty object")
    for word, reading in words.items():
        if not is_candidate(word) or not isinstance(reading, str):
            raise ValueError(f"Invalid idiom entry: {word}")
        if len(reading.split()) != len(word):
            raise ValueError(f"Invalid reading length: {word}")
        for syllable in reading.split():
            split_pinyin(syllable)
    return words


def load_answers(
    words: dict[str, str] | None = None,
    path: Path = RESOURCE_DIR / "answers.json",
) -> tuple[str, ...]:
    """Load common answers separately from the larger accepted-guess dictionary."""
    words = load_words() if words is None else words
    answers = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(answers, list) or not answers:
        raise ValueError("Answer pool must be a nonempty list")
    if any(not isinstance(word, str) or word not in words for word in answers):
        raise ValueError("Every answer must be in the guess dictionary")
    if len(answers) != len(set(answers)):
        raise ValueError("Answer pool must not contain duplicates")
    return tuple(answers)


def parse_word(word: str, words: dict[str, str]) -> tuple[Syllable, ...]:
    if word in words:
        readings = words[word].split()
    else:
        readings = [
            part[0]
            for part in pinyin(word, style=Style.TONE3, neutral_tone_with_five=True)
        ]
    if len(readings) != len(word):
        raise ValueError("Cannot parse guess pronunciation")
    return tuple(split_pinyin(value) for value in readings)


def match_tokens(guess: list, answer: list) -> list[str]:
    """Reserve exact matches first, then consume each remaining token once."""
    result = ["exact" if a == b else "none" for a, b in zip(guess, answer)]
    remaining = Counter(b for b, state in zip(answer, result) if state != "exact")
    for i, token in enumerate(guess):
        if result[i] != "exact" and remaining[token]:
            result[i] = "misplaced"
            remaining[token] -= 1
    return result


@dataclass(frozen=True)
class Cell:
    char: str
    syllable: Syllable
    char_match: str
    initial_match: str
    final_match: str
    tone_match: str


def evaluate(guess: str, answer: str, words: dict[str, str]) -> tuple[Cell, ...]:
    if not is_candidate(answer) or not is_candidate(guess, len(answer)):
        raise ValueError("Expected four Chinese characters")
    target = parse_word(answer, words)
    parsed = list(parse_word(guess, words))
    # The same character uses the answer's reading, as in Handle.
    for i, char in enumerate(guess):
        if char in answer:
            parsed[i] = target[answer.index(char)]
    chars = match_tokens(list(guess), list(answer))
    tones = match_tokens([s.tone for s in parsed], [s.tone for s in target])
    remaining = Counter(
        part
        for source, dest in zip(parsed, target)
        for part in dest.parts
        if part not in source.parts
    )
    cells = []
    for i, syllable in enumerate(parsed):
        matches = []
        for part in (syllable.initial, syllable.final):
            if not part or part in target[i].parts:
                matches.append("exact")
            elif remaining[part]:
                matches.append("misplaced")
                remaining[part] -= 1
            else:
                matches.append("none")
        cells.append(Cell(guess[i], syllable, chars[i], *matches, tones[i]))
    return tuple(cells)


@dataclass(frozen=True)
class Guess:
    text: str
    cells: tuple[Cell, ...]


@dataclass
class IdiomGame:
    answer: str
    words: dict[str, str] = field(repr=False)
    deadline: float
    idle_seconds: float = IDLE_SECONDS
    guesses: list[Guess] = field(default_factory=list)
    status: str = "playing"
    game_id: str = field(default="idiom_wordle", init=False)
    display_name: str = field(default="猜成语", init=False)

    @classmethod
    def create(
        cls,
        *,
        now: float,
        words: dict[str, str] | None = None,
        answer: str | None = None,
        idle_seconds: float = IDLE_SECONDS,
        answer_pool: tuple[str, ...] | None = None,
    ) -> IdiomGame:
        try:
            if isinstance(idle_seconds, bool):
                raise ValueError("Boolean timeout is invalid")
            idle_seconds = float(idle_seconds)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Idle timeout must be finite and positive") from exc
        if not math.isfinite(idle_seconds) or idle_seconds <= 0:
            raise ValueError("Idle timeout must be finite and positive")
        use_default_pool = words is None
        words = load_words() if words is None else words
        if not words:
            raise ValueError("Empty answer dictionary")
        if answer is None:
            if answer_pool is None:
                answer_pool = load_answers(words) if use_default_pool else tuple(words)
            if not answer_pool or any(word not in words for word in answer_pool):
                raise ValueError("Answer pool must contain known idioms")
            answer = random.choice(answer_pool)
        if answer not in words:
            raise ValueError("Answer must be in the dictionary")
        evaluate(answer, answer, words)
        return cls(answer, words, now + idle_seconds, idle_seconds=idle_seconds)

    def expire(self, now: float) -> bool:
        if self.status == "playing" and now >= self.deadline:
            self.status = "timeout"
            return True
        return False

    def submit(self, text: str, *, now: float) -> str:
        if self.expire(now) or self.status != "playing":
            return "ended"
        text = text.strip()
        if len(text) != len(self.answer):
            return "invalid"
        if text not in self.words:
            return "not_idiom"
        if any(g.text == text for g in self.guesses):
            return "duplicate"
        try:
            cells = evaluate(text, self.answer, self.words)
        except ValueError:
            return "invalid"
        self.guesses.append(Guess(text, cells))
        self.deadline = now + self.idle_seconds
        if text == self.answer:
            self.status = "won"
        elif len(self.guesses) == MAX_GUESSES:
            self.status = "lost"
        return "accepted"

    def stop(self) -> None:
        if self.status == "playing":
            self.status = "stopped"
