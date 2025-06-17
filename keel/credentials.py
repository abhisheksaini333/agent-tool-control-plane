"""Trusted host credential lookup; workers receive exactly one read-only file."""
from contextlib import contextmanager
from pathlib import Path
import os
import errno
import stat
import tempfile

ALIASES = frozenset({"report-signing", "inventory-signing"})


class CredentialVault:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def read(self, alias):
        if alias not in ALIASES:
            raise ValueError("Unknown credential alias")
        path = self.root / alias
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError as error:
            if error.errno == errno.ELOOP:
                raise PermissionError("Credential must be a private regular file") from error
            raise
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
                raise PermissionError("Credential must be a private regular file")
            if metadata.st_uid != os.getuid():
                raise PermissionError("Credential must belong to the worker host user")
            if not 32 <= metadata.st_size <= 4096:
                raise ValueError("Credential must contain 32 to 4096 bytes")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                raw = stream.read(4097)
            if not 32 <= len(raw) <= 4096 or any(byte < 33 or byte > 126 for byte in raw):
                raise ValueError("Credential must be one printable ASCII token of 32 to 4096 bytes")
            value = raw.decode("ascii")
        finally:
            os.close(descriptor)
        return value

    @contextmanager
    def materialize(self, alias):
        secret = self.read(alias)
        with tempfile.TemporaryDirectory(prefix="keel-credential-") as directory:
            path = Path(directory) / "key"
            path.write_text(secret)
            path.chmod(0o400)
            yield directory, secret
