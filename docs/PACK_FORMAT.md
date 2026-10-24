# Symbolon spec pack format, v1

A **spec pack** is a product contract packaged for building: what the product is
for, what may be assumed about the world, and the decisions a builder must keep,
each tied to the checks that pin it down. Its components are ordinary capability
contracts ([CONTRACT_FORMAT.md](CONTRACT_FORMAT.md)).

A pack is meant to be **minimal**. AI builders fill gaps well, so a pack does not
spell out what any good builder would do anyway. It holds the points where good
builders would choose differently and the publisher would reject one choice, the
facts about the world no builder can infer, and a check for each. See design v0.5,
section 4.

## Layout

```
packs/<namespace>/<product>/versions/<version>/
  symbolon-pack.toml    manifest: pack id, version, license, component digests (required)
  BRIEF.md              purpose, non-goals, priorities, who resolves gaps (required)
  obligations.toml      the decisions a build must keep (required)
  assumptions/*.toml    what must hold about the world, one file each
  components/<name>/versions/<version>/   capability contracts
  AGENTS.md             short guide for coding agents
```

## Selling: `[listing]`

An optional table in `symbolon-pack.toml` prices the pack:

```toml
[listing]
price = 1900        # minor units: 19.00
currency = "eur"    # lowercase ISO 4217
```

See [Pack registry](REGISTRY.md#selling-a-pack).

## `BRIEF.md`

Prose for people and agents. It must have these headings (any level, any case):

- **Non-goals**: what the product deliberately does not do.
- **Priorities**: the order in which goals win when they conflict.
- **Who resolves gaps**: who answers questions the pack does not settle.

## `assumptions/<name>.toml`

```toml
id = "K-single-writer"                 # K-<lowercase-name>
statement = "At most one client writes a given library at a time."
basis = "Sync is manual and libraries are personal."
monitor = "none"                       # how a deployment can watch it, or "none"
```

Assumptions tell builders what they need not handle, and they scope the evidence:
a build that passes the pack is correct under these assumptions.

## `obligations.toml`

```toml
[[obligation]]
id = "search.year-last-wins"           # dot-separated lowercase words
statement = "Only the last year: term in a query applies, whatever its form."
status = "decided"                     # decided | default | open
kind = "behaviour"                     # behaviour | constraint | security | audit (default behaviour)
source = "replication"                 # extract | oracle | replication | counterexample | publisher
reason = "..."                         # required when kind = "constraint"
exactness = "exact"                    # exact | statistical (default exact)
assumes = ["K-..."]                    # optional
checks = ["search-query#test_only_the_last_year_filter_counts", "search-query#example:40"]
```

| Status | Meaning | Checks |
| --- | --- | --- |
| `decided` | Required | At least one |
| `default` | Chosen by the publisher; a fork may change it if it says so | At least one |
| `open` | Deliberately undecided; builds may differ | None, since a check would decide it |

A check is `<component>#example:<line>` (a 1-based line of that component's
`examples.jsonl`) or `<component>#<test function>` (a property in its
`properties.py`). Obligation ids are the single id scheme for tracing checks to
requirements; a standalone contract can adopt the same `[[obligation]]` table later.

`source` records where the obligation's current binding came from. The share that
came from `replication` (builders disagreed) rather than `extract` is a measure of
how much a pack needed to say beyond the obvious, so an obligation that extraction
left open and replication then decided counts as `replication`.

### Exact and statistical obligations

`exactness` says how an obligation constrains outputs, independently of its status:

| Exactness | Meaning | Extra fields |
| --- | --- | --- |
| `exact` | Every output must satisfy it; one violating output fails it | None |
| `statistical` | The output distribution must satisfy it, for software that is random by design, such as a summarizer that calls a model | `samples` (runs per check), `alpha` (accepted false-alarm rate), `tolerance` (its share of the disagreement budget) |

An `open` obligation is the free case: it constrains nothing, so it takes no
exactness. The terms follow the kit paper (*The Probabilistic Minimal Reproduction
Kit*, section 5.4). The runner does not yet repeat statistical checks; until it
does, the fields record what a check must do.

## What `symbolon pack validate` checks

1. `symbolon-pack.toml`, `BRIEF.md` and `obligations.toml` exist.
2. Every component listed in the manifest is present with the same digest, and none is unlisted.
3. `BRIEF.md` has the three required sections.
4. Every assumption file is well-formed, with a unique id.
5. Every obligation is well-formed, with a unique id.
6. Every `decided` or `default` obligation has checks, every `open` one has none,
   every constraint has a reason, every check exists, and every assumption it names exists.
7. A `statistical` obligation is not `open` and gives `samples`, `alpha` and
   `tolerance`; an exact one gives none of them.

It then reports obligations by status, source and exactness, assumptions and how many are
monitored, and how many of the components' checks trace to an obligation. It does
not run contract code; use `symbolon validate` on each component for that.
