"""Redis admission is advisory capacity control; PostgreSQL owns execution truth."""
from redis.exceptions import RedisError
from .canonical import digest

SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {count, redis.call('TTL', KEYS[1])}
"""


class AdmissionDenied(RuntimeError):
    def __init__(self, retry_after):
        super().__init__("Request rate exceeded")
        self.retry_after = max(1, retry_after)


class AdmissionUnavailable(RuntimeError):
    pass


class RedisAdmission:
    def __init__(self, client, limit=30, window=60, prefix="keel:admission"):
        if (
            type(limit) is not int
            or not 1 <= limit <= 1000
            or type(window) is not int
            or not 1 <= window <= 3600
        ):
            raise ValueError("Invalid admission limits")
        self.client = client
        self.limit = limit
        self.window = window
        self.prefix = prefix

    def check(self, actor):
        key = (
            self.prefix
            + ":"
            + digest({"tenant": actor.tenant, "caller": actor.subject})
        )
        try:
            count, remaining = self.client.eval(SCRIPT, 1, key, self.window)
        except RedisError as error:
            raise AdmissionUnavailable("Admission service unavailable") from error
        if count > self.limit:
            raise AdmissionDenied(remaining)
