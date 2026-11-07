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


def main():
    source = RESOURCE_DIR / "handle"
    idioms = (source / "idioms.txt").read_text(encoding="utf-8").splitlines()
    polyphones = json.loads((source / "polyphones.json").read_text(encoding="utf-8"))
    overrides = json.loads(
        (RESOURCE_DIR / "pronunciation_overrides.json").read_text(encoding="utf-8")
    )
    words = build_dictionary(idioms, polyphones, overrides)
    # Build and validate everything before replacing the runtime dictionary.
    output = RESOURCE_DIR / "idioms.json"
    output.write_text(
        json.dumps(words, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Updated {output.name}: {len(words)} idioms")


if __name__ == "__main__":
    main()
