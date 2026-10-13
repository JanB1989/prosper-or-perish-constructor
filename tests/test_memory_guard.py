import subprocess

from prosper_or_perish_constructor import cli, memory_guard


def test_heavy_commands_rerun_inside_a_capped_scope_with_jemalloc_release(monkeypatch) -> None:
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs.get("env")))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv(memory_guard.INSIDE, raising=False)
    monkeypatch.delenv(memory_guard.JEMALLOC_ENV, raising=False)
    monkeypatch.setattr(memory_guard.shutil, "which", lambda name: "/usr/bin/systemd-run")
    monkeypatch.setattr(memory_guard.subprocess, "run", fake_run)
    assert memory_guard.run_capped(["report", "--publish"], 16) == 0
    command, env = calls[-1]
    assert command[:4] == ["systemd-run", "--user", "--scope", "-q"]
    assert "MemoryMax=16384M" in command and "MemorySwapMax=0" in command
    assert command[-2:] == ["report", "--publish"]
    assert env[memory_guard.INSIDE] == "16" and env[memory_guard.JEMALLOC_ENV] == memory_guard.JEMALLOC_CONF
    assert {"report", "savegame-notebooks"} <= cli.MEMORY_CAPPED_COMMANDS


def test_no_second_scope_inside_one_and_kill_is_reported(monkeypatch, capsys) -> None:
    monkeypatch.setenv(memory_guard.INSIDE, "16")
    assert memory_guard.run_capped(["report"], 16) is None
    monkeypatch.delenv(memory_guard.INSIDE)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(memory_guard.shutil, "which", lambda name: "/usr/bin/systemd-run")
    monkeypatch.setattr(memory_guard.subprocess, "run",
                        lambda command, **kwargs: subprocess.CompletedProcess(command, 0 if command[-1] == "true" else 137))
    assert memory_guard.run_capped(["report"], 16) == 137
    assert "memory cap of 16 GB" in capsys.readouterr().err
