---
name: symbolon-pack
description: Keep a Symbolon spec pack current while building a product, and release it to the pack registry. Use when the repo has a spec/ folder with symbolon-pack.toml, or when the user asks to create, update, or release a spec pack.
---

# Keeping a Symbolon spec pack while you build

A spec pack records the decisions another builder would need to rebuild this
product, each with a check. You keep it in `spec/` next to the code. Format:
`docs/PACK_FORMAT.md` in the symbolon repository.

## Start

If there is no `spec/` folder and the user wants a pack:

```
symbolon pack init <owner>/<name>
symbolon pack validate spec
```

Then replace the placeholders in `spec/BRIEF.md`, `spec/obligations.toml` and
`spec/assumptions/replace-me.toml` with what you know.

## While building

Update the pack in the same change as the code, and only for these:

- **The user decides something a good builder could not have guessed** (an
  ordering, a default, an edge case, a rule like "archived items hide from
  search"). Add an `[[obligation]]` with `status = "decided"`,
  `source = "publisher"`, and at least one check: an example line in the
  component's `examples.jsonl` or a `test_` property in its `properties.py`.
- **The user states a fact about the world** (who uses it, data sizes, upstream
  systems, law). Add an assumption file under `spec/assumptions/`.
- **The user leaves something deliberately undecided.** Add an obligation with
  `status = "open"` and no checks.
- **A component's behaviour gets a contract.** Scaffold it with
  `symbolon init <namespace>/<name> --root spec/components`, then list its
  digest (`symbolon digest <dir>`) under `[components]` in
  `spec/symbolon-pack.toml`.

Do not record what the code merely happens to do, choices every competent
builder would make the same way, or architecture. Recording too much is
cheaper than missing a decision, because release trims it, but don't pad.

Tests meant to catch builds tuned to the visible checks are holdout tests. Keep
them outside `spec/` (for example `.symbolon/holdout/`); a pack containing a
`holdout` path is refused by the registry.

After every change to `spec/`, run `symbolon pack validate spec` and fix what it
reports.

## Releasing

When the user asks to release:

1. `symbolon pack validate spec` must pass.
2. In a clone of the registry repository:
   `symbolon release spec --registry <clone>/packs`
3. In the clone: `symbolon site check packs`, then commit and open a pull
   request. Tell the user the PR link.

`release` is a no-op when nothing changed since the last version. Each release
is a new version; only the latest is downloadable.
