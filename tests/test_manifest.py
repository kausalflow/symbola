import pytest
from pydantic import ValidationError

from symbola.manifest import Manifest

BASE = {
    "contract": {
        "id": "core/thing",
        "version": 1,
        "title": "Thing",
        "regenerability": "disposable",
        "license": "MIT",
        "authors": ["a"],
    }
}


def with_contract(**changes):
    data = {"contract": {**BASE["contract"], **changes}}
    return Manifest.model_validate(data)


def test_minimal_manifest_gets_defaults():
    m = with_contract()
    assert m.alias == "core/thing@1"
    assert m.entrypoint.function == "run"
    assert m.requires.network == []
    assert m.spec.seed == 0


@pytest.mark.parametrize("bad_id", ["thing", "Core/thing", "core/thing/extra", "core/", "-x/y"])
def test_rejects_bad_ids(bad_id):
    with pytest.raises(ValidationError):
        with_contract(id=bad_id)


def test_sovereign_is_reserved():
    with pytest.raises(ValidationError, match="reserved"):
        with_contract(regenerability="sovereign")


def test_rejects_unknown_keys():
    with pytest.raises(ValidationError):
        Manifest.model_validate({**BASE, "extra": {}})
    with pytest.raises(ValidationError):
        with_contract(colour="blue")


def test_version_must_be_positive():
    with pytest.raises(ValidationError):
        with_contract(version=0)


def test_forked_from_must_be_a_digest():
    with_contract(forked_from="sha256:" + "a" * 64)
    with pytest.raises(ValidationError):
        with_contract(forked_from="core/other@1")
