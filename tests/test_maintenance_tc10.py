import pytest
from keel.protocol import verify_reply
from test_receipts import ready

def test_worker_reply_has_an_explicit_text_boundary():
    _,_,request=ready()
    for raw in [None,b'{}',{},'\ud800']:
        with pytest.raises(ValueError): verify_reply(request,raw,'secret')
