import json

import pytest

from symbolon.digest import contract_digest
from symbolon.spec import SpecError, load_examples
from symbolon.validate import validate

from .conftest import REPO

SEARCH = REPO / "packs" / "kausalflow" / "lightkone" / "1" / "components" / "search-query" / "1"


def write_examples(contract, *lines):
    (contract / "examples.jsonl").write_text("".join(json.dumps(l) + "\n" for l in lines))


def test_fixture_references_are_replaced(contract):
    (contract / "fixtures").mkdir()
    (contract / "fixtures" / "words.json").write_text('"hello"')
    write_examples(
        contract,
        {"input": {"text": {"$fixture": "words.json"}}, "output": {"text": "HELLO"}},
        {"input": {"text": "a"}, "output": {"text": "A"}},
    )
    examples = load_examples(contract / "examples.jsonl")
    assert examples[0]["input"] == {"text": "hello"}
    assert validate(contract).ok


def test_each_example_gets_its_own_copy(contract):
    (contract / "fixtures").mkdir()
    (contract / "fixtures" / "list.json").write_text("[1, 2]")
    write_examples(contract, *[{"input": {"xs": {"$fixture": "list.json"}}, "output": {}}] * 2)
    a, b = load_examples(contract / "examples.jsonl")
    a["input"]["xs"].append(3)
    assert b["input"]["xs"] == [1, 2]


@pytest.mark.parametrize("name, problem", [
    ("missing.json", "no such file"),
    ("../symbolon.toml", "inside fixtures/"),
    ("/etc/passwd.json", "inside fixtures/"),
    ("notes.txt", "inside fixtures/"),
    (7, "inside fixtures/"),
])
def test_bad_fixture_references_are_rejected(contract, name, problem):
    write_examples(contract, {"input": {"text": {"$fixture": name}}, "output": {"text": ""}})
    with pytest.raises(SpecError, match=problem):
        load_examples(contract / "examples.jsonl")


def test_objects_with_other_keys_are_left_alone(contract):
    write_examples(contract, {"input": {"text": {"$fixture": "x.json", "other": 1}}, "output": {}})
    assert load_examples(contract / "examples.jsonl")[0]["input"]["text"] == {"$fixture": "x.json", "other": 1}


def test_fixtures_are_part_of_the_digest(contract):
    (contract / "fixtures").mkdir()
    (contract / "fixtures" / "a.json").write_text("1")
    before = contract_digest(contract)
    (contract / "fixtures" / "a.json").write_text("2")
    assert contract_digest(contract) != before


def test_lightkone_search_examples_share_one_library():
    examples = load_examples(SEARCH / "examples.jsonl")
    assert all(len(e["input"]["papers"]) == 10 for e in examples)
    assert '"$fixture": "library.json"' in (SEARCH / "examples.jsonl").read_text()
