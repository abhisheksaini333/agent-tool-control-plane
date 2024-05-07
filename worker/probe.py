"""Operator-only isolation probes; never registered as agent tools."""
import json
import os
from pathlib import Path
import resource
import socket
import sys
import time


def cgroup(name):
    return Path("/sys/fs/cgroup", name).read_text().strip()


def isolation():
    report = {
        "uid": os.getuid(),
        "memory_max": int(cgroup("memory.max")),
        "pids_max": int(cgroup("pids.max")),
        "cpu_max": cgroup("cpu.max"),
        "nofile": resource.getrlimit(resource.RLIMIT_NOFILE),
    }
    try:
        Path("/app/denied-write").write_text("must not persist")
        report["root_write_denied"] = False
    except OSError as error:
        report.update(root_write_denied=True, root_write_errno=error.errno)
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=0.5):
            report["network_denied"] = False
    except OSError as error:
        report.update(network_denied=True, network_errno=error.errno)
    status = dict(
        line.split(":", 1)
        for line in Path("/proc/self/status").read_text().splitlines()
        if ":" in line
    )
    report["no_new_privileges"] = status["NoNewPrivs"].strip()
    report["effective_capabilities"] = status["CapEff"].strip()
    return report


def cpu():
    before = dict(line.split() for line in cgroup("cpu.stat").splitlines())
    wall_start, cpu_start = time.monotonic(), time.process_time()
    iterations = 0
    while time.monotonic() - wall_start < 3:
        iterations += 1
    after = dict(line.split() for line in cgroup("cpu.stat").splitlines())
    return {
        "cpu_max": cgroup("cpu.max"),
        "wall_seconds": time.monotonic() - wall_start,
        "cpu_seconds": time.process_time() - cpu_start,
        "throttled_periods": int(after["nr_throttled"]) - int(before["nr_throttled"]),
        "iterations": iterations,
    }


if __name__ == "__main__":
    if sys.argv[1:] == ["sleep"]:
        print(json.dumps({"started": True}), flush=True)
        time.sleep(60)
    elif sys.argv[1:] == ["memory"]:
        chunks = []
        while True:
            chunks.append(bytearray(b"x" * (4 * 1024 * 1024)))
    elif sys.argv[1:] == ["cpu"]:
        print(json.dumps(cpu(), sort_keys=True))
    elif sys.argv[1:] == ["isolation"]:
        print(json.dumps(isolation(), sort_keys=True))
    else:
        raise SystemExit("Unknown operator probe")
