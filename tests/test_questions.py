import json
import tomllib

import pytest
from typer.testing import CliRunner

from symbola.cli import app
from symbola.extract import sync_components
from symbola.pack import validate_pack
from symbola.questions import QuestionError, answer, confirm, review, unanswered
from symbola.registry import scaffold_pack
from symbola.scaffold import scaffold
from symbola.validate import regenerate_schema

runner = CliRunner()

QUESTIONS = '''
[[question]]
id = "shout.keeps-digits"
ask = "Shouting 'r2d2': are digits kept?"
component = "upper"
input = '{"text": "r2d2"}'
recommended = "a"

[[question.choice]]
key = "a"
label = "Yes, digits stay"
statement = "Digits pass through unchanged."
output = { text = "R2D2" }

[[question.choice]]
key = "b"
label = "No, digits are dropped"
statement = "Digits are removed."
output = '{"text": "RD"}'

[[question]]
id = "shout.no-accounts"
ask = "Does the app need user accounts?"
recommended = "a"
unchecked = "a product-level check that no sign-in screen exists"

[[question.choice]]
key = "a"
label = "No accounts"
statement = "The app has no user accounts."

[[question.choice]]
key = "b"
label = "Accounts"
statement = "Users sign in."
'''


@pytest.fixture
def pack(tmp_path):
    root = scaffold_pack("acme/shout", tmp_path / "spec")
    regenerate_schema(scaffold("acme/upper", root / "components"))
    (root / ".symbolon").mkdir()
    (root / ".symbolon" / "questions.toml").write_text(QUESTIONS)
    return root


def obligations(pack):
    return {o["id"]: o for o in tomllib.loads((pack / "obligations.toml").read_text())["obligation"]}


def test_init_inside_a_pack_uses_the_pack_layout(pack):
    assert (pack / "components" / "upper" / "versions" / "1" / "symbolon.toml").is_file()


def test_a_pick_becomes_a_decided_obligation_with_an_example(pack):
    o = answer(pack, "shout.keeps-digits", "a")
    assert o["status"] == "decided" and o["checks"] == ["upper#example:4"]
    line = (pack / "components" / "upper" / "versions" / "1" / "examples.jsonl").read_text().splitlines()[3]
    assert json.loads(line)["output"] == {"text": "R2D2"}
    assert list(obligations(pack)) == ["shout.keeps-digits"], "the placeholder is replaced"
    assert validate_pack(pack).ok


def test_default_takes_the_recommended_choice(pack):
    o = answer(pack, "shout.keeps-digits", "default")
    assert o["status"] == "default" and o["statement"] == "Digits pass through unchanged."


def test_open_has_no_check_and_product_questions_are_unchecked(pack):
    assert "checks" not in answer(pack, "shout.keeps-digits", "open")
    o = answer(pack, "shout.no-accounts", "a")
    assert o["unchecked"].startswith("a product-level check")
    assert [q.id for q in unanswered(pack)] == []


def test_an_answer_is_recorded_once(pack):
    answer(pack, "shout.keeps-digits", "a")
    with pytest.raises(QuestionError, match="already answered"):
        answer(pack, "shout.keeps-digits", "b")
    with pytest.raises(QuestionError, match="no choice 'c'"):
        answer(pack, "shout.no-accounts", "c")


def test_a_component_question_needs_an_input(pack):
    path = pack / ".symbolon" / "questions.toml"
    path.write_text(path.read_text().replace("input = '{\"text\": \"r2d2\"}'\n", ""))
    with pytest.raises(QuestionError, match="needs the input"):
        unanswered(pack)


def test_contradicting_examples_fail_pack_validate(pack):
    answer(pack, "shout.keeps-digits", "a")
    examples = pack / "components" / "upper" / "versions" / "1" / "examples.jsonl"
    examples.write_text(examples.read_text() + '{"input": {"text": "r2d2"}, "output": {"text": "RD"}}\n')
    sync_components(pack)
    failed = {c.name: c.detail for c in validate_pack(pack).checks if not c.ok}
    assert "examples 4 and 5 have the same input" in failed["examples do not contradict each other"]


def test_cli_questions_and_answer(pack):
    result = runner.invoke(app, ["blueprint", "questions", str(pack)])
    assert result.exit_code == 0 and "(recommended)" in result.output and "2 unanswered" in result.output
    result = runner.invoke(app, ["blueprint", "answer", str(pack), "shout.keeps-digits", "b"])
    assert result.exit_code == 0, result.output
    assert "1 unanswered" in runner.invoke(app, ["blueprint", "questions", str(pack)]).output


def test_review_lists_what_people_must_settle(pack):
    answer(pack, "shout.keeps-digits", "default")
    todo = review(pack)
    assert [q.id for q in todo["questions"]] == ["shout.no-accounts"]
    assert [o["id"] for o in todo["defaults"]] == ["shout.keeps-digits"]
    assert todo["open"] == []


def test_confirm_keeps_or_leaves_open_a_default(pack):
    answer(pack, "shout.keeps-digits", "default")
    answer(pack, "shout.no-accounts", "default")
    header = (pack / "obligations.toml").read_text().split("[[obligation]]")[0]
    o = confirm(pack, "shout.keeps-digits")
    assert o["status"] == "decided" and o["checks"] == ["upper#example:4"]
    o = confirm(pack, "shout.no-accounts", to="open")
    assert o["status"] == "open" and "unchecked" not in o
    found = obligations(pack)
    assert found["shout.keeps-digits"]["status"] == "decided" and found["shout.no-accounts"]["status"] == "open"
    assert (pack / "obligations.toml").read_text().startswith(header), "comments before the first obligation stay"
    assert validate_pack(pack).ok
    with pytest.raises(QuestionError, match="not default"):
        confirm(pack, "shout.keeps-digits")
    with pytest.raises(QuestionError, match="no obligation"):
        confirm(pack, "shout.nope")


def test_cli_review_and_confirm(pack):
    answer(pack, "shout.keeps-digits", "default")
    result = runner.invoke(app, ["blueprint", "review", str(pack)])
    assert result.exit_code == 0, result.output
    assert "Questions to answer (1)" in result.output and "[shout.no-accounts]" in result.output
    assert "Decisions to confirm (1)" in result.output and "Digits pass through unchanged." in result.output
    assert "2 to settle." in result.output
    data = json.loads(runner.invoke(app, ["blueprint", "review", str(pack), "--json"]).output)
    assert [o["id"] for o in data["defaults"]] == ["shout.keeps-digits"]
    result = runner.invoke(app, ["blueprint", "confirm", str(pack), "shout.keeps-digits"])
    assert result.exit_code == 0 and "shout.keeps-digits: decided" in result.output
    assert runner.invoke(app, ["blueprint", "confirm", str(pack), "shout.keeps-digits"]).exit_code == 1
