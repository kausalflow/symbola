import json
import shutil

import pytest
from typer.testing import CliRunner

from symbolon import keys
from symbolon.cli import app
from symbolon.pack import validate_pack
from symbolon.registry import RegistryError, build_site, check_registry, pack_digest, pull, release, scaffold_pack

from .conftest import REPO

LIGHTKONE = REPO / "packs" / "kausalflow" / "lightkone" / "versions" / "1"
runner = CliRunner()


@pytest.fixture
def registry(tmp_path):
    """A registry with lightkone at versions 1 and 2; only 2 should be published."""
    root = tmp_path / "packs"
    for n in (1, 2):
        shutil.copytree(LIGHTKONE, root / "kausalflow" / "lightkone" / "versions" / str(n),
                        ignore=shutil.ignore_patterns("__pycache__"))
    brief = root / "kausalflow" / "lightkone" / "versions" / "2" / "BRIEF.md"
    brief.write_text(brief.read_text() + "\nVersion two.\n")
    return root


@pytest.fixture
def site(registry, tmp_path):
    out = tmp_path / "site"
    build_site(registry, out)
    return out


def test_pack_init_passes_pack_validate(tmp_path):
    target = scaffold_pack("acme/demo", tmp_path / "spec", "me@example.com")
    report = validate_pack(target)
    assert report.ok, [c for c in report.checks if not c.ok]
    assert report.summary["by_status"]["open"] == 1


def test_pack_init_refuses_a_bad_id_or_a_used_folder(tmp_path):
    with pytest.raises(ValueError):
        scaffold_pack("not-an-id", tmp_path / "a")
    scaffold_pack("acme/demo", tmp_path / "b")
    with pytest.raises(FileExistsError):
        scaffold_pack("acme/demo", tmp_path / "b")


def test_site_publishes_only_the_latest_version(site, registry):
    index = json.loads((site / "index.json").read_text())
    (entry,) = index["packs"]
    assert entry["id"] == "kausalflow/lightkone" and entry["version"] == 2
    assert entry["digest"] == pack_digest(registry / "kausalflow" / "lightkone" / "versions" / "2")
    files = site / "packs" / "kausalflow" / "lightkone"
    assert "Version two." in (files / "files" / "BRIEF.md").read_text()
    assert "Version two." in (files / "pack.md").read_text()
    assert "kausalflow/lightkone" in (site / "llms.txt").read_text()
    assert "files/obligations.toml" in (files / "llms.txt").read_text()


def test_tarball_is_byte_identical_across_builds(registry, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    build_site(registry, a)
    build_site(registry, b)
    rel = "packs/kausalflow/lightkone/latest.tar.gz"
    assert (a / rel).read_bytes() == (b / rel).read_bytes()


def test_site_refuses_a_pack_with_holdout_files(registry, tmp_path):
    held = registry / "kausalflow" / "lightkone" / "versions" / "2" / "holdout" / "x.jsonl"
    held.parent.mkdir()
    held.write_text("{}\n")
    with pytest.raises(RegistryError, match="holdout"):
        build_site(registry, tmp_path / "site")


def test_site_refuses_an_invalid_pack(registry, tmp_path):
    (registry / "kausalflow" / "lightkone" / "versions" / "2" / "BRIEF.md").write_text("# Nothing\n")
    with pytest.raises(RegistryError, match="pack validate fails"):
        build_site(registry, tmp_path / "site")


def test_pull_unpacks_a_pack_with_the_listed_digest(site, tmp_path):
    got = pull("kausalflow/lightkone", str(site), tmp_path / "lk")
    assert got.version == 2
    assert pack_digest(tmp_path / "lk") == got.digest
    assert validate_pack(tmp_path / "lk").ok


def test_pull_rejects_a_tampered_tarball(site, tmp_path):
    tarball = site / "packs" / "kausalflow" / "lightkone" / "latest.tar.gz"
    tarball.write_bytes(tarball.read_bytes() + b"x")
    with pytest.raises(RegistryError, match="sha256"):
        pull("kausalflow/lightkone", str(site), tmp_path / "lk")


def test_pull_does_not_take_a_version(site, tmp_path):
    with pytest.raises(RegistryError, match="only the latest"):
        pull("kausalflow/lightkone@1", str(site), tmp_path / "lk")


def test_signed_pull_checks_the_publisher_key(registry, tmp_path):
    key = keys.generate(tmp_path / "keys" / "publisher.key")
    other = keys.generate(tmp_path / "keys" / "other.key")
    build_site(registry, tmp_path / "site", key_path=key)
    got = pull("kausalflow/lightkone", str(tmp_path / "site"), tmp_path / "lk", trust=keys.public_path(key))
    assert got.version == 2
    with pytest.raises(RegistryError, match="signature"):
        pull("kausalflow/lightkone", str(tmp_path / "site"), tmp_path / "lk2", trust=keys.public_path(other))


def test_cli_init_build_and_pull(registry, tmp_path):
    r = runner.invoke(app, ["pack", "init", "acme/demo", "--dir", str(tmp_path / "spec")])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["site", "build", str(registry), "--out", str(tmp_path / "site")])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["pull", "kausalflow/lightkone", "--registry", str(tmp_path / "site"),
                            "--dest", str(tmp_path / "lk")])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "lk" / "AGENTS.md").is_file()


@pytest.fixture
def publisher(tmp_path):
    return keys.generate(tmp_path / "keys" / "publisher.key")


def test_release_freezes_signs_and_claims_the_owner(tmp_path, publisher):
    spec = scaffold_pack("acme/demo", tmp_path / "spec")
    reg = tmp_path / "packs"
    r = release(spec, reg, publisher)
    assert r.created and r.version == 1
    assert (reg / "acme" / "publisher.pub").is_file()
    assert (reg / "acme" / "demo" / "signatures" / "1.json").is_file()
    assert pack_digest(reg / "acme" / "demo" / "versions" / "1") == pack_digest(spec) == r.digest
    assert check_registry(reg) == []


def test_release_of_unchanged_content_is_a_no_op(tmp_path, publisher):
    spec = scaffold_pack("acme/demo", tmp_path / "spec")
    reg = tmp_path / "packs"
    release(spec, reg, publisher)
    assert not release(spec, reg, publisher).created
    (spec / "BRIEF.md").write_text((spec / "BRIEF.md").read_text() + "\nMore.\n")
    r = release(spec, reg, publisher)
    assert r.created and r.version == 2
    assert 'version = 2' in (reg / "acme" / "demo" / "versions" / "2" / "symbolon-pack.toml").read_text()
    assert check_registry(reg) == []


def test_release_refuses_another_owners_key(tmp_path, publisher):
    reg = tmp_path / "packs"
    release(scaffold_pack("acme/demo", tmp_path / "spec"), reg, publisher)
    intruder = keys.generate(tmp_path / "keys" / "intruder.key")
    with pytest.raises(RegistryError, match="another key"):
        release(scaffold_pack("acme/other", tmp_path / "spec2"), reg, intruder)


def test_check_registry_rejects_an_edited_signed_version(tmp_path, publisher):
    reg = tmp_path / "packs"
    release(scaffold_pack("acme/demo", tmp_path / "spec"), reg, publisher)
    brief = reg / "acme" / "demo" / "versions" / "1" / "BRIEF.md"
    brief.write_text(brief.read_text() + "\nTampered.\n")
    with pytest.raises(RegistryError, match="signs version 1"):
        check_registry(reg)


def test_check_registry_warns_about_unsigned_owners(registry):
    assert check_registry(registry) == ["kausalflow/lightkone: unsigned; kausalflow/ has no publisher.pub"]


def _price(registry, amount=1900):
    manifest = registry / "kausalflow" / "lightkone" / "versions" / "2" / "symbolon-pack.toml"
    manifest.write_text(manifest.read_text() + f'\n[listing]\nprice = {amount}\ncurrency = "eur"\n')


@pytest.fixture
def store(tmp_path):
    """A stand-in for the store Worker: serves private tarballs to one valid token."""
    import http.server
    import threading

    root = tmp_path / "private"

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = root / "packs" / self.path.removeprefix("/download/") / "latest.tar.gz"
            if self.headers.get("Authorization") != "Bearer good" or not path.is_file():
                self.send_response(403)
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(path.read_bytes())

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield root, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_priced_pack_tarball_stays_off_the_public_site(registry, tmp_path, store):
    _price(registry)
    private, url = store
    build_site(registry, tmp_path / "site", private_out=private, store_url=url)
    index = json.loads((tmp_path / "site" / "index.json").read_text())
    assert index["store"] == url and index["packs"][0]["price"] == {"amount": 1900, "currency": "eur"}
    public = tmp_path / "site" / "packs" / "kausalflow" / "lightkone"
    assert not (public / "latest.tar.gz").exists()
    assert (public / "pack.md").is_file() and (public / "latest.sha256").is_file()
    assert (private / "packs" / "kausalflow" / "lightkone" / "latest.tar.gz").is_file()


def test_priced_pack_needs_a_store(registry, tmp_path):
    _price(registry)
    with pytest.raises(RegistryError, match="--private-out and --store-url"):
        build_site(registry, tmp_path / "site")


def test_bad_price_is_refused(registry, tmp_path):
    _price(registry, amount=0)
    with pytest.raises(RegistryError, match="positive integer"):
        build_site(registry, tmp_path / "site", private_out=tmp_path / "p", store_url="https://x")


def test_pull_of_a_priced_pack_needs_a_valid_token(registry, tmp_path, store):
    _price(registry)
    private, url = store
    build_site(registry, tmp_path / "site", private_out=private, store_url=url)
    site = str(tmp_path / "site")
    with pytest.raises(RegistryError, match="costs 19.00 EUR"):
        pull("kausalflow/lightkone", site, tmp_path / "a")
    with pytest.raises(RegistryError, match="could not fetch"):
        pull("kausalflow/lightkone", site, tmp_path / "b", token="bad")
    got = pull("kausalflow/lightkone", site, tmp_path / "c", token="good")
    assert pack_digest(tmp_path / "c") == got.digest


def test_check_registry_accepts_priced_packs(registry):
    _price(registry)
    assert check_registry(registry)
