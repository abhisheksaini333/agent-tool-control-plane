from pathlib import Path
import os
import pytest
from keel.credentials import CredentialVault


def test_only_selected_tool_key_is_materialized_and_removed(tmp_path):
    root = tmp_path / "vault"
    root.mkdir(mode=0o700)
    for alias in ["report-signing", "inventory-signing"]:
        file = root / alias
        file.write_text(alias + "-" + "a" * 40)
        file.chmod(0o600)
    vault = CredentialVault(root)
    with vault.materialize("report-signing") as (directory, secret):
        directory = Path(directory)
        assert sorted(p.name for p in directory.iterdir()) == ["key"]
        assert directory.joinpath("key").read_text() == secret
        assert "inventory" not in secret
        assert directory.joinpath("key").stat().st_mode & 0o777 == 0o400
    assert not directory.exists()


def test_unknown_alias_symlink_and_public_keys_are_rejected(tmp_path):
    vault = CredentialVault(tmp_path)
    with pytest.raises(ValueError):
        vault.read("../../secret")
    path = tmp_path / "report-signing"
    path.write_text("x" * 40)
    path.chmod(0o644)
    with pytest.raises(PermissionError):
        vault.read("report-signing")
    path.unlink()
    path.symlink_to(tmp_path / "other")
    with pytest.raises(PermissionError):
        vault.read("report-signing")
