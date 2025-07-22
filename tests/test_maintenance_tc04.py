import pytest
from keel.admission import RedisAdmission,AdmissionDenied,AdmissionUnavailable
from helpers import ALICE

class Reply:
    def __init__(self,value): self.value=value
    def eval(self,*args): return self.value

def test_malformed_admission_replies_fail_closed():
    for reply in [None,[],[0,3],[True,3],[1,True],[1,-1],[1,10000],[1.5,3],['1',3]]:
        with pytest.raises(AdmissionUnavailable): RedisAdmission(Reply(reply)).check(ALICE)
    with pytest.raises(AdmissionDenied): RedisAdmission(Reply([31,60])).check(ALICE)
    RedisAdmission(Reply([1,60])).check(ALICE)
