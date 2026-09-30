# 02 — Machine Python and project Python

> [!NOTE]
> This document is retained as historical/learning material and describes an earlier project stage. Repository paths, dependency inventories, commands, and expected outputs may be outdated. For current structure, setup, and execution instructions, see the [root README](../../README.md).


```text
This Windows computer
│
├── Base Python installation
│   └── ...\AppData\Local\Python\pythoncore-3.14-64
│       └── interpreter support + standard library
│
└── D:\data-agent
    ├── .python-version          requests 3.14
    ├── pyproject.toml           accepts >=3.14
    ├── uv.lock                  resolved project information
    └── .venv
        ├── pyvenv.cfg           refers to the base installation
        ├── Scripts\python.exe  project interpreter entry point
        ├── Scripts\data-agent.exe
        └── Lib\site-packages   packages / installed metadata
```

## Python installation and interpreter

**WHAT?** Python is a language. A Python installation provides an interpreter, the standard library, and supporting files. The interpreter is the executable that runs `.py` code. This environment uses **CPython**, the usual Python implementation.

**WHY?** A `.py` file is text; something must execute it. Think of the interpreter's role as similar to `php.exe` executing a PHP script. uv is a separate tool that can find/use an interpreter; uv does not replace it.

**WITHOUT IT?** You can edit Python source but cannot execute it as Python code.

VERIFIED from the existing interpreter:

| Observation | Value |
| --- | --- |
| Python release | `3.14.7`, 64-bit CPython |
| `sys.executable` | `D:\data-agent\.venv\Scripts\python.exe` |
| `sys.prefix` | `D:\data-agent\.venv` |
| `sys.base_prefix` | `C:\Users\USAMA TRADERS\AppData\Local\Python\pythoncore-3.14-64` |

`sys` is a standard-library module with information about the running interpreter. `prefix` identifies this environment; `base_prefix` identifies the base installation it uses. The directory name does not prove which person/tool installed that base Python.

## Virtual environment and .venv

**WHAT?** A virtual environment gives a project its own installed-package area and interpreter entry point, based on a Python installation.

**WHY?** Two projects may need conflicting versions of the same package. Separate environments let each keep its own selection.

**WITHOUT IT?** You must manage shared packages or provide isolation some other way. Installing one project's dependencies can otherwise interfere with another project's requirements.

`.venv` is a conventional directory name, and uv's default project environment location. The dot is a naming convention; it is not what creates isolation. Python's `venv` module is one tool for creating such environments. uv can create environments itself without requiring you to run `python -m venv` first.

A virtual environment is **not necessarily a complete independent copy of Python**. It uses the base installation and standard library. Depending on the platform/tool, interpreter files can be copies, links, or launchers. On Windows this project's executables are in `Scripts`; on Linux/macOS the corresponding directory is normally `bin`. Moving the folder to another machine is not a reliable way to reproduce it. [Python virtual environment documentation](https://docs.python.org/3.14/library/venv.html).

### What's inside this environment?

All entries below are VERIFIED present. Internal roles are tooling conventions. The environment configuration identifies uv; exact authorship of each support file is not independently known.

| Item | Purpose / consumer | Edit, commit, delete, regenerate? |
| --- | --- | --- |
| `pyvenv.cfg` | Interpreter configuration: base location, CPython version, uv creator version, prompt. `include-system-site-packages = false` excludes the base installation's site-packages by default. | Do not hand-edit as routine setup. Do not commit. Removing it can break environment recognition; recreate the environment when needed. |
| `Scripts/python.exe`, `pythonw.exe` | Python entry points for this environment; `pythonw` is the Windows variant without a console window. | Generated; no manual edits or Git. Deletion breaks corresponding execution; environment recreation restores them. |
| `Scripts/data-agent.exe` | Installed console-command launcher for this project. | Generated from project metadata; no manual edits or Git. If lost, reinstalling/syncing the project can restore it. |
| Activation files, `deactivate.bat`, `pydoc.bat` | Shell helpers and a Python documentation helper. Different activation files target different shells. | Generated; no manual edits or Git. Deletion loses those helpers, not source. Recreate environment to restore. |
| `Lib/site-packages/` | Installed packages and metadata used by Python and packaging tools. | Do not manually maintain; no Git. Deletion breaks installations. Restore through the dependency workflow. |
| `data_agent.pth` | Contains `D:\data-agent\src`; makes source discoverable in this editable installation. | Generated; no manual edits or Git. Deletion can break imports. Reinstalling the local package restores it. |
| `data_agent-0.1.0.dist-info/` | Installed project metadata, including entry point and editable source location. Used by package tools and metadata APIs. | Generated; no manual edits or Git. Removing it can leave tools unable to recognize the install. Restore by reinstalling. |
| `_virtualenv.py`, `_virtualenv.pth` | Environment support code/configuration loaded during interpreter startup. | Generated infrastructure; leave alone, do not commit. Restore with the environment if damaged. |
| `__pycache__/` | Cached Python bytecode; the observed file is `_virtualenv.cpython-314.pyc`. | Generated by Python; no manual edits or Git. Disposable cache, normally recreated when code runs. |
| `.gitignore` | Contains `*` to ignore files within this environment. | Tool-created ignore convention; no routine edits or commit. Without it, protection from this file disappears. A recreated environment may supply it again. |
| `.lock` | Tool coordination file, inferred to support environment locking. | Leave tool-managed; do not edit/commit or remove while tools run. Exact recovery behavior was not inspected. |
| `CACHEDIR.TAG` | Marks disposable/cache-like contents for tools that recognize the tag. | Generated marker, no edits/Git. Losing it affects such tools, not source; recreation can restore it. |

Deleting the whole environment removes installed artifacts, not your `src/` code or dependency declarations. A later `uv sync` can rebuild it. That is a modifying operation, not an exercise performed here. Keep source/configuration in Git; rebuild generated local state. See [item lifecycle decisions](01_PROJECT_STRUCTURE.md#what-to-own-and-what-to-regenerate).

Mental analogy: packages installed under `site-packages` can feel like libraries under Composer's `vendor/`. But `.venv` also selects an isolated interpreter environment and contains executables and activation support. **`.venv` is not simply Python's name for `vendor/`.**

## site-packages and isolation

`site-packages` is the usual directory for installed third-party Python packages and metadata in an environment. At startup, Python normally includes the environment's relevant locations in its import search path. [How imports use those locations](04_PYTHON_RUNTIME.md#imports-and-installation).

```text
Base Python interpreter          Project .venv interpreter
        ↓                                ↓
its installed packages           its installed packages
```

`pip install something` targets an environment determined by which pip you invoked. Success there does not mean the project's interpreter can import the package. In this environment, base system site-packages are excluded. Isolation is about package selection, not a security sandbox; it does not prevent code from accessing files or the network.

VERIFIED: installed distribution metadata lists only `data-agent 0.1.0`. Its editable installation points to `src`, so changing your source later is normally visible without copying it into site-packages. The standard library still exists through Python's base installation; an almost empty site-packages directory does not mean Python has no built-in capabilities.

## .python-version selects; it does not install

The file contains:

```text
3.14
```

**WHAT?** A version request used by uv and some other Python version-selection tools, such as pyenv.

**WHY?** It communicates the preferred local Python series.

**WITHOUT IT?** Tool discovery and the project's compatibility requirement guide selection instead.

Writing `3.14` does not download or install anything. A tool must read the request and find a matching interpreter. uv can download a suitable interpreter when needed and allowed, or fail if none is available and downloads are disabled. This file requests the 3.14 series, not exactly patch release 3.14.7. [uv Python version selection](https://docs.astral.sh/uv/concepts/python-versions/).

| Setting | Meaning in this project |
| --- | --- |
| `.python-version`: `3.14` | Preferred local interpreter series. |
| `requires-python`: `>=3.14` | Project's declared interpreter compatibility range. |
| Observed interpreter: `3.14.7` | What the existing environment actually runs. |
| Project `version`: `0.1.0` | Your application's version. |
| Build requirement: `uv_build>=0.12.17,<0.13.0` | Allowed versions of a separate build package. |

**IMPORTANT NOW: Python version ≠ dependency/package version.** Changing a package constraint does not change the Python language version.

## PATH and interpreter confusion

**PATH** is a list of directories your shell searches for executable commands. It is not the list of Python import locations. PowerShell is the shell here; the terminal is the window hosting it.

From the project root, these are inspection commands:

```powershell
Get-Location
Get-Command python, uv -ErrorAction SilentlyContinue
where.exe python
python --version
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -B -c "import sys; print(sys.executable)"
```

`where.exe python` is the Windows executable lookup command. In PowerShell, bare `where` can mean `Where-Object`, so use `where.exe`. `python --version` reports the version of whichever `python` the shell resolves, or fails if it cannot find one. The explicit path avoids that ambiguity. `-c` executes the following Python text; `-B` prevents writing bytecode caches.

On Linux/macOS the corresponding checks are commonly `which python` (or `command -v python`) and `python --version`; some installations expose only `python3`. Their project interpreter path is usually `.venv/bin/python`.

When uv is available, this documents interpreter discovery without installation:

```powershell
uv python find --no-python-downloads
```

It finds a Python candidate in the current context; overrides can change that choice. To see the interpreter in an actual project run while skipping synchronization, see the [safe exercises](05_HANDS_ON_EXERCISES.md#2-find-the-running-interpreter). uv was unavailable in this task shell, so its selection command could not be executed locally.

Activation temporarily prepends the environment's executable directory to the shell's PATH. It makes typing `python` or `data-agent` convenient; it does not install dependencies. Explicit interpreter paths and `uv run` do not require manual activation.

An installed CLI may live in `.venv\Scripts`, while that directory is absent from your current PATH. So “package installed successfully” does not guarantee its command can be found. Also, many packages provide no CLI at all. Check the executable location separately from package installation.

## Environment variables and .env

“Environment” can mean either the Python environment discussed above or a process's environment variables. These are related through the running process but are different concepts.

Unlike Laravel's usual startup, this starter has no automatic `.env` loading. Python does not load the file simply because it exists. The current source never reads it. Future code or a command such as uv's explicit `--env-file` option can load values; that is a deliberate choice. Existing values were not printed, copied, or tested.

Continue to [uv and pip](03_UV_GUIDE.md).
