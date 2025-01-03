import pytest
from keel.settings import service_url

def test_service_urls_have_hosts_ports_and_no_parser_normalization():
    for url in ["https://:443","https://api.example:bad","https://api.example:0","https://api.example:99999","https://api. example","https://api.example/\n"]:
        with pytest.raises(ValueError): service_url(url,False)
    assert service_url("https://id.example/realms/team",False)=="https://id.example/realms/team"
    assert service_url("http://127.0.0.1:8090",True)=="http://127.0.0.1:8090"
