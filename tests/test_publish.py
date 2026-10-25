"""`symbola login`, `logout` and `publish`, against a faked symbola.sh and GitHub."""

import gzip
import io
import json
import tarfile
import urllib.parse

import pytest
from typer.testing import CliRunner

from symbola import publish as pub
from symbola.cli import app
from symbola.registry import scaffold_pack

SITE = "https://symbola.test"


class Fake:
    """Answers urlopen like the site and GitHub would, and records what was sent."""

    def __init__(self, polls_before_approval=1):
        self.sent = []
        self.pending = polls_before_approval
        self.states = ["queued", "merging"]

    def __call__(self, req, timeout=None):
        url, body = req.full_url, req.data
        self.sent.append((req.get_method(), url, dict(req.header_items()), body))
        if url == f"{SITE}/api/cli/config":
            return self.answer({"client_id": "Iv1.abc"})
        if url == "https://github.com/login/device/code":
            assert urllib.parse.parse_qs(body.decode()) == {"client_id": ["Iv1.abc"]}
            return self.answer({"device_code": "dc", "user_code": "ABCD-1234", "verification_uri": "https://github.com/login/device",
                                "interval": 5, "expires_in": 900})
        if url == "https://github.com/login/oauth/access_token":
            if self.pending:
                self.pending -= 1
                return self.answer({"error": "authorization_pending"})
            return self.answer({"access_token": "ghu_x"})
        if url == f"{SITE}/api/cli/token":
            assert json.loads(body)["github_token"] == "ghu_x"
            return self.answer({"token": "sym_abc", "login": "ada", "namespaces": ["ada", "acme"]})
        if url == f"{SITE}/api/publish":
            return self.answer({"request": {"id": "r1", "pack": "acme/demo", "state": "queued"},
                                "url": f"{SITE}/publish/request/?id=r1"})
        if url == f"{SITE}/api/requests/r1":
            state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
            return self.answer({"request": {"id": "r1", "pack": "acme/demo", "state": state, "message": f"now {state}",
                                            "pr": "https://github.com/x/y/pull/1"}})
        raise AssertionError(f"unexpected {url}")

    @staticmethod
    def answer(data):
        return io.BytesIO(json.dumps(data).encode())


@pytest.fixture
def fake(monkeypatch, tmp_path):
    f = Fake()
    monkeypatch.setattr(pub.urllib.request, "urlopen", f)
    monkeypatch.setattr(pub.time, "sleep", lambda s: None)
    monkeypatch.setattr("symbola.cli.time.sleep", lambda s: None)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("SYMBOLON_PUBLISH_TOKEN", raising=False)
    return f


def test_login_saves_a_symbola_token_and_logout_forgets_it(fake, tmp_path):
    out = CliRunner().invoke(app, ["login", "--site", SITE, "--name", "laptop"])
    assert out.exit_code == 0, out.output
    assert "ABCD-1234" in out.output and "signed in to https://symbola.test as ada" in out.output
    saved = json.loads(pub.credentials_path().read_text())
    assert saved == {SITE: {"token": "sym_abc", "login": "ada"}}
    assert oct(pub.credentials_path().stat().st_mode & 0o777) == "0o600"
    assert json.loads(fake.sent[-1][3])["name"] == "laptop"
    assert CliRunner().invoke(app, ["logout", "--site", SITE]).exit_code == 0
    assert json.loads(pub.credentials_path().read_text()) == {}


def test_publish_validates_uploads_a_tarball_and_follows_the_request(fake, tmp_path):
    spec = scaffold_pack("acme/demo", tmp_path / "spec", "me@example.com")
    out = CliRunner().invoke(app, ["publish", str(spec), "--site", SITE])
    assert "not signed in" in out.output and out.exit_code == 1
    pub.save_credentials(SITE, {"token": "sym_abc", "login": "ada"})
    out = CliRunner().invoke(app, ["publish", str(spec), "--site", SITE])
    assert out.exit_code == 0, out.output
    assert "uploaded acme/demo" in out.output and "now merging" in out.output
    method, url, headers, body = next(s for s in fake.sent if s[1].endswith("/api/publish"))
    assert (method, headers["Authorization"], headers["Content-type"]) == ("POST", "Bearer sym_abc", "application/gzip")
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(body))) as tar:
        assert "demo/symbolon-pack.toml" in tar.getnames()


def test_publish_reports_a_refusal(fake, tmp_path, monkeypatch):
    spec = scaffold_pack("acme/demo", tmp_path / "spec", "me@example.com")
    monkeypatch.setenv("SYMBOLON_PUBLISH_TOKEN", "sym_ci")
    fake.states = ["failed"]
    out = CliRunner().invoke(app, ["publish", str(spec), "--site", SITE])
    assert out.exit_code == 1 and "the registry refused the pack" in out.output
    assert next(s for s in fake.sent if s[1].endswith("/api/publish"))[2]["Authorization"] == "Bearer sym_ci"


def test_publish_refuses_a_folder_that_is_not_a_pack(fake, tmp_path):
    pub.save_credentials(SITE, {"token": "sym_abc", "login": "ada"})
    out = CliRunner().invoke(app, ["publish", str(tmp_path), "--site", SITE])
    assert out.exit_code == 1 and "no symbolon-pack.toml" in out.output
