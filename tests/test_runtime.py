import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def launcher(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "src/labledger/resources/backend.py"
    spec = importlib.util.spec_from_file_location("test_launcher", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plugin = tmp_path / "plugin"
    (plugin / "runtime").mkdir(parents=True)
    (plugin / "runtime/requirements.txt").write_text("psutil==7.2.2\n")
    monkeypatch.setattr(module, "PLUGIN_ROOT", plugin)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    return module


def test_unprepared_hook_runtime_never_creates_cache(launcher, tmp_path):
    assert launcher.ensure_environment(install=False) is None
    assert not (tmp_path / "cache").exists()


def test_failed_runtime_setup_is_retryable_and_warm_runtime_needs_no_install(launcher, monkeypatch):
    environment = launcher.environment_path()

    class Environment:
        def __init__(self, **kwargs):
            pass

        def create(self, destination):
            (destination / "bin").mkdir(parents=True)
            (destination / "bin/python").touch()

    monkeypatch.setattr(launcher.venv, "EnvBuilder", Environment)
    calls = []

    def install(command, **kwargs):
        calls.append(command)
        assert command[:4] == [str(environment / "bin/python"), "-I", "-m", "pip"]
        return SimpleNamespace(returncode=1 if len(calls) == 1 else 0)

    monkeypatch.setattr(launcher.subprocess, "run", install)
    with pytest.raises(RuntimeError, match="prepare plugin dependencies"):
        launcher.ensure_environment()
    assert not launcher.ready(environment)
    (environment / "partial-install").touch()
    assert launcher.ensure_environment() == environment
    assert not (environment / "partial-install").exists()
    assert launcher.ready(environment)

    def offline(*args, **kwargs):
        raise subprocess.TimeoutExpired("unexpected installation", 1)

    monkeypatch.setattr(launcher.subprocess, "run", offline)
    assert launcher.ensure_environment() == environment
    assert launcher.ensure_environment(install=False) == environment
    assert len(calls) == 2
