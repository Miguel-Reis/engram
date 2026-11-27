"""Cross-platform port/process guard for Engram local web dashboard (zero internal deps)."""

from __future__ import annotations

import os
import re
import signal
import subprocess
from typing import Optional


def kill_other_dashboard_processes(exclude_pid: int = 0, port: int = 8765) -> None:
    """Terminate stale web_dashboard.py processes bound to `port` on Windows/macOS/Linux."""
    if os.environ.get("BRAIN_TEST_MODE") == "1":
        return
    my_pid = exclude_pid or os.getpid()
    try:
        if os.name == "nt":
            ns = subprocess.run(
                ["netstat", "-ano", "-p", "TCP"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=3,
                creationflags=0x08000000,
            )
            pids_to_kill: set[int] = set()
            port_tok = f":{port}"
            for line in (ns.stdout or "").splitlines():
                parts = line.split()
                if len(parts) >= 5 and port_tok in parts[1] and parts[3].upper() == "LISTENING":
                    if parts[4].isdigit():
                        pid_val = int(parts[4])
                        if pid_val > 0 and pid_val != my_pid:
                            pids_to_kill.add(pid_val)
            for pid_val in pids_to_kill:
                subprocess.run(
                    ["taskkill", "/PID", str(pid_val), "/F"],
                    capture_output=True,
                    timeout=3,
                    creationflags=0x08000000,
                )
        else:
            pids_to_kill = set()
            for cmd in (
                ["lsof", "-ti", f"tcp:{port}"],
                ["fuser", f"{port}/tcp"],
            ):
                try:
                    proc = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="ignore",
                        timeout=3,
                    )
                    for tok in re.findall(r"\b(\d+)\b", proc.stdout or ""):
                        pid_val = int(tok)
                        if pid_val > 0 and pid_val != my_pid:
                            pids_to_kill.add(pid_val)
                    if pids_to_kill:
                        break
                except FileNotFoundError:
                    continue
            if not pids_to_kill:
                try:
                    ss_proc = subprocess.run(
                        ["ss", "-tlnp"],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="ignore",
                        timeout=3,
                    )
                    port_tok = f":{port}"
                    for line in (ss_proc.stdout or "").splitlines():
                        if port_tok in line:
                            for tok in re.findall(r"pid=(\d+)", line):
                                pid_val = int(tok)
                                if pid_val > 0 and pid_val != my_pid:
                                    pids_to_kill.add(pid_val)
                except FileNotFoundError:
                    pass
            for pid_val in pids_to_kill:
                try:
                    os.kill(pid_val, signal.SIGTERM)
                except ProcessLookupError:
                    pass
    except Exception:
        pass
