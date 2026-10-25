import random
import textwrap

import pytest
from hypothesis import given, strategies as st

from symbola.manifest import Statistical
from symbola.spec import run_statistical
from symbola.validate import check_impl, regenerate_schema, validate

MANIFEST = '''\
[contract]
id = "test/noise"
version = 1
title = "Standard normal draws"
description = "n independent draws from N(0, 1), reproducible for a seed."
regenerability = "disposable"
license = "Apache-2.0"
authors = ["you@example.com"]

[spec]
max_examples = 20

[spec.statistical.test_draws_have_mean_zero]
at_least = -0.02
at_most = 0.02

[spec.statistical.test_draws_have_unit_spread]
at_least = 0.97
at_most = 1.03
samples = 50
'''

SCHEMA = '''\
from pydantic import BaseModel


class Input(BaseModel):
    seed: int
    n: int


class Output(BaseModel):
    values: list[float]
'''

PROPERTIES = '''\
import statistics

from hypothesis import given, strategies as st

from schema import Input


@given(st.integers(0, 10**6), st.integers(2, 50))
def test_n_draws_and_the_same_seed_repeats(impl, seed, n):
    a = impl(Input(seed=seed, n=n)).values
    assert len(a) == n and a == impl(Input(seed=seed, n=n)).values


def test_draws_have_mean_zero(impl, seed):
    return statistics.fmean(impl(Input(seed=seed, n=1000)).values)


def test_draws_have_unit_spread(impl, seed):
    return statistics.stdev(impl(Input(seed=seed, n=1000)).values)
'''


def impl_source(std=1.0, shift=0.0):
    return textwrap.dedent(f'''\
        import random


        def run(input):
            rng = random.Random(input["seed"])
            return {{"values": [rng.gauss({shift}, {std}) for _ in range(input["n"])]}}
        ''')


@pytest.fixture
def noise(tmp_path):
    root = tmp_path / "noise"
    (root / "reference").mkdir(parents=True)
    (root / "symbolon.toml").write_text(MANIFEST)
    (root / "schema.py").write_text(SCHEMA)
    (root / "properties.py").write_text(PROPERTIES)
    (root / "examples.jsonl").write_text(
        '{"input": {"seed": 1, "n": 0}, "output": {"values": []}}\n'
        '{"input": {"seed": 1, "n": 1}, "output": {"values": [1.2881847531554629]}}\n')
    (root / "reference" / "impl.py").write_text(impl_source())
    regenerate_schema(root)
    return root


def write_impl(tmp_path, **kw):
    path = tmp_path / "impl.py"
    path.write_text(impl_source(**kw))
    return path


def by_name(result):
    return {c["name"]: c for c in result["examples"] + result["properties"]}


def test_statistical_contract_validates(noise):
    report = validate(noise)
    assert report.ok, [c for c in report.checks if not c.ok]


def test_correct_implementation_passes_and_reports_the_interval(noise, tmp_path):
    result = check_impl(noise, write_impl(tmp_path))
    assert result["passed"], result
    detail = by_name(result)["test_draws_have_unit_spread"]["detail"]
    assert "over 50 seeds" in detail and "must be between 0.97 and 1.03" in detail


def test_a_wrong_spread_fails_only_the_statistical_check(noise, tmp_path):
    checks = by_name(check_impl(noise, write_impl(tmp_path, std=1.05)))
    assert not checks["test_draws_have_unit_spread"]["ok"]
    assert checks["test_draws_have_mean_zero"]["ok"] and checks["test_n_draws_and_the_same_seed_repeats"]["ok"]


def test_a_small_bias_fails(noise, tmp_path):
    assert not by_name(check_impl(noise, write_impl(tmp_path, shift=0.03)))["test_draws_have_mean_zero"]["ok"]


def test_a_statistical_property_must_return_a_number(noise, tmp_path):
    path = noise / "properties.py"
    path.write_text(path.read_text().replace("return statistics.fmean", "statistics.fmean"))
    detail = by_name(check_impl(noise, write_impl(tmp_path)))["test_draws_have_mean_zero"]["detail"]
    assert "seed 0: returned None" in detail


def test_a_declared_name_must_exist(noise):
    path = noise / "symbolon.toml"
    path.write_text(path.read_text() + "\n[spec.statistical.test_missing]\nat_least = 0\n")
    bad = [c for c in validate(noise).checks if not c.ok]
    assert "properties.py has no test_missing" in bad[0].detail


def test_a_statistical_property_takes_impl_and_seed(noise):
    path = noise / "properties.py"
    path.write_text(path.read_text().replace("def test_draws_have_unit_spread(impl, seed)",
                                             "def test_draws_have_unit_spread(impl, seed, n)"))
    bad = [c for c in validate(noise).checks if not c.ok]
    assert "takes exactly (impl, seed)" in bad[0].detail


@pytest.mark.parametrize("band, message", [({}, "give at_least, at_most or both"),
                                           ({"at_least": 2, "at_most": 1}, "at_least is above at_most")])
def test_a_statistical_check_needs_a_band(band, message):
    with pytest.raises(ValueError, match=message):
        Statistical(**band)


def test_false_alarms_stay_near_alpha_and_real_violations_are_caught():
    # The true mean sits exactly on the limit, the worst case for false alarms.
    def on_the_limit(impl, seed):
        return random.Random(seed).gauss(0.0, 1.0)

    check = Statistical(at_least=0.0, samples=50, alpha=0.05)
    alarms = sum(not run_statistical("t", on_the_limit, None, check, base * 50).ok for base in range(400))
    assert alarms < 40  # expected 20

    def below(impl, seed):
        return random.Random(seed).gauss(-0.6, 1.0)

    assert not any(run_statistical("t", below, None, check, base * 50).ok for base in range(50))


def test_given_is_refused_on_a_statistical_property():
    @given(st.integers())
    def prop(impl, seed):
        return 0.0

    assert "do not use @given" in run_statistical("t", prop, None, Statistical(at_least=0), 0).detail
