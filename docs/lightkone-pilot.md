# Lightkone pilot

The first spec pack built from a real product: lightkone, a static web app for keeping a personal library of research papers. The pack lives in [kausalflow/symbola-registry](https://github.com/kausalflow/symbola-registry), under `packs/kausalflow/lightkone/`.

| Path | What it is | Ships to buyers |
| --- | --- | --- |
| `versions/1/` | The pack, version 1: BRIEF, PRODUCT (the app), AGENTS, assumptions, obligations, and eight component contracts | yes |
| `oracle/` | Publisher side: lightkone's own TypeScript bundled as command implementations, fixtures, example recorder, holdout, differential tester | no |
| `rebuilds/python-1/` | Milestone 1: an AI build in Python (Claude Opus 5.5 in Claude Code) of the first three contracts | no |
| `rebuilds/go-1/` | Milestone 2: a second AI build in Go of all eight contracts, with its NOTES.md | no |
| `attestations/` | Signed evidence for both builds, plus the runner keys | yes, as evidence |

## What the pack covers

`PRODUCT.md` describes the app a build delivers: its shape, files, screens, flows and interfaces, and the components each flow uses. The components are the app's core:

| Component | What it does |
| --- | --- |
| `lightkone/search-query@1` | The search box: filters, words with accent folding, ranking, sort orders, and the trash rule |
| `lightkone/bibtex-import@1` | Reading BibTeX from the common reference managers into paper drafts |
| `lightkone/bibtex-export@1` | Writing a paper as the exact BibTeX entry lightkone writes, byte for byte |
| `lightkone/citation-key@1` | Paperpile-style citation keys for new papers, unique within the library |
| `lightkone/pdf-filing@1` | Where a paper's PDF goes, named the way Paperpile names it |
| `lightkone/library-merge@1` | Merging two devices' edits to `library.json` without losing either |
| `lightkone/tidy@1` | Finding duplicate papers and how to merge each group |
| `lightkone/library-file@1` | Reading `library.json` and writing it back, with `library.bib`, byte for byte |

`symbola pack validate packs/kausalflow/lightkone/versions/1` reports a product pack with 73 obligations (72 decided, 1 open, 5 of them unchecked app decisions) and 4 assumptions, and every one of the components' 360 checks traces to an obligation.

## The field test: components are not the product

On 2026-10-25 kausalflow asked a coding agent to build lightkone from the pack, as a user would. It ported all eight components faithfully and then wrapped them in a demo page that looked nothing like lightkone, because the pack described the app in one paragraph and said later versions would add the rest. Every earlier build had passed because it was asked for the components only. The fix is `PRODUCT.md` ([pack format](PACK_FORMAT.md#productmd)): a pack with it is built as the product, and the build steps on its page say so.

## Results (milestone 4: replicate over the whole pack)

`symbola replicate` gave all eight components to three Claude Code builds: Sonnet, Opus and Haiku. Lightkone was the reference and the holdout was on. All three builders wrote Python, and their logs show no reads outside the builder's copy. The builds took 11, 16 and 21 minutes and cost $1.76, $5.13 and $1.15 in agent time.

Every build passed every component and every holdout: 24 of 24 on both. They still differ. `diff` found 27 splits, 15 of them in `bibtex-import`. Builders' probes found 12 of the 27. `bibtex-export` and `citation-key` converged.

| Kind | Splits | Examples |
| --- | --- | --- |
| One build differs from lightkone and the other two, on well-formed input; the checks of a decided obligation miss it | 9 | Opus keeps duplicate tags when merging (`merge.sets`). Haiku does not treat U+FEFF as whitespace in filing and search. Haiku strips a DOI's trailing `/` and a page range's letters. Sonnet takes `annote` over `note`. Sonnet and Haiku print large numbers in `library.json` differently from JavaScript. Haiku reads `"a b"c` differently |
| One build differs on truncated or broken BibTeX | 9 | Unclosed `\emph{`, a field cut off after `=` |
| All three builds agree and lightkone differs | 3 | **Lightkone's `tidy` crashes (TypeError) on a paper with no `authors`**, although the contract's `Input` accepts one. On two broken BibTeX inputs, lightkone keeps a stray `"` in a venue, or returns an entry from an unclosed `{{` |
| Allowed by the pack | 1 | `year:2.017e3`: the contract leaves number spellings other than digits and a fraction unspecified |
| Ordering of rare symbols in title sort (format tier) | 1 | Opus's collation differs on symbols such as `⯛` and `ѽ` |

The row where all builds agree against lightkone is what replication alone cannot show: there is no disagreement among the builds to find. Only the reference shows it. The milestone 1 to 3 builds never reached the `tidy` crash, because no example has a paper without authors.

The weaker builder needed more from the pack. Haiku's splits were on Unicode whitespace and DOI and page normalisation, points Sonnet and Opus got right from the description. Opus, the strongest model, had most of the `bibtex-import` and `library-merge` splits: it read more into the text than the examples pinned. A pack that converges for one builder may not converge for another (design v0.5, "minimal for whom").

Kausalflow chose (2026-10-24) to pin lightkone's behaviour on the well-formed points and leave broken BibTeX for later. The pack now lives in kausalflow/symbola-registry. The change is [symbola-registry#5](https://github.com/kausalflow/symbola-registry/pull/5). It records examples from lightkone and adds them to the obligations that missed these points:

- `merge.sets`: a tag listed twice is kept once.
- `filing.paperpile-layout`: U+FEFF is whitespace.
- `search.query-tokens`: a quoted phrase ends at its closing quote. Search whitespace was already pinned by `search.whitespace`.
- `import.identifiers`: a DOI keeps its trailing slash.
- `import.draft-fields`: `annote` wins whenever the entry has one, even when it is empty, and pages keep their letters.
- `file.exact-text`: numbers print as JavaScript prints them.

Lightkone passes the five changed contracts and is re-attested on them by `runner-c`. The `tidy` crash is filed as [kausalflow/lightkone#54](https://github.com/kausalflow/lightkone/issues/54). The pack will record an example once lightkone is fixed.

## Results (milestone 3: the first `replicate` runs)

`symbola replicate` handed `search-query` and `citation-key` to two Claude Code builds, one on Sonnet and one on Opus, with lightkone as the reference and the publisher's holdout. Each agent got only the builder's copy of `versions/1/`. Their logs show no reads outside it. Both chose Python. The runs cost $1.41 and $1.56 in agent time, and each took under eight minutes.

| Run | Builds pass | Holdout | Splits found | What it showed |
| --- | --- | --- | --- | --- |
| 1 | 2/2 on both | 2/2 on both | 0 in 1,113 inputs | Converged, but wrongly: by hand, `author:` with nothing after the colon runs differently, and both builders had written that point down |
| 2, with probes | 2/2 on both | 2/2 on both | 2, both from probes | `author:` (Opus finds every paper; lightkone and Sonnet find none) and an unknown field with a quoted value, `o:"bar baz"` (Opus splits it into two words; lightkone and Sonnet keep one word) |

So passing every check and the holdout still left two gaps in `search-query`, and only the builders' own probes found them. Builders now attach `probes` to each reading in `readings.toml`, and `diff` runs every build's probes on every build. Kausalflow chose lightkone's behaviour for both (2026-10-24). `search-query` now states the rule and has three new examples recorded from lightkone, under a new decided obligation, `search.field-edge-cases`, whose source is `replication`. Lightkone and the Sonnet build pass the new contract. The Opus build fails it, and so does the milestone 2 Go build, on `o:"bar baz"`: the gap was already there in milestone 2, and nothing caught it. Lightkone is re-attested on the new digest by a new runner key, `attestations/runner-c.pub`, in the process sandbox. The Go and Python attestations for `search-query` stay as they are; they are for the earlier digests.

## Results (milestone 2)

Five more contracts: `citation-key`, `pdf-filing`, `library-merge`, `tidy`, and `library-file`, the data contract for `library.json` itself (how lightkone reads it and writes it back, byte for byte, with `library.bib`). Contracts can now share sample data in `fixtures/`, including raw text files with `{"$text": ...}`; `library-file` ships three sample libraries.

| Contract | Checks | lightkone | Go rebuild | Holdout (Go) | Second runner |
| --- | --- | --- | --- | --- | --- |
| `lightkone/search-query@1` | 81 examples + 11 properties | PASSED | PASSED | 101/101 | reproduced both |
| `lightkone/bibtex-import@1` | 37 examples + 13 properties | PASSED | PASSED | 56/56 | reproduced both |
| `lightkone/bibtex-export@1` | 19 examples + 6 properties | PASSED | PASSED | 28/28 | reproduced both |
| `lightkone/citation-key@1` | 19 examples + 6 properties | PASSED | PASSED | 28/28 | reproduced both |
| `lightkone/pdf-filing@1` | 19 examples + 6 properties | PASSED | PASSED | 28/28 | reproduced both |
| `lightkone/library-merge@1` | 21 examples + 8 properties | PASSED | PASSED | 31/31 | reproduced both |
| `lightkone/tidy@1` | 21 examples + 5 properties | PASSED | PASSED | 28/28 | reproduced both |
| `lightkone/library-file@1` | 39 examples + 7 properties | PASSED | PASSED | 54/54 | reproduced both |

How it went:

1. **Second build, second language.** A fresh Claude Code session (Claude Opus 5.5, the same model as the Python build, with no access to it) got only `versions/1/` and built all eight components in Go (standard library only), with lightkone, the oracle and the Python rebuild moved off the machine. It passed all eight contracts and all eight holdouts.
2. **Passing is not agreeing.** `oracle/differential.py` sends the same generated inputs to lightkone and the Go build and reports every disagreement on inputs the contract accepts. On about 5,000 inputs, six contracts agreed completely. `bibtex-import` and `search-query` showed five real gaps that both the spec and the holdout had missed:
   - a malformed BibTeX field skipped to a `}` ends the entry, but one skipped to a comma does not (the contract said the rest was always lost);
   - "whitespace" means JavaScript's `\s`, including no-break space and U+2028;
   - the arXiv URL match ignores case, so `V3` and `.PDF` are stripped;
   - `year:` terms that are not numbers do not count, and do not replace an earlier one;
   - `title` sort is Unicode collation (`localeCompare`), not code-point order.
3. **Tightened and rebuilt.** The contracts now state each rule, with 18 new examples recorded from lightkone. The Go builder revised from the new text alone (adding `golang.org/x/text` for collation) and passes. The differential test then found no disagreement on search-query within scope, and 11 in 2,000 heavily mutated BibTeX files, all deliberately broken input (unbalanced braces, a value starting with `#`); those are left for a later version.
4. **Evidence.** Runner A attested lightkone and the Go build on all eight contracts; runner B re-ran all sixteen in fresh containers with identical outcomes. The Python build's milestone 1 attestations are kept: they are for the earlier digests of search-query and bibtex-import.

The pack now has 63 obligations, all decided. Four defaults that were lightkone bugs are fixed and decided: papers in the trash are left out of `library.bib`, and top-level keys of `library.json` that lightkone does not use are kept on save (lightkone#51); a user folder named in capitals (`ML`, `2019`) is no longer taken for a Paperpile author folder unless it is an author's surname, and blank DOIs no longer match each other in tidy (lightkone#52). On 2026-10-24 kausalflow settled the last five: an empty `journal` no longer hides the `booktitle` as the venue, and a `library.json` saved by a newer lightkone is refused rather than read as version 1 (lightkone#53); a mistyped `year:` filter still filters nothing, title sort keeps Unicode collation, and import keeps JavaScript's whitespace set.

Two Symbola bugs turned up and are fixed: examples containing U+2028 were split into two lines, and the container sandbox removed the execute bit, so no compiled implementation could run.

## Results (milestone 1)

| Contract | Checks | lightkone (oracle) | Python rebuild | Holdout (rebuild) | Second runner |
| --- | --- | --- | --- | --- | --- |
| `lightkone/search-query@1` | 71 examples + 11 properties | PASSED | PASSED | 91/91 | reproduced both |
| `lightkone/bibtex-import@1` | 28 examples + 13 properties | PASSED | PASSED | 47/47 | reproduced both |
| `lightkone/bibtex-export@1` | 19 examples + 6 properties | PASSED | PASSED | 28/28 | reproduced both |

1. **Oracle check.** Examples were recorded by running lightkone's own code through the command protocol. The properties were written from the description, and lightkone passed all of them.
2. **Replication.** An AI builder got only `versions/1/`, with lightkone's source and the oracle moved off the machine. It passed all three contracts, then passed the holdout: a different property seed, 5× the generated cases, and 18 examples it never saw.
3. **Divergence found.** Comparing the two builds on the builder's listed ambiguities found one real gap in how repeated `year:` filters combine. The contract now states the rule, with a property and two examples for it, and both builds pass it.
4. **Reproduction.** A second runner key re-ran all six attestations in a fresh container, and every check had the same outcome.
5. **Kill rate.** Plausible wrong versions of the rebuild live in `examples/mutants/lightkone/`, outside the pack so the component digests stay put. search-query rejects 8 of 9; the one survivor ignores a malformed `year:` term, which is exactly what the `open` obligation `search.year-malformed` leaves to the builder. bibtex-export rejects 7 of 7. bibtex-import rejects 7 of 8; the survivor reads a two-digit year like `99` as a number, which the description rules out but no check covers, so it is a gap for the next pack version.

## Measuring the remaining ambiguity

`symbola diff` turns the milestone 2 differential test into a command that works on any number of builds (see [Measuring ambiguity](guides/measuring-ambiguity.md)). Run on `search-query` with lightkone as the reference and both rebuilds, it puts the Go build at distance 0 from lightkone. It finds the two rules milestone 2 tightened, `search.year-malformed` and `search.title-sort-other`, as the splits between the milestone 1 Python build and the other two. On `bibtex-import`, after the importer fix in kausalflow/lightkone#50, it finds no disagreement between lightkone and the Go build.

## Re-running the evidence

```bash
git clone https://github.com/kausalflow/symbola-registry && cd symbola-registry/packs/kausalflow/lightkone
symbola pack validate 1
symbola verify attestations/search-query.go-1.json --trust attestations/runner-a.pub \
  --contract versions/1/components/search-query/versions/1 --impl rebuilds/go-1/search-query --rerun
```

The pack's own `README.md` has the full notes, including the three importer bugs the contracts found, now fixed in lightkone#50.
