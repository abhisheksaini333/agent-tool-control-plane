"""Trusted host credential lookup; workers receive exactly one read-only file."""
from contextlib import contextmanager
from pathlib import Path
import os
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
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
            raise PermissionError("Credential must be a private regular file")
        if metadata.st_uid != os.getuid():
            raise PermissionError("Credential must belong to the worker host user")
        if not 32 <= metadata.st_size <= 4096:
            raise ValueError("Credential must contain 32 to 4096 bytes")
        value = path.read_text()
        if not value.isascii() or any(char.isspace() for char in value):
            raise ValueError("Credential must be one ASCII token")
        return value

    @contextmanager
    def materialize(self, alias):
        secret = self.read(alias)
        with tempfile.TemporaryDirectory(prefix="keel-credential-") as directory:
            path = Path(directory) / "key"
            path.write_text(secret)
            path.chmod(0o400)
            yield directory, secret
