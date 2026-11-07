# Repository Guidelines

## Project Structure & Module Organization

This repository currently contains a minimal AstrBot Python plugin template.

- `main.py`: plugin registration, the `MyPlugin` class, lifecycle hooks, and the `/helloworld` command handler.
- `metadata.yaml`: plugin identity, display name, description, version, author, and repository URL.
- `README.md`: project introduction and links to AstrBot development documentation.
- `LICENSE`: repository license.

There are currently no test, asset, or packaging directories. Keep small changes in the existing files; introduce focused modules when functionality grows.

## Build, Test, and Development Commands

- `python3 -m py_compile main.py`: check Python syntax without starting AstrBot. This does not validate framework imports or runtime behavior.
- `git diff --check`: detect whitespace errors before committing.

There is no standalone build command, dependency manifest, or local runner. Install or load this repository as a plugin in an AstrBot development instance, enable it, and send `/helloworld` through a connected messaging adapter. Use the documentation linked in `README.md` for host setup.

## Coding Style & Naming Conventions

Use four spaces for Python indentation, `snake_case` for functions and variables, and `PascalCase` for classes. Follow the existing asynchronous AstrBot API patterns: command handlers use `@filter.command(...)` and yield event results. Keep handler docstrings descriptive because AstrBot exposes them as command documentation.

No formatter or linter is configured. Keep changes readable and avoid unrelated formatting churn. When changing plugin identity or releasing a version, review both `@register(...)` in `main.py` and `metadata.yaml`; the template currently contains placeholder values and differing versions.

## Testing Guidelines

No automated testing framework or coverage threshold is configured. Verify changes in AstrBot: confirm the plugin loads, `/helloworld` returns the sender name and message text, and disabling or reloading the plugin produces no lifecycle errors. Inspect host logs for exceptions.

If adding automated tests, place them under `tests/` with names such as `test_hello_command.py`, and document the required dependencies and invocation.

## Commit & Pull Request Guidelines

Git history currently contains only `Initial commit`, so no established commit convention exists. Use short, imperative summaries describing the change, such as `Add greeting command validation`.

Pull requests should explain the behavior change, link relevant issues, and list validation performed. Include example command input and output for messaging changes; attach screenshots when they clarify user-visible behavior. Never commit credentials, tokens, or private message logs.
