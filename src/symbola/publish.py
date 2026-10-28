"""Publishing to symbola.sh from the command line: `symbola login`, `logout` and `publish`.

`login` signs in with GitHub's device flow, using the Symbola GitHub App's public client id
(the site serves it at /api/cli/config), and trades the GitHub token for a Symbola token at
/api/cli/token. Only the Symbola token is kept, in ~/.config/symbolon/credentials.json.
`publish` validates a pack locally, then uploads it as a .tar.gz to /api/publish. The site's
registry workflow runs `release` and `site check` again and opens the pull request.

With `--evidence`, the upload also carries attestations from a test build of the pack, in
`.evidence/` (a dot folder, so not part of the pack), with each runner's public key. The
registry places them beside the pack, where its page lists them as evidence.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from cryptography.hazmat.primitives import serialization

from . import USER_AGENT, keys
from .attest import AttestError, verify_attestation
from .digest import contract_digest, hex_of
from .pack import _component_dirs, validate_pack
from .registry import PACK_MANIFEST_FILE, PACK_REF_RE, RegistryError, _manifest, make_tarball

DEFAULT_SITE = "https://symbola.sh"
MAX_UPLOAD = 5 * 1024 * 1024
EVIDENCE_DIR = ".evidence"


class PublishError(Exception):
    pass


def credentials_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "symbolon" / "credentials.json"


def _request(url: str, data: bytes | None = None, headers: dict | None = None, method: str | None = None) -> dict:
    req = urllib.request.Request(url, data=data, headers={"accept": "application/json", "user-agent": USER_AGENT,
                                                          **(headers or {})}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            message = json.loads(e.read()).get("error") or e.reason
        except (ValueError, AttributeError):
            message = e.reason
        raise PublishError(f"{url}: {message}") from None
    except (urllib.error.URLError, OSError) as e:
        raise PublishError(f"could not reach {url}: {e}") from None


def _json(url: str, body: dict, headers: dict | None = None) -> dict:
    return _request(url, json.dumps(body).encode(), {"content-type": "application/json", **(headers or {})})


@dataclass
class DeviceCode:
    user_code: str
    verification_uri: str
    device_code: str
    interval: int
    expires_in: int


def start_login(site: str) -> tuple[str, DeviceCode]:
    """Ask GitHub for a device code for the site's app; returns the client id and the code."""
    client_id = _request(f"{site}/api/cli/config")["client_id"]
    d = _request("https://github.com/login/device/code",
                 urllib.parse.urlencode({"client_id": client_id}).encode())
    return client_id, DeviceCode(d["user_code"], d["verification_uri"], d["device_code"],
                                 int(d.get("interval", 5)), int(d.get("expires_in", 900)))


def finish_login(site: str, client_id: str, code: DeviceCode, name: str,
                 sleep: Callable[[float], None] = time.sleep) -> dict:
    """Wait until the person approves the code on github.com, then get a Symbola token and save it."""
    interval, waited = code.interval, 0
    while waited < code.expires_in:
        sleep(interval)
        waited += interval
        t = _request("https://github.com/login/oauth/access_token", urllib.parse.urlencode({
            "client_id": client_id, "device_code": code.device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code"}).encode())
        if "access_token" in t:
            got = _json(f"{site}/api/cli/token", {"github_token": t["access_token"], "name": name})
            save_credentials(site, got)
            return got
        if t.get("error") == "slow_down":
            interval = int(t.get("interval", interval + 5))
        elif t.get("error") != "authorization_pending":
            raise PublishError(f"GitHub sign-in failed: {t.get('error_description') or t.get('error')}")
    raise PublishError("the code expired before it was approved; run `symbola login` again")


def save_credentials(site: str, got: dict) -> Path:
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(path.read_text()) if path.is_file() else {}
    data[site] = {"token": got["token"], "login": got["login"]}
    path.write_text(json.dumps(data, indent=2) + "\n")
    path.chmod(0o600)
    return path


def logout(site: str) -> bool:
    path = credentials_path()
    data = json.loads(path.read_text()) if path.is_file() else {}
    if site not in data:
        return False
    del data[site]
    path.write_text(json.dumps(data, indent=2) + "\n")
    return True


def token_for(site: str) -> str:
    if os.environ.get("SYMBOLON_PUBLISH_TOKEN"):
        return os.environ["SYMBOLON_PUBLISH_TOKEN"]
    path = credentials_path()
    data = json.loads(path.read_text()) if path.is_file() else {}
    if site not in data:
        raise PublishError(f"not signed in to {site}; run `symbola login` (or set SYMBOLON_PUBLISH_TOKEN)")
    return data[site]["token"]


def evidence_files(spec: Path, evidence: Path) -> dict[str, bytes]:
    """Attestations in `evidence` that cover this pack's components, with their runners' keys.

    Each must verify and name a component of the pack as it is now; anything else is
    refused here rather than by the registry. Keys are written from the attestations.
    """
    digests = {hex_of(contract_digest(d)): name for name, d in _component_dirs(Path(spec)).items()}
    found = sorted(Path(evidence).rglob("*.json"))
    if not found:
        raise PublishError(f"{evidence}: no attestations (*.json); make them with `symbola attest` or `symbola replicate`")
    files, runners = {}, {}
    for path in found:
        try:
            envelope = json.loads(path.read_text())
            check = verify_attestation(envelope)
        except (AttestError, ValueError) as e:
            raise PublishError(f"{path}: {e}") from None
        if check.problems:
            raise PublishError(f"{path}: {'; '.join(check.problems)}")
        contract = next(c for c in check.predicate["configuration"] if c["name"].startswith("contract:"))
        if contract["digest"]["sha256"] not in digests:
            raise PublishError(f"{path}: attests {contract['name'].split(':', 1)[1]}, which is not a component of "
                               "this pack as it is now; build and attest again")
        files[f"{EVIDENCE_DIR}/{path.name}"] = path.read_bytes()
        runners[check.keyid] = check.predicate["symbolon"]["runner"]["publicKey"]
    for n, (kid, b64) in enumerate(sorted(runners.items()), 1):
        pem = keys.public_from_b64(b64).public_bytes(serialization.Encoding.PEM,
                                                      serialization.PublicFormat.SubjectPublicKeyInfo)
        files[f"{EVIDENCE_DIR}/runner-{n}.pub"] = pem
    return files


def package(spec: Path, evidence: Path | None = None) -> tuple[str, bytes]:
    """Validate a pack folder and return its id and a .tar.gz of its files (and evidence)."""
    spec = Path(spec)
    if not (spec / PACK_MANIFEST_FILE).is_file():
        raise PublishError(f"{spec}: no {PACK_MANIFEST_FILE}; is this the folder `symbola pack init` made?")
    report = validate_pack(spec)
    if not report.ok:
        bad = "; ".join(f"{c.name}: {c.detail}" for c in report.checks if not c.ok)
        raise PublishError(f"pack validate fails: {bad}")
    pack_id = _manifest(spec).get("id", "")
    if not PACK_REF_RE.match(pack_id):
        raise PublishError(f"{PACK_MANIFEST_FILE}: id must look like 'owner/name', got {pack_id!r}")
    try:
        extra = evidence_files(spec, evidence) if evidence else None
        tarball = make_tarball(spec, pack_id.split("/")[1], extra)
    except RegistryError as e:
        raise PublishError(str(e)) from None
    if len(tarball) > MAX_UPLOAD:
        raise PublishError(f"the pack is {len(tarball) // 1024} KB packed; the limit is {MAX_UPLOAD // 1024 // 1024} MB")
    return pack_id, tarball


def publish(spec: Path, site: str, evidence: Path | None = None) -> dict:
    """Upload a pack; returns the API's answer ({request, url})."""
    token = token_for(site)
    _, tarball = package(spec, evidence)
    return _request(f"{site}/api/publish", tarball,
                    {"authorization": f"Bearer {token}", "content-type": "application/gzip"}, method="POST")


def request_state(site: str, request_id: str) -> dict:
    return _request(f"{site}/api/requests/{request_id}", headers={"authorization": f"Bearer {token_for(site)}"})["request"]
