# Python Learning Guides

These guides describe an earlier project stage. Start with the [current project instructions](../../README.md) to run the application. Return to the [documentation index](../README.md) for current references.

The original introduction is preserved below as historical learning material. Machine paths, dependency observations, and execution examples are not current setup instructions.

---

# Understand this Python project

This guide explains the actual starter at `D:\data-agent`, inspected on 20 September 2026. It assumes you understand PHP/Laravel backend development and are learning Python. General programming ideas are familiar; Python's environment, packaging, and execution rules are new.

After reading, you should know which files express your choices, which files tools generate, which interpreter runs the code, and how an installed dependency becomes importable.

## Start here

1. [Project structure](01_PROJECT_STRUCTURE.md): every important item, its ownership, and its lifecycle.
2. [Python environment](02_PYTHON_ENVIRONMENT.md): machine Python versus project Python.
3. [uv guide](03_UV_GUIDE.md): responsibilities, commands, pip, and dependency workflows.
4. [Python runtime](04_PYTHON_RUNTIME.md): how this application's command reaches its code.
5. [Hands-on exercises](05_HANDS_ON_EXERCISES.md): observe first, then optionally change dependencies.
6. [Glossary](GLOSSARY.md): short definitions whenever needed.

```text
01 Project structure
        ↓
02 Python environment
        ↓
03 uv guide
        ↓
04 Python runtime
        ↓
05 Exercises       ←→       Glossary whenever needed
```

## The big picture

```text
uv (a separate executable)
 ├── reads project choices: pyproject.toml + .python-version
 ├── maintains resolved dependency information: uv.lock
 ├── finds a suitable Python installation (can install one if needed)
 └── prepares and uses the project's .venv
                                 │
Python installation ─────────────┤ base interpreter / standard library
                                 ↓
                    .venv/Scripts/python.exe
                                 │
                    .venv/Lib/site-packages
                                 │
                    editable link to src/
                                 ↓
                    src/data_agent/__init__.py
```

Python executes your program. uv organizes the environment in which it runs. The interpreter and installed packages are different pieces; neither `pyproject.toml` nor `uv.lock` contains the packages themselves. See the [responsibilities table](03_UV_GUIDE.md#responsibilities).

**IMPORTANT NOW:** this is a packaged application. Its configured command is `data-agent`. The root `main.py` exists but is empty. The greeting lives in `src/data_agent/__init__.py`.

## Evidence and limits

- **VERIFIED** means confirmed from files or read-only output in this workspace.
- **INFERRED** means the evidence suggests it, but does not prove it.
- **UNKNOWN** means the available evidence cannot establish it.

VERIFIED: project name `data-agent`, project version `0.1.0`, no declared runtime dependencies, no development dependency group, and a local editable installation. The environment runs CPython `3.14.7`; its configuration records uv `0.12.17`. That record does not prove which uv version would run today.

`uv`, `python`, `py`, and `git` were not found through this task's PowerShell command lookup. The explicit `.venv\Scripts\python.exe` path works. Your IDE terminal may have a different PATH. No `.git` entry exists at the project root or its `D:\` parent, and there is no root `.gitignore`. Git tracking/history therefore could not be established.

Official documentation was checked for current tool behavior and is linked beside relevant explanations. Installed uv help could not be checked because no uv executable was located. Examples using uv are documented behavior, not claims that those commands were executed here. Current uv documentation can change; check your own `uv --version` and `uv <command> --help` when available.

**GOOD TO KNOW:** Laravel comparisons here are mental analogies, not exact equivalents. `.venv` is broader than `vendor/`, and Python imports are not Composer autoloading.

**LEARN LATER:** publishing wheels, alternative build backends, and import hooks. Their basic roles are explained where needed; you do not need to master them to run this starter.

## Scope of this documentation task

Only these seven Markdown documents were added under `docs/`. Existing source, configuration, secrets, and environment files were preserved. `.env` values are deliberately not reproduced. No dependency installation, synchronization, initialization, removal, or environment recreation was performed.

Both initial and final Git status attempts failed because Git was unavailable. A separate hash check verified all 37 original files were unchanged. All 32 internal documentation links were checked successfully. The only files created by this task are the seven guides. One additional empty source file, `agents/sql-analyst.py`, appeared concurrently outside these edits; it was left untouched and added to the inventory. These guides describe the observed starter, not future changes made by the exercises.
