"""Hard memory cap for the heavy commands (`ppc report`, `ppc savegame-notebooks build`).

The command runs itself again inside a systemd scope with `MemoryMax` and no swap. The cap covers the whole process
tree (worker processes, ffmpeg), so a run that outgrows it is killed by the kernel instead of pushing the WSL VM into
swap until it stops responding (2026-10-13: a report of a 674 MB-save run froze WSL while EU5 held 23 GB on Windows).
The Windows save engine (eu5save.exe) runs outside the VM and has its own budget (eu5gameparser EU5SAVE_MEMORY_GB).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

INSIDE = "PPC_MEMORY_CAP_GB"  # set inside the scope: the cap in GB
DEFAULT_GB = 16.0
# Polars' jemalloc kept freed pages: the report held 8.7 GB after loading a run whose tables are 1.2 GB (run 331d3616,
# 100 saves) and peaked at 15.1 GB. Returning them after 1 s via a background thread: 2.3 GB held, peak about 10 GB,
# no step slower (2026-10-13). Read once when polars loads, so it is set for the capped child process.
JEMALLOC_ENV = "_RJEM_MALLOC_CONF"
JEMALLOC_CONF = "background_thread:true,dirty_decay_ms:1000,muzzy_decay_ms:0"


def run_capped(argv: Sequence[str], gb: float) -> int | None:
    """Run `ppc <argv>` inside a memory-capped scope and return its exit code; None when already inside one or when
    no scope can be made (the caller then runs the command itself, uncapped)."""
    if os.environ.get(INSIDE) or gb <= 0 or os.environ.get("PYTEST_CURRENT_TEST"):  # tests call cli.main in-process
        return None
    if shutil.which("systemd-run") is None:
        print("memory cap: systemd-run not found, running without a cap", file=sys.stderr, flush=True)
        return None
    probe = subprocess.run(["systemd-run", "--user", "--scope", "-q", "true"], capture_output=True)
    if probe.returncode != 0:
        print("memory cap: no user systemd scope, running without a cap", file=sys.stderr, flush=True)
        return None
    command = [
        "systemd-run", "--user", "--scope", "-q",
        "-p", f"MemoryMax={int(gb * 1024)}M", "-p", "MemorySwapMax=0",
        sys.executable, "-c", "import sys; from prosper_or_perish_constructor.cli import main; sys.exit(main())",
        *argv,
    ]
    code = subprocess.run(command, env={**os.environ, INSIDE: f"{gb:g}", JEMALLOC_ENV: os.environ.get(JEMALLOC_ENV, JEMALLOC_CONF)}).returncode
    if code in (137, -9):
        print(f"\nppc {' '.join(argv[:1])}: stopped at the memory cap of {gb:g} GB (the kernel killed it; WSL is fine). "
              f"Set PPC_MEMORY_GB higher if this run really needs more.",
              file=sys.stderr, flush=True)
    return code


def cap_gb(settings: dict) -> float:
    return float(os.environ.get("PPC_MEMORY_GB") or settings.get("memory_gb") or DEFAULT_GB)


def _scope_dir() -> Path | None:
    try:
        group = Path("/proc/self/cgroup").read_text().strip().split("::", 1)[1]
    except (OSError, IndexError):
        return None
    path = Path("/sys/fs/cgroup") / group.lstrip("/")
    return path if (path / "memory.stat").is_file() else None


class PeakSampler:
    """Largest anonymous memory (process memory, not the page cache the kernel can drop) of the scope, sampled twice
    a second in a daemon thread; `line()` is the summary for the command's last log line."""

    def __init__(self) -> None:
        import threading

        self.scope = _scope_dir() if os.environ.get(INSIDE) else None
        self.peak = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True) if self.scope else None
        if self._thread:
            self._thread.start()

    def _anon(self) -> int:
        for line in (self.scope / "memory.stat").read_text().splitlines():  # type: ignore[operator]
            if line.startswith("anon "):
                return int(line.split()[1])
        return 0

    def _run(self) -> None:
        while not self._stop.wait(0.5):
            try:
                self.peak = max(self.peak, self._anon())
            except OSError:
                return

    def line(self) -> str:
        if not self._thread:
            return ""
        self._stop.set()
        return f"memory peak {self.peak / 1024**3:.1f} GB of the {os.environ[INSIDE]} GB cap"
