"""Validation of a Python environment picked for external execution, the
counterpart of the desktop's ``PythonEnvironmentCheck``.

A node runs externally through the library's ``ExternalNodeExecutor``,
which spawns ``<env>/bin/tomviz-pipeline`` (``Scripts\\tomviz-pipeline.exe``
on Windows). ``check_environment`` tells, before anything runs, whether a
path is such an environment, in order:

1. is it a Python environment (an interpreter where one lives)? The root,
   its ``bin/`` (``Scripts\\``) or the interpreter itself are accepted and
   normalized to the root (``resolve_environment_root``);
2. is the tomviz-pipeline CLI installed in it?
3. does ``tomviz-pipeline --version`` run, with the scrubbed environment
   the executor uses, and is the version in ``[required, next major)``?
   ``required`` is the app's own ``tomviz-pipeline>=`` pin.

The verdict is advisory: its ``message`` says what is wrong and how to fix
it. ``check_environment`` blocks (up to ``timeout`` seconds for the CLI), so
the UI runs it on a worker thread."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from importlib import metadata
from pathlib import Path

import tomviz_pipeline
from tomviz_pipeline import ExternalNodeExecutor

# Seconds to wait for ``tomviz-pipeline --version`` (a cold conda env can
# take a while to import its packages).
DEFAULT_TIMEOUT = 60

DISTRIBUTION = "tomviz-web"
WINDOWS = os.name == "nt"
BIN_DIR = "Scripts" if WINDOWS else "bin"
INTERPRETER_HINT = "python.exe or Scripts\\python.exe" if WINDOWS else "bin/python"

VERSION = re.compile(r"^\s*v?(\d+)\.(\d+)(?:\.(\d+))?")
# click prints "tomviz-pipeline, version 3.2.0".
CLI_VERSION = re.compile(r"version\s+(\S+)")
BARE_VERSION = re.compile(r"(\d+\.\d+(?:\.\d+)?\S*)")
PIN = re.compile(r"^tomviz[-_.]pipeline\s*.*>=\s*([0-9][0-9.]*)", re.IGNORECASE)


class EnvironmentStatus(str, Enum):
    NO_PATH = "no_path"  # nothing to check
    NOT_AN_ENVIRONMENT = "not_an_environment"  # no interpreter found
    CLI_MISSING = "cli_missing"  # no tomviz-pipeline in it
    CLI_BROKEN = "cli_broken"  # it does not run, or says nothing usable
    VERSION_TOO_OLD = "version_too_old"
    VERSION_TOO_NEW = "version_too_new"  # a newer major than the app's
    OK = "ok"


@dataclass(frozen=True)
class EnvironmentInfo:
    """Outcome of ``check_environment``. ``env_path`` is the environment
    root the check settled on, set whenever the path led to one (also when
    its tomviz-pipeline is missing or incompatible)."""

    status: EnvironmentStatus = EnvironmentStatus.NO_PATH
    env_path: str = ""
    cli_path: str = ""
    version: str = ""
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status == EnvironmentStatus.OK


# -----------------------------------------------------------------------------
# Version rule
# -----------------------------------------------------------------------------


def required_version() -> str:
    """The tomviz-pipeline version the app depends on: the ``>=`` bound
    of its requirement, else the version running in the app."""
    try:
        requirements = metadata.requires(DISTRIBUTION) or []
    except metadata.PackageNotFoundError:
        requirements = []
    for requirement in requirements:
        match = PIN.match(requirement)
        if match and ";" not in requirement:
            return match.group(1).rstrip(".")
    return tomviz_pipeline.__version__


def parse_version(text: str) -> tuple[int, int, int] | None:
    """The leading ``major.minor[.patch]`` of ``text`` (suffixes are
    ignored), or None."""
    match = VERSION.match(text or "")
    if match is None:
        return None
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch or 0)


def requirement_spec(required: str) -> str:
    """The pip specifier of the versions compatible with ``required``."""
    version = parse_version(required)
    if version is None:
        return f"tomviz-pipeline>={required}"
    return f"tomviz-pipeline>={required},<{version[0] + 1}"


def is_compatible_version(found: str, required: str) -> bool:
    """Whether ``found`` is ``required`` or newer within the same major:
    minor releases keep the CLI contract. An unparsable ``required``
    disables the check."""
    minimum = parse_version(required)
    if minimum is None:
        return True
    version = parse_version(found)
    return version is not None and version[0] == minimum[0] and version >= minimum


# -----------------------------------------------------------------------------
# Filesystem lookups
# -----------------------------------------------------------------------------


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _has_interpreter(root: Path) -> bool:
    """Whether ``root`` holds a Python interpreter where an environment
    keeps it (conda: ``<env>\\python.exe``, venv: ``<env>\\Scripts``)."""
    if WINDOWS:
        names = ("python.exe", "Scripts/python.exe")
    else:
        names = ("bin/python", "bin/python3")
    return any(_is_executable(root / name) for name in names)


def _looks_like_interpreter(name: str) -> bool:
    name = name.lower()
    if WINDOWS:
        return name in ("python.exe", "pythonw.exe")
    # python, python3, python3.12, ...
    return name == "python" or (
        name.startswith("python") and "-" not in name and len(name) <= 12
    )


def resolve_environment_root(path: str | os.PathLike) -> str:
    """The root of the environment ``path`` points at: the root itself,
    its ``bin/`` (``Scripts\\``) or the interpreter inside it. Empty when
    no interpreter is found."""
    text = str(path).strip()
    if not text:
        return ""
    candidate = Path(text).expanduser().absolute()
    if candidate.is_file():
        if not _looks_like_interpreter(candidate.name):
            return ""
        candidate = candidate.parent
    elif not candidate.is_dir():
        return ""

    # <env>/bin first: a venv's Scripts\ holds python.exe itself and would
    # otherwise pass as a root of its own.
    if candidate.name == BIN_DIR and _has_interpreter(candidate.parent):
        return os.path.normpath(candidate.parent)
    if _has_interpreter(candidate):
        return os.path.normpath(candidate)
    return ""


def find_cli_executable(root: str) -> str:
    """The tomviz-pipeline CLI the executor would run in ``root``, or
    empty."""
    return ExternalNodeExecutor(root).find_cli_executable() or ""


def child_environment() -> dict:
    """The environment ``ExternalNodeExecutor`` spawns the CLI with: the
    app's own Python configuration scrubbed."""
    env = dict(os.environ)
    for key in ("TOMVIZ_APPLICATION", "PYTHONHOME", "PYTHONPATH"):
        env.pop(key, None)
    env["PYTHONUNBUFFERED"] = "ON"
    return env


# -----------------------------------------------------------------------------
# Messages
# -----------------------------------------------------------------------------


def _conda_managed(root: str) -> bool:
    """Whether conda installed tomviz-pipeline into ``root`` (pip leaves no
    record in ``conda-meta``): conda's next update would undo a pip fix."""
    meta = Path(root) / "conda-meta"
    return meta.is_dir() and any(meta.glob("tomviz-pipeline-*.json"))


def _install_command(root: str, spec: str, upgrade: bool) -> str:
    if _conda_managed(root):
        return f'conda install -c conda-forge "{spec}"'
    return f'pip install {"-U " if upgrade else ""}"{spec}"'


def _with_fix(problem: str, command: str) -> str:
    return f"{problem}\n\nTo fix: activate the environment, then run:\n{command}"


def _last_line(text: str, max_chars: int = 240) -> str:
    lines = [line.strip() for line in (text or "").strip().splitlines() if line]
    if not lines:
        return ""
    line = lines[-1]
    return line if len(line) <= max_chars else line[:max_chars] + "..."


# -----------------------------------------------------------------------------
# Check
# -----------------------------------------------------------------------------


def check_environment(
    path: str | os.PathLike,
    timeout: float = DEFAULT_TIMEOUT,
    required: str | None = None,
) -> EnvironmentInfo:
    """Validate ``path`` for external execution (see the module docstring).
    Blocks while ``tomviz-pipeline --version`` runs."""
    if not str(path).strip():
        return EnvironmentInfo()
    required = required or required_version()
    spec = requirement_spec(required)

    root = resolve_environment_root(path)
    if not root:
        return EnvironmentInfo(
            EnvironmentStatus.NOT_AN_ENVIRONMENT,
            message=(
                "The selected path is not a Python environment: "
                f"no {INTERPRETER_HINT} found inside it."
            ),
        )

    cli = find_cli_executable(root)
    if not cli:
        return EnvironmentInfo(
            EnvironmentStatus.CLI_MISSING,
            env_path=root,
            message=_with_fix(
                "tomviz-pipeline is not installed in this environment.",
                _install_command(root, spec, upgrade=False),
            ),
        )

    def verdict(status, message, version=""):
        return EnvironmentInfo(status, root, cli, version, message)

    # The package is there but does not work: the child's own error is the
    # best clue, and a plain install fills in missing requirements.
    broken_fix = (
        "Check the error above. If a dependency is missing, activate the "
        "environment, then run:\n" + _install_command(root, spec, upgrade=False)
    )
    try:
        run = subprocess.run(
            [cli, "--version"],
            env=child_environment(),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return verdict(
            EnvironmentStatus.CLI_BROKEN,
            f"tomviz-pipeline did not respond within {timeout:g} s in this "
            "environment.",
        )
    except OSError as error:
        return verdict(
            EnvironmentStatus.CLI_BROKEN,
            f"tomviz-pipeline could not be started in this environment "
            f"({error.strerror or error}).\n\nThe environment may have been "
            "moved or deleted. Recreate it, or select a different one.",
        )

    if run.returncode != 0:
        # tomviz-pipeline < 3.1 has no --version at all: click rejects the
        # flag with exit code 2. The environment predates the app.
        if (
            run.returncode == 2
            and "--version" in run.stderr
            and "such option" in run.stderr.lower()
        ):
            return verdict(
                EnvironmentStatus.VERSION_TOO_OLD,
                _with_fix(
                    "tomviz-pipeline in this environment predates "
                    f"{required} and is too old.",
                    _install_command(root, spec, upgrade=True),
                ),
            )
        detail = _last_line(run.stderr)
        return verdict(
            EnvironmentStatus.CLI_BROKEN,
            "tomviz-pipeline is installed in this environment but failed to "
            f"run (exit code {run.returncode})"
            + (f":\n{detail}" if detail else "")
            + f"\n\n{broken_fix}",
        )

    match = CLI_VERSION.search(run.stdout) or BARE_VERSION.search(run.stdout)
    if match is None:
        return verdict(
            EnvironmentStatus.CLI_BROKEN,
            "tomviz-pipeline is installed in this environment but reported "
            f"no version (output: '{_last_line(run.stdout)}').\n\n{broken_fix}",
        )
    version = match.group(1)
    found = parse_version(version)
    if found is None:
        return verdict(
            EnvironmentStatus.CLI_BROKEN,
            "tomviz-pipeline in this environment reported an unrecognized "
            f"version '{version}'.\n\n{broken_fix}",
            version,
        )

    if is_compatible_version(version, required):
        return verdict(
            EnvironmentStatus.OK,
            f"This environment is compatible: tomviz-pipeline {version}",
            version,
        )
    # Incompatible, so ``required`` parsed.
    if found < parse_version(required):
        return verdict(
            EnvironmentStatus.VERSION_TOO_OLD,
            _with_fix(
                f"tomviz-pipeline {version} is installed in this environment, "
                "but is too old.",
                _install_command(root, spec, upgrade=True),
            ),
            version,
        )
    return verdict(
        EnvironmentStatus.VERSION_TOO_NEW,
        _with_fix(
            f"tomviz-pipeline {version} is installed in this environment, "
            "but is newer than supported.",
            _install_command(root, spec, upgrade=False),
        ),
        version,
    )
