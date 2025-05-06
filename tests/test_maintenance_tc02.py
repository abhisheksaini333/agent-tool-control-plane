import pytest
from keel.settings import Settings

def test_datastore_urls_fail_during_configuration_not_connection():
    for key,prefix in [("KEEL_DATABASE_URL","postgresql"),("KEEL_REDIS_URL","redis")]:
        for suffix in [":",":///db","://:5432/db","://localhost:bad/db","://localhost:0/db","://localhost/db#ignored"]:
            with pytest.raises(ValueError): Settings.from_env({"KEEL_LOCAL_DEMO":"1",key:prefix+suffix})
    value="postgresql://alice:secret@localhost:5432/db?sslmode=require"
    assert Settings.from_env({"KEEL_LOCAL_DEMO":"1","KEEL_DATABASE_URL":value}).database_url==value
