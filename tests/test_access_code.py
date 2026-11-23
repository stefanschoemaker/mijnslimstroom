import pytest

from custom_components.mijnslimstroom.api import InvalidAuth, MijnSlimstroomApi
from custom_components.mijnslimstroom.config_flow import _credentials


class _Response:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        return None

    async def json(self):
        return self._body

    async def text(self):
        return ""


class _Session:
    def __init__(self, status=200):
        self.status = status
        self.calls = []

    def post(self, url, **kw):
        self.calls.append(("POST", url, kw["headers"].get("Authorization")))
        return _Response(self.status, {})

    def get(self, url, **kw):
        self.calls.append(("GET", url, kw["headers"].get("Authorization")))
        return _Response(self.status, {"username": "testuser", "site_id": "thuis", "display_name": "Test"})


async def test_an_access_code_never_logs_in_with_a_password():
    session = _Session()
    api = MijnSlimstroomApi(session, "", "", "https://app.test", access_token="synthetic-test-code")
    await api.login()
    await api.live()
    await api.report_meters([])
    assert (api.username, api.site_id) == ("testuser", "thuis")
    assert [c[1] for c in session.calls] == [
        "https://app.test/api/whoami", "https://app.test/api/live", "https://app.test/api/meters"]
    assert {c[2] for c in session.calls} == {"Bearer synthetic-test-code"}


async def test_a_withdrawn_code_asks_for_a_new_one_at_once():
    session = _Session(status=401)
    api = MijnSlimstroomApi(session, "", "", "https://app.test", access_token="synthetic-test-code")
    with pytest.raises(InvalidAuth):
        await api.login()
    api._token, api._token_expires = "synthetic-test-code", float("inf")
    with pytest.raises(InvalidAuth):
        await api.live()
    assert len(session.calls) == 2


def test_form_takes_a_code_or_a_name_with_password():
    assert _credentials({"access_token": " synthetic-test-code ", "username": "testuser"}) == {
        "access_token": "synthetic-test-code"}
    assert _credentials({"username": "testuser", "password": "synthetic-test-pw-123"}) == {
        "username": "testuser", "password": "synthetic-test-pw-123"}
    assert _credentials({"password": "synthetic-test-pw-123"}, "testuser") == {
        "username": "testuser", "password": "synthetic-test-pw-123"}
    assert _credentials({"username": "testuser"}) is None
    assert _credentials({}) is None
