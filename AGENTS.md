# Repository Guidelines

## Project Structure & Module Organization

This repository is an AstrBot Python plugin providing chat games.

- `main.py`: AstrBot commands, message routing, and plugin lifecycle management.
- `game_manager.py`: framework-independent game registry and chat scopes.
- `_conf_schema.json`: AstrBot settings schema; adapt configuration at framework boundaries.
- `games/<game_id>/`: one self-contained directory per game, including implementation, resources, tests, and `README.md`.
- `tests/`: shared registry and AstrBot adapter contract tests.

Keep game rules independent of AstrBot. Initialization, player actions, and rendering must each be callable and testable directly from Python. Put game-specific rules, commands, debugging examples, resource updates, and implementation notes in that game's `README.md`.

## Development & Validation Commands

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
git diff --check
```

Use `.venv/bin/ruff format .` to format changes. Follow each game's README for standalone debugging commands.

Real message delivery requires an AstrBot host. Reload through its plugin manager and verify relevant message handling, media delivery, and lifecycle behavior. Distinguish host verification from tests using framework doubles.

## Coding & Testing Conventions

Use four-space indentation, `snake_case` functions and variables, and `PascalCase` classes. Name tests `test_*.py`.

Scope games by platform instance and group; private chats use sender IDs. All game types share the registry, allowing one active game per scope. Serialize state changes and responses within each scope; stale callbacks must never remove replacement sessions.

Test game-specific rules alongside shared concerns: state transitions, concurrency, isolation, and failure handling. Inject clocks for time-dependent behavior rather than waiting in tests. Inspect generated images when changing rendering. Keep runtime files outside plugin source directories and retain licenses for external resources.

When changing input validation or presentation, verify state and timing side effects alongside displayed output. Keep rendered summaries separate from recorded player actions, and check both interactive responses and background notifications. Apply presentation requirements to failure paths as well as successful responses.

When adding configuration, keep schema defaults and runtime fallbacks consistent. Document units, validation, and when changes take effect. When changing units, update schema keys, runtime handling, messages, and tests together. Read-only commands must derive their output from public state without advancing progress or refreshing activity deadlines.

## Reusable Development Workflow

1. Read repository instructions, the affected game's README, and relevant official AstrBot documentation.
2. Divide work into reviewable stages appropriate to the change, keeping game logic, rendering, and framework integration separately verifiable.
3. Implement and validate each stage, update its documentation, and create a focused imperative Git commit before proceeding to the next stage.
4. Document behavior changes, commands, resource provenance, and verification limitations in the appropriate README.
5. As the final development step, review lessons learned: update this file only with reusable repository-wide guidance, keep game-specific details in the game's README, validate documentation, and commit workflow updates separately.

Pull requests should describe behavior changes, linked issues, validation, and relevant sample output. Never commit credentials or private message logs.
