"""Rebuild the offline dictionary from checked-in Handle source snapshots."""

import json

from pypinyin import Style, pinyin

from .core import RESOURCE_DIR, is_candidate, split_pinyin


def build_dictionary(
    idioms: list[str], polyphones: dict[str, str], overrides: dict[str, str]
) -> dict[str, str]:
    """Merge disjoint upstream lists, prioritizing explicit and local readings."""
    candidates = set(idioms) | polyphones.keys()
    if not candidates:
        raise ValueError("Source dictionary is empty")
    if overrides.keys() - candidates:
        raise ValueError("Pronunciation overrides must refer to source words")
    words = {}
    for word in sorted(candidates):
        if not is_candidate(word):
            raise ValueError(f"Expected four Chinese characters: {word}")
        reading = overrides.get(word) or polyphones.get(word)
        tokens = (
            reading.split()
            if reading
            else [
                item[0]
                for item in pinyin(word, style=Style.TONE3, neutral_tone_with_five=True)
            ]
        )
        # Handle represents a missing tone as neutral; our format uses tone 5.
        tokens = [t if t[-1:].isdigit() else t + "5" for t in tokens]
        if len(tokens) != len(word):
            raise ValueError(f"Invalid pronunciation length: {word}")
        for token in tokens:
            split_pinyin(token)
        words[word] = " ".join(tokens)
    return words


def build_answer_pool(frequent: list[str], words: dict[str, str]) -> list[str]:
    """Keep reviewed frequent idioms with a validated local pronunciation."""
    if any(not is_candidate(word) for word in frequent):
        raise ValueError("Answer candidates must be four Chinese characters")
    answers = sorted(set(frequent) & words.keys())
    if not answers:
        raise ValueError("Common answer pool is empty")
    return answers


def main():
    source = RESOURCE_DIR / "handle"
    idioms = (source / "idioms.txt").read_text(encoding="utf-8").splitlines()
    polyphones = json.loads((source / "polyphones.json").read_text(encoding="utf-8"))
    overrides = json.loads(
        (RESOURCE_DIR / "pronunciation_overrides.json").read_text(encoding="utf-8")
    )
    words = build_dictionary(idioms, polyphones, overrides)
    frequent = json.loads(
        (RESOURCE_DIR / "chinese_wordle" / "freq-idioms.json").read_text(
            encoding="utf-8"
        )
    )
    answers = build_answer_pool(frequent, words)
    # Build and validate everything before replacing the runtime dictionary.
    output = RESOURCE_DIR / "idioms.json"
    output.write_text(
        json.dumps(words, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (RESOURCE_DIR / "answers.json").write_text(
        json.dumps(answers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Updated {output.name}: {len(words)} idioms")
    print(f"Updated answers.json: {len(answers)} common answers")
    missing = sorted(set(frequent) - words.keys())
    if missing:
        print(
            "Skipped answer candidates missing from the dictionary: "
            + ", ".join(missing)
        )


if __name__ == "__main__":
    main()
