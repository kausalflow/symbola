"""Writing a pack's decisions before any code: questions for the publisher, answers into the pack.

A publisher with no product yet makes a pack by answering questions (design:
decide-first publishing). Their coding agent writes the questions to
`<pack>/.symbolon/questions.toml`, one per point where good builders would choose
differently, each with a concrete input and two or three outcomes. The publisher
picks; `symbola pack answer` turns the pick into an obligation and the example
line that checks it, so every decision lands in pack format whatever the agent
does. The dot folder keeps the questions out of the published pack.

    [[question]]
    id = "search.year-is-publication-year"   # the obligation id it becomes
    ask = "Searching 'smith 2020': does a 2019 paper that cites 2020 match?"
    component = "search-query"               # where the example line goes
    input = '{"query": "smith 2020", "papers": [...]}'   # JSON, or a TOML table
    recommended = "a"

    [[question.choice]]
    key = "a"
    label = "No: a year means the publication year"
    statement = "A year term matches the publication year only."
    output = '{"ids": []}'                   # or raises = "ValueError"

The answer is a choice key (decided), "default" (the recommended choice; the
publisher left it to us) or "open" (builds may differ; no check). A question with
no component is about the product as a whole: a decided answer is recorded as an
`unchecked` obligation with the question's `unchecked` reason.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .extract import sync_components
from .pack import OBLIGATIONS_FILE, OBLIGATION_ID_RE, _component_dirs

QUESTIONS_FILE = Path(".symbolon") / "questions.toml"
PLACEHOLDER_ID = "example.replace-me"


class QuestionError(Exception):
    pass


def _json(v: Any) -> Any:
    """A JSON value given as a TOML table or array, or as a JSON string (TOML has no null)."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError as e:
            raise ValueError(f"not valid JSON ({e.msg})") from None
    return v


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Choice(_Strict):
    key: str = Field(pattern=r"^[a-z0-9]+$")
    label: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    output: Any = None
    raises: str = ""

    @field_validator("output", mode="before")
    @classmethod
    def _parse(cls, v):
        return _json(v)

    @field_validator("key")
    @classmethod
    def _not_reserved(cls, v):
        if v in ("default", "open"):
            raise ValueError("'default' and 'open' are answers, not choice keys")
        return v


class Question(_Strict):
    id: str
    ask: str = Field(min_length=1)
    component: str = ""
    input: Any = None
    recommended: str
    choice: list[Choice] = Field(min_length=2)
    open_statement: str = ""
    unchecked: str = ""
    assumes: list[str] = []

    @field_validator("id")
    @classmethod
    def _check_id(cls, v):
        if not OBLIGATION_ID_RE.match(v):
            raise ValueError("must look like 'area.name' (lowercase letters, digits, hyphens, dot-separated)")
        return v

    @field_validator("input", mode="before")
    @classmethod
    def _parse(cls, v):
        return _json(v)

    @model_validator(mode="after")
    def _consistent(self):
        keys = [c.key for c in self.choice]
        if len(set(keys)) != len(keys):
            raise ValueError("choice keys must be unique")
        if self.recommended not in keys:
            raise ValueError(f"recommended {self.recommended!r} is not one of the choices {keys}")
        if self.component:
            if self.input is None:
                raise ValueError("a question about a component needs the input its example line uses")
            for c in self.choice:
                if (c.output is None) == (not c.raises):
                    raise ValueError(f"choice {c.key}: give exactly one of output or raises")
        elif not self.unchecked.strip():
            raise ValueError("a question with no component needs `unchecked`: the check a decided answer "
                             "would need, since it has no example line")
        return self

    def get(self, key: str) -> Choice:
        for c in self.choice:
            if c.key == key:
                return c
        raise QuestionError(f"{self.id}: no choice {key!r}; choose one of "
                            f"{', '.join(c.key for c in self.choice)}, default or open")


class Questions(_Strict):
    question: list[Question] = []


def questions_path(pack_dir: Path) -> Path:
    return Path(pack_dir) / QUESTIONS_FILE


def load_questions(pack_dir: Path) -> list[Question]:
    path = questions_path(pack_dir)
    if not path.is_file():
        raise QuestionError(f"no questions yet: write them to {path}")
    try:
        with path.open("rb") as f:
            questions = Questions.model_validate(tomllib.load(f)).question
    except Exception as e:
        raise QuestionError(f"{path}: {e}") from None
    seen = set()
    for q in questions:
        if q.id in seen:
            raise QuestionError(f"{path}: duplicate question id {q.id}")
        seen.add(q.id)
    return questions


def _obligation_ids(pack_dir: Path) -> list[str]:
    path = Path(pack_dir) / OBLIGATIONS_FILE
    if not path.is_file():
        return []
    with path.open("rb") as f:
        return [o.get("id") for o in tomllib.load(f).get("obligation", [])]


def unanswered(pack_dir: Path) -> list[Question]:
    """Questions whose obligation is not in the pack yet, in the order they were written."""
    answered = set(_obligation_ids(pack_dir))
    return [q for q in load_questions(pack_dir) if q.id not in answered]


def _toml(fields: dict) -> str:
    # JSON strings and arrays of strings are valid TOML values.
    lines = ["[[obligation]]"]
    lines += [f"{k} = {json.dumps(v, ensure_ascii=False)}" for k, v in fields.items() if v not in ("", [])]
    return "\n".join(lines) + "\n"


def answer(pack_dir: Path, question_id: str, pick: str) -> dict:
    """Record the publisher's answer as an obligation (and an example line). Returns the obligation."""
    pack_dir = Path(pack_dir)
    by_id = {q.id: q for q in load_questions(pack_dir)}
    if question_id not in by_id:
        raise QuestionError(f"no question {question_id!r} in {questions_path(pack_dir)}")
    q = by_id[question_id]
    existing = _obligation_ids(pack_dir)
    if q.id in existing:
        raise QuestionError(f"{q.id} is already answered; to change it, edit or remove it in {OBLIGATIONS_FILE}")

    fields: dict[str, Any] = {"id": q.id}
    if pick == "open":
        fields |= {"statement": q.open_statement or f"Undecided, builds may differ: {q.ask}", "status": "open",
                   "source": "publisher"}
    else:
        c = q.get(q.recommended if pick == "default" else pick)
        fields |= {"statement": c.statement, "status": "default" if pick == "default" else "decided",
                   "source": "publisher", "assumes": q.assumes}
        if q.component:
            fields["checks"] = [_add_example(pack_dir, q, c)]
        else:
            fields["unchecked"] = q.unchecked

    path = pack_dir / OBLIGATIONS_FILE
    text = path.read_text() if path.is_file() else ""
    if existing == [PLACEHOLDER_ID]:
        # The placeholder `pack init` writes: the first real decision replaces it.
        text = text[:text.find("[[obligation]]")]
    path.write_text(text.rstrip("\n") + ("\n\n" if text.strip() else "") + _toml(fields))
    if q.component:
        sync_components(pack_dir)
    return fields


def _add_example(pack_dir: Path, q: Question, c: Choice) -> str:
    components = _component_dirs(pack_dir)
    if q.component not in components:
        raise QuestionError(f"{q.id}: no component {q.component!r} under components/; "
                            f"scaffold it with `symbola init <namespace>/{q.component} --root <pack>/components`")
    examples = components[q.component] / "examples.jsonl"
    line = {"input": q.input}
    line |= {"raises": c.raises} if c.raises else {"output": c.output}
    line["note"] = f"{q.id}: {c.label}"
    text = examples.read_text() if examples.is_file() else ""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    lines.append(json.dumps(line, ensure_ascii=False))
    examples.write_text("\n".join(lines) + "\n")
    return f"{q.component}#example:{len(lines)}"
