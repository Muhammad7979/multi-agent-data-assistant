# Glossary

> [!NOTE]
> This document is retained as historical/learning material and describes an earlier project stage. Repository paths, dependency inventories, commands, and expected outputs may be outdated. For current structure, setup, and execution instructions, see the [root README](../../README.md).


Definitions are short on purpose. Follow the topic links for the detailed explanation.

## Python and execution

Detailed guide: [Python runtime](04_PYTHON_RUNTIME.md).

| Term | Meaning |
| --- | --- |
| Python | A programming language; often also shorthand for its interpreter/installation. |
| CPython | The Python implementation used by this environment. |
| Interpreter | Program that executes Python code. |
| Runtime | The machinery/state involved while a program executes, including its interpreter. |
| Process | One running instance of a program. |
| Source code | Human-readable program instructions. |
| Module | Importable unit of Python code, often a `.py` file. |
| Package | In imports, a module containing submodules; in installation discussions, often shorthand for a distribution. |
| Distribution | An installable Python project, potentially providing modules and commands. |
| Library | Reusable code used by another program. |
| Import | Load a module and make its contents accessible to code. |
| `__init__.py` | File used to initialize a regular Python package when imported. |
| `__name__` | Module variable identifying its import name or `__main__` during direct script execution. |
| `__main__` | Name Python gives the top-level execution module; also the filename convention for a package runnable with `-m`. |
| Top-level statement | Statement outside function/class bodies; runs when the module executes. |
| Type annotation | Information describing intended types, not automatic runtime type enforcement. |
| `None` | Python object representing absence of a meaningful value. |
| Entry point | Configured place execution begins; here the command targets `data_agent:main`. |
| Console script | Installed command that calls a Python function. |
| Exit code | Numeric completion status; `0` normally indicates success. |

## Environments and command lookup

Detailed guide: [Python environment](02_PYTHON_ENVIRONMENT.md).

| Term | Meaning |
| --- | --- |
| Python installation | Interpreter, standard library, and supporting files on a machine. |
| Standard library | Modules shipped with Python, such as `sys`. |
| Virtual environment | Project-specific package environment based on a Python installation. |
| `.venv` | Conventional directory for the project's virtual environment. |
| `venv` | Standard-library module that creates virtual environments. |
| Environment | Context used by a program; distinguish Python package environments from process environment variables. |
| Environment variable | Named value available to a process, such as PATH. |
| `.env` | Conventional text file holding variable-style settings; requires something to load it. |
| `.python-version` | Tool-readable request for a Python version. |
| Activation | Temporary shell changes that prioritize environment commands. |
| `site-packages` | Usual installed-package/metadata location in a Python environment. |
| `sys.path` | Running Python's list of module search locations. |
| PATH | Shell/OS search directories for executable commands, not Python modules. |
| Executable | File the operating system can run as a program. |
| Shell | Program that interprets commands and launches programs. |
| Terminal | Application/window used to interact with a shell. |
| PowerShell | The command shell used during this Windows inspection. |
| Bytecode | Intermediate instructions used by CPython, often cached in `.pyc` files. |
| `__pycache__` | Directory for generated Python bytecode caches. |
| `.pth` file | Site configuration file that can add import locations or run startup support. |
| Editable installation | Installation linked to working source, allowing ordinary source edits to take effect without copying it again. |

## Packages and project tooling

Detailed guides: [uv and pip](03_UV_GUIDE.md), [actual configuration and lock](01_PROJECT_STRUCTURE.md).

| Term | Meaning |
| --- | --- |
| Dependency | Code/package a project needs. |
| Direct dependency | Requirement explicitly declared by your project. |
| Transitive dependency | Requirement brought in through another dependency. |
| Runtime dependency | Package needed by the application's normal execution. |
| Development dependency | Tool needed for development tasks such as tests or linting. |
| Dependency group | Named collection of requirements, often development tools. |
| Build dependency | Package needed to build/install a project. |
| Dependency resolution | Choosing versions that satisfy the relevant requirements together. |
| Version constraint | Rule allowing certain versions, such as `>=3.14`. |
| pip | Python package installer. |
| uv | Integrated Python project, interpreter, environment, and package workflow tool. |
| PyPI | Public Python Package Index. |
| Package index | Service listing/distributing installable packages. |
| TOML | Structured text configuration format used by `pyproject.toml`. |
| `pyproject.toml` | Project metadata, dependencies, and build/tool settings. |
| Lock file | Generated record of resolved dependency selections. |
| `uv.lock` | uv's project lock file. |
| Synchronization | Adjusting installed packages to match selected project requirements. |
| Build backend | Tool implementing how source becomes an installable distribution. |
| `uv_build` | This project's selected build backend; distinct from the uv CLI executable. |
| Wheel | Common built Python package archive used for installation. |
| Configuration | Data telling tools/programs how they should behave. |
| Generated file | File produced by a tool rather than maintained as primary source. |
| Reproducibility | Ability to recreate a controlled environment from recorded inputs, subject to platform and availability limits. |

## Git and evidence

Detailed context: [project inventory](01_PROJECT_STRUCTURE.md#what-to-own-and-what-to-regenerate), [evidence rules](README.md#evidence-and-limits).

| Term | Meaning |
| --- | --- |
| Git | Version-control tool recording changes to tracked files. |
| Repository | Source tree with version-control metadata/history. |
| `.git` | Git repository metadata location; absent in the inspected root. |
| `.gitignore` | Patterns controlling which untracked paths Git ignores. |
| Commit | Recorded snapshot of tracked changes in Git history. |
| VERIFIED | Confirmed by observed project files or read-only output. |
| INFERRED | Suggested by evidence but not directly proven. |
| UNKNOWN | Not safely established from available evidence. |

Return to [the reading guide](../README.md).
