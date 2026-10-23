#!/usr/bin/env bash
# Walk through MVP steps 1 and 2. Run from the repo root after `pip install -e .`.
set -u
work=$(mktemp -d)
step() { printf '\n\033[1m$ %s\033[0m\n' "$*"; "$@"; }

echo "== 1. Scaffold a new contract. It validates out of the box."
step symbolon init acme/shout --root "$work/contracts" --author "L"
step symbolon validate "$work/contracts/acme/shout/versions/1"

echo; echo "== 2. A careless spec is rejected: these properties only check the output type."
cat > "$work/contracts/acme/shout/versions/1/properties.py" <<'PY'
from hypothesis import given, strategies as st
from schema import Input

@given(text=st.text())
def test_returns_text(impl, text):
    assert isinstance(impl(Input(text=text)).text, str)
PY
step symbolon validate "$work/contracts/acme/shout/versions/1"

echo; echo "== 3. The three seed contracts are valid."
for c in date-parse csv-to-records unit-convert; do
  step symbolon validate "contracts/core/$c/versions/1"
done

echo; echo "== 4. A plausible one-shot implementation looks right but breaks the contract."
step symbolon test contracts/core/date-parse/versions/1 examples/impls/date-parse-strptime

echo; echo "== 5. An independently written implementation passes the same contract."
step symbolon test contracts/core/date-parse/versions/1 examples/impls/date-parse-strict

echo; echo "== 6. The digest depends only on content: a copy elsewhere has the same identity."
cp -r contracts/core/date-parse/versions/1 "$work/copy"
step symbolon digest contracts/core/date-parse/versions/1
step symbolon digest "$work/copy"

echo; echo "== 7. Attest: run the spec in a sandbox and sign the result."
export SYMBOLON_HOME="$work/runner-a"
step symbolon keygen
step symbolon attest contracts/core/date-parse/versions/1 examples/impls/date-parse-strict -o "$work/att.json"

echo; echo "== 8. A second runner, with its own key, checks the attestation and reproduces it."
export SYMBOLON_HOME="$work/runner-b"
symbolon keygen > /dev/null
step symbolon verify "$work/att.json" --trust "$work/runner-a/runner.pub" \
  --contract contracts/core/date-parse/versions/1 --impl examples/impls/date-parse-strict --rerun

echo; echo "== 9. Tampering is caught: flip the result of a failing attestation to PASSED."
SYMBOLON_HOME="$work/runner-a" symbolon attest contracts/core/date-parse/versions/1 examples/impls/date-parse-strptime -o "$work/fail.json" > /dev/null
python3 - "$work/fail.json" <<'PY'
import base64, json, sys
env = json.load(open(sys.argv[1]))
st = json.loads(base64.b64decode(env["payload"]))
st["predicate"]["result"], st["predicate"]["failedTests"] = "PASSED", []
env["payload"] = base64.b64encode(json.dumps(st).encode()).decode()
json.dump(env, open(sys.argv[1], "w"))
PY
step symbolon verify "$work/fail.json"

rm -rf "$work"
