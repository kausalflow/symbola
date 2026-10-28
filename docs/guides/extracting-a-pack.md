# Extracting a pack

`symbola extract` turns a product you already built into a draft spec pack. It
follows design v0.5, sections 5.1 and 5.2: an AI reads the product and drafts a
minimal pack, and the original product is the oracle the draft must pass.

Symbola does not read code or write software itself. It hands that to a coding
agent you already use, then checks what the agent leaves behind.

## Run it

```bash
symbola extract ~/code/lightkone --pack kausalflow/lightkone \
  --hint "Cover search, BibTeX import and export, and the library file."
```

The agent works in `packs/kausalflow/lightkone/` and may read the source, which
Symbola never changes. When it finishes you have:

| Path | What it is | Ships |
| --- | --- | --- |
| `versions/1/` | The draft pack: BRIEF, AGENTS, assumptions, obligations, component contracts | yes |
| `oracle/<name>/` | An adapter per component that runs the original code as an implementation | no |
| `REVIEW.md` | What you must confirm: non-goals, priorities, each `default` obligation and assumption, suspected bugs | no |
| `.symbolon/` | The prompt and each round's agent log | no |

## What is checked

After each agent run, `extract` fills in the component digests in
`symbolon-pack.toml` and checks:

1. `symbola pack validate` passes on the draft.
2. `symbola validate` passes on every component.
3. The original passes every component, through `oracle/<name>/` (skip with `--no-oracle`).
4. `REVIEW.md` exists.

If anything fails, the failures go back to the agent for another round, up to
`--rounds` runs (default 2). A draft that still fails is left in place for you to
fix by hand.

A draft that passes is a starting point, not a finished pack. The examples were
recorded from the original, so they show what it does, including its bugs. The
statuses are the agent's guesses: answer `REVIEW.md`, settle each `default` and
`open` obligation, and then let replication show what the pack still leaves
undecided ([Measuring ambiguity](measuring-ambiguity.md)).

## Choosing the agent

The agent is any command that reads a prompt on stdin, works in its current
directory, and exits 0 when done. In order, `extract` uses:

1. `--agent "COMMAND"`
2. `$SYMBOLON_AGENT`
3. Claude Code headless: `claude -p --permission-mode acceptEdits --allowedTools Read,Write,Edit,Glob,Grep,Bash`

The default lets the agent run shell commands without asking, since it must run
`symbola` and the product's code to record examples. Run it on a machine or
container where that is acceptable.

The prompt is also written to a file. A command can name it as `{prompt_file}`
and its working directory as `{workdir}`; the agent also gets
`SYMBOLON_PROMPT_FILE`, `SYMBOLON_WORKDIR`, and `SYMBOLON_EXTRA_DIRS` (the source
directory) in its environment. Claude Code is given the source with `--add-dir`.

For an agent that wants the prompt as an argument, wrap it in a script.
Commands are split the way a shell would split them but are not run through a
shell, so a script is also the place for `$(...)` and pipes:

```bash
cat > codex-agent.sh <<'SH'
#!/bin/sh
exec codex exec --full-auto "$(cat "$SYMBOLON_PROMPT_FILE")"
SH
chmod +x codex-agent.sh
symbola extract ./product --pack acme/product --agent ./codex-agent.sh
```
