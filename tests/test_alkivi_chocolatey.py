"""Tests sans Windows : choco.exe est simulé, on compte ses appels.

Lancer avec le Python de Salt : /opt/salt/bin/python3 -m pytest tests/
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeChoco:
    def __init__(self):
        self.calls = []
        self.packages = {"chocolatey": "2.4.3", "chocolatey-license": "2027.8.23", "firefox": "130.0"}
        self.features = {"useBackgroundService": "Enabled", "showNonElevatedWarnings": "Disabled"}

    def run_all(self, cmd, python_shell=False):
        args = cmd[1:]
        self.calls.append(args)
        out = ""
        if args[0] == "list":
            out = "\n".join("{0}|{1}".format(k, v) for k, v in self.packages.items())
        elif args[0] == "features":
            out = "\n".join("{0}|{1}|desc".format(k, v) for k, v in self.features.items())
        elif args[0] == "feature":
            self.features[args[3]] = "Enabled" if args[1] == "enable" else "Disabled"
        elif args[0] == "install":
            self.packages[args[1]] = args[args.index("--version") + 1] if "--version" in args else "1.0"
        return {"retcode": 0, "stdout": out, "stderr": ""}


@pytest.fixture
def env():
    choco = FakeChoco()
    mod = _load("alkivi_chocolatey_module", ROOT / "_modules" / "alkivi_chocolatey.py")
    state = _load("alkivi_chocolatey_state", ROOT / "_states" / "alkivi_chocolatey.py")
    salt = {"cmd.run_all": choco.run_all, "cmd.run": lambda cmd, python_shell=False: "2.4.3"}
    mod.__context__ = {"chocolatey._path": "choco.exe"}
    mod.__salt__ = salt
    for fn in ("list_local", "install", "list_features", "enable_feature", "disable_feature"):
        salt["alkivi_chocolatey." + fn] = getattr(mod, fn)
    state.__salt__ = salt
    state.__opts__ = {"test": False}
    return choco, state


def test_installed_lists_once_per_run(env):
    choco, state = env
    for name in ("firefox", "chocolatey-license"):
        ret = state.installed(name)
        assert ret["result"] is True and ret["changes"] == {}
    assert state.installed("chocolatey-license", version="2027.8.23")["changes"] == {}
    assert choco.calls == [["list", "--limit-output"]]


def test_installed_missing_package(env):
    choco, state = env
    ret = state.installed("7zip")
    assert ret["changes"] == {"7zip": {"old": "", "new": "1.0"}}
    assert choco.calls[1][:2] == ["install", "7zip"]
    assert choco.calls[-1] == ["list", "--limit-output"]


def test_installed_other_version_forces(env):
    choco, state = env
    ret = state.installed("firefox", version="131.0")
    assert ret["changes"] == {"firefox": {"old": "130.0", "new": "131.0"}}
    assert "--force" in choco.calls[1]


def test_installed_test_mode(env):
    choco, state = env
    state.__opts__["test"] = True
    ret = state.installed("7zip")
    assert ret["result"] is None
    assert all(call[0] != "install" for call in choco.calls)


def test_feature_already_in_state_is_not_rewritten(env):
    choco, state = env
    assert state.feature_enabled("useBackgroundService")["changes"] == {}
    assert state.feature_disabled("showNonElevatedWarnings")["changes"] == {}
    assert choco.calls == [["features", "--limit-output"]]


def test_feature_change_refreshes_cache(env):
    choco, state = env
    assert state.feature_enabled("showNonElevatedWarnings")["changes"]
    choco.calls.clear()
    assert state.feature_enabled("showNonElevatedWarnings")["changes"] == {}
    assert choco.calls == [["features", "--limit-output"]]
