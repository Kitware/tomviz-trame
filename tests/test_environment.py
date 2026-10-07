"""The external-execution environment check: version rule, root
resolution, and the verdicts of ``check_environment`` against fake
environments whose ``tomviz-pipeline`` is a shell script (POSIX only), plus
the environment the tests run in, which is a real one."""

import os
import stat
import sys

import pytest

from tomviz_web.app.pipeline.environment import (
    EnvironmentStatus,
    check_environment,
    is_compatible_version,
    parse_version,
    required_version,
    requirement_spec,
    resolve_environment_root,
)

posix_only = pytest.mark.skipif(os.name == "nt", reason="fake envs use sh scripts")


def executable(path, text="#!/bin/sh\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def fake_env(root, cli=None):
    """An environment with an interpreter and, given its body, a
    tomviz-pipeline script."""
    executable(root / "bin" / "python")
    if cli is not None:
        executable(root / "bin" / "tomviz-pipeline", f"#!/bin/sh\n{cli}\n")
    return root


def test_version_rule():
    assert parse_version("3.2.0") == (3, 2, 0)
    assert parse_version("v3.2") == (3, 2, 0)
    assert parse_version("3.2.1.dev4+g123") == (3, 2, 1)
    assert parse_version("three") is None

    assert is_compatible_version("3.2.0", "3.2.0")
    assert is_compatible_version("3.4.1", "3.2.0")
    assert not is_compatible_version("3.1.9", "3.2.0")
    assert not is_compatible_version("4.0.0", "3.2.0")
    assert not is_compatible_version("garbage", "3.2.0")
    assert is_compatible_version("anything", "unparsable")

    assert requirement_spec("3.2.0") == "tomviz-pipeline>=3.2.0,<4"


def test_required_version_is_the_app_pin():
    import tomviz_pipeline

    required = parse_version(required_version())
    assert required is not None
    assert required <= parse_version(tomviz_pipeline.__version__)


@posix_only
def test_root_resolution(tmp_path):
    root = fake_env(tmp_path / "env")
    expected = str(root)
    assert resolve_environment_root(root) == expected
    assert resolve_environment_root(root / "bin") == expected
    assert resolve_environment_root(root / "bin" / "python") == expected
    assert resolve_environment_root(f"  {root}  ") == expected

    other = executable(root / "bin" / "pip")
    assert resolve_environment_root(other) == ""
    assert resolve_environment_root(tmp_path) == ""
    assert resolve_environment_root(tmp_path / "missing") == ""
    assert resolve_environment_root("") == ""


@posix_only
def test_verdicts(tmp_path, monkeypatch):
    def check(name, cli=None, **kwargs):
        root = fake_env(tmp_path / name, cli)
        return check_environment(root / "bin", required="3.2.0", **kwargs)

    assert check_environment("").status == EnvironmentStatus.NO_PATH

    info = check_environment(tmp_path, required="3.2.0")
    assert info.status == EnvironmentStatus.NOT_AN_ENVIRONMENT
    assert "not a Python environment" in info.message

    info = check("bare")
    assert info.status == EnvironmentStatus.CLI_MISSING
    assert info.env_path == str(tmp_path / "bare")
    assert 'pip install "tomviz-pipeline>=3.2.0,<4"' in info.message

    # conda installed it: the fix goes through conda
    meta = tmp_path / "conda" / "conda-meta"
    meta.mkdir(parents=True)
    (meta / "tomviz-pipeline-3.1.0-py_0.json").write_text("{}")
    info = check("conda", "echo 'tomviz-pipeline, version 3.1.0'")
    assert info.status == EnvironmentStatus.VERSION_TOO_OLD
    assert info.version == "3.1.0"
    assert 'conda install -c conda-forge "tomviz-pipeline>=3.2.0,<4"' in info.message

    info = check("old", "echo 'tomviz-pipeline, version 3.1.0'")
    assert info.status == EnvironmentStatus.VERSION_TOO_OLD
    assert 'pip install -U "tomviz-pipeline>=3.2.0,<4"' in info.message

    # tomviz-pipeline < 3.1 has no --version at all
    info = check("older", "echo 'Error: No such option: --version' >&2; exit 2")
    assert info.status == EnvironmentStatus.VERSION_TOO_OLD

    info = check("new", "echo 'tomviz-pipeline, version 4.0.0'")
    assert info.status == EnvironmentStatus.VERSION_TOO_NEW

    info = check("broken", "echo \"No module named 'numpy'\" >&2; exit 1")
    assert info.status == EnvironmentStatus.CLI_BROKEN
    assert "exit code 1" in info.message
    assert "No module named 'numpy'" in info.message

    info = check("mute", "echo hello")
    assert info.status == EnvironmentStatus.CLI_BROKEN
    assert "no version" in info.message

    info = check("slow", "exec sleep 5", timeout=0.5)
    assert info.status == EnvironmentStatus.CLI_BROKEN
    assert "did not respond" in info.message

    info = check("good", "echo 'tomviz-pipeline, version 3.2.5'")
    assert info.ok
    assert info.version == "3.2.5"
    assert info.env_path == str(tmp_path / "good")
    assert info.cli_path == str(tmp_path / "good" / "bin" / "tomviz-pipeline")

    # The CLI runs with the app's Python configuration scrubbed, as the
    # executor runs it.
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    info = check(
        "scrubbed",
        '[ -n "$PYTHONPATH" ] && exit 1; echo "tomviz-pipeline, version 3.2.0"',
    )
    assert info.ok


@posix_only
def test_the_running_environment_is_compatible():
    info = check_environment(sys.prefix)
    assert info.ok, info.message
    assert info.env_path == os.path.normpath(sys.prefix)
