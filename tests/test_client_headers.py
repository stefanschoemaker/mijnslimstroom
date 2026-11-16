import json
from pathlib import Path

from custom_components.mijnslimstroom.api import MijnSlimstroomApi
from custom_components.mijnslimstroom.const import CLIENT_HEADERS, VERSION

ROOT = Path(__file__).parent.parent / "custom_components" / "mijnslimstroom"


class _Response:
    status = 200

    def __init__(self, body):
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
    def __init__(self):
        self.calls = []

    def post(self, url, **kw):
        self.calls.append((url, kw["headers"]))
        return _Response({"access_token": "synthetic-test-token", "expires_in": 3600})

    def get(self, url, **kw):
        self.calls.append((url, kw["headers"]))
        return _Response({})


def test_version_matches_the_manifest():
    assert json.loads((ROOT / "manifest.json").read_text())["version"] == VERSION


async def test_every_request_says_it_is_home_assistant():
    session = _Session()
    api = MijnSlimstroomApi(session, "testuser", "synthetic-test-pw-123", "https://app.test")
    await api.live()
    await api.report_meters([])
    assert len(session.calls) == 3
    for _url, headers in session.calls:
        assert headers["X-Client"] == "home-assistant"
        assert headers["X-Client-Version"] == VERSION
    assert CLIENT_HEADERS.items() <= session.calls[1][1].items()
    assert session.calls[1][1]["Authorization"] == "Bearer synthetic-test-token"
