# Lightkone pilot

The first spec pack built from a real product: lightkone, a static web app for keeping a personal library of research papers. The pack lives in `packs/kausalflow/lightkone/`.

| Path | What it is | Ships to buyers |
| --- | --- | --- |
| `1/` | The pack: BRIEF, AGENTS, assumptions, obligations, and three component contracts | yes |
| `oracle/` | Publisher side: lightkone's own TypeScript bundled as command implementations, fixtures, example recorder, holdout | no |
| `rebuilds/python-1/` | An AI build in Python made from `1/` alone, with the builder's NOTES.md | no |
| `attestations/` | Signed evidence for both builds, plus the runner keys | yes, as evidence |

## What the pack covers

| Component | What it does |
| --- | --- |
| `lightkone/search-query@1` | The search box: filters, words with accent folding, ranking, sort orders, and the trash rule |
| `lightkone/bibtex-import@1` | Reading BibTeX from the common reference managers into paper drafts |
| `lightkone/bibtex-export@1` | Writing a paper as the exact BibTeX entry lightkone writes, byte for byte |

`symbolon pack validate packs/kausalflow/lightkone/1` reports 35 obligations (30 decided, 1 default, 4 open) and 4 assumptions, and every one of the components' 148 checks traces to an obligation.

## Results

| Contract | Checks | lightkone (oracle) | Python rebuild | Holdout (rebuild) | Second runner |
| --- | --- | --- | --- | --- | --- |
| `lightkone/search-query@1` | 71 examples + 11 properties | PASSED | PASSED | 91/91 | reproduced both |
| `lightkone/bibtex-import@1` | 28 examples + 13 properties | PASSED | PASSED | 47/47 | reproduced both |
| `lightkone/bibtex-export@1` | 19 examples + 6 properties | PASSED | PASSED | 28/28 | reproduced both |

1. **Oracle check.** Examples were recorded by running lightkone's own code through the command protocol. The properties were written from the description, and lightkone passed all of them.
2. **Replication.** An AI builder got only `1/`, with lightkone's source and the oracle moved off the machine. It passed all three contracts, then passed the holdout: a different property seed, 5× the generated cases, and 18 examples it never saw.
3. **Divergence found.** Comparing the two builds on the builder's listed ambiguities found one real gap in how repeated `year:` filters combine. The contract now states the rule, with a property and two examples for it, and both builds pass it.
4. **Reproduction.** A second runner key re-ran all six attestations in a fresh container, and every check had the same outcome.
5. **Kill rate.** Plausible wrong versions of the rebuild live in `examples/mutants/lightkone/`, outside the pack so the component digests stay put. search-query rejects 8 of 9; the one survivor ignores a malformed `year:` term, which is exactly what the `open` obligation `search.year-malformed` leaves to the builder. bibtex-export rejects 7 of 7. bibtex-import has no mutants yet.

## Re-running the evidence

```bash
cd packs/kausalflow/lightkone
symbolon pack validate 1
symbolon verify attestations/search-query.python-1.json --trust attestations/runner-a.pub \
  --contract 1/components/search-query/1 --impl rebuilds/python-1/search-query --rerun
```

The pack's own `README.md` has the full notes, including lightkone quirks the contracts pin rather than fix.
