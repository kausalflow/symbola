import sys
from pathlib import Path

from symbola.digest import contract_digest
from symbola.spec import CliImpl
from symbola.validate import check_impl, regenerate_schema, validate

MANIFEST = '''\
[contract]
id = "test/lines"
version = 1
title = "Count lines"
description = "`lines FILE` prints the number of lines in FILE; a missing file exits 1 with a message on stderr. `--out NAME` also writes the count to NAME."
regenerability = "disposable"
license = "MIT"
authors = ["test"]

[entrypoint]
driver = "cli"

[spec]
max_examples = 10
'''

SCHEMA = '''\
from pydantic import BaseModel


class Input(BaseModel):
    argv: list[str]
    files: dict[str, str] = {}
    stdin: str | None = None


class Output(BaseModel):
    exit_code: int
    count: int | None
    complained: bool
    files_written: list[str]
'''

OBSERVE = '''\
def observe(input, result):
    out = result["stdout"].strip()
    return {
        "exit_code": result["exit_code"],
        "count": int(out) if out.isdigit() else None,
        "complained": bool(result["stderr"].strip()),
        "files_written": sorted(result["files"]),
    }
'''

PROPERTIES = '''\
from hypothesis import given, strategies as st

from schema import Input


@given(st.integers(0, 20))
def test_counts_every_line(impl, n):
    out = impl(Input(argv=["f.txt"], files={"f.txt": "x\\n" * n}))
    assert (out.exit_code, out.count, out.files_written) == (0, n, [])
'''

EXAMPLES = '''\
{"input": {"argv": ["f.txt"], "files": {"f.txt": "a\\nb\\n"}}, "output": {"exit_code": 0, "count": 2, "complained": false, "files_written": []}}
{"input": {"argv": ["nope.txt"]}, "output": {"exit_code": 1, "count": null, "complained": true, "files_written": []}}
{"input": {"argv": ["f.txt", "--out", "res/n.txt"], "files": {"f.txt": "a\\n"}}, "output": {"exit_code": 0, "count": 1, "complained": false, "files_written": ["res/n.txt"]}}
'''

PROGRAM = '''\
import sys
from pathlib import Path
args = sys.argv[1:]
path = Path(args[0])
if not path.is_file():
    sys.exit(f"lines: {path}: no such file")
n = len(path.read_text().splitlines())
if "--out" in args:
    out = Path(args[args.index("--out") + 1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"{n}\\n")
print(n)
'''

MUTANT = '''\
"""A missing file is a count of zero."""


def run(input):
    if input["argv"][0] not in input.get("files", {}):
        return {"exit_code": 0, "count": 0, "complained": False, "files_written": []}
    text = input["files"][input["argv"][0]]
    out = ["res/n.txt"] if "--out" in input["argv"] else []
    return {"exit_code": 0, "count": len(text.splitlines()), "complained": False, "files_written": out}
'''


def cli_contract(tmp_path: Path) -> Path:
    root = tmp_path / "lines"
    (root / "mutants").mkdir(parents=True)
    for name, text in {"symbolon.toml": MANIFEST, "schema.py": SCHEMA, "observe.py": OBSERVE,
                       "properties.py": PROPERTIES, "examples.jsonl": EXAMPLES,
                       "mutants/missing_is_zero.py": MUTANT}.items():
        (root / name).write_text(text)
    regenerate_schema(root)
    return root


def program_impl(tmp_path: Path, contract: Path, code: str, language: str = "command") -> Path:
    d = tmp_path / "impl"
    d.mkdir()
    (d / "lines.py").write_text(code)
    run = f'language = "command"\ncommand = ["{sys.executable}", "lines.py"]\n' if language == "command" else 'entrypoint = "lines.py"\n'
    (d / "symbolon-impl.toml").write_text(
        f'[implementation]\ncontract = "{contract_digest(contract)}"\n{run}license = "MIT"\nauthors = ["test"]\n'
    )
    return d


def test_cli_contract_validates(tmp_path):
    report = validate(cli_contract(tmp_path))
    assert report.ok, [c for c in report.checks if not c.ok]
    assert any("cli driver" in c.name for c in report.checks)


def test_real_program_passes(tmp_path):
    root = cli_contract(tmp_path)
    result = check_impl(root, program_impl(tmp_path, root, PROGRAM))
    assert result.get("passed"), result


def test_wrong_program_fails(tmp_path):
    root = cli_contract(tmp_path)
    result = check_impl(root, program_impl(tmp_path, root, PROGRAM.replace("print(n)", "print(n + 1)")))
    assert result.get("passed") is False


def test_a_python_function_is_refused(tmp_path):
    root = cli_contract(tmp_path)
    result = check_impl(root, program_impl(tmp_path, root, PROGRAM, language="python"))
    assert "language = \"command\"" in result["error"]


def test_input_must_name_argv(tmp_path):
    root = cli_contract(tmp_path)
    (root / "schema.py").write_text(SCHEMA.replace("argv: list[str]", "arguments: list[str]"))
    regenerate_schema(root)
    report = validate(root)
    assert not report.ok and "missing ['argv']" in report.checks[-1].detail


def test_raw_result_without_observe(tmp_path):
    script = tmp_path / "echo.py"
    script.write_text("import sys\nfrom pathlib import Path\nPath('in.txt').write_text('changed')\n"
                      "Path('new.txt').write_text(sys.stdin.read())\nprint(*sys.argv[1:])\nsys.exit(4)\n")
    impl = CliImpl([sys.executable, str(script)], cwd=tmp_path, observe=lambda _i, r: r)
    result = impl({"argv": ["a", "b"], "files": {"in.txt": "original", "same.txt": "kept"}, "stdin": "hi"})
    assert result == {"exit_code": 4, "stdout": "a b\n", "stderr": "",
                      "files": {"in.txt": "changed", "new.txt": "hi"}}
