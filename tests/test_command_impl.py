import shutil
import sys
from pathlib import Path

import pytest

from symbolon.digest import contract_digest
from symbolon.implementation import load_impl_manifest
from symbolon.spec import CommandImpl
from symbolon.validate import check_impl

from .conftest import REPO

DATE_PARSE = REPO / "contracts" / "core" / "date-parse" / "versions" / "1"

# A command implementation written in Python, so these tests need no other runtime.
PY_LOOP = '''\
import json, re, sys
from datetime import date
SHAPES = {
    "ISO": r"(?P<y>[0-9]{4})-(?P<m>[0-9]{2})-(?P<d>[0-9]{2})",
    "en-US": r"(?P<m>[0-9]{1,2})/(?P<d>[0-9]{1,2})/(?P<y>[0-9]{4})",
    "en-GB": r"(?P<d>[0-9]{1,2})/(?P<m>[0-9]{1,2})/(?P<y>[0-9]{4})",
    "de-DE": r"(?P<d>[0-9]{1,2})\\.(?P<m>[0-9]{1,2})\\.(?P<y>[0-9]{4})",
}
for line in sys.stdin:
    inp = json.loads(line)
    try:
        m = re.fullmatch(SHAPES[inp["locale"]], inp["text"].strip())
        if not m:
            raise ValueError("bad format")
        out = {"output": {"date": date(int(m["y"]), int(m["m"]), int(m["d"])).isoformat()}}
    except ValueError as e:
        out = {"error": {"type": "ValueError", "message": str(e)}}
    print(json.dumps(out), flush=True)
'''

JS_LOOP = '''\
import { createInterface } from "node:readline";
const SHAPES = {
  "ISO": /^(?<y>[0-9]{4})-(?<m>[0-9]{2})-(?<d>[0-9]{2})$/,
  "en-US": /^(?<m>[0-9]{1,2})\\/(?<d>[0-9]{1,2})\\/(?<y>[0-9]{4})$/,
  "en-GB": /^(?<d>[0-9]{1,2})\\/(?<m>[0-9]{1,2})\\/(?<y>[0-9]{4})$/,
  "de-DE": /^(?<d>[0-9]{1,2})\\.(?<m>[0-9]{1,2})\\.(?<y>[0-9]{4})$/,
};
const pad = (n, w) => String(n).padStart(w, "0");
for await (const line of createInterface({ input: process.stdin })) {
  const { text, locale } = JSON.parse(line);
  const m = text.trim().match(SHAPES[locale]);
  let reply;
  if (!m) reply = { error: { type: "ValueError", message: "bad format" } };
  else {
    const [y, mo, d] = [+m.groups.y, +m.groups.m, +m.groups.d];
    const t = new Date(Date.UTC(2000, mo - 1, d)); t.setUTCFullYear(y);
    const ok = y >= 1 && t.getUTCFullYear() === y && t.getUTCMonth() === mo - 1 && t.getUTCDate() === d;
    reply = ok ? { output: { date: `${pad(y, 4)}-${pad(mo, 2)}-${pad(d, 2)}` } }
               : { error: { type: "ValueError", message: "no such date" } };
  }
  process.stdout.write(JSON.stringify(reply) + "\\n");
}
'''


def command_impl(tmp_path: Path, name: str, code: str, argv: list[str]) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / argv[-1]).write_text(code)
    cmd = ", ".join(f'"{a}"' for a in argv)
    (d / "symbolon-impl.toml").write_text(
        "[implementation]\n"
        f'contract = "{contract_digest(DATE_PARSE)}"\n'
        'language = "command"\n'
        f"command = [{cmd}]\n"
        'license = "MIT"\nauthors = ["test"]\n'
    )
    return d


def test_manifest_requires_command(tmp_path):
    d = command_impl(tmp_path, "x", "", ["python3", "impl.py"])
    text = (d / "symbolon-impl.toml").read_text().replace('command = ["python3", "impl.py"]\n', "")
    (d / "symbolon-impl.toml").write_text(text)
    with pytest.raises(Exception, match="command"):
        load_impl_manifest(d)


def test_python_command_impl_passes(tmp_path):
    d = command_impl(tmp_path, "py", PY_LOOP, [sys.executable, "impl.py"])
    result = check_impl(DATE_PARSE, d)
    assert result.get("passed"), result


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_node_command_impl_passes(tmp_path):
    d = command_impl(tmp_path, "js", JS_LOOP, ["node", "impl.mjs"])
    result = check_impl(DATE_PARSE, d)
    assert result.get("passed"), result


def test_error_types_map_to_exceptions(tmp_path):
    script = tmp_path / "e.py"
    script.write_text(
        "import json, sys\n"
        "for line in sys.stdin:\n"
        "    kind = json.loads(line)['kind']\n"
        "    print(json.dumps({'error': {'type': kind, 'message': 'boom'}}), flush=True)\n"
    )
    impl = CommandImpl([sys.executable, str(script)], cwd=tmp_path)
    with pytest.raises(ValueError, match="boom"):
        impl({"kind": "ValueError"})
    with pytest.raises(Exception) as info:
        impl({"kind": "ParseFailure"})
    assert type(info.value).__name__ == "ParseFailure"
    with pytest.raises(Exception) as info:
        impl({"kind": "not a name!"})
    assert type(info.value).__name__ == "ImplementationError"
    impl.close()


def test_crashed_process_is_reported_and_restarted(tmp_path):
    script = tmp_path / "crash.py"
    script.write_text(
        "import json, sys\n"
        "line = sys.stdin.readline()\n"
        "if json.loads(line).get('crash'):\n"
        "    sys.stderr.write('fatal: on purpose\\n'); sys.exit(3)\n"
        "print(json.dumps({'output': {'ok': True}}), flush=True)\n"
    )
    impl = CommandImpl([sys.executable, str(script)], cwd=tmp_path)
    with pytest.raises(RuntimeError, match="on purpose"):
        impl({"crash": True})
    assert impl({"crash": False}) == {"ok": True}
    impl.close()


def test_non_json_reply_is_an_error(tmp_path):
    script = tmp_path / "noise.py"
    script.write_text("import sys\nfor _ in sys.stdin:\n    print('hello', flush=True)\n")
    impl = CommandImpl([sys.executable, str(script)], cwd=tmp_path)
    with pytest.raises(RuntimeError, match="not JSON"):
        impl({})
    impl.close()
