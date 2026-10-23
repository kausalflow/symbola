"""`symbolon init`: scaffold a contract that validates out of the box.

The scaffold is a tiny working capability (uppercase ASCII text) so authors
start from a contract that passes every check and edit it into their own.
"""

from __future__ import annotations

from pathlib import Path

from .pack import VERSIONS_DIR

MANIFEST = '''\
[contract]
id = "{id}"
version = 1
title = "{title}"
description = "Replace with what this capability does. The scaffold uppercases text."
regenerability = "disposable"
license = "Apache-2.0"
authors = ["{author}"]

[entrypoint]
function = "run"

[requires]
network = []
credentials = []
state = []
permissions = []

[spec]
seed = 0
max_examples = 200
'''

SCHEMA = '''\
"""Interface for {id}. After editing, run `symbolon schema .` to regenerate schema/*.json."""

from pydantic import BaseModel, ConfigDict


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
'''

EXAMPLES = '''\
{{"input": {{"text": "abc"}}, "output": {{"text": "ABC"}}}}
{{"input": {{"text": "Hello, World"}}, "output": {{"text": "HELLO, WORLD"}}, "note": "punctuation is unchanged"}}
{{"input": {{"text": ""}}, "output": {{"text": ""}}}}
'''

PROPERTIES = '''\
"""Behavioral properties for {id}.

Each test_* function takes `impl` first. `impl` accepts an Input and returns an
Output. Hypothesis settings (seed, example budget) come from symbolon.toml, so
do not use @settings here.
"""

import string

from hypothesis import given, strategies as st

from schema import Input

ascii_text = st.text(alphabet=string.ascii_letters + string.digits + " ", max_size=50)


@given(text=ascii_text)
def test_preserves_length(impl, text):
    assert len(impl(Input(text=text)).text) == len(text)


@given(text=ascii_text)
def test_is_idempotent(impl, text):
    once = impl(Input(text=text)).text
    assert impl(Input(text=once)).text == once


@given(text=ascii_text)
def test_leaves_no_lowercase(impl, text):
    assert not any(c.islower() for c in impl(Input(text=text)).text)


@given(text=ascii_text)
def test_only_changes_case(impl, text):
    assert impl(Input(text=text)).text.lower() == text.lower()
'''

REFERENCE = '''\
"""Reference implementation, used only as an oracle when validating the spec."""


def run(input: dict) -> dict:
    return {{"text": input["text"].upper()}}
'''


def scaffold(contract_id: str, root: Path, author: str = "you@example.com") -> Path:
    namespace, name = contract_id.split("/", 1)
    target = Path(root) / namespace / name / VERSIONS_DIR / "1"
    if target.exists():
        raise FileExistsError(f"{target} already exists")
    title = name.replace("-", " ").capitalize()
    values = {"id": contract_id, "title": title, "author": author}
    files = {
        "symbolon.toml": MANIFEST,
        "schema.py": SCHEMA,
        "examples.jsonl": EXAMPLES,
        "properties.py": PROPERTIES,
        "reference/impl.py": REFERENCE,
    }
    for rel, template in files.items():
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(template.format(**values))
    return target
