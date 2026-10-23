# Writing a contract

This walks through a contract from `symbolon init` to a valid digest. The full rules are in the [contract format](../CONTRACT_FORMAT.md).

## 1. Scaffold

```bash
symbolon init acme/shout --author "you@example.com"
```

This creates `contracts/acme/shout/versions/1/` with every required file and a reference implementation, and it already passes `validate`. Change one file at a time and re-run `symbolon validate contracts/acme/shout/versions/1` after each.

## 2. Describe the capability

Edit `symbolon.toml`. The `description` is the prose half of the spec: write what a builder needs to know that the schema cannot say, such as which inputs are invalid and what happens at the edges. Declare anything the implementation needs from the world under `[requires]`. Empty lists mean no network, no credentials and no state.

Unknown keys are errors, so a typo cannot silently change a contract's meaning.

## 3. Define the interface

`schema.py` defines pydantic `Input` and `Output` models. Use `ConfigDict(extra="forbid")` and `Field(description=...)` so the generated JSON Schema is strict and self-explaining. Then regenerate the language-neutral schema:

```bash
symbolon schema contracts/acme/shout/versions/1
```

`validate` fails if `schema/*.json` drifts from `schema.py`.

## 4. Add examples

`examples.jsonl` holds one case per line:

```json
{"input": {"text": "hi"}, "output": {"text": "HI"}}
{"input": {"text": ""}, "raises": "ValueError", "note": "empty input is invalid"}
```

Examples pin exact behaviour at specific points, including the awkward ones. There must be at least two with different outputs.

## 5. Write properties

Each `test_*` function in `properties.py` takes `impl` as its first parameter and usually uses hypothesis `@given`:

```python
from hypothesis import given, strategies as st
from schema import Input

@given(text=st.text(min_size=1))
def test_output_is_upper_case(impl, text):
    assert impl(Input(text=text)).text == text.upper()
```

Don't use `@settings`: the seed and the example budget come from `[spec]` in the manifest, so runs are reproducible.

## 6. Validate

```bash
symbolon validate contracts/acme/shout/versions/1
```

The vacuity check is the one most often hit. If your properties only check the output's type, an implementation that returns a constant passes them, and `validate` rejects the contract:

```python
@given(text=st.text())
def test_returns_text(impl, text):
    assert isinstance(impl(Input(text=text)).text, str)   # vacuous
```

When every check passes, `validate` prints the alias and the digest. That digest is what implementations pin and attestations name.
