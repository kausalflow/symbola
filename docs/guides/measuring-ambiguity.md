# Measuring ambiguity

Passing a contract shows a build agrees with the spec on the cases the spec
samples. Two builds that both pass can still behave differently. Each difference
is a point the contract leaves undecided, whether or not anyone meant it to.
`symbolon diff` finds these points and measures how much they cost. It follows
the sufficiency test in *The Probabilistic Minimal Reproduction Kit* (sections 4
and 6.2).

## Run it

```bash
cd symbolon-registry/packs/kausalflow/lightkone   # a clone of kausalflow/symbolon-registry
symbolon diff versions/1/components/search-query/versions/1 \
  oracle/search-query rebuilds/go-1/search-query rebuilds/python-1/search-query \
  --reference oracle -o diff-search-query.json
```

```
pool       1295 inputs (80 example, 718 property, 315 mutation, 182 search), 188 with a disagreement
ensemble   go-1  weight 1  no [generator] recorded
ensemble   python-1  weight 1  python  (built for another contract digest)
reference  oracle  (compared, not in the ensemble)
distance   oracle | go-1  0.0000
distance   oracle | python-1  0.1028
distance   go-1 | python-1  0.1028
ambiguity  0.1028  (95% 0.0865–0.1230; expected error ≥ 0.0514)
...
splits, largest first (3):
1. oracle, go-1 | python-1   95% of ambiguity, 127 inputs, value
   traces to  search.year-malformed
   witness    {"papers": [...], "query": "..."}
2. oracle, go-1 | python-1   4% of ambiguity, 55 inputs, format
   traces to  search.title-sort-other
```

The Python build is from milestone 1, before the year and title-sort rules were
tightened, so `diff` finds those two rules again from the builds alone.

## The input pool

| Source | What it adds |
| --- | --- |
| Examples | Every example input |
| Properties | The inputs each property's generator produces (`--property-cases` per property) |
| Mutations | Copies of the above with a changed leaf, or a list item dropped, repeated or swapped (`--mutations`) |
| `--pool FILE` | Your own inputs, one JSON input or `{"input": ...}` per line |
| Search | More mutations of each disagreeing input, since a split is rarely found by one input alone (`--search`) |

Only inputs the contract's `Input` accepts are used. Random generators rarely
produce the rare combinations where readings differ. In the lightkone pilot, the
year rule hid for that reason: no generated query had an exact year followed by a
range. Mutation and search are there to find these.

The pool is not a sample of real use, so its estimate is biased towards the inputs
the spec already thinks about. Pass `--realistic FILE` with inputs drawn from real
use (exported libraries, logged queries) to get a separate estimate on that pool alone.

## What the numbers mean

- **Distance** between two builds: the share of inputs on which they disagree,
  weighted by severity. A `crash` (an output that breaks the schema, or a process
  that died) and a different `value` cost 1. A `format` difference costs 0.1:
  outputs that agree once case, spacing and list order are ignored. Change the costs
  with `--severity`.
- **Ambiguity**: the expected distance between two builds drawn from the ensemble,
  with a bootstrap interval over inputs. Half of it is a lower bound on the expected
  error of a build, whatever the intended behaviour is. Disagreement is not the only
  source of error: builds can all agree on the same wrong reading, and that shows
  only against the reference, a holdout or mutants.
- **Behaviours**: builds with identical outcomes on every input form one class.
  The Chao estimate guesses how many classes have not been seen yet. Both need
  more than a handful of builds to mean much.
- **Error vs reference**: each build's distance to `--reference`, when there is one.
  The reference is not part of the ensemble, so the ambiguity does not need it.

## Splits and the ambiguity map

A split is one way the builds divide (`oracle, go-1 | python-1`) about one thing.
That thing is the obligations whose checks the inputs came from, or the inputs'
origin when nothing traces. Splits are ranked by their share of the ambiguity, so
the first one is the question worth settling first. Each split has a witness, its
smallest input, shrunk while the builds still split the same way.

"no obligation: a gap in the pack" means the inputs came from a `--pool` file or
from checks no obligation lists. Settle it by adding an obligation with a check,
or by marking the point `open`.

## The ensemble

The estimate is only as good as the builds behind it. One model tends to choose
the same reading every time, so the builds should come from several model
families and at least two languages. Record each build's model in its
`symbolon-impl.toml`:

```toml
[generator]
model = "..."
family = "..."
language = "go"
```

`--weight NAME=W` gives a build more or less weight (default 1). The report's
`ensemble` table records all of this next to the estimate.

## Readings

Builders should record the points where they chose between readings, in
`readings.toml` next to the build. It goes in the implementation directory, or at
the build root with a `component` on each entry:

```toml
[[reading]]
component = "search-query"
point = "Two year: terms in one query"
obligation = "search.year-last-wins"    # optional: the obligation it is about
considered = ["all must hold", "last wins"]
chosen = "last wins"
probes = [                              # optional: inputs where the readings differ
  { papers = { "$fixture" = "library.json" }, sort = "added", query = "year:2019 year:2017" },
]
```

`diff` lists the points that two or more builds recorded, by the same wording, and
chose differently. More useful are the `probes`: every build's probes go into the
pool for all builds, so a point one builder noticed is tested on every build,
whatever the others wrote. Probes may name the contract's `fixtures/` like examples
do; a probe the contract's `Input` rejects is dropped. Splits found by a probe show
`pool:probes-<build>.jsonl` as their origin.

In the first real `replicate` run on lightkone, two builds agreed on all 1,113 pooled
inputs, yet ran differently on `author:` with nothing after the colon, a point
both builders had written down. Probes catch exactly this.

## In CI

```bash
symbolon diff CONTRACT build-a build-b --max-ambiguity 0.01
```

This exits 1 when the estimate is above the threshold. A contract change that
raises the ambiguity is a regression of the contract, even if every check passes.
