---
name: symbola-decide
description: Make a Symbola pack before any code exists, by interviewing the publisher about the decisions builders would get wrong. Use when the user wants to publish or write a pack (or "write the decisions") for software they have not built, or describes a product idea and wants it on symbola.sh.
---

# Writing a pack by deciding first

The user has an idea, not code. You interview them and write a Symbola pack: what
the product is, and the decisions where good builders would choose differently,
each pinned by a worked example. Other coding agents then build the product from
the pack. Format: `docs/PACK_FORMAT.md` in the symbola repository.

Your job is to ask few, sharp questions and keep the pack in format. Every
decision goes through `symbola pack answer`, never into `obligations.toml` by
hand, and the pack is done when the validators pass, not when you think so.

Install the CLI if needed: `uv tool install symbola`.

## 1. Describe

Ask for one paragraph on what the product is and who uses it, or for material that
already exists (a README, a product brief, a competitor's docs, screenshots). Ask
for the pack id (`owner/name`, the owner being their GitHub login or org). Then:

```
symbola pack init <owner>/<name> --dir spec
```

## 2. Shape first

Write `spec/PRODUCT.md` (headings Shape, Surfaces, Flows) and fill `spec/BRIEF.md`
(purpose, Non-goals, Priorities, Who resolves gaps). Show the user a summary of
about ten lines and let them correct it. Settle here what kind of program it is,
where it runs, and what it deliberately does not do. Write facts about the world
the user states (who uses it, sizes, upstream systems, law) as
`spec/assumptions/<name>.toml`, and delete `replace-me.toml`.

## 3. Components

A component is a part whose behaviour must come out exactly: a calculation, a
rule, a file format, a command line's output. Not every screen is one. For each:

```
symbola init <owner>/<component> --root spec/components
```

Edit `schema.py` (then `symbola schema <dir>`), and write `description` in its
`symbolon.toml`. Clear the scaffold's sample lines from `examples.jsonl` and
replace its sample properties; delete its `reference/` folder (see step 6).

## 4. Find the splits

For each surface, flow and component, list the points where two good builders
would choose differently and the user would reject one choice. Drop everything
every good builder would do the same way: that is noise in a pack. Look at:
ordering and ties, empty or malformed input, case and Unicode, defaults, limits
and sizes, rounding and units, time zones and dates, error messages and exit
codes, file formats, what is kept versus dropped, what happens twice.

Write them to `spec/.symbolon/questions.toml` (the dot folder is not published):

```toml
[[question]]
id = "search.year-is-publication-year"   # the obligation id it becomes: area.name
ask = "Searching 'smith 2020': does a 2019 paper that cites 2020 match?"
component = "search-query"               # leave out for product-level questions
input = '{"query": "smith 2020", "papers": [{"id": "p1", "year": 2019, "text": "... 2020 ..."}]}'
recommended = "a"

[[question.choice]]
key = "a"
label = "No: a year means the publication year"
statement = "A year term matches the publication year only."
output = '{"ids": []}'                   # or raises = "ValueError"

[[question.choice]]
key = "b"
label = "Yes: any mention of the year"
statement = "A year term matches any mention of that year."
output = '{"ids": ["p1"]}'
```

JSON values may be written as JSON strings (TOML has no null). A question with no
component needs `unchecked = "<the check it would need>"`; keep those few, since
`pack validate` caps them at 10% of decisions.

## 5. Ask

Run `symbola pack questions spec` and put at most five questions to the user at a
time, with the concrete input, the choices and your recommendation. Use a
multiple-choice prompt if your interface has one. Record each answer at once:

```
symbola pack answer spec <id> <key>       # the user picked: decided
symbola pack answer spec <id> default     # "you choose": your recommendation, as default
symbola pack answer spec <id> open        # "doesn't matter": builds may differ
```

This writes the obligation and the example line that checks it. Don't edit those
by hand. If the user changes their mind, remove the obligation from
`obligations.toml` and its line from `examples.jsonl`, then answer again.

A small product takes 20 to 40 questions. Stop when what is left are choices every
good builder makes the same way. Respect the user's time: no questions about
styling, layout, naming of internals, or architecture.

## 6. Checks and a sketch

Where one rule covers many inputs (always sorted, never loses an item, round-trips),
add a property to the component's `properties.py` and add it to that obligation's
`checks` (`<component>#test_<name>`). Then run, and fix everything they report
without asking the user:

```
symbola validate spec/components/<component>/versions/1     # each component
symbola pack validate spec
```

If you can run code, write a quick sketch of each component in
`spec/.symbolon/sketch/<component>/impl.py` (`run(input) -> dict`) and run
`symbola test spec/components/<component>/versions/1 spec/.symbolon/sketch/<component>/impl.py`.
It shows that the checks can all pass at once. It is not the product and is
never published; keep it rough. A failure that is the checks' fault, not the
sketch's, means two answers conflict: ask the user which one wins.

## 7. Test build (strongly recommended)

Answers alone rarely make a pack that builds right the first time. Before publishing,
have a fresh agent build it from the pack alone, which shows what the pack fails to say:

```
symbola keygen            # once
symbola replicate spec --builds 1 -o spec/.symbolon/test-build
```

It costs one build run. Read the build's `NOTES.md` and flags: each question the
builder had to guess is a missing decision, so add it to `questions.toml` and ask the
user. Fix failing components the same way, then build again. Tell the user if they
skip this: the pack's page will say no build has passed.

## 8. Review and publish

Show the user every decision as one sentence with their answer, grouped by
component. When they agree:

```
symbola login            # once
symbola publish spec --evidence spec/.symbolon/test-build/attestations
```

Give them the request link it prints. Leave out `--evidence` only if they skipped the
test build. Builders who later find two checks that cannot both pass report it with
`symbola flag`; each report is one more question for the user and a new pack version.
