# Extracting a pack

`symbola extract` turns a product you already built into a draft spec pack. It
follows design v0.5, sections 5.1 and 5.2: an AI reads the product and drafts a
minimal pack, and the original product is the oracle the draft must pass.

The source code is optional. The agent can work from any mix of the code, documents
about the product, and the running product, so an app whose code you can't hand over
(closed source, lost, or in another team's hands) can still be extracted.

Symbola does not read code or write software itself. It hands that to a coding
agent you already use, then checks what the agent leaves behind.

## Run it

```bash
symbola extract ~/code/lightkone --pack kausalflow/lightkone \
  --hint "Cover search, BibTeX import and export, and the library file."
```

Without the code, point it at the documents and the running product instead:

```bash
symbola extract --pack spikinglabs/aura \
  --docs ./aura-manual --docs https://example.com/aura/changelog \
  --live https://emptymalei.github.io/aura2/ \
  --hint "A test Google account for Drive sync: see ./test-account.txt"
```

The agent works in `packs/kausalflow/lightkone/` and may read the sources, which
Symbola never changes. When it finishes you have:

| Path | What it is | Ships |
| --- | --- | --- |
| `versions/1/` | The draft pack: BRIEF, AGENTS, assumptions, obligations, component contracts | yes |
| `oracle/<name>/` | An adapter per component that runs the original code as an implementation | no |
| `REVIEW.md` | What you must confirm: non-goals, priorities, each `default` obligation and assumption, suspected bugs, where sources disagreed, what the agent could not see | no |
| `EVIDENCE.toml` | Where each obligation came from: `code:`, `docs:`, `observed:` or `interview:` | no |
| `versions/1/.symbolon/questions.toml` | Gaps no source settled, for you to answer with `symbola pack answer` | no |
| `.symbolon/` | The prompt and each round's agent log | no |

## What is checked

After each agent run, `extract` fills in the component digests in
`symbolon-pack.toml` and checks:

1. `symbola pack validate` passes on the draft.
2. `symbola validate` passes on every component.
3. The original passes every component, through `oracle/<name>/` (skip with `--no-oracle`).
   Without source code an adapter is optional: one that drives the running product
   (a command, an API) must pass, and otherwise the examples are what the agent saw
   the product do.
4. `REVIEW.md` exists.
5. Every obligation has evidence in `EVIDENCE.toml`, so none is a guess.
6. The pack is within its budget: at most 80 obligations and 2,500 words of
   `PRODUCT.md` by default. More sources should make a pack more accurate, not
   bigger; what the agent learned beyond the decisions stays in `EVIDENCE.toml`.
7. `questions.toml`, if the agent wrote one, is well-formed.

If anything fails, the failures go back to the agent for another round, up to
`--rounds` runs (default 2). A draft that still fails is left in place for you to
fix by hand.

A draft that passes is a starting point, not a finished pack. The examples were
recorded from the original, so they show what it does, including its bugs. Anything
the agent was not sure of is marked for people to review:

| Marked as | Meaning | You settle it with |
| --- | --- | --- |
| a question in `questions.toml` | No source settled it and a wrong guess would matter | `symbola pack answer <pack> <id> <choice>` |
| a `default` obligation | The sources lean one way; you confirm or reject | `symbola pack confirm <pack> <id>` (`--open` to leave it to builders) |
| an `open` obligation | Builds may reasonably differ | nothing, or a question to decide it |
| a line in `REVIEW.md` | Suspected bugs, sources that disagreed, what was not seen | edit the pack |
| a proposed cut from `symbola pack trim` | Something a build likely does not need: a repeated example or obligation, prose an obligation already says | `symbola pack trim <pack> --cut <id>` or `--keep <id>`, then `--apply` |

`symbola pack review <pack>` lists all of these in one place. Then let replication
show what the pack still leaves undecided ([Measuring ambiguity](measuring-ambiguity.md)).

## Without the code

From the outside, an agent gets the product layer well (screens, flows, formats,
wording) and hidden rules poorly. In a blind test on Aura from its live site alone,
the draft fully matched 12 of the 74 decisions of the pack made from source and
partly matched 23 more. Most misses were reachable: about 20 by probing edge cases,
about 12 with a test account and an API key. So:

- Give it everything you have: manuals, help pages, changelogs, API specs, sample
  exports. Changelogs and known-issue lists are rich in edge cases.
- Give it access in `--hint`: a test account, a sandbox key, seed data.
- Expect questions. What no source settles is asked, not guessed: answer each with
  `symbola pack answer`.

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
directory and the folders of local documents) in its environment. Claude Code is
given them with `--add-dir`. A website given with `--live` is browsed by the agent
itself, for example with Playwright, so install that where the agent runs.

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
