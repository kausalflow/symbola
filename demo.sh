#!/usr/bin/env bash
# Walk through MVP step 1. Run from the repo root after `pip install -e .`.
set -u
work=$(mktemp -d)
step() { printf '\n\033[1m$ %s\033[0m\n' "$*"; "$@"; }

echo "== 1. Scaffold a new contract. It validates out of the box."
step symbolon init acme/shout --root "$work/contracts" --author "L"
step symbolon validate "$work/contracts/acme/shout/1"

echo; echo "== 2. A careless spec is rejected: these properties only check the output type."
cat > "$work/contracts/acme/shout/1/properties.py" <<'PY'
from hypothesis import given, strategies as st
from schema import Input

@given(text=st.text())
def test_returns_text(impl, text):
    assert isinstance(impl(Input(text=text)).text, str)
PY
step symbolon validate "$work/contracts/acme/shout/1"

echo; echo "== 3. The three seed contracts are valid."
for c in date-parse csv-to-records unit-convert; do
  step symbolon validate "contracts/core/$c/1"
done

echo; echo "== 4. A plausible one-shot implementation looks right but breaks the contract."
step symbolon test contracts/core/date-parse/1 examples/impls/date_parse_strptime.py

echo; echo "== 5. An independently written implementation passes the same contract."
step symbolon test contracts/core/date-parse/1 examples/impls/date_parse_strict.py

echo; echo "== 6. The digest depends only on content: a copy elsewhere has the same identity."
cp -r contracts/core/date-parse/1 "$work/copy"
step symbolon digest contracts/core/date-parse/1
step symbolon digest "$work/copy"

rm -rf "$work"
