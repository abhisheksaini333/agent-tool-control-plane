import os
import uuid
import pytest
from keel.admission import RedisAdmission, AdmissionDenied, AdmissionUnavailable
from helpers import ALICE, BOB


class OfflineRedis:
    def eval(self, *args):
        from redis.exceptions import ConnectionError

        raise ConnectionError("offline")


def test_admission_fails_closed_when_redis_is_unavailable():
    with pytest.raises(AdmissionUnavailable):
        RedisAdmission(OfflineRedis()).check(ALICE)


@pytest.mark.skipif(
    not os.environ.get("KEEL_TEST_REDIS_URL"), reason="Actual Redis URL not configured"
)
def test_actual_redis_limits_callers_independently():
    import redis

    client = redis.Redis.from_url(os.environ["KEEL_TEST_REDIS_URL"])
    admission = RedisAdmission(
        client, limit=2, window=10, prefix="keel-test-" + uuid.uuid4().hex
    )
    admission.check(ALICE)
    admission.check(ALICE)
    with pytest.raises(AdmissionDenied):
        admission.check(ALICE)
    admission.check(BOB)
    client.close()
