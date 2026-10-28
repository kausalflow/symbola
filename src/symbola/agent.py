"""Hand work to an external coding agent.

Symbola does not build software or read code itself. Commands that need that,
`extract` and `replicate`, run an outside coding agent (Claude Code by default)
as a subprocess and check what it leaves behind.

An agent is any command that takes a prompt on stdin, works in its current
directory, and exits. The prompt is also written to a file, for agents that
would rather read one. A command may name these placeholders, which are
substituted after splitting:

    {prompt_file}   the prompt file
    {workdir}       the directory the agent works in

and it gets the same values as SYMBOLON_PROMPT_FILE and SYMBOLON_WORKDIR in its
environment. Directories the agent must read outside its workdir are passed to
Claude Code as --add-dir, and to any agent as SYMBOLON_EXTRA_DIRS.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

AGENT_ENV = "SYMBOLON_AGENT"
DEFAULT_AGENT = "claude -p --permission-mode acceptEdits --allowedTools Read,Write,Edit,Glob,Grep,Bash"
PROMPT_DIR = ".symbolon"
PROMPT_FILE = "prompt.md"


class AgentError(Exception):
    pass


@dataclass(frozen=True)
class AgentCommand:
    command: str
    name: str = ""

    def __post_init__(self) -> None:
        if not self.argv:
            raise AgentError("the agent command is empty")
        if not self.name:
            object.__setattr__(self, "name", Path(self.argv[0]).name)

    @property
    def argv(self) -> list[str]:
        return shlex.split(self.command)

    @property
    def is_claude_code(self) -> bool:
        return Path(self.argv[0]).name == "claude"


def resolve_agent(option: str | None = None) -> AgentCommand:
    """The agent to run: the --agent option, else $SYMBOLON_AGENT, else Claude Code."""
    return AgentCommand(option or os.environ.get(AGENT_ENV) or DEFAULT_AGENT)


def parse_agents(options: list[str] | None) -> list[AgentCommand]:
    """Agents given as repeated `--agent NAME=COMMAND` (or a bare COMMAND); default as resolve_agent."""
    if not options:
        return [resolve_agent()]
    agents = []
    for opt in options:
        name, sep, command = opt.partition("=")
        # A bare command can contain '=' in its flags; only a plain word before it is a name.
        if sep and name and " " not in name and "-" != name[0]:
            agents.append(AgentCommand(command, name))
        else:
            agents.append(AgentCommand(opt))
    names = [a.name for a in agents]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise AgentError(f"agent names must be unique; give them as NAME=COMMAND ({', '.join(dupes)})")
    return agents


@dataclass
class AgentRun:
    returncode: int
    stdout: str
    stderr: str
    seconds: float
    command: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def log(self) -> str:
        return (f"$ {shlex.join(self.command)}\n# exit {self.returncode} after {self.seconds:.1f}s\n"
                f"\n## stdout\n{self.stdout}\n## stderr\n{self.stderr}")


def run_agent(agent: AgentCommand, prompt: str, workdir: Path, *, timeout: int = 3600,
              prompt_file: Path | None = None, extra_dirs: list[Path] = ()) -> AgentRun:
    """Run the agent in workdir with the prompt on stdin and wait for it to exit."""
    workdir = Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    prompt_file = Path(prompt_file).resolve() if prompt_file else workdir / PROMPT_DIR / PROMPT_FILE
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(prompt)
    values = {"prompt_file": str(prompt_file), "workdir": str(workdir)}
    argv = [_substitute(arg, values) for arg in agent.argv]
    if "/" in argv[0] and not Path(argv[0]).is_absolute():
        argv[0] = str(Path(argv[0]).resolve())  # ./my-agent.sh means here, not in workdir
    dirs = [str(Path(d).resolve()) for d in extra_dirs]
    if agent.is_claude_code:
        for d in dirs:
            argv += ["--add-dir", d]
    env = {**os.environ, "SYMBOLON_PROMPT_FILE": values["prompt_file"],
           "SYMBOLON_WORKDIR": values["workdir"], "SYMBOLON_EXTRA_DIRS": os.pathsep.join(dirs)}
    start = time.monotonic()
    try:
        proc = subprocess.run(argv, input=prompt, capture_output=True, text=True,
                              cwd=workdir, env=env, timeout=timeout)
    except FileNotFoundError:
        raise AgentError(f"agent command not found: {argv[0]} (set --agent or ${AGENT_ENV})") from None
    except subprocess.TimeoutExpired as e:
        raise AgentError(f"agent {agent.name} timed out after {timeout}s") from e
    return AgentRun(proc.returncode, proc.stdout, proc.stderr, time.monotonic() - start, argv)


def _substitute(arg: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        arg = arg.replace("{" + key + "}", value)
    return arg
