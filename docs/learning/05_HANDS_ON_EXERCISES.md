# 05 — Learn through observation

> [!NOTE]
> This document is retained as historical/learning material and describes an earlier project stage. Repository paths, dependency inventories, commands, and expected outputs may be outdated. For current structure, setup, and execution instructions, see the [root README](../../README.md).


Start in `D:\data-agent` using PowerShell. These exercises are instructions for you. No project-modifying exercise was executed during documentation.

The task shell could not locate uv, so begin with the existing interpreter. If a uv example says the command is not recognized, that is a [PATH/tool availability issue](02_PYTHON_ENVIRONMENT.md#path-and-interpreter-confusion), not evidence that your source or dependencies are broken. Once uv is available, inspect `uv --version` and `uv run --help`; this guide's uv options were checked in official documentation, not local help.

## 1. Inspect Python

**SAFE INSPECTION EXERCISE**

```powershell
Get-Location
.\.venv\Scripts\python.exe --version
Get-Content .python-version
```

Expected for the inspected starter: project directory `D:\data-agent`, Python `3.14.7`, and requested series `3.14`. Explain why those last two outputs are compatible.

When uv is available, this variant skips project synchronization and network access:

```powershell
uv run --no-sync --offline --no-python-downloads python -B --version
```

The frequently shown `uv run python --version` is **POTENTIALLY PROJECT-MODIFYING**, because a normal project run can synchronize first. A harmless child command does not make uv's setup phase read-only. `--no-sync` also means you are trusting existing installed state, not checking that it matches configuration. [uv command options](https://docs.astral.sh/uv/reference/cli/).

## 2. Find the running interpreter

**SAFE INSPECTION EXERCISE**

```powershell
.\.venv\Scripts\python.exe -B -c "import sys; print(sys.executable); print(sys.prefix); print(sys.base_prefix)"
```

Expected: an executable under `.venv\Scripts`, a project `.venv` prefix, and a different base prefix under the machine's Python installation. This directly answers “which Python is executing my code?”

With uv available:

```powershell
uv run --no-sync --offline --no-python-downloads python -B -c "import sys; print(sys.executable)"
uv python find --no-python-downloads
```

The first prints the interpreter actually running the child command. The second reports discovery in the current context. Investigate overrides or working directory if they differ; do not assume a global `python` command names either one.

## 3. Inspect declared, locked, and installed packages

**SAFE INSPECTION EXERCISE**

```powershell
Get-Content pyproject.toml
Get-Content uv.lock
.\.venv\Scripts\python.exe -B -c "from importlib.metadata import distributions; print([(d.metadata['Name'], d.version) for d in distributions()])"
```

The three views mean “requested,” “resolved,” and “installed.” Expected now: empty runtime declarations, a lock containing the local project, and installed distribution `data-agent 0.1.0`. `uv_build` is a build requirement rather than an installed runtime dependency.

With uv available:

```powershell
uv tree --frozen --offline
```

Expect a root project with no external runtime dependency branches; formatting can vary. This inspects the existing lock, not actual installed-package metadata. Plain `uv tree` can update a lock; do not use it as a guaranteed read-only substitute.

## 4. Connect installed metadata to your source

**SAFE INSPECTION EXERCISE for the current, inspected starter**

```powershell
Get-Content .venv\Lib\site-packages\data_agent.pth
.\.venv\Scripts\python.exe -B -c "import data_agent; print(data_agent.__file__); print(data_agent.__name__)"
```

Expect the `src` path, then the package's `__init__.py` path and name `data_agent`. There is no greeting because you imported the function but did not call it.

Then compare:

```powershell
.\.venv\Scripts\python.exe -B main.py
.\.venv\Scripts\python.exe -B -c "from data_agent import main; main()"
$LASTEXITCODE
```

Expected: the first command prints nothing; the second prints `Hello from data-agent!`; the successful second process exits with `0`. `-B` prevents bytecode cache writes. These specific current functions only print; importing or running arbitrary future code is not automatically read-only.

## 5. Add a dependency and inspect the effect

**PROJECT-MODIFYING EXERCISE — OPTIONAL, after understanding the previous chapters**

Prerequisite: uv works, and you are willing to change dependencies and install packages. Save/commit intended work first if you have set up Git; inspect changes without sharing `.env` contents. There is no Git repository confirmed in the current starter.

```powershell
uv add requests
```

Now inspect `pyproject.toml`, `uv.lock`, and the installed-distributions command in exercise 3.

Expect:

- `pyproject.toml`: requests added as a direct runtime requirement.
- `uv.lock`: resolved requests and its transitive dependencies recorded. Exact versions depend on the available releases and constraints at exercise time.
- `.venv`: package files and metadata installed. `uv add` may also refresh the local application installation.

Then:

```powershell
.\.venv\Scripts\python.exe -B -c "import requests; print(requests.__file__)"
```

It should now find requests in this environment. No network request is made by this example. Explain why writing only `import requests` earlier would not have installed anything.

## 6. Remove the practice dependency

**PROJECT-MODIFYING EXERCISE**

```powershell
uv remove requests
```

Inspect the same three locations again. The direct requirement disappears, the lock updates, and packages no longer needed are removed from the environment. Shared dependencies remain if another requirement needs them. In this starter, no other runtime dependencies were declared.

Do not assume an add/remove round trip restores every file byte-for-byte: tool versions and resolution can affect generated output. Inspect changes. Removal only works as this exercise intends if requests is still the practice dependency you added.

## Common beginner mistakes

| Mistake | Why it causes confusion / better check |
| --- | --- |
| Installing everything globally | Projects share versions and can conflict; select an intentional project environment. |
| Confusing base Python with project Python | Same language version can have different packages; print `sys.executable`. |
| Committing `.venv` | It contains generated files and machine-specific paths; commit reproducible inputs instead. |
| Editing `uv.lock` by hand | A plausible text change can produce inconsistent resolution data; use uv and review changes. |
| Confusing Python and package versions | Compatibility and dependency constraints control different things; identify which component each number names. |
| Treating import as installation | Import searches existing code; it does not fetch packages. |
| Assuming uv replaces Python | uv prepares/runs; the interpreter executes code. |
| Assuming pip is obsolete | pip is still useful; uv integrates a broader workflow. |
| Not checking the executing interpreter | A successful install may target a different environment from the one running your code. |
| Running from the wrong directory | Relative paths and project discovery can point somewhere else; check `Get-Location`. |
| Mixing pip/venv/uv without checking targets | Manual installs can diverge from declarations and later be removed by sync. |
| Assuming an installed CLI is on PATH | Its executable may be under `.venv\Scripts`, or the package may not provide a CLI. |
| Assuming root `main.py` is the application | Here it is empty; the configured command calls `data_agent:main`. |
| Expecting Laravel-style `.env` loading | This starter does not load it; file presence alone has no effect. |

## Check your understanding

Before changing the project further, explain in your own words:

1. Why does this application have an installed package when `dependencies` is empty?
2. Which file connects the command `data-agent` to `main()`?
3. Why can the project interpreter import from `src`?
4. Which pieces would another developer obtain from Git, and which would they regenerate?
5. Why can `python main.py` and `uv run main.py` differ even though both name the same file?

If an answer is unclear, return to [structure](01_PROJECT_STRUCTURE.md), [environment](02_PYTHON_ENVIRONMENT.md), or [runtime](04_PYTHON_RUNTIME.md). Use the [glossary](GLOSSARY.md) for terminology.
