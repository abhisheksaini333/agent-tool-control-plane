"""Local operator entry points. No implicit seed or remote deployment."""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
from .api import create_app
from .bootstrap import seed_demo
from .credentials import CredentialVault, ALIASES
from .runner import DockerRunner
from .runtime import Runtime
from .settings import Settings
from .worker import Worker


def prepare_credentials(directory):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink() or root.stat().st_mode & 0o077:
        raise PermissionError("Credential directory must be private")
    for alias in sorted(ALIASES):
        path = root / alias
        if not path.exists():
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "w") as stream:
                stream.write(secrets.token_hex(32))
        CredentialVault(root).read(alias)


def main():
    parser = argparse.ArgumentParser(description="Keel local control-plane operations")
    parser.add_argument("command", choices=["seed", "serve", "worker", "check"])
    parser.add_argument("--port", type=int, default=5484)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()
    runtime = Runtime(settings)
    try:
        if args.command == "seed":
            seed_demo(runtime.store, settings.local_demo)
            prepare_credentials(settings.credential_directory)
            print("Demo identities, tools, inventory and private credentials are ready")
        elif args.command == "check":
            checks = runtime.checks()
            print(json.dumps(checks, sort_keys=True))
            return 0 if all(checks.values()) else 1
        elif args.command == "serve":
            import uvicorn

            app = create_app(
                runtime.control,
                runtime.verifier,
                settings,
                admission=runtime.admission,
                readiness=runtime.checks,
            )
            uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)
        else:
            runner = DockerRunner(
                CredentialVault(settings.credential_directory),
                settings.worker_image,
                settings.worker_timeout,
            )
            worker = Worker(runtime.control, runner, settings.tenants)
            signal.signal(signal.SIGINT, lambda *_: worker.stop.set())
            signal.signal(signal.SIGTERM, lambda *_: worker.stop.set())
            if args.once:
                print(json.dumps({"processed": worker.once()}))
            else:
                worker.run()
    finally:
        runtime.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
