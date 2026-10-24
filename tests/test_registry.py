import json
import shutil

import pytest
from typer.testing import CliRunner

from symbolon import keys
from symbolon.cli import app
from symbolon.pack import validate_pack
from symbolon.registry import RegistryError, build_site, pack_digest, pull, scaffold_pack

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
