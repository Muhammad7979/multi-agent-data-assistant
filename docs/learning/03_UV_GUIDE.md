# 03 — uv, pip, and the dependency workflow

> [!NOTE]
> This document is retained as historical/learning material and describes an earlier project stage. Repository paths, dependency inventories, commands, and expected outputs may be outdated. For current structure, setup, and execution instructions, see the [root README](../../README.md).


## Responsibilities

| Thing | Main responsibility |
| --- | --- |
| Python interpreter | Executes Python code. |
| pip | Installs Python packages into a selected Python environment. |
| `venv` | Python standard-library module that creates virtual environments. |
| `.venv` | This project's actual virtual environment directory. |
| `pyproject.toml` | Declares project metadata, dependency requirements, and build/tool configuration. |
| uv | Coordinates project setup, Python selection, environments, packages, locking, and command execution. |
| `uv.lock` | Records resolved project dependency information for uv. |
| PyPI | Public Python Package Index, from which installers can obtain packages. Private indexes and local packages are also possible. |
| `site-packages` | Environment location containing installed packages/metadata. |
| `import` | Python operation that loads a module so code can use it; it does not install packages. |

Follow the connections: declarations in `pyproject.toml` → resolved choices in `uv.lock` → packages installed in `.venv` → interpreter finds modules when code imports them. Your local application is also a package; it need not be downloaded from PyPI.

## What exactly is uv?

**WHAT?** A separate executable that combines common Python project and package tasks.

**WHY?** It provides one coordinated workflow for selecting Python, declaring requirements, resolving versions, maintaining an environment, and running project commands.

**WITHOUT IT?** Python still works. You can combine tools such as pip and `venv`, with separate conventions for dependency files and locking.

uv does not replace Python. It arranges for Python to execute code. In this workspace the environment records uv `0.12.17`, but no uv command was found in the task's PATH. All uv examples below are for you to understand/use later, not commands executed during documentation.

## uv init: define a project

`uv init` creates starter project files; it does not implement your application. Template flags affect the layout. Current uv documentation describes packaged applications as the default from uv 0.12 onward; older tutorials may show a root `main.py` instead. `--lib` selects a library; `--no-package` omits the packaged layout. [Official project initialization guide](https://docs.astral.sh/uv/concepts/projects/init/).

INFERRED for this project: `.python-version`, root `README.md`, `pyproject.toml`, and `src/data_agent/__init__.py` match the current packaged application template. That match cannot prove each file's author or the exact flags used. The empty root `main.py`, `.env`, and empty folders have unknown provenance. No Git metadata is present even though initialization can set up Git when circumstances/options allow it.

Initialization is separate from installing the project's environment. It does not by itself mean the declared dependencies and command are installed. Do not repeat `uv init` to repair or reproduce an existing project; it normally rejects an existing project definition.

## uv sync: make the environment match

**WHAT?** Synchronizing means making installed project packages match the requirements selected for the environment.

**WHY?** Editing a dependency declaration does not itself put package files on disk.

**WITHOUT IT?** The environment may be missing packages or contain outdated/unrecorded ones.

```text
uv sync
   ↓
read project requirements and Python selection
   ↓
check/use lock information; resolve/update it when needed
   ↓
ensure a suitable local environment is available
   ↓
install the local project and selected dependencies;
remove packages outside the selected requirements
```

This is a conceptual flow, not a guaranteed internal step order. First use may create `.venv`, obtain Python/build requirements, generate a lock, and install the project. Later uses reuse suitable existing state and make needed changes. Sync is exact by default, so manual extra installs can be removed. This project has a build system, so the local package and command are installed, normally editable. `uv sync --locked` requires a current lock but still changes the environment. [Locking and synchronization behavior](https://docs.astral.sh/uv/concepts/projects/sync/).

The three roles stay separate: `pyproject.toml` declares; `uv.lock` records resolution; `.venv` holds installed state. See the [actual lock explanation](01_PROJECT_STRUCTURE.md#the-actual-uvlock).

## Command guide and side effects

Run project commands from `D:\data-agent`. **READ-ONLY / INSPECTION** below means no intended project/environment changes. Tools may still read settings or use caches. A program launched by uv can have its own side effects.

| Command and example | When / what it does | Classification | Project files / .venv effects |
| --- | --- | --- | --- |
| `uv init` | Start a new project. | PROJECT-MODIFYING | Creates metadata/source/version/readme files as applicable; may initialize Git. Not the dependency sync step. |
| `uv sync` | Prepare or align this project's installation. | PROJECT-MODIFYING | May create/update `uv.lock`; creates/changes `.venv`, including removing extras. Normally reads `pyproject.toml`. |
| `uv add requests` | Declare a runtime dependency and install the resulting selection. | PROJECT-MODIFYING | Normally updates `pyproject.toml`, `uv.lock`, and `.venv`. |
| `uv remove requests` | Remove a declared requirement and adjust its installation. | PROJECT-MODIFYING | Normally updates the same three locations; shared dependencies can remain. |
| `uv run data-agent` | Run the actual installed application command. | PROJECT-MODIFYING (potentially) | Can update the lock/environment before execution; program may write other files. |
| `uv lock` | Resolve/save requirements without synchronizing the project environment. | PROJECT-MODIFYING | Creates/updates `uv.lock`; does not install that dependency set into `.venv`. Resolution may need Python/build metadata/cache access. |
| `uv tree` | Display the project dependency tree. | PROJECT-MODIFYING (potentially) | Can update the lock first; does not synchronize `.venv`. |
| `uv tree --frozen --offline` | Inspect the existing lock's dependency tree. | READ-ONLY / INSPECTION | Does not update lock or sync environment; may show stale lock information. |
| `uv python --help` | Discover Python-management subcommands. | READ-ONLY / INSPECTION | No project or `.venv` edits. `uv python` is a command family, not a Python interpreter. |
| `uv python list` | See installed/discoverable versions and available downloads. | READ-ONLY / INSPECTION | Does not install displayed versions or sync `.venv`. Available downloads depend on the uv release. |
| `uv python install 3.14` | Make a suitable Python installation available. | MACHINE-MODIFYING | Installs Python outside the project; may add managed executable entries. Does not itself synchronize `.venv` or declare dependencies. |

`uv tree --frozen --offline` reads the existing lock without updating it. For inspection runs, `uv run --no-sync --offline ...` skips environment synchronization and implies a frozen lock; it does not validate that the environment is current. `--no-python-downloads` prevents automatic Python downloads. `--locked` prevents lock changes but does **not** mean no environment changes. Check local help when uv is available. [uv CLI reference](https://docs.astral.sh/uv/reference/cli/).

## uv add: declaration through installation

Hypothetical — `requests` is **not currently installed or declared**:

```text
uv add requests
       ↓
pyproject.toml: declare requests as a runtime requirement
       ↓
resolution: choose compatible requests + its dependencies
       ↓
uv.lock: record the result
       ↓
.venv: install the required packages
```

uv normally chooses a requirement constraint when you omit one; inspect the result rather than assuming an exact version string. Transitive packages need not become direct declarations. `uv remove requests` removes the direct request and updates the environment; a package still required elsewhere remains. [Managing dependencies](https://docs.astral.sh/uv/concepts/projects/dependencies/).

Mental analogy: `uv add requests ≈ composer require package`. Both express the dependency in configuration and update installed state. They use different package indexes, naming rules, lock formats, and environments.

## uv run: arrange the environment, then execute

In `uv run main.py`, `uv` is the executable your shell finds, and `run` is its subcommand. For a Python file, uv arranges the project's environment and executes the file with Python. Manual activation is unnecessary. Ordinary project runs can first update lock/environment state. [Running commands with uv](https://docs.astral.sh/uv/concepts/projects/run/).

| Invocation | Interpreter / meaning here |
| --- | --- |
| `python main.py` | Uses shell-resolved Python; does not synchronize dependencies. It may be global, activated, or unavailable. |
| `.\.venv\Scripts\python.exe main.py` | Uses the explicit existing project interpreter; no synchronization. |
| `uv run main.py` | Uses uv's project environment workflow; the file is empty, so no program output. |
| `uv run data-agent` | Runs the installed command that calls the greeting function. |

Packages become available through the chosen interpreter's environment and import paths. uv does not inject an `import` statement into your code. Environment overrides or a different working directory can change the context; these explanations assume the inspected root and normal settings. See the full [runtime trace](04_PYTHON_RUNTIME.md).

## pip from zero

**WHAT?** pip is a Python package installer. It can resolve and install packages from PyPI, other indexes, local projects, or package files.

**WHY?** It provides package installation without requiring uv's project workflow. It remains widely used and useful.

**WITHOUT IT?** Another installer, such as uv, can install packages. Python itself does not require pip to execute already available code.

`python -m pip` means “use this Python interpreter to run the pip module.” This connects pip to a specific interpreter more clearly than a bare `pip` command. It still requires pip to be installed there. This `.venv` has no pip distribution in its inspected metadata; that does not prevent uv-managed installation.

### Traditional workflow — alternative example, not for this existing .venv

The following is a **PROJECT-MODIFYING EXAMPLE for a separate practice directory**. Do not run its first command on this project's current environment just to follow the guide.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install requests
```

Python's `venv` creates the environment, activation selects its commands for this shell, and pip installs into it. Standard `venv` normally bootstraps pip unless told otherwise; platform availability can vary. If PowerShell blocks activation, an explicit interpreter path avoids needing activation rather than requiring a policy change. On Linux/macOS, activation commonly uses `source .venv/bin/activate`.

`requirements.txt` is a common file listing pip installation requirements. `python -m pip install -r requirements.txt` installs its contents. Exact pins and hashes can strengthen repeatability; a list of broad version ranges alone does not fix every version. `pip freeze` reports installed distributions, which may include more than your intended direct requirements. No `requirements.txt` exists here, and not every pip project needs one. [pip repeatable installs](https://pip.pypa.io/en/stable/topics/repeatable-installs/).

## uv versus pip

These tools overlap, but have different scope. “pip is obsolete” is the wrong lesson.

| Area | pip | uv |
| --- | --- | --- |
| Package installation | Core job; targets a Python environment. | Supports installation through projects and a pip-style interface. |
| Virtual environments | Usually paired with Python's `venv`. | Can create/manage environments as part of projects or explicitly. |
| Project dependencies | Installs requirements; does not ordinarily maintain your `[project].dependencies` with an add command. | `uv add/remove` maintain declarations, lock, and environment. |
| Locking | Pins/hashes and related tools are common; current pip also has experimental `pip lock`. | Integrated `uv.lock` project workflow. |
| Python management | Does not install/manage interpreter versions. | Can discover/download/select Python. |
| Running project commands | Use the chosen interpreter/CLI separately. | `uv run` coordinates environment and execution. |
| Speed | Depends on downloads, builds, caching, and workload. | Designed for speed; no benchmark was run on this project. |
| Reproducibility | Depends on the workflow's pins, hashes, environment, and tooling. | Lock and sync work together; platform/interpreter/build conditions still matter. |

Current pip's experimental lock command targets the current Python version and platform; it is not interchangeable with `uv.lock`. This was checked against current official documentation, not an installed pip in this environment. [pip lock documentation](https://pip.pypa.io/en/stable/cli/pip_lock/).

A new project might choose uv to reduce the number of separate setup steps and keep declarations, locking, and installation coordinated. pip is perfectly reasonable when a team already has a dependable pip workflow, a platform expects it, or you only need installation in an existing environment.

**GOOD TO KNOW:** `uv pip install` is uv's pip-style interface, not a call to an installed pip. It changes installed state without adding a normal project declaration. Mixing that with `uv add`, or manually using pip in `.venv`, can make installed state differ from the lock. Understand which environment and which files a command owns before mixing workflows.

Continue to [how Python runs this project](04_PYTHON_RUNTIME.md).
