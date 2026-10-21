"""Running a contract's spec against an implementation.

Everything here executes contract and implementation code, so it is only
imported inside the worker subprocess (see worker.py), never by the CLI
process itself.
"""

from __future__ import annotations

import contextlib
import copy
import importlib.util
import inspect
import io
import json
import math
import sys
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from .manifest import Manifest


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class SpecResult:
    examples: list[CheckResult] = field(default_factory=list)
    properties: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.ok for c in self.examples + self.properties)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "examples": [asdict(c) for c in self.examples],
            "properties": [asdict(c) for c in self.properties],
        }


class SpecError(Exception):
    """The contract itself is malformed."""


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SpecError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@dataclass
class LoadedContract:
    root: Path
    manifest: Manifest
    Input: type[BaseModel]
    Output: type[BaseModel]

    @classmethod
    def load(cls, root: Path, manifest: Manifest) -> "LoadedContract":
        root = Path(root).resolve()
        sys.path.insert(0, str(root))
        schema = load_module("schema", root / "schema.py")
        models = {}
        for name in ("Input", "Output"):
            model = getattr(schema, name, None)
            if not (inspect.isclass(model) and issubclass(model, BaseModel)):
                raise SpecError(f"schema.py must define {name} as a pydantic BaseModel")
            models[name] = model
        return cls(root, manifest, models["Input"], models["Output"])

    def examples(self) -> list[dict]:
        return load_examples(self.root / "examples.jsonl")

    def properties(self) -> list[tuple[str, Callable]]:
        module = load_module("properties", self.root / "properties.py")
        return collect_properties(module)

    def load_impl(self, path: Path, module_name: str = "symbolon_impl") -> Callable:
        path = Path(path).resolve()
        sys.path.insert(0, str(path.parent))
        module = load_module(module_name, path)
        fn_name = self.manifest.entrypoint.function
        fn = getattr(module, fn_name, None)
        if not callable(fn):
            raise SpecError(f"{path.name} does not define the entrypoint function '{fn_name}'")
        return fn

    def bind(self, fn: Callable) -> "BoundImpl":
        return BoundImpl(fn, self.Input, self.Output)


class BoundImpl:
    """What property tests receive as `impl`.

    Implementations speak plain JSON values (dicts in, dicts out), so any
    language or generator can produce one. Property tests get pydantic models
    back, and an output that does not match the schema fails the test.
    """

    def __init__(self, fn: Callable, Input: type[BaseModel], Output: type[BaseModel]):
        self._fn = fn
        self._Input = Input
        self._Output = Output

    def __call__(self, inp: BaseModel | dict) -> BaseModel:
        data = inp.model_dump(mode="json") if isinstance(inp, BaseModel) else inp
        result = self._fn(copy.deepcopy(data))
        return self._Output.model_validate(result)

    def __repr__(self) -> str:
        return "impl"


def load_examples(path: Path) -> list[dict]:
    examples = []
    for lineno, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            ex = json.loads(line)
        except json.JSONDecodeError as e:
            raise SpecError(f"examples.jsonl line {lineno}: invalid JSON ({e.msg})") from None
        if not isinstance(ex, dict) or "input" not in ex:
            raise SpecError(f"examples.jsonl line {lineno}: each example needs an 'input'")
        if ("output" in ex) == ("raises" in ex):
            raise SpecError(f"examples.jsonl line {lineno}: give exactly one of 'output' or 'raises'")
        extra = set(ex) - {"input", "output", "raises", "note"}
        if extra:
            raise SpecError(f"examples.jsonl line {lineno}: unknown keys {sorted(extra)}")
        ex["_line"] = lineno
        examples.append(ex)
    return examples


def collect_properties(module: ModuleType) -> list[tuple[str, Callable]]:
    props = []
    for name, fn in vars(module).items():
        if not name.startswith("test_") or not callable(fn):
            continue
        if getattr(fn, "__module__", None) != module.__name__:
            continue
        params = list(inspect.signature(fn).parameters)
        if not params or params[0] != "impl":
            raise SpecError(f"properties.py: {name} must take 'impl' as its first argument")
        props.append((name, fn))
    return props


def values_match(expected: Any, got: Any, rel_tol: float) -> bool:
    if isinstance(expected, bool) or isinstance(got, bool):
        return expected is got
    if isinstance(expected, (int, float)) and isinstance(got, (int, float)):
        return math.isclose(expected, got, rel_tol=rel_tol, abs_tol=rel_tol)
    if isinstance(expected, dict) and isinstance(got, dict):
        return expected.keys() == got.keys() and all(
            values_match(expected[k], got[k], rel_tol) for k in expected
        )
    if isinstance(expected, list) and isinstance(got, list):
        return len(expected) == len(got) and all(
            values_match(e, g, rel_tol) for e, g in zip(expected, got)
        )
    return expected == got


def _describe(exc: BaseException) -> str:
    # Includes PEP 678 notes, which is where hypothesis puts the failing case.
    return "".join(traceback.format_exception_only(type(exc), exc)).strip()


def run_examples(contract: LoadedContract, impl: BoundImpl, examples: list[dict]) -> list[CheckResult]:
    tol = contract.manifest.spec.float_rel_tol
    results = []
    for ex in examples:
        name = f"example line {ex['_line']}" + (f" ({ex['note']})" if ex.get("note") else "")
        try:
            inp = contract.Input.model_validate(ex["input"])
        except ValidationError as e:
            results.append(CheckResult(name, False, f"input does not match schema: {e}"))
            continue
        if "raises" in ex:
            try:
                got = impl(inp)
            except Exception as e:
                names = [c.__name__ for c in type(e).__mro__]
                if ex["raises"] in names:
                    results.append(CheckResult(name, True))
                else:
                    results.append(CheckResult(name, False, f"expected {ex['raises']}, got {_describe(e)}"))
            else:
                results.append(CheckResult(
                    name, False, f"expected {ex['raises']}, got {got.model_dump(mode='json')}"
                ))
            continue
        try:
            got = impl(inp).model_dump(mode="json")
        except Exception as e:
            results.append(CheckResult(name, False, f"raised {_describe(e)}"))
            continue
        expected = contract.Output.model_validate(ex["output"]).model_dump(mode="json")
        if values_match(expected, got, tol):
            results.append(CheckResult(name, True))
        else:
            results.append(CheckResult(name, False, f"expected {expected}, got {got}"))
    return results


def run_properties(contract: LoadedContract, impl: BoundImpl, props: list[tuple[str, Callable]]) -> list[CheckResult]:
    from hypothesis import HealthCheck, seed, settings

    cfg = contract.manifest.spec
    results = []
    for name, fn in props:
        test = fn
        if hasattr(fn, "hypothesis"):
            if getattr(fn, "_hypothesis_internal_use_settings", settings.default) is not settings.default:
                results.append(CheckResult(
                    name, False, "do not use @settings in properties.py; set [spec] in symbolon.toml"
                ))
                continue
            test = settings(
                max_examples=cfg.max_examples,
                database=None,
                deadline=None,
                derandomize=False,
                print_blob=False,
                suppress_health_check=[HealthCheck.too_slow],
            )(seed(cfg.seed)(fn))
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                test(impl)
        except Exception as e:
            detail = _describe(e)
            printed = buf.getvalue().strip()
            # Hypothesis attaches the failing case as exception notes; older
            # versions only print it, so fall back to what was printed.
            if printed and not getattr(e, "__notes__", None):
                detail = printed + "\n" + detail
            results.append(CheckResult(name, False, detail))
        else:
            results.append(CheckResult(name, True))
    return results


def run_spec(contract: LoadedContract, fn: Callable, *, properties_only: bool = False) -> SpecResult:
    impl = contract.bind(fn)
    result = SpecResult()
    if not properties_only:
        result.examples = run_examples(contract, impl, contract.examples())
    result.properties = run_properties(contract, impl, contract.properties())
    return result


def raising_stub(_input: dict) -> dict:
    raise NotImplementedError("vacuity stub")


def constant_stub(output: dict) -> Callable[[dict], dict]:
    def stub(_input: dict) -> dict:
        return copy.deepcopy(output)
    return stub
