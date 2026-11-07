# Repository Guidelines

## Project Structure & Module Organization

This repository is an AstrBot Python plugin providing chat games.

- `main.py`: AstrBot commands, message routing, asynchronous locks, and expiry notifications.
- `game_manager.py`: framework-independent game registry and chat scopes.
- `games/<game_id>/`: one self-contained directory per game, including resources, tests, and `DEVELOPMENT.md`.
- `games/idiom_wordle/core.py`: initialization, pronunciation matching, guesses, and state transitions.
- `games/idiom_wordle/render.py`: pure PNG generation; `__main__.py` provides local debugging.
- `tests/`: registry and AstrBot adapter contract tests.

Keep game rules independent of AstrBot. Initialization, guessing, and rendering must each be callable and testable directly from Python.

## Development & Validation Commands

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
git diff --check
```

Use `.venv/bin/ruff format .` to format changes. Debug without AstrBot:

```sh
.venv/bin/python -m games.idiom_wordle --answer 一心一意 --guess 画蛇添足 --output /tmp/board.png
```

Real message delivery requires an AstrBot host. Reload through its plugin manager and verify ordinary group messages, image uploads, and proactive expiry notifications. Distinguish host verification from tests using framework doubles.

## Game Invariants & Testing

Scope games by platform instance and group; private chats use sender IDs. All game types share the registry, allowing one active game per scope. Serialize state changes and outgoing boards within each scope; stale callbacks must never remove replacement sessions.

Idiom Wordle permits ten guesses. Use only one resettable 300-second idle deadline, with no separate total-duration timer. Invalid and duplicate guesses neither consume attempts nor reset expiry. Inject monotonic timestamps in tests; use one timestamp for expiry checking and submission.

Name tests `test_*.py`. Cover duplicate-token counts, pronunciation, terminal states, expiry boundaries, concurrency, isolation, and failure handling. Inspect generated images when changing rendering.

## External Dictionary Updates

Preserve upstream snapshots, commit IDs, checksums, and licenses. Merge companion pronunciation data before generating runtime dictionaries; keep local corrections in override files. Validate full source coverage and pronunciation parsing, document the generator version, and regenerate offline with `python -m games.idiom_wordle.update_dictionary`. Edit sources or overrides rather than generated `idioms.json`.

## Reusable Development Workflow

1. Read repository instructions, the affected game's development document, and relevant official AstrBot documentation.
2. Divide work into reviewable stages: independent rules, rendering/local debugging, then framework integration.
3. Implement and validate each stage, update its development document, and create a focused imperative Git commit before completing the next stage.
4. Document commands, resource licenses, behavior changes, and verification limitations. Keep runtime files outside plugin source directories.
5. As the final development step, update this file with reusable lessons and revised workflow requirements, validate the documentation, and commit it separately.

Pull requests should describe behavior changes, linked issues, validation, and relevant sample output. Never commit credentials or private message logs.
