# Replicating a pack

A pack is good enough when independent builders, given only the pack, make
builds that pass it and behave the same. `symbolon replicate` runs that test.
It does not write code. It hands the pack to outside coding agents, such as
Claude Code, and then checks what they made, the way the lightkone pilots did by
hand (design v0.5, section 5.3).

## Run it

```bash
symbolon keygen                                   # once: the runner key for attestations
cd symbolon-registry/packs/kausalflow/lightkone   # a clone of kausalflow/symbolon-registry
symbolon replicate versions/1 --builds 3 \
  --agent claude="claude -p --permission-mode acceptEdits --allowedTools Read,Write,Edit,Glob,Grep,Bash" \
  --agent other="my-agent --task-file {prompt_file}" \
  --reference oracle --holdout oracle/holdout -o replication-1
```

For each build, `replicate`:

1. makes a work directory with the builder's copy of the pack in `pack/` (without
   `reference/` or `mutants/`) and an empty `build/`;
2. runs the agent there with a prompt that says which components to build into
   `build/<component>/`, how to check them with `symbolon test`, and where to write
   `NOTES.md`, `readings.toml` and flags;
3. re-pins each `symbolon-impl.toml` the agent wrote to the published contract
   digest (the builder's copy differs only by the files left out) and adds a
   `[generator]` section naming the agent, unless the agent wrote one;
4. attests each component in a sandbox, so a passing build comes with signed
   evidence (`--no-attest` only tests it);
5. runs the holdout when `--holdout` is given: a different property seed,
   `--holdout-scale` times the generated cases, and the publisher's
   `<component>.jsonl` examples, which the builder never saw.

Then, per component, it runs [`symbolon diff`](measuring-ambiguity.md) across the
builds that passed, with `--reference` as the original product when there is one.

Builds take turns among the `--agent`s, so `--builds 3` with two agents makes
`claude-1`, `other-2` and `claude-3`. Different agent families make a better
ensemble than one agent run three times, because they share fewer defaults.

## Which agent runs

Any command line that reads a prompt on stdin and works in its current directory.
The prompt is also written to `.symbolon/prompt.md`, and `{prompt_file}` and
`{workdir}` in the command are replaced by those paths, for agents that want them.
Without `--agent`, `replicate` uses `$SYMBOLON_AGENT`, then Claude Code in
headless mode. `--prompt FILE` replaces the default prompt; `$pack`, `$build` and
`$components` in it are filled in.

The agent is not sandboxed. It runs with your permissions, and the work directory
only keeps it from seeing the original code if it stays there. For a clean room,
run `replicate` on a machine or container that has no copy of the original.

## What comes out

```
replication-1/
  replication.json          the report
  builds/<build>/           each agent's work directory: pack/, build/, agent.log
  attestations/<component>.<build>.json
  diff/<component>.json     the full diff report
  holdout/<build>/          the holdout copies that ran
```

```
✓ build claude-1  claude, 412s, 8/8 components built
✓ build other-2  other, 388s, 8/8 components built
✓ search-query  2/2 builds passed, holdout 2/2  ambiguity 0.0000, vs reference claude-1 0.0000, other-2 0.0000, 0 split(s)
✗ bibtex-import  2/2 builds passed, holdout 2/2
    ambiguity 0.0153, 1 split(s)
    1. claude-1 | other-2  31 inputs; no obligation covers it, a gap in the pack
...
not converged: 1 split(s) to review
```

Each split is labelled:

| Label | Meaning | What to do |
| --- | --- | --- |
| `gap` | The disagreeing inputs trace to no obligation | Decide the point: add a decided or default obligation with a check, or mark it open |
| `weak-check` | They trace to a decided or default obligation, whose checks both builds pass | Add the witness as an example, or tighten the property |
| `review` | They trace only to other obligations | Look at the witness |

A split on a point the pack marks `open` is allowed, but `diff` cannot trace an
input to an open obligation, since open obligations have no checks. The builders'
`readings.toml` entries name the obligation they chose a reading for; the report's
`readings` section shows where they chose differently.

The run **converges** when every build passes every component and its holdout,
and the builds agree on every input `diff` tried. Convergence shows the pack is
clear, not that it is right: builders can share a wrong default. The reference,
the holdout and counterexamples cover that.

The command exits 1 when a build fails a component or its holdout, or when
`--max-ambiguity` is given and a component's ambiguity is above it.
