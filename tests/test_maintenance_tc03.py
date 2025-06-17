from pathlib import Path
import pytest
from keel.credentials import CredentialVault

def test_path_replacement_cannot_change_the_credential_checked(tmp_path,monkeypatch):
    key=tmp_path/'report-signing';key.write_text('a'*40);key.chmod(0o600)
    old_lstat=Path.lstat
    def replaced(path,*args,**kwargs):
        metadata=old_lstat(path,*args,**kwargs)
        if path==key:
            path.unlink();path.write_text('b'*40);path.chmod(0o600)
        return metadata
    monkeypatch.setattr(Path,'lstat',replaced)
    assert CredentialVault(tmp_path).read('report-signing')=='a'*40

def test_nonprintable_credentials_are_rejected(tmp_path):
    key=tmp_path/'report-signing'
    for value in ['a'*39+'\0','a'*39+'\x1b','a'*39+'\x7f']:
        key.write_text(value);key.chmod(0o600)
        with pytest.raises(ValueError): CredentialVault(tmp_path).read('report-signing')
