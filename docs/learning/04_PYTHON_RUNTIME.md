# 04 — How this project runs

> [!NOTE]
> This document is retained as historical/learning material and describes an earlier project stage. Repository paths, dependency inventories, commands, and expected outputs may be outdated. For current structure, setup, and execution instructions, see the [root README](../../README.md).


## Follow uv run main.py

```text
Terminal hosting PowerShell
   ↓
shell finds the uv executable
   ↓
uv run selects project / Python environment
   ↓
ordinary run may update lock and synchronize .venv
   ↓
project Python interpreter executes main.py
   ↓
top-level statements run in order
   └── imports happen here when encountered (none in this file)
   ↓
no program output: this main.py is empty
   ↓
process exits successfully
```

Imports are executable statements, not an automatic separate phase before every program. Startup can also load Python support modules. The diagram describes your script's execution, not every interpreter startup detail.

VERIFIED: invoking `.\.venv\Scripts\python.exe -B main.py` returned exit code `0` and no output. `uv run main.py` was not executed because uv was unavailable and ordinary runs can synchronize. If that uv command succeeds in preparing the environment, the empty script likewise has nothing to print. uv's own setup/status messages are separate from program output.

### Words used in that trace

| Word | Meaning here |
| --- | --- |
| Terminal | The window/application where you interact with command-line programs. |
| Shell | PowerShell, which reads command text and launches programs. |
| Command | An instruction such as `uv run data-agent`, including arguments. |
| Executable | A runnable program file, such as `python.exe` or `data-agent.exe`. |
| Process | A running program instance, with its own memory and environment variables. |
| Interpreter | Python's executable and runtime machinery executing your source. |
| Source file | Human-written program text, conventionally ending in `.py`. |
| Exit code | Numeric completion status returned to the caller; `0` normally means success. PowerShell exposes the last native program's status through `$LASTEXITCODE`. |

The virtual [environment](02_PYTHON_ENVIRONMENT.md) selects available packages; it is not itself a running process. Starting the command creates running program activity; keeping `.venv` on disk does not keep an application running.

## Follow the actual application command

```text
uv run data-agent
   ↓
uv prepares/selects this project's environment
   ↓
.venv\Scripts\data-agent.exe
   ↓
Python imports data_agent
   ↓
editable installation makes src\data_agent\__init__.py discoverable
   ↓
top-level def statement defines main
   ↓
launcher calls data_agent.main()
   ↓
print("Hello from data-agent!")
   ↓
function returns None; command completes successfully
```

The configured entry point and generated launcher metadata both say `data_agent:main`. The installed `.pth` file points to `D:\data-agent\src`. Those connections were verified; the greeting function was executed with the existing Python interpreter and `-B` to suppress cache writes. The launcher itself was not executed.

No HTTP server starts. There is no Laravel application lifecycle here: no route dispatch, request handler, database connection, or long-running service. This starter prints one line and finishes.

**IMPORTANT NOW:** a function named `main` is an ordinary Python function. It runs here because the installed command calls it. Running `src/data_agent/__init__.py` directly would only define the function. `python -m data_agent` would require a package `__main__.py`, which this project does not have.

## Direct execution versus importing

The following is a **hypothetical teaching example, not this project's source**:

```python
def main() -> None:
    print("Example output")

if __name__ == "__main__":
    main()
```

Python supplies the module variable `__name__`. Directly executing this hypothetical file sets it to `"__main__"`, so the condition calls the function. Importing it under a module name gives it that name, so the condition does not call the function. This lets a file serve as both reusable code and a runnable script. [Python modules tutorial](https://docs.python.org/3.14/tutorial/modules.html).

There is no such guard in the actual package file, and none is required for its configured console command. In the verified import, `data_agent.__name__` is `"data_agent"`.

Python does not use a `$` prefix for variables. Assignment binds a name to an object. The special-looking double underscores in `__name__` identify a Python-defined convention; they do not indicate an environment variable.

## Imports and installation

**WHAT?** An import loads a module and makes it available to your code.

**WHY?** It lets a program use code from another file, Python's standard library, or an installed dependency.

**WITHOUT IT?** Installing a package does not automatically give your module names for its functions/classes. Your code must import what it uses.

Hypothetical example — `requests` is not a current dependency:

```python
import requests
```

```text
running Python interpreter encounters import requests
       ↓
check whether the module is already loaded
       ↓ if needed
search using the import system and sys.path
       ↓
find an importable requests package
       ↓ commonly
this interpreter's site-packages
       ↓
load its module code and bind the name requests
```

**`sys.path`** is Python's list of search locations for modules. It normally includes a script/current-directory-related location, standard-library locations, and this interpreter's site-packages. Environment setup and `.pth` files can add paths. Here an editable-install `.pth` adds `src`; that is why the environment can import `data_agent` even though it is nested below the root.

The exact search machinery also handles built-in modules and caches. **LEARN LATER:** import finders and loaders. For now, know that the selected interpreter and its search locations determine what it can import.

| Term | Useful distinction |
| --- | --- |
| Module | An importable unit of code, often one `.py` file. |
| Package (import sense) | A module that can contain submodules. This project's regular package uses `__init__.py`. |
| Distribution (installation sense) | A project installed by a package manager; it can provide one or more import packages and CLI commands. |
| Library | A broad term for reusable code; it need not correspond to exactly one file or distribution. |

Installing obtains/registers code in an environment. Importing finds and loads code at runtime. `import requests` does not download requests. If no matching module is available, Python normally raises `ModuleNotFoundError`.

Distribution names and import names can differ. Our distribution is `data-agent`, but code says `import data_agent`. Do not assume every name used with `uv add` can be copied unchanged into an import.

Unlike a typical PHP `require`, importing a Python module normally executes its top-level code once per interpreter process, then reuses the loaded module for later imports. This is also not Composer class autoloading: Python explicitly loads module objects. Top-level side effects happen during that first load, so placing application startup inside functions keeps importing predictable.

## Reproduce this project

This is a **future workflow**, not a claim that this folder is already a Git repository or has a remote:

```text
developer publishes intended source/configuration to Git
    ↓
another developer clones it and enters the project directory
    ↓
source + pyproject.toml + uv.lock + .python-version
    ↓
uv and a suitable Python are available (or uv obtains Python)
    ↓
uv sync --locked
    ↓
new local .venv + editable project installation + dependencies
    ↓
uv run data-agent
    ↓
Hello from data-agent!
```

Commands for that developer, after cloning and installing/locating uv:

```powershell
uv sync --locked
uv run data-agent
```

These are **PROJECT-MODIFYING** environment setup/execution commands. `--locked` fails rather than silently changing an out-of-date lock; it still creates/changes the environment. Plain `uv sync` is also a normal setup command but may update lock information.

Share source and declared/resolved requirements, not `.venv`. The new machine needs its own executable paths and compatible installation. This project's editable link contains an absolute local path, another reason not to copy the environment.

`.python-version` requests a series rather than an exact patch, and the lock does not pin every external build tool or operating-system component. Reproducibility means a controlled dependency selection, not a promise of identical machine state. Local `.env` values must be supplied separately if later code requires them. Empty directories will not arrive through ordinary Git unless they gain tracked contents.

Continue to [exercises](05_HANDS_ON_EXERCISES.md).
