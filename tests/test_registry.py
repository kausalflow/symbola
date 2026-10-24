import json
import shutil
import tarfile

import pytest
from typer.testing import CliRunner

from symbolon.digest import contract_digest
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
    assert "parts/tidy-v1.md" in (files / "pack.md").read_text()
    assert "kausalflow/lightkone" in (site / "llms.txt").read_text()
    assert "files/obligations.toml" in (files / "llms.txt").read_text()


def test_pack_md_is_split_into_parts_small_enough_for_one_read(site, tmp_path):
    files = site / "packs" / "kausalflow" / "lightkone"
    core = (files / "pack.md").read_text()
    parts = sorted((files / "parts").glob("*.md"))
    assert [p.name for p in parts][:2] == ["bibtex-export-v1.md", "bibtex-import-v1.md"]
    assert "## obligations.toml" in core and "## components/" not in core
    assert len(core.encode()) < 64_000 and all(len(p.read_bytes()) < 64_000 for p in parts)
    tidy = (files / "parts" / "tidy-v1.md").read_text()
    assert "## components/tidy/versions/1/symbolon.toml" in tidy
    assert "(../files/components/tidy/versions/1/examples.jsonl)" in tidy
    assert "[tidy-v1.tar.gz](tidy-v1.tar.gz)" in tidy and "symbolon keygen" in tidy
    with tarfile.open(files / "parts" / "tidy-v1.tar.gz") as tar:
        tar.extractall(tmp_path / "tidy", filter="data")
    assert contract_digest(tmp_path / "tidy" / "tidy-v1") == contract_digest(
        LIGHTKONE / "components" / "tidy" / "versions" / "1")
    for part in parts:
        assert f"(parts/{part.name})" in core


@pytest.fixture
def attested(registry):
    """Lightkone's attestations beside the registry copy; version 2 changes the tidy contract."""
    shutil.copytree(LIGHTKONE.parent.parent / "attestations", registry / "kausalflow" / "lightkone" / "attestations")
    desc = registry / "kausalflow" / "lightkone" / "versions" / "2" / "components" / "tidy" / "versions" / "1" / "symbolon.toml"
    before = contract_digest(desc.parent)
    desc.write_text(desc.read_text() + "\n# version 2\n")
    manifest = desc.parents[4] / "symbolon-pack.toml"
    manifest.write_text(manifest.read_text().replace(before, contract_digest(desc.parent)))
    return registry


def test_site_shows_checked_evidence_and_keeps_attested_versions(attested, tmp_path):
    site = tmp_path / "site"
    build_site(attested, site)
    files = site / "packs" / "kausalflow" / "lightkone"
    evidence = json.loads((files / "evidence.json").read_text())
    records = {r["file"]: r for r in evidence["attestations"]}
    assert all(r["valid"] for r in records.values())
    assert records["attestations/citation-key.go-1.json"]["covers"] == "latest"
    tidy = records["attestations/tidy.go-1.json"]
    assert tidy["covers"] == "older" and tidy["pack_version"] == 1
    (entry,) = json.loads((site / "index.json").read_text())["packs"]
    assert entry["evidence"]["components_with_passing_build"] == 7
    assert "go-1 rebuild" in entry["evidence"]["builds"]
    (old,) = entry["older"]
    assert old["version"] == 1 and tidy["pack_digest"] == old["digest"]
    assert (files / old["path"]).is_file() and (files / "attestations" / "runner-a.pub").is_file()

    got = pull("kausalflow/lightkone", str(site), tmp_path / "v1", digest=old["digest"])
    assert got.version == 1 and got.digest == old["digest"]
    with pytest.raises(RegistryError, match="no evidence names"):
        pull("kausalflow/lightkone", str(site), tmp_path / "x", digest="sha256:" + "0" * 64)


def test_a_tampered_attestation_is_shown_as_invalid(attested, tmp_path):
    path = attested / "kausalflow" / "lightkone" / "attestations" / "tidy.go-1.json"
    envelope = json.loads(path.read_text())
    envelope["signatures"][0]["sig"] = envelope["signatures"][0]["sig"][::-1]
    path.write_text(json.dumps(envelope))
    build_site(attested, tmp_path / "site")
    evidence = json.loads((tmp_path / "site" / "packs" / "kausalflow" / "lightkone" / "evidence.json").read_text())
    bad = next(r for r in evidence["attestations"] if r["file"].endswith("tidy.go-1.json"))
    assert not bad["valid"] and bad["problems"] and evidence["summary"]["invalid"] == 1


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


def test_cli_init_build_and_pull(registry, tmp_path):
    r = runner.invoke(app, ["pack", "init", "acme/demo", "--dir", str(tmp_path / "spec")])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["site", "build", str(registry), "--out", str(tmp_path / "site")])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["pull", "kausalflow/lightkone", "--registry", str(tmp_path / "site"),
                            "--dest", str(tmp_path / "lk")])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "lk" / "AGENTS.md").is_file()


def test_release_freezes_and_records_the_digest(tmp_path):
    spec = scaffold_pack("acme/demo", tmp_path / "spec")
    reg = tmp_path / "packs"
    r = release(spec, reg)
    assert r.created and r.version == 1
    assert (reg / "acme" / "demo" / "digests.txt").read_text() == f"1 {r.digest}\n"
    assert pack_digest(reg / "acme" / "demo" / "versions" / "1") == pack_digest(spec) == r.digest
    assert check_registry(reg) == []


def test_release_of_unchanged_content_is_a_no_op(tmp_path):
    spec = scaffold_pack("acme/demo", tmp_path / "spec")
    reg = tmp_path / "packs"
    release(spec, reg)
    assert not release(spec, reg).created
    (spec / "BRIEF.md").write_text((spec / "BRIEF.md").read_text() + "\nMore.\n")
    r = release(spec, reg)
    assert r.created and r.version == 2
    assert 'version = 2' in (reg / "acme" / "demo" / "versions" / "2" / "symbolon-pack.toml").read_text()
    assert check_registry(reg) == []


def test_check_registry_rejects_an_edited_released_version(tmp_path):
    reg = tmp_path / "packs"
    release(scaffold_pack("acme/demo", tmp_path / "spec"), reg)
    brief = reg / "acme" / "demo" / "versions" / "1" / "BRIEF.md"
    brief.write_text(brief.read_text() + "\nTampered.\n")
    with pytest.raises(RegistryError, match="version 1 was released as"):
        check_registry(reg)


def test_check_registry_warns_about_packs_without_recorded_digests(registry):
    assert check_registry(registry) == [
        "kausalflow/lightkone: no digests.txt, so edits to released versions are not caught"]


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


def test_priced_pack_previews_only_its_brief_unless_it_asks_for_more(registry, tmp_path, store):
    _price(registry)
    private, url = store
    build_site(registry, tmp_path / "site", private_out=private, store_url=url)
    (entry,) = json.loads((tmp_path / "site" / "index.json").read_text())["packs"]
    public = tmp_path / "site" / "packs" / "kausalflow" / "lightkone"
    assert entry["preview"] == "brief" and not any(f.startswith("components/") for f in entry["files"])
    assert (public / "files" / "BRIEF.md").is_file() and not (public / "files" / "components").exists()
    assert not (public / "parts").exists()
    core = (public / "pack.md").read_text()
    assert "## obligations.toml" in core and "- tidy-v1" in core and "parts/" not in core

    manifest = registry / "kausalflow" / "lightkone" / "versions" / "2" / "symbolon-pack.toml"
    manifest.write_text(manifest.read_text() + 'preview = "full"\n')
    build_site(registry, tmp_path / "full", private_out=private, store_url=url)
    assert (tmp_path / "full" / "packs" / "kausalflow" / "lightkone" / "parts" / "tidy-v1.md").is_file()


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
