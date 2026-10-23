import shutil
from pathlib import Path

import pytest

from symbolon.scaffold import scaffold
from symbolon.validate import regenerate_schema

REPO = Path(__file__).resolve().parent.parent
SEEDS = sorted((REPO / "contracts").glob("*/*/versions/*/symbolon.toml"))
assert SEEDS, "no seed contracts found under contracts/<namespace>/<name>/versions/"


@pytest.fixture
def contract(tmp_path) -> Path:
    """A freshly scaffolded, valid contract."""
    target = scaffold("test/upper", tmp_path / "contracts")
    regenerate_schema(target)
    return target


@pytest.fixture
def copy_seed(tmp_path):
    def _copy(contract_id: str) -> Path:
        src = REPO / "contracts" / contract_id / "versions" / "1"
        dst = tmp_path / contract_id.replace("/", "-")
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
        return dst
    return _copy
