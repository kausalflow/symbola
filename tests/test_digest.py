from symbolon.digest import contract_digest, contract_files


def test_digest_is_stable(contract):
    assert contract_digest(contract) == contract_digest(contract)
    assert contract_digest(contract).startswith("sha256:")


def test_digest_changes_with_content(contract):
    before = contract_digest(contract)
    (contract / "examples.jsonl").write_text((contract / "examples.jsonl").read_text() + "\n")
    assert contract_digest(contract) != before


def test_digest_changes_with_file_name(contract):
    before = contract_digest(contract)
    (contract / "reference" / "impl.py").rename(contract / "reference" / "other.py")
    assert contract_digest(contract) != before


def test_digest_ignores_caches_and_hidden_files(contract):
    before = contract_digest(contract)
    (contract / "__pycache__").mkdir(exist_ok=True)
    (contract / "__pycache__" / "x.pyc").write_bytes(b"junk")
    (contract / ".hypothesis").mkdir()
    (contract / ".hypothesis" / "db").write_text("junk")
    (contract / "notes.pyc").write_bytes(b"junk")
    assert contract_digest(contract) == before


def test_digest_normalizes_line_endings(contract):
    before = contract_digest(contract)
    path = contract / "schema.py"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert contract_digest(contract) == before


def test_digest_is_independent_of_location(contract, tmp_path):
    import shutil
    moved = tmp_path / "elsewhere"
    shutil.copytree(contract, moved)
    assert contract_digest(moved) == contract_digest(contract)


def test_files_sorted_by_posix_path(contract):
    names = [p.relative_to(contract).as_posix() for p in contract_files(contract)]
    assert names == sorted(names)
    assert "schema/input.json" in names
