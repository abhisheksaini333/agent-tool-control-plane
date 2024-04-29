"""Privileged host runner for fixed, constrained Docker workers.

The runner's Docker access is a trust boundary. It is never mounted into workers.
"""
from contextlib import nullcontext
import json
import os
import subprocess
import tempfile
import time
import uuid
from .canonical import canonical
from .protocol import payload_for, verify_reply
from .registry import HANDLERS


class WorkerFailure(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class DockerRunner:
    def __init__(self, vault=None, image="keel-worker:local", timeout=5):
        if not 0.1 <= timeout <= 30:
            raise ValueError("Worker deadline must be at most 30 seconds")
        self.vault = vault
        self.image = image
        self.timeout = timeout
        self.last_execution = None

    def create_command(self, name, credential_directory, command=None):
        if os.getuid() == 0:
            raise PermissionError("Run the host runner as a non-root user")
        arguments = [
            "docker",
            "create",
            "-i",
            "--name",
            name,
            "--label",
            "app=keel-worker",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--memory=64m",
            "--memory-swap=64m",
            "--cpus=0.25",
            "--pids-limit=32",
            "--ulimit",
            "nofile=64:64",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=8m",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
        ]
        if credential_directory:
            if "," in credential_directory:
                raise ValueError("Unsupported credential mount path")
            arguments.extend(
                [
                    "--mount",
                    f"type=bind,src={credential_directory},dst=/run/credential,readonly",
                ]
            )
        arguments.append(self.image)
        if command:
            arguments.extend(command)
        return arguments

    def _remove(self, name):
        subprocess.run(
            ["docker", "rm", "-f", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )

    def _invoke(
        self, payload, credential_directory=None, cancelled=lambda: False, command=None
    ):
        name = "keel-job-" + uuid.uuid4().hex
        process = None
        started = time.monotonic()
        self.last_execution = None
        try:
            created = subprocess.run(
                self.create_command(name, credential_directory, command),
                capture_output=True,
                timeout=10,
            )
            if created.returncode:
                raise WorkerFailure("worker_unavailable")
            with tempfile.TemporaryFile() as stdin, tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
                stdin.write(canonical(payload).encode())
                stdin.seek(0)
                started = time.monotonic()
                process = subprocess.Popen(
                    ["docker", "start", "-a", "-i", name],
                    stdin=stdin,
                    stdout=stdout,
                    stderr=stderr,
                )
                while process.poll() is None:
                    if cancelled():
                        raise WorkerFailure("cancelled")
                    if time.monotonic() - started >= self.timeout:
                        raise WorkerFailure("worker_timeout")
                    if (
                        os.fstat(stdout.fileno()).st_size
                        + os.fstat(stderr.fileno()).st_size
                        > 65536
                    ):
                        raise WorkerFailure("invalid_output")
                    time.sleep(0.05)
                elapsed = time.monotonic() - started
                inspection = subprocess.run(
                    ["docker", "inspect", name],
                    capture_output=True,
                    timeout=5,
                    check=True,
                )
                inspected = json.loads(inspection.stdout)[0]
                state, host = inspected["State"], inspected["HostConfig"]
                self.last_execution = {
                    "name": name,
                    "elapsed_ms": round(elapsed * 1000, 2),
                    "exit_code": state["ExitCode"],
                    "oom_killed": state["OOMKilled"],
                    "network": host["NetworkMode"],
                    "memory_bytes": host["Memory"],
                    "nano_cpus": host["NanoCpus"],
                    "pids_limit": host["PidsLimit"],
                    "read_only": host["ReadonlyRootfs"],
                    "user": inspected["Config"]["User"],
                }
                if state["OOMKilled"]:
                    raise WorkerFailure("resource_limit")
                if process.returncode or state["ExitCode"]:
                    raise WorkerFailure("worker_exit")
                if (
                    os.fstat(stdout.fileno()).st_size
                    + os.fstat(stderr.fileno()).st_size
                    > 65536
                ):
                    raise WorkerFailure("invalid_output")
                stdout.seek(0)
                return stdout.read(65537).decode(), dict(self.last_execution)
        except WorkerFailure as error:
            self.last_execution = {
                **(self.last_execution or {}),
                "name": name,
                "failure": error.code,
                "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
            }
            raise
        except (
            subprocess.SubprocessError,
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as error:
            raise WorkerFailure("worker_unavailable") from error
        finally:
            try:
                self._remove(name)
            except (subprocess.SubprocessError, OSError):
                self.last_execution = {
                    **(self.last_execution or {}),
                    "name": name,
                    "cleanup_pending": True,
                }
            finally:
                if process and process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)

    def run(self, request, cancelled=lambda: False):
        handler = request["tool"]["handler"]
        if handler not in HANDLERS:
            raise WorkerFailure("invalid_output")
        alias = HANDLERS[handler]["credential"]
        if alias and not self.vault:
            raise WorkerFailure("worker_unavailable")
        context = self.vault.materialize(alias) if alias else nullcontext((None, None))
        with context as (directory, secret):
            raw, metrics = self._invoke(payload_for(request), directory, cancelled)
            try:
                result = verify_reply(request, raw, secret)
            except ValueError as error:
                raise WorkerFailure("invalid_output") from error
        return {"result": result, "metrics": metrics}
