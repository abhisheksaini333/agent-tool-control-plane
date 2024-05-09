"""Worker coordinator; only an acquired lease may finalize an execution."""
import logging
import threading
import time
import uuid
from .execution import Execution
from .policy import PolicyUnavailable
from .runner import WorkerFailure

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, control, runner, tenants, clock=None):
        self.control = control
        self.execution = Execution(control)
        self.runner = runner
        self.tenants = tuple(tenants)
        self.clock = clock or time.time
        self.control.clock = self.clock
        self.owner = "worker-" + uuid.uuid4().hex
        self.stop = threading.Event()
        self.last_error = None

    def _cancelled(self, request):
        current = self.control._request(request["tenant"], request["id"])
        return self.stop.is_set() or not self.execution.owns(
            current, request["lease"], self.clock()
        )

    def _perform(self, request):
        tenant, key, lease = request["tenant"], request["id"], request["lease"]
        try:
            output = self.runner.run(request, lambda: self._cancelled(request))
            self.execution.complete(tenant, key, lease, output, self.clock())
            self.last_error = None
            return
        except WorkerFailure as error:
            code = "worker_unavailable" if error.code == "cancelled" else error.code
        except PolicyUnavailable:
            code = "policy_unavailable"
        except (PermissionError, ValueError):
            code = "authorization_changed"
        except Exception as error:
            code = "internal_failure"
            logger.error("Worker execution failed: %s", type(error).__name__)
        self.last_error = code
        self.execution.fail(tenant, key, lease, code, self.clock())

    def once(self):
        for tenant in self.tenants:
            for candidate in self.execution.ready(tenant, self.clock()):
                if self.stop.is_set():
                    return False
                try:
                    claimed = self.execution.claim(
                        tenant, candidate["id"], self.owner, self.clock()
                    )
                except (ValueError, PermissionError):
                    continue
                self._perform(claimed)
                return True
        return False

    def run(self):
        while not self.stop.is_set():
            try:
                worked = self.once()
            except Exception as error:
                self.last_error = type(error).__name__
                logger.error("Worker polling failed: %s", type(error).__name__)
                worked = False
            if not worked:
                self.stop.wait(1)
