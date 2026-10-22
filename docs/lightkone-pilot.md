# Lightkone pilot

The first spec pack built from a real product: lightkone, a static web app for keeping a personal library of research papers. The pack lives in `packs/kausalflow/lightkone/`.

| Path | What it is | Ships to buyers |
| --- | --- | --- |
| `1/` | The pack: BRIEF, AGENTS, assumptions, obligations, and eight component contracts | yes |
| `oracle/` | Publisher side: lightkone's own TypeScript bundled as command implementations, fixtures, example recorder, holdout, differential tester | no |
| `rebuilds/python-1/` | Milestone 1: an AI build in Python of the first three contracts | no |
| `rebuilds/go-1/` | Milestone 2: a second AI's build in Go of all eight contracts, with its NOTES.md | no |
| `attestations/` | Signed evidence for both builds, plus the runner keys | yes, as evidence |

## What the pack covers

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

`symbolon pack validate packs/kausalflow/lightkone/1` reports 63 obligations (53 decided, 9 default, 1 open) and 4 assumptions, and every one of the components' 317 checks traces to an obligation.

## Results (milestone 2)

Five more contracts: `citation-key`, `pdf-filing`, `library-merge`, `tidy`, and `library-file`, the data contract for `library.json` itself (how lightkone reads it and writes it back, byte for byte, with `library.bib`). Contracts can now share sample data in `fixtures/`, including raw text files with `{"$text": ...}`; `library-file` ships three sample libraries.

| Contract | Checks | lightkone | Go rebuild | Holdout (Go) | Second runner |
| --- | --- | --- | --- | --- | --- |
| `lightkone/search-query@1` | 81 examples + 11 properties | PASSED | PASSED | 101/101 | reproduced both |
| `lightkone/bibtex-import@1` | 36 examples + 13 properties | PASSED | PASSED | 55/55 | reproduced both |
| `lightkone/bibtex-export@1` | 19 examples + 6 properties | PASSED | PASSED | 28/28 | reproduced both |
| `lightkone/citation-key@1` | 19 examples + 6 properties | PASSED | PASSED | 28/28 | reproduced both |
| `lightkone/pdf-filing@1` | 19 examples + 6 properties | PASSED | PASSED | 28/28 | reproduced both |
| `lightkone/library-merge@1` | 21 examples + 8 properties | PASSED | PASSED | 31/31 | reproduced both |
| `lightkone/tidy@1` | 21 examples + 5 properties | PASSED | PASSED | 28/28 | reproduced both |
| `lightkone/library-file@1` | 39 examples + 7 properties | PASSED | PASSED | 54/54 | reproduced both |

How it went:

1. **Second builder, second language.** A different AI model got only `1/` and built all eight components in Go (standard library only), with lightkone, the oracle and the Python rebuild moved off the machine. It passed all eight contracts and all eight holdouts.
2. **Passing is not agreeing.** `oracle/differential.py` sends the same generated inputs to lightkone and the Go build and reports every disagreement on inputs the contract accepts. On about 5,000 inputs, six contracts agreed completely. `bibtex-import` and `search-query` showed five real gaps that both the spec and the holdout had missed:
   - a malformed BibTeX field skipped to a `}` ends the entry, but one skipped to a comma does not (the contract said the rest was always lost);
   - "whitespace" means JavaScript's `\s`, including no-break space and U+2028;
   - the arXiv URL match ignores case, so `V3` and `.PDF` are stripped;
   - `year:` terms that are not numbers do not count, and do not replace an earlier one;
   - `title` sort is Unicode collation (`localeCompare`), not code-point order.
3. **Tightened and rebuilt.** The contracts now state each rule, with 18 new examples recorded from lightkone. The Go builder revised from the new text alone (adding `golang.org/x/text` for collation) and passes. The differential test then found no disagreement on search-query within scope, and 11 in 2,000 heavily mutated BibTeX files, all deliberately broken input (unbalanced braces, a value starting with `#`); those are left for a later version.
4. **Evidence.** Runner A attested lightkone and the Go build on all eight contracts; runner B re-ran all sixteen in fresh containers with identical outcomes. The Python build's milestone 1 attestations are kept: they are for the earlier digests of search-query and bibtex-import.

The pack now has 63 obligations: 53 decided, 9 defaults (lightkone's current behaviour, pinned until kausalflow decides), 1 open. Defaults that look like lightkone bugs: trashed papers are still written to `library.bib`, a user folder named in capitals (`ML`, `2019`) is taken for a Paperpile author folder, unknown top-level keys of `library.json` are dropped on save, whitespace-only DOIs match each other in tidy, and fields after a malformed BibTeX field are lost when the skip reaches a `}`.

Two Symbolon bugs turned up and are fixed: examples containing U+2028 were split into two lines, and the container sandbox removed the execute bit, so no compiled implementation could run.

## Results (milestone 1)

| Contract | Checks | lightkone (oracle) | Python rebuild | Holdout (rebuild) | Second runner |
| --- | --- | --- | --- | --- | --- |
| `lightkone/search-query@1` | 71 examples + 11 properties | PASSED | PASSED | 91/91 | reproduced both |
| `lightkone/bibtex-import@1` | 28 examples + 13 properties | PASSED | PASSED | 47/47 | reproduced both |
| `lightkone/bibtex-export@1` | 19 examples + 6 properties | PASSED | PASSED | 28/28 | reproduced both |

1. **Oracle check.** Examples were recorded by running lightkone's own code through the command protocol. The properties were written from the description, and lightkone passed all of them.
2. **Replication.** An AI builder got only `1/`, with lightkone's source and the oracle moved off the machine. It passed all three contracts, then passed the holdout: a different property seed, 5× the generated cases, and 18 examples it never saw.
3. **Divergence found.** Comparing the two builds on the builder's listed ambiguities found one real gap in how repeated `year:` filters combine. The contract now states the rule, with a property and two examples for it, and both builds pass it.
4. **Reproduction.** A second runner key re-ran all six attestations in a fresh container, and every check had the same outcome.
5. **Kill rate.** Plausible wrong versions of the rebuild live in `examples/mutants/lightkone/`, outside the pack so the component digests stay put. search-query rejects 8 of 9; the one survivor ignores a malformed `year:` term, which is exactly what the `open` obligation `search.year-malformed` leaves to the builder. bibtex-export rejects 7 of 7. bibtex-import rejects 7 of 8; the survivor reads a two-digit year like `99` as a number, which the description rules out but no check covers, so it is a gap for the next pack version.

## Re-running the evidence

```bash
cd packs/kausalflow/lightkone
symbolon pack validate 1
symbolon verify attestations/search-query.go-1.json --trust attestations/runner-a.pub \
  --contract 1/components/search-query/1 --impl rebuilds/go-1/search-query --rerun
```

The pack's own `README.md` has the full notes, including lightkone quirks the contracts pin rather than fix.
