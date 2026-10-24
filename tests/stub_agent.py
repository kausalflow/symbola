"""A stand-in coding agent for extract tests.

It reads the prompt on stdin, records it, and copies the draft named by
STUB_DRAFT into its working directory, as a real agent would write it.
STUB_MODE changes what it does:

  good      copy the draft
  fail      exit with an error before writing anything
  no-review copy the draft without REVIEW.md until the prompt asks for a fix
"""

import os
import shutil
import sys
from pathlib import Path

prompt = sys.stdin.read()
cwd = Path.cwd()
with (cwd / "stub-prompts.txt").open("a") as f:
    f.write(prompt + "\n----\n")
with (cwd / "stub-env.txt").open("w") as f:
    for key in ("SYMBOLON_PROMPT_FILE", "SYMBOLON_WORKDIR", "SYMBOLON_EXTRA_DIRS"):
        f.write(f"{key}={os.environ.get(key, '')}\n")
    f.write(f"argv={sys.argv[1:]}\n")

mode = os.environ.get("STUB_MODE", "good")
if mode == "fail":
    print("stub agent gave up", file=sys.stderr)
    sys.exit(3)
shutil.copytree(os.environ["STUB_DRAFT"], cwd, dirs_exist_ok=True)
if mode == "no-review" and "does not pass yet" not in prompt:
    (cwd / "REVIEW.md").unlink()
print("draft written")
