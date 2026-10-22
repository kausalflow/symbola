import json
import shutil

import pytest
from typer.testing import CliRunner

from symbolon.cli import app
from symbolon.digest import contract_digest
from symbolon.diff import Member, Reading, chao1, chao_shen_bits, compare_readings, rao, tier

runner = CliRunner()


def test_tiers():
    assert tier({"output": {"a": 1}}, {"output": {"a": 1}}) is None
    assert tier({"output": {"a": [1, 2]}}, {"output": {"a": [2, 1]}}) == "format"
    assert tier({"output": {"a": "X  y"}}, {"output": {"a": "x y"}}) == "format"
    assert tier({"output": {"a": 1}}, {"output": {"a": 2}}) == "value"
    assert tier({"raises": "ValueError"}, {"output": {"a": 1}}) == "value"
    assert tier({"raises": "ValueError"}, {"raises": "KeyError"}) == "value"
    assert tier({"crash": "died"}, {"output": {"a": 1}}) == "crash"


def test_rao_matches_the_toy_model():
    # Paper section 2: shares 0.6, 0.3, 0.1 become 6, 3 and 1 builds of A, B and C.
    labels = ["A"] * 6 + ["B"] * 3 + ["C"]
    d = {("A", "B"): 1, ("A", "C"): 0.05, ("B", "C"): 1}
    distances = {}
    for i, a in enumerate(labels):
        for j, b in enumerate(labels):
            if i != j:
                distances[f"{i}", f"{j}"] = 0 if a == b else d.get((a, b), d.get((b, a)))
    est = rao(distances, {f"{i}": 1.0 for i in range(len(labels))})
    # The U-statistic over 10 builds: sum over distinct pairs, so n/(n-1) times the plug-in 0.426.
    assert est == pytest.approx(0.426 * 10 / 9, abs=1e-9)


def test_rao_needs_two_members():
    assert rao({}, {"a": 1.0}) is None


def test_chao():
    assert chao1([3, 2]) == 2  # nothing seen once: nothing unseen
    assert chao1([1, 1, 1]) == pytest.approx(3 + 2 / 3 * 3 * 2 / 2)
    assert chao_shen_bits([4]) == 0
    assert chao_shen_bits([5, 5]) > 0.99


def test_compare_readings():
    a = Member("a", None, readings=[Reading(point="Repeated year:", considered=["x", "y"], chosen="last wins")])
    b = Member("b", None, readings=[Reading(point="repeated  YEAR:", considered=["x", "y"], chosen="all hold"),
                                    Reading(point="tie order", considered=["x"], chosen="x")])
    r = compare_readings([a, b])
    assert r["points"] == 2 and r["shared"] == 1
    assert r["splits"][0]["chosen"] == {"a": "last wins", "b": "all hold"}


@pytest.fixture
def date_pack(tmp_path, copy_seed):
    """core/date-parse inside a pack, with a reference build and two variants."""
    contract = tmp_path / "pack" / "components" / "date-parse" / "1"
    contract.parent.mkdir(parents=True)
    shutil.move(copy_seed("core/date-parse"), contract)
    (tmp_path / "pack" / "symbolon-pack.toml").write_text("[components]\n")
    (tmp_path / "pack" / "obligations.toml").write_text(
        '[[obligation]]\nid = "date.round-trip"\nstatement = "Every date round-trips, padded or not."\n'
        'status = "decided"\nchecks = ["date-parse#test_round_trips_every_date"]\n'
    )
    ref = (contract / "reference" / "impl.py").read_text()
    builds = {}
    for name, source in {
        "same": ref,
        "gbus": ref.replace('("day", "month", "year")),\n    "de-DE"', '("month", "day", "year")),\n    "de-DE"'),
        "badde": ref.replace("def run(input: dict) -> dict:\n",
                             'def run(input: dict) -> dict:\n    if input["locale"] == "de-DE":\n'
                             '        return {"date": 5}\n'),
    }.items():
        d = tmp_path / "builds" / name
        d.mkdir(parents=True)
        (d / "impl.py").write_text(source)
        (d / "symbolon-impl.toml").write_text(
            f'[implementation]\ncontract = "{contract_digest(contract)}"\nlicense = "MIT"\nauthors = ["test"]\n\n'
            f'[generator]\nmodel = "m-{name}"\nfamily = "f"\n')
        builds[name] = d / "impl.py"
    (tmp_path / "builds" / "gbus" / "readings.toml").write_text(
        '[[reading]]\npoint = "en-GB field order"\nconsidered = ["day first", "month first"]\nchosen = "month first"\n')
    (tmp_path / "builds" / "same" / "readings.toml").write_text(
        '[[reading]]\npoint = "en-gb  field order"\nconsidered = ["day first", "month first"]\nchosen = "day first"\n')
    return contract, builds


def _diff(contract, *impls, extra=()):
    result = runner.invoke(app, ["diff", str(contract), *map(str, impls), "--json",
                                 "--mutations", "100", "--property-cases", "20", "--search", "50", *extra])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_identical_builds_agree(date_pack):
    contract, b = date_pack
    r = _diff(contract, f"a={b['same']}", f"b={contract / 'reference' / 'impl.py'}")
    assert r["rao"]["estimate"] == 0
    assert r["splits"] == [] and r["behaviours"]["observed"] == 1


def test_finds_and_traces_a_split(date_pack):
    contract, b = date_pack
    r = _diff(contract, b["same"].parent, b["gbus"].parent, b["badde"].parent)
    assert r["pool"]["by_how"]["example"] > 0 and r["pool"]["by_how"]["property"] > 0
    assert r["rao"]["estimate"] > 0
    lo, hi = r["rao"]["interval95"]
    assert lo <= r["rao"]["estimate"] <= hi
    assert r["tiers"]["crash"] > 0
    assert sum(s["share_of_ambiguity"] for s in r["splits"]) == pytest.approx(1)
    gbus = [s for s in r["splits"] if ["gbus"] in s["groups"] and len(s["groups"]) == 2]
    assert gbus, r["splits"]
    assert "date.round-trip" in r["ambiguity_map"]["obligations"]
    w = min(gbus, key=lambda s: len(json.dumps(s["witness"]["input"])))["witness"]
    assert w["input"]["locale"] == "en-GB"
    assert r["readings"]["splits"][0]["chosen"] == {"same": "day first", "gbus": "month first"}


def test_reference_is_not_in_the_ensemble(date_pack):
    contract, b = date_pack
    r = _diff(contract, f"ref={contract / 'reference' / 'impl.py'}", b["same"].parent, b["gbus"].parent,
              extra=["--reference", "ref"])
    assert [m["name"] for m in r["ensemble"]] == ["same", "gbus"]
    assert r["to_reference"]["same"] == 0 and r["to_reference"]["gbus"] > 0
    assert r["rao"]["estimate"] == pytest.approx(r["to_reference"]["gbus"])


def test_extra_pool_and_max_ambiguity(date_pack, tmp_path):
    contract, b = date_pack
    pool = tmp_path / "pool.jsonl"
    pool.write_text('{"text": "1.2.2020", "locale": "de-DE"}\n{"input": {"text": " 2020-01-02", "locale": "ISO"}}\n')
    r = _diff(contract, b["same"].parent, b["badde"].parent,
              extra=["--pool", str(pool), "--mutations", "0", "--search", "0", "--property-cases", "0"])
    assert r["pool"]["by_how"]["pool"] == 2
    assert any("pool:pool.jsonl" in s["origins"] for s in r["splits"])
    assert r["ambiguity_map"]["untraced"] >= 1
    result = runner.invoke(app, ["diff", str(contract), str(b["same"].parent), str(b["badde"].parent),
                                 "--max-ambiguity", "0", "--mutations", "20", "--property-cases", "5"])
    assert result.exit_code == 1 and "above --max-ambiguity" in result.output


def test_realistic_pool_is_reported_separately(date_pack, tmp_path):
    contract, b = date_pack
    real = tmp_path / "real.jsonl"
    real.write_text("".join(json.dumps({"text": f"2020-01-{d:02d}", "locale": "ISO"}) + "\n" for d in range(1, 11)))
    r = _diff(contract, b["same"].parent, b["badde"].parent, extra=["--realistic", str(real)])
    assert r["realistic"]["pool"]["inputs"] == 10
    assert r["realistic"]["rao"]["estimate"] == 0  # no de-DE dates in real use
    assert r["rao"]["estimate"] > 0


def test_rejects_duplicate_names(date_pack):
    contract, b = date_pack
    result = runner.invoke(app, ["diff", str(contract), f"x={b['same']}", f"x={b['gbus']}"])
    assert result.exit_code != 0 and "NAME=PATH" in result.output
