import pytest

from symbolon.validate import check_impl, validate

from .conftest import SEEDS


def failed(report):
    return [c for c in report.checks if not c.ok]


def test_scaffold_is_valid(contract):
    report = validate(contract)
    assert report.ok, failed(report)
    assert report.alias == "test/upper@1"
    assert report.digest.startswith("sha256:")


@pytest.mark.parametrize("manifest", SEEDS, ids=lambda p: p.parent.parent.name)
def test_seed_contracts_are_valid(manifest):
    report = validate(manifest.parent)
    assert report.ok, failed(report)


def test_missing_files(contract):
    (contract / "properties.py").unlink()
    report = validate(contract)
    assert not report.ok
    assert "properties.py" in failed(report)[0].detail


def test_invalid_manifest(contract):
    path = contract / "symbolon.toml"
    path.write_text(path.read_text().replace('regenerability = "disposable"', 'regenerability = "sometimes"'))
    report = validate(contract)
    assert failed(report)[0].name == "symbolon.toml is valid"
    assert "regenerability" in failed(report)[0].detail


def test_schema_drift_is_caught(contract):
    path = contract / "schema.py"
    path.write_text(path.read_text().replace("    text: str\n", "    text: str\n    loud: bool = True\n", 1))
    report = validate(contract)
    assert failed(report)[0].name == "schema/*.json matches schema.py"


def test_example_must_match_schema(contract):
    path = contract / "examples.jsonl"
    path.write_text(path.read_text() + '{"input": {"txt": "x"}, "output": {"text": "X"}}\n')
    report = validate(contract)
    assert failed(report)[0].name == "examples.jsonl is valid"


def test_needs_two_distinct_outputs(contract):
    (contract / "examples.jsonl").write_text('{"input": {"text": "a"}, "output": {"text": "A"}}\n')
    report = validate(contract)
    assert "two examples" in failed(report)[0].detail


def test_reference_must_pass(contract):
    (contract / "reference" / "impl.py").write_text('def run(input):\n    return {"text": input["text"]}\n')
    report = validate(contract)
    assert failed(report)[0].name == "spec passes against reference implementation"


def test_property_must_take_impl(contract):
    (contract / "properties.py").write_text("def test_x(thing):\n    pass\n")
    report = validate(contract)
    assert "impl" in failed(report)[0].detail


def test_settings_in_properties_rejected(contract):
    path = contract / "properties.py"
    text = path.read_text().replace(
        "@given(text=ascii_text)\ndef test_preserves_length",
        "from hypothesis import settings\n\n@settings(max_examples=1)\n@given(text=ascii_text)\ndef test_preserves_length",
    )
    path.write_text(text)
    report = validate(contract)
    assert "@settings" in failed(report)[0].detail


def test_vacuous_spec_rejected(contract):
    # Properties that only check the output type pass against a constant stub.
    (contract / "properties.py").write_text(
        "from hypothesis import given, strategies as st\n"
        "from schema import Input\n\n"
        "@given(text=st.text())\n"
        "def test_returns_text(impl, text):\n"
        "    assert isinstance(impl(Input(text=text)).text, str)\n"
    )
    report = validate(contract)
    bad = failed(report)
    assert bad[0].name == "vacuity: properties reject an implementation that returns a constant"


def test_contract_code_runs_out_of_process(contract):
    # A contract that kills its interpreter must not take the CLI down with it.
    (contract / "schema.py").write_text("import os\nos._exit(3)\n")
    report = validate(contract)
    assert failed(report)[0].name == "contract code runs"


def test_check_impl_reports_failures(copy_seed, tmp_path):
    root = copy_seed("core/date-parse")
    impl = tmp_path / "lenient.py"
    impl.write_text(
        "from datetime import datetime\n"
        "F = {'ISO': '%Y-%m-%d', 'en-US': '%m/%d/%Y', 'en-GB': '%d/%m/%Y', 'de-DE': '%d.%m.%Y'}\n"
        "def run(input):\n"
        "    return {'date': datetime.strptime(input['text'].strip(), F[input['locale']]).date().isoformat()}\n"
    )
    result = check_impl(root, impl)
    assert not result["passed"]
    bad = {c["name"] for c in result["examples"] + result["properties"] if not c["ok"]}
    assert "test_iso_requires_two_digit_month_and_day" in bad


def test_check_impl_passes_independent_implementation(copy_seed):
    from .conftest import REPO
    root = copy_seed("core/date-parse")
    result = check_impl(root, REPO / "examples" / "impls" / "date-parse-strict" / "impl.py")
    assert result["passed"]


def test_check_impl_missing_entrypoint(copy_seed, tmp_path):
    root = copy_seed("core/date-parse")
    impl = tmp_path / "empty.py"
    impl.write_text("def parse(x):\n    return x\n")
    assert "entrypoint" in check_impl(root, impl)["error"]
