import os
from pathlib import Path
import pytest
from keel.cli import prepare_credentials
from keel.credentials import CredentialVault


def test_runtime_credentials_are_private_and_preserved_across_setup(tmp_path):
    root = tmp_path / "credentials"
    prepare_credentials(root)
    first = {path.name: path.read_text() for path in root.iterdir()}
    assert set(first) == {"inventory-signing", "report-signing"}
    assert len(set(first.values())) == 2
    prepare_credentials(root)
    assert {path.name: path.read_text() for path in root.iterdir()} == first
    for name, value in first.items():
        assert CredentialVault(root).read(name) == value
        assert root.joinpath(name).stat().st_mode & 0o777 == 0o600


def test_runtime_setup_refuses_an_existing_public_credential_directory(tmp_path):
    root = tmp_path / "credentials"
    root.mkdir(mode=0o755)
    with pytest.raises(PermissionError):
        prepare_credentials(root)
