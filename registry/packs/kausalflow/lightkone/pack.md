# kausalflow/lightkone (version 1)

Pack digest: `sha256:149c31512ee855ae94efd4eac6565c2b2c03d12bf62649e14053083e2cdaf2de`. Every file of the pack follows, one section each.

## AGENTS.md

# AGENTS.md

This is a Symbolon spec pack for lightkone's core components. Build from it;
do not look for lightkone's source.

1. Read `BRIEF.md`: what the product is, its non-goals and priorities.
2. Read `assumptions/`: what you may take as true about the world. Don't build for cases they rule out.
3. Read `obligations.toml`: the decisions you must keep. Obligations marked `open` are yours to choose.
4. Each component's full specification is `components/<name>/versions/1/`: `symbolon.toml`
   (the description), `schema.py`, `examples.jsonl` and `properties.py`. Where the
   description and an example seem to disagree, the example is what lightkone does.

**Harness.** An implementation is a directory with `symbolon-impl.toml`
(`symbolon impl-init <dir> --contract components/<name>/versions/1`). In Python, define
`run(input)` returning the contract's output; in any other language, a program
that reads one JSON input per line on stdin and writes `{"output": ...}` per
line (`docs/ATTESTATION.md`, "Implementations in other languages").

**Done** means `symbolon attest components/<name>/versions/1 <impl-dir>` reports PASSED
for every component. Don't special-case the examples: the properties generate
other inputs, and the publisher keeps a holdout. Write questions about unclear
parts, and the reading you chose, in `NOTES.md` next to your build.

**If the spec contradicts itself** (an example disagrees with the description or
with a property), don't code around it. Run
`symbolon flag <component>#example:<line> "<what disagrees, and the reading you chose>" --dir <impl-dir>`,
build the reading you think is right, and carry on. A flagged contradiction counts
in your favour; matching an example the spec rules out does not.

## BRIEF.md

# Lightkone

Lightkone is a research-paper library for people who read a lot of papers and
want to own their data. It is a static web app with no server: the library is
plain files (`lightkone/library.json` and a generated `library.bib`) in storage
the owner chooses, such as the browser, an S3 or R2 bucket, or a GitHub
repository.

People use it to collect papers (by DOI, arXiv id, BibTeX import or PDF), find
them again with a small query language, file them in folders, tag them, read
and highlight PDFs, and keep `.bib` files in sync with their manuscripts on
Overleaf.

## What this version of the pack covers

Version 1 covers the pure components everything else leans on, and the
library file they all share:

| Component | What it does |
| --- | --- |
| `lightkone/search-query@1` | The search box: filters (`tag:`, `author:`, `year:`, `in:`, `has:`, `no:`, `is:`), words with accent folding, ranking, sort orders, and the trash rule |
| `lightkone/bibtex-import@1` | Reading BibTeX from Paperpile, Zotero, JabRef and Google Scholar into paper drafts, including LaTeX accents, macros, author names and arXiv ids |
| `lightkone/bibtex-export@1` | Writing a paper as the exact BibTeX entry lightkone writes, byte for byte |
| `lightkone/citation-key@1` | Paperpile-style citation keys for new papers, unique within the library |
| `lightkone/pdf-filing@1` | Where a paper's PDF goes, named the way Paperpile names it |
| `lightkone/library-merge@1` | Merging two devices' edits to `library.json` without losing either |
| `lightkone/tidy@1` | Finding duplicate papers and how to merge each group |
| `lightkone/library-file@1` | Reading `library.json` and writing it back, with `library.bib`, byte for byte |

Later versions add the MCP server's tools and UI acceptance scenarios.

## Who it is for

Builders who want lightkone's behavior in their own stack: a different
language, a server instead of a static app, or a fork with their own features.
A build that passes these contracts reads the same queries and BibTeX the same
way lightkone does, so its users' libraries and habits carry over.

## Non-goals

- Full-text search inside PDFs. Search covers metadata and notes only.
- Collaboration. A library belongs to one person; there are no shared libraries, roles or permissions.
- Being a general BibTeX validator. Import reads what the common managers export and skips the rest.
- Pixel-level UI. Later versions specify user flows, not layout or styling.

## Priorities

When goals conflict, earlier ones win:

1. **The owner's data stays theirs and stays readable.** Never lose or corrupt a library, and keep it in plain files.
2. **Compatibility with lightkone's files.** A build reads and writes the same `library.json` and `library.bib`, byte for byte where the contracts say so.
3. **Same answers to the same queries,** so habits carry over between builds.
4. Speed and features beyond the pack.

## Who resolves gaps

kausalflow, as the namespace holder. If the pack doesn't settle something, record the
question and the reading you chose in `NOTES.md` next to your build; obligations marked
`open` in `obligations.toml` are yours to choose. Unsettled questions are answered in the
next version of the pack.

## assumptions/bibtex-sources.toml

```toml
id = "K-bibtex-sources"
statement = "Imported BibTeX comes from Paperpile, Zotero, JabRef or Google Scholar exports, or from a library.bib lightkone wrote."
basis = "These are the managers lightkone's users migrate from; the import rules and examples were drawn from their exports."
monitor = "Count entries dropped per import; report when more than 5% of an import is dropped."
```

## assumptions/iso-timestamps.toml

```toml
id = "K-iso-timestamps"
statement = "Every added and opened timestamp was written by JavaScript's toISOString (UTC, milliseconds), so string order is time order."
basis = "lightkone writes all timestamps itself; libraries are not edited by other tools."
monitor = "On load, report papers whose timestamps do not match the schema pattern."
```

## assumptions/personal-library.toml

```toml
id = "K-personal-library"
statement = "A library belongs to one person, holds at most tens of thousands of papers, and is searched in memory on their device."
basis = "lightkone is a static app with no server, so search runs over the whole library in the browser."
monitor = "Report the library size when it is loaded."
```

## assumptions/single-writer.toml

```toml
id = "K-single-writer"
statement = "Two clients (devices, or Claude through MCP) do not write the same library within the moment between lightkone re-reading library.json and writing it."
basis = "Libraries are personal and saves are small. Writes that are minutes apart are reconciled by lightkone/library-merge; storage offers no lock for the instant in between."
monitor = "After each save, re-read library.json and report when it differs from what was written."
```

## obligations.toml

```toml
# Obligations of the lightkone spec pack (format: docs/PACK_FORMAT.md).
#
# Each obligation is one decision a builder could get wrong, with the checks
# that pin it down. status: decided (required), default (chosen; a fork may
# change it with a note), open (deliberately undecided; builds may differ).
# Checks are "<component>#example:<line in examples.jsonl>" or
# "<component>#<property test name>".
#
# This is a retrofit of the v1 pack, which was written before v0.5. Pruning
# (dropping obligations that builders get right unprompted) comes with
# `replicate` in step 4.

# ── search-query ──────────────────────────────────────────────────────────

[[obligation]]
id = "search.results-from-library"
statement = "Results are distinct ids of papers in the input library."
status = "decided"
source = "extract"
checks = ["search-query#test_results_are_distinct_papers_from_the_library"]

[[obligation]]
id = "search.trash"
statement = "Trashed papers appear only with is:trash, and then only trashed papers appear; an empty trashed field is not trashed."
status = "decided"
source = "extract"
checks = ["search-query#test_trash_shows_only_with_is_trash", "search-query#example:25", "search-query#example:61", "search-query#example:62"]

[[obligation]]
id = "search.query-tokens"
statement = "Terms split on whitespace; quotes make one word; an unknown field:value or unmatched quote is an ordinary word."
status = "decided"
source = "extract"
checks = ["search-query#example:8", "search-query#example:9", "search-query#example:21", "search-query#example:22", "search-query#example:23", "search-query#example:27"]

[[obligation]]
id = "search.terms-conjunctive"
statement = "Every filter and every word must hold (except year:, see search.year-last-wins)."
status = "decided"
source = "extract"
checks = ["search-query#test_terms_are_conjunctive", "search-query#example:7", "search-query#example:31", "search-query#example:36", "search-query#example:47", "search-query#example:52", "search-query#example:63", "search-query#example:71"]

[[obligation]]
id = "search.folding"
statement = "Text and query compare after NFKD, removing combining marks, and lower-casing."
status = "decided"
source = "extract"
checks = ["search-query#test_case_and_accents_in_the_query_do_not_matter", "search-query#example:12", "search-query#example:13", "search-query#example:14", "search-query#example:15", "search-query#example:16"]

[[obligation]]
id = "search.word-scoring"
statement = "A word scores 5 in the title, 4 in authors joined by ' ; ', 1 in the rest text; a paper with any zero-scoring word is left out."
status = "decided"
source = "extract"
checks = ["search-query#test_words_rank_title_over_author_over_rest", "search-query#example:3", "search-query#example:6", "search-query#example:10", "search-query#example:11", "search-query#example:17", "search-query#example:18", "search-query#example:19", "search-query#example:20", "search-query#example:24", "search-query#example:68", "search-query#example:69"]

[[obligation]]
id = "search.filter-tag"
statement = "tag:T matches a whole tag after folding, never a substring."
status = "decided"
source = "extract"
checks = ["search-query#test_each_filter_selects_what_it_says", "search-query#example:26", "search-query#example:28", "search-query#example:29", "search-query#example:30", "search-query#example:32"]

[[obligation]]
id = "search.filter-author"
statement = "author:A is a substring of the folded authors joined with ' ; '."
status = "decided"
source = "extract"
checks = ["search-query#test_each_filter_selects_what_it_says", "search-query#example:33", "search-query#example:34", "search-query#example:35"]

[[obligation]]
id = "search.filter-year"
statement = "year:Y is an exact year and year:A-B an inclusive range; a missing year never matches."
status = "decided"
source = "extract"
checks = ["search-query#test_each_filter_selects_what_it_says", "search-query#example:37", "search-query#example:38", "search-query#example:39"]

[[obligation]]
id = "search.year-last-wins"
statement = "Only the last year: term that counts applies; a term whose value is not a number does not count."
status = "decided"
source = "replication"
reason = "The python-1 rebuild read repeated year: filters differently; lightkone keeps one year slot."
checks = ["search-query#test_only_the_last_year_filter_counts", "search-query#example:40", "search-query#example:41", "search-query#example:42"]

[[obligation]]
id = "search.year-malformed"
statement = "year:A-B parts: A not a number or 0 means the term does not count; B missing, empty, 0 or not a number means A; later parts are ignored. A typo such as year:20l7 filters nothing, by kausalflow's decision (2026-10-24): forgiving, low stakes."
status = "decided"
source = "replication"
checks = ["search-query#example:74", "search-query#example:75", "search-query#example:76", "search-query#example:77", "search-query#example:78", "search-query#example:79", "search-query#example:80", "search-query#example:81"]

[[obligation]]
id = "search.filter-folder"
statement = "in:F matches folder F and folders inside it, after folding, ignoring trailing slashes, never by name prefix."
status = "decided"
source = "extract"
checks = ["search-query#test_each_filter_selects_what_it_says", "search-query#example:43", "search-query#example:44", "search-query#example:45", "search-query#example:46"]

[[obligation]]
id = "search.filter-has-no"
statement = "has:/no: test presence of pdf, abstract, arxiv and notes; empty counts as absent; has:pdf also accepts file; unknown values are ignored."
status = "decided"
source = "extract"
checks = ["search-query#test_each_filter_selects_what_it_says", "search-query#example:48", "search-query#example:49", "search-query#example:50", "search-query#example:51", "search-query#example:53", "search-query#example:54", "search-query#example:55", "search-query#example:56"]

[[obligation]]
id = "search.filter-is"
statement = "is:starred and is:recent select starred and opened papers; unknown is: values are ignored."
status = "decided"
source = "extract"
checks = ["search-query#test_each_filter_selects_what_it_says", "search-query#example:57", "search-query#example:64"]

[[obligation]]
id = "search.default-order"
statement = "The default sort is newest added first, relevance when there are words, opened with is:recent; ties keep input order, relevance ties fall back to newest added."
status = "decided"
source = "extract"
checks = ["search-query#test_empty_query_lists_the_library_newest_first", "search-query#example:1", "search-query#example:2", "search-query#example:4", "search-query#example:59", "search-query#example:67", "search-query#example:70"]
assumes = ["K-iso-timestamps"]

[[obligation]]
id = "search.explicit-sorts"
statement = "year: later first, missing as 0; opened: latest first, never-opened last; an explicit sort overrides the default."
status = "decided"
source = "extract"
checks = ["search-query#test_year_sort_puts_later_years_first", "search-query#test_opened_order_and_is_recent", "search-query#example:5", "search-query#example:58", "search-query#example:60", "search-query#example:65", "search-query#example:66"]
assumes = ["K-iso-timestamps"]

[[obligation]]
id = "search.title-sort-ascii"
statement = "title: sort is ascending and stable for titles of lowercase ASCII letters, digits and spaces."
status = "decided"
source = "extract"
checks = ["search-query#test_title_sort_is_ascending_and_stable"]

[[obligation]]
id = "search.title-sort-other"
statement = "title: sort uses Unicode collation (CLDR root, tertiary), as JavaScript's localeCompare does: accents and case only break ties. Kept by kausalflow's decision (2026-10-24); builds need an ICU-grade collator."
status = "decided"
source = "replication"
checks = ["search-query#example:72", "search-query#example:73"]

# ── bibtex-import ─────────────────────────────────────────────────────────

[[obligation]]
id = "import.never-fails"
statement = "Import never fails: malformed parts are skipped and the rest is read."
status = "decided"
kind = "constraint"
source = "extract"
reason = "People import whole .bib files from other managers; one bad entry must not lose the file."
checks = ["bibtex-import#test_well_formed_entries_become_drafts", "bibtex-import#example:24", "bibtex-import#example:25", "bibtex-import#example:26"]
assumes = ["K-bibtex-sources"]

[[obligation]]
id = "import.entries"
statement = "@type{key, fields} and @type(key, fields) become drafts; @comment, @preamble and untitled entries do not."
status = "decided"
source = "extract"
checks = ["bibtex-import#test_entries_without_a_title_are_left_out", "bibtex-import#test_comments_and_preambles_are_not_entries", "bibtex-import#example:1", "bibtex-import#example:2", "bibtex-import#example:7", "bibtex-import#example:9", "bibtex-import#example:10", "bibtex-import#example:11", "bibtex-import#example:12"]

[[obligation]]
id = "import.malformed-field-skip"
statement = "A field without a name or '=' is skipped to the next comma or the end of the entry, skipping its braced and quoted values whole; the fields after it are read."
status = "decided"
source = "replication"
reason = "Lost fields after a malformed one were a lightkone bug, fixed in kausalflow/lightkone#50."
checks = ["bibtex-import#example:18", "bibtex-import#example:29", "bibtex-import#example:30"]

[[obligation]]
id = "import.values"
statement = "Values are braced, quoted, numeric or macro parts joined by #; @string and month macros expand; later fields replace earlier ones; whitespace collapses."
status = "decided"
source = "extract"
checks = ["bibtex-import#test_string_macros_and_concatenation", "bibtex-import#test_month_macros", "bibtex-import#test_whitespace_in_values_collapses", "bibtex-import#test_later_fields_replace_earlier_ones", "bibtex-import#example:8", "bibtex-import#example:17", "bibtex-import#example:21", "bibtex-import#example:22"]

[[obligation]]
id = "import.non-ascii-whitespace"
statement = "Whitespace is JavaScript's \\s set (incl. no-break space, U+2028, U+3000, BOM), everywhere in import. Kept by kausalflow's decision (2026-10-24)."
status = "decided"
checks = ["bibtex-import#example:31", "bibtex-import#example:32", "bibtex-import#example:36"]
source = "replication"
assumes = ["K-bibtex-sources"]

[[obligation]]
id = "import.latex-to-plain"
statement = "Title, venue, abstract, names and tags go through plain(): LaTeX accents and specials become Unicode, formatting commands unwrap, braces go."
status = "decided"
source = "extract"
checks = ["bibtex-import#example:3", "bibtex-import#example:6", "bibtex-import#example:13", "bibtex-import#example:14"]

[[obligation]]
id = "import.authors"
statement = "Authors split on 'and'; First Last flips to Last, First; comma names, 'others' and {braced} names are kept; editor stands in only without an author field."
status = "decided"
source = "extract"
checks = ["bibtex-import#test_braced_names_and_others_are_kept", "bibtex-import#test_editors_stand_in_for_missing_authors", "bibtex-import#example:5", "bibtex-import#example:11", "bibtex-import#example:19", "bibtex-import#example:27"]

[[obligation]]
id = "import.identifiers"
statement = "doi loses its resolver prefix; arxiv ids come from arxivid, arXiv eprints, arxiv.org URLs or new-style bare eprints, without version."
status = "decided"
source = "extract"
checks = ["bibtex-import#test_doi_loses_its_resolver_prefix", "bibtex-import#test_arxiv_ids_are_found", "bibtex-import#test_other_eprints_stay_in_fields", "bibtex-import#example:16", "bibtex-import#example:28", "bibtex-import#example:33", "bibtex-import#example:34"]

[[obligation]]
id = "import.draft-fields"
statement = "year is the first four digits; venue is journal, else booktitle, else publisher; notes is annote, else note; empty abstract, doi and venue are absent."
status = "decided"
source = "extract"
checks = ["bibtex-import#example:4", "bibtex-import#example:20", "bibtex-import#example:23", "bibtex-import#example:35", "bibtex-import#example:37"]

[[obligation]]
id = "import.venue-empty-journal"
statement = "The venue is the first of journal, booktitle, publisher that is not empty, so an empty journal does not hide a booktitle. Fixed in lightkone#53; until then an empty journal left the paper without a venue."
status = "decided"
source = "replication"
checks = ["bibtex-import#example:38", "bibtex-import#example:39"]

[[obligation]]
id = "import.tags"
statement = "keywords split on ; or , into tags, dropping identifiers and URLs."
status = "decided"
source = "extract"
checks = ["bibtex-import#test_keywords_become_tags_without_identifiers", "bibtex-import#example:15"]

# ── bibtex-export ─────────────────────────────────────────────────────────

[[obligation]]
id = "export.byte-exact"
statement = "Export writes the exact entry lightkone writes: frame, aligned names, field order."
status = "decided"
kind = "constraint"
source = "extract"
reason = "library.bib is synced with Overleaf and git; any difference shows up as a spurious diff for every user."
checks = ["bibtex-export#test_entry_frame", "bibtex-export#test_names_are_aligned", "bibtex-export#test_fields_appear_in_order_when_present", "bibtex-export#example:1", "bibtex-export#example:11", "bibtex-export#example:13"]

[[obligation]]
id = "export.values"
statement = "Values are written as given, except that & % # are escaped once in title, venue and abstract."
status = "decided"
source = "extract"
checks = ["bibtex-export#test_values_are_written_as_given", "bibtex-export#test_title_venue_and_abstract_are_escaped", "bibtex-export#example:9", "bibtex-export#example:14", "bibtex-export#example:16", "bibtex-export#example:19"]

[[obligation]]
id = "export.venue"
statement = "The venue is written as journal, or booktitle for inproceedings and incollection, unless a non-empty journal field is already there."
status = "decided"
source = "extract"
checks = ["bibtex-export#example:2", "bibtex-export#example:3", "bibtex-export#example:4", "bibtex-export#example:5"]

[[obligation]]
id = "export.authors-and-keywords"
statement = "Authors join with ' and ', whole names braced; tags join with ';' as keywords."
status = "decided"
source = "extract"
checks = ["bibtex-export#test_authors_and_keywords", "bibtex-export#example:7", "bibtex-export#example:8", "bibtex-export#example:18"]

[[obligation]]
id = "export.empty-values"
statement = "Empty values are left out, except title and year 0; an empty type becomes misc."
status = "decided"
source = "extract"
checks = ["bibtex-export#example:6", "bibtex-export#example:12", "bibtex-export#example:15", "bibtex-export#example:17"]

[[obligation]]
id = "export.no-private-fields"
statement = "Fields whose names start with lightkone- are private and never written to BibTeX."
status = "decided"
kind = "security"
source = "extract"
checks = ["bibtex-export#example:10"]


# ── citation-key ──────────────────────────────────────────────────────

[[obligation]]
id = "keys.format"
statement = "A new key is surname (NFKD, ASCII letters, Anon if none) + year + '-' + first letters of the first two title words longer than 3 letters."
status = "decided"
source = "oracle"
checks = ["citation-key#test_a_key_is_surname_year_and_two_title_letters", "citation-key#example:1", "citation-key#example:2", "citation-key#example:3", "citation-key#example:10", "citation-key#example:11", "citation-key#example:12", "citation-key#example:13", "citation-key#example:14", "citation-key#example:15", "citation-key#example:16", "citation-key#example:17", "citation-key#example:18"]

[[obligation]]
id = "keys.unique"
statement = "Keys are unique in the library: a taken key counts up from 2, and keys given earlier in a batch are taken."
status = "decided"
source = "oracle"
checks = ["citation-key#test_keys_are_unique_and_never_taken", "citation-key#test_collisions_count_up_from_two", "citation-key#test_identical_drafts_in_one_batch_get_distinct_keys", "citation-key#example:4", "citation-key#example:5", "citation-key#example:6", "citation-key#example:19"]

[[obligation]]
id = "keys.stable"
statement = "A key a paper arrives with is kept when it is free, so keys from an imported .bib never change."
status = "decided"
source = "oracle"
checks = ["citation-key#test_an_arriving_key_is_kept_when_free", "citation-key#test_keys_look_like_keys", "citation-key#example:7", "citation-key#example:8", "citation-key#example:9"]

# ── pdf-filing ────────────────────────────────────────────────────────

[[obligation]]
id = "filing.paperpile-layout"
statement = "PDFs are filed as papers/All Papers/<SURNAME>/<Who Year - Title>.pdf, Paperpile's own layout, so a Paperpile folder can be copied in unchanged."
status = "decided"
source = "oracle"
checks = ["pdf-filing#test_pdf_is_the_file_under_papers", "pdf-filing#test_folder_is_the_first_surname_in_capitals", "pdf-filing#test_same_paper_same_place", "pdf-filing#example:1", "pdf-filing#example:2", "pdf-filing#example:3", "pdf-filing#example:7", "pdf-filing#example:8", "pdf-filing#example:9", "pdf-filing#example:10", "pdf-filing#example:16", "pdf-filing#example:17"]

[[obligation]]
id = "filing.clean-names"
statement = "File names hold no characters a file system or Drive rejects; they become ' - ', and -- / --- become dashes."
status = "decided"
source = "oracle"
checks = ["pdf-filing#test_names_hold_no_forbidden_characters", "pdf-filing#example:4", "pdf-filing#example:5", "pdf-filing#example:6", "pdf-filing#example:18", "pdf-filing#example:19"]

[[obligation]]
id = "filing.length"
statement = "Long author lists and names are shortened the way Paperpile shortens them."
status = "decided"
source = "oracle"
checks = ["pdf-filing#test_long_names_are_shortened_around_an_ellipsis", "pdf-filing#example:11", "pdf-filing#example:12"]

[[obligation]]
id = "filing.no-overwrite"
statement = "A new PDF never takes a name another paper uses; it gets (2), (3), ..."
status = "decided"
source = "oracle"
checks = ["pdf-filing#test_taken_names_count_up_and_own_pdf_is_ignored", "pdf-filing#example:13", "pdf-filing#example:14", "pdf-filing#example:15"]

# ── library-merge ─────────────────────────────────────────────────────

[[obligation]]
id = "merge.no-lost-edits"
statement = "A save never silently drops a change made elsewhere: one-sided changes are taken, different fields of one paper both survive."
status = "decided"
source = "oracle"
checks = ["library-merge#test_nothing_changed_merges_to_itself", "library-merge#test_changes_made_only_elsewhere_are_taken_whole", "library-merge#test_changes_made_only_here_are_kept", "library-merge#test_edits_to_different_fields_both_survive", "library-merge#example:1", "library-merge#example:2", "library-merge#example:3", "library-merge#example:4", "library-merge#example:9"]

[[obligation]]
id = "merge.conflict-ours"
statement = "When both sides change the same field differently, this device's edit wins."
status = "decided"
source = "oracle"
checks = ["library-merge#test_the_same_field_changed_both_ways_keeps_ours", "library-merge#example:5", "library-merge#example:20"]

[[obligation]]
id = "merge.sets"
statement = "tags and folders merge as sets: additions from either side are kept, removals from either side stick."
status = "decided"
source = "oracle"
checks = ["library-merge#test_tags_merge_as_sets", "library-merge#example:6", "library-merge#example:7", "library-merge#example:8", "library-merge#example:21"]

[[obligation]]
id = "merge.deletes"
statement = "A paper deleted on one side and unchanged on the other is gone; changed on the other, it survives."
status = "decided"
source = "oracle"
checks = ["library-merge#test_a_paper_deleted_here_but_changed_there_survives", "library-merge#example:10", "library-merge#example:11", "library-merge#example:12", "library-merge#example:13", "library-merge#example:14"]

[[obligation]]
id = "merge.order-and-count"
statement = "Their order first, then papers only here; fromThem counts papers that took a change made elsewhere."
status = "decided"
source = "oracle"
checks = ["library-merge#test_without_a_base_every_paper_is_kept_and_ours_wins", "library-merge#example:15", "library-merge#example:16", "library-merge#example:17"]

[[obligation]]
id = "merge.bibsync"
statement = "bibSync takes theirs unless changed here, and is written only when non-empty."
status = "decided"
source = "oracle"
checks = ["library-merge#example:18", "library-merge#example:19"]

# ── tidy ──────────────────────────────────────────────────────────────

[[obligation]]
id = "tidy.match"
statement = "Duplicates share a DOI, an arXiv id, a long title, or a short title and first author, after normalising; chains join."
status = "decided"
source = "oracle"
checks = ["tidy#test_groups_are_exactly_the_papers_that_share_a_key", "tidy#example:1", "tidy#example:2", "tidy#example:3", "tidy#example:4", "tidy#example:5", "tidy#example:6", "tidy#example:7", "tidy#example:8", "tidy#example:18", "tidy#example:19", "tidy#example:20", "tidy#example:21"]

[[obligation]]
id = "tidy.trash-ignored"
statement = "Papers in the trash are never grouped."
status = "decided"
source = "oracle"
checks = ["tidy#test_trash_is_never_grouped", "tidy#example:9"]

[[obligation]]
id = "tidy.keeper"
statement = "The kept paper is the one with a PDF, then notes, then the oldest."
status = "decided"
source = "oracle"
checks = ["tidy#test_the_keeper_has_a_pdf_then_notes_then_is_oldest", "tidy#example:11", "tidy#example:12", "tidy#example:13", "tidy#example:14"]

[[obligation]]
id = "tidy.nothing-lost"
statement = "Merging keeps every tag, folder, note and star, and fills the keeper's missing fields from the others."
status = "decided"
source = "oracle"
checks = ["tidy#test_the_keeper_gains_what_the_others_have", "tidy#test_fields_prefer_the_keeper_then_earlier_papers", "tidy#example:15", "tidy#example:16", "tidy#example:17"]

[[obligation]]
id = "tidy.blank-ids-ignored"
statement = "A DOI or arXiv id that is empty once trimmed and stripped of its prefix gives no match key, so blank ones never make papers duplicates. Fixed in lightkone#52; until then whitespace-only DOIs matched each other."
status = "decided"
source = "oracle"
checks = ["tidy#example:10", "tidy#example:22", "tidy#example:23", "tidy#test_groups_are_exactly_the_papers_that_share_a_key"]

[[obligation]]
id = "file.refuse-foreign"
statement = "A file that is not a lightkone library (not JSON, wrong format, no papers list, a paper that is not an object) is refused with an error and nothing is written."
status = "decided"
source = "oracle"
checks = ["library-file#test_anything_else_is_refused", "library-file#example:25", "library-file#example:26", "library-file#example:27", "library-file#example:28", "library-file#example:29", "library-file#example:30", "library-file#example:31", "library-file#example:32", "library-file#example:33", "library-file#example:34", "library-file#example:35", "library-file#example:36", "library-file#example:37", "library-file#example:38", "library-file#example:39"]

[[obligation]]
id = "file.keeps-papers"
statement = "Opening and saving keeps every paper and every key of every paper, in order, plus bibSync when it has entries."
status = "decided"
source = "oracle"
checks = ["library-file#test_saved_file_keeps_exactly_the_library", "library-file#example:1", "library-file#example:3", "library-file#example:7", "library-file#example:23"]

[[obligation]]
id = "file.keeps-unknown-keys"
statement = "Top-level keys other than format, version, papers and bibSync are kept on save, after lightkone's own, in the file's order, so another tool's data at the top level survives. Fixed in lightkone#51; until then they were dropped."
status = "decided"
source = "oracle"
checks = ["library-file#example:3", "library-file#example:40", "library-file#example:41", "library-file#example:42", "library-file#test_saved_file_keeps_exactly_the_library"]

[[obligation]]
id = "file.newer-version-refused"
statement = "A library.json whose version is a number above 1 was saved by a newer lightkone and is refused, writing nothing; any other version, or none, is read and saved as 1. Fixed in lightkone#53; until then a newer file was read as version 1 and could lose data on save."
status = "decided"
source = "oracle"
checks = ["library-file#example:8", "library-file#example:50", "library-file#example:51", "library-file#example:52", "library-file#example:53", "library-file#example:54", "library-file#test_anything_else_is_refused"]

[[obligation]]
id = "file.folders"
statement = "Papers without folders take them once from Paperpile's Drive paths, skipping All Papers, author folders and Other."
status = "decided"
source = "oracle"
checks = ["library-file#test_papers_gain_folders_from_paperpile_paths", "library-file#example:1", "library-file#example:10", "library-file#example:11", "library-file#example:13", "library-file#example:14", "library-file#example:15", "library-file#example:16", "library-file#example:17"]

[[obligation]]
id = "file.folders-author-only"
statement = "A single directory is skipped as an author folder only when it is Other or one of the paper's authors' surnames in capitals, so a user's own ML or 2019 folder is kept. With no authors to compare, a directory in capitals with a letter is still skipped. Fixed in lightkone#52; until then every single directory in capitals was skipped."
status = "decided"
source = "oracle"
checks = ["library-file#example:12", "library-file#example:46", "library-file#example:47", "library-file#example:48", "library-file#example:49", "library-file#test_papers_gain_folders_from_paperpile_paths"]

[[obligation]]
id = "file.exact-text"
statement = "library.json is written byte for byte as lightkone writes it: JSON with a one-space indent, JavaScript's key order, escaping and number printing."
status = "decided"
source = "oracle"
checks = ["library-file#test_layout_is_one_space_indented_json", "library-file#example:4", "library-file#example:9", "library-file#example:18", "library-file#example:19", "library-file#example:20", "library-file#example:24"]

[[obligation]]
id = "file.no-needless-write"
statement = "Nothing is written when the file would not change, so opening a library on several devices does not cause sync churn."
status = "decided"
source = "oracle"
checks = ["library-file#test_writes_only_when_the_text_changes", "library-file#test_saving_again_writes_nothing", "library-file#example:2", "library-file#example:5", "library-file#example:6"]

[[obligation]]
id = "file.bib-alongside"
statement = "library.bib is written with every save: the BibTeX entry of each paper not in the trash, in library order."
status = "decided"
source = "oracle"
checks = ["library-file#test_bib_has_one_entry_per_live_paper_in_order", "library-file#example:21"]

[[obligation]]
id = "file.bib-leaves-out-trash"
statement = "Papers in the trash are left out of library.bib, so Overleaf does not see deleted papers. A paper is in the trash when its trashed value is true in JavaScript. Fixed in lightkone#51; until then they were written."
status = "decided"
source = "oracle"
checks = ["library-file#example:22", "library-file#example:43", "library-file#example:44", "library-file#example:45", "library-file#test_bib_has_one_entry_per_live_paper_in_order"]
```

## symbolon-pack.toml

```toml
# Spec pack manifest. Pack tooling (symbolon pack validate/pull) comes later;
# for now this records which contract versions make up the pack.
[pack]
id = "kausalflow/lightkone"
version = 1
title = "Lightkone core: search, BibTeX, keys, filing, merge, tidy and the library file"
license = "Proprietary (kausalflow)"
authors = ["kausalflow"]

[components]
"lightkone/search-query@1" = "sha256:0af52a9bc30cb440bf1ec9924e6c00c5659ca0b05e478501080466699d0a49bc"
"lightkone/bibtex-import@1" = "sha256:549f518845ebd601650bf502cd18bb372368a3fea4e44510d2e67a53ba8ee88a"
"lightkone/bibtex-export@1" = "sha256:b2be7e43a14a1cdf9f5f65dcef181d159fe2afb95859dd1c6c836a6a89c3b97c"
"lightkone/citation-key@1" = "sha256:69041cb4a2e57a7ab161892db71ac21b103afb7e9187624207c66bbac1e5db94"
"lightkone/pdf-filing@1" = "sha256:583b0fa4549f4b8e1a6f6818a2d32d7f4062114e1cd74eba18c5f24786b5fff9"
"lightkone/library-merge@1" = "sha256:70141d55339b28b0dd81d1b37e1426f04e8d1de9d0380cb90766666b7a8ed89b"
"lightkone/tidy@1" = "sha256:b7513bd79d1c0b85eec6ff719f16f92dc9c4ec641b01fb6ab9a76fc7403f6e96"
"lightkone/library-file@1" = "sha256:c51dba7de999b5fbcaee57007e3b55aea18ea538bc28e898f0f92c12696b1b51"
```

## components/bibtex-export/versions/1/examples.jsonl

```json
{"input": {"paper": {"key": "Hinton2012-ab", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey E", "Srivastava, Nitish"], "tags": ["ml", "dropout"], "fields": {"month": "July"}, "year": 2012, "venue": "arXiv [cs.NE]", "arxiv": "1207.0580", "file": "All Papers/H/Hinton 2012.pdf"}}, "output": {"text": "@article{Hinton2012-ab,\n  title         = {{Improving neural networks by preventing co-adaptation}},\n  author        = {Hinton, Geoffrey E and Srivastava, Nitish},\n  year          = {2012},\n  journal       = {arXiv [cs.NE]},\n  eprint        = {1207.0580},\n  archiveprefix = {arXiv},\n  keywords      = {ml;dropout},\n  file          = {All Papers/H/Hinton 2012.pdf},\n  month         = {July}\n}\n"}, "note": "a typical article"}
{"input": {"paper": {"key": "vaswani2017", "type": "inproceedings", "title": "Attention is all you need", "authors": ["Vaswani, Ashish"], "tags": [], "fields": {"volume": "30"}, "year": 2017, "venue": "NeurIPS"}}, "output": {"text": "@inproceedings{vaswani2017,\n  title     = {{Attention is all you need}},\n  author    = {Vaswani, Ashish},\n  year      = {2017},\n  booktitle = {NeurIPS},\n  volume    = {30}\n}\n"}, "note": "inproceedings writes the venue as booktitle"}
{"input": {"paper": {"key": "Hinton2012-ab", "type": "incollection", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey E", "Srivastava, Nitish"], "tags": [], "fields": {}, "venue": "Collected Works"}}, "output": {"text": "@incollection{Hinton2012-ab,\n  title     = {{Improving neural networks by preventing co-adaptation}},\n  author    = {Hinton, Geoffrey E and Srivastava, Nitish},\n  booktitle = {Collected Works}\n}\n"}, "note": "incollection also uses booktitle"}
{"input": {"paper": {"key": "Hinton2012-ab", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey E", "Srivastava, Nitish"], "tags": [], "fields": {"journal": "J. Kept", "pages": "1--2"}, "venue": "Ignored"}}, "output": {"text": "@article{Hinton2012-ab,\n  title   = {{Improving neural networks by preventing co-adaptation}},\n  author  = {Hinton, Geoffrey E and Srivastava, Nitish},\n  journal = {J. Kept},\n  pages   = {1--2}\n}\n"}, "note": "an existing journal field wins over the venue"}
{"input": {"paper": {"key": "Hinton2012-ab", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey E", "Srivastava, Nitish"], "tags": [], "fields": {"journal": ""}, "venue": "Used"}}, "output": {"text": "@article{Hinton2012-ab,\n  title   = {{Improving neural networks by preventing co-adaptation}},\n  author  = {Hinton, Geoffrey E and Srivastava, Nitish},\n  journal = {Used}\n}\n"}, "note": "an empty journal field does not stop the venue"}
{"input": {"paper": {"key": "Hinton2012-ab", "type": "", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey E", "Srivastava, Nitish"], "tags": [""], "fields": {}, "venue": "", "doi": "", "url": "", "abstract": "", "file": ""}}, "output": {"text": "@misc{Hinton2012-ab,\n  title  = {{Improving neural networks by preventing co-adaptation}},\n  author = {Hinton, Geoffrey E and Srivastava, Nitish}\n}\n"}, "note": "empty type becomes misc; empty values are left out"}
{"input": {"paper": {"key": "Hinton2012-ab", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["LIGO Scientific Collaboration", "Abbott, B. P.", "others", "Others", "Plato"], "tags": [], "fields": {}}}, "output": {"text": "@article{Hinton2012-ab,\n  title  = {{Improving neural networks by preventing co-adaptation}},\n  author = {{LIGO Scientific Collaboration} and Abbott, B. P. and others and {Others} and {Plato}}\n}\n"}, "note": "whole names are braced; comma names and others are not"}
{"input": {"paper": {"key": "Hinton2012-ab", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "tags": [], "fields": {}}}, "output": {"text": "@article{Hinton2012-ab,\n  title = {{Improving neural networks by preventing co-adaptation}}\n}\n"}, "note": "no authors, no author line"}
{"input": {"paper": {"key": "Hinton2012-ab", "type": "article", "title": "R&D: 50% of #1 \\& more", "authors": ["Hinton, Geoffrey E", "Srivastava, Nitish"], "tags": [], "fields": {"note": "5% & #"}, "venue": "Science & Nature", "abstract": "100% sure #hash", "doi": "10.1/a&b", "url": "https://x.org/?a=1&b=2#frag"}}, "output": {"text": "@article{Hinton2012-ab,\n  title    = {{R\\&D: 50\\% of \\#1 \\& more}},\n  author   = {Hinton, Geoffrey E and Srivastava, Nitish},\n  journal  = {Science \\& Nature},\n  doi      = {10.1/a&b},\n  url      = {https://x.org/?a=1&b=2#frag},\n  abstract = {100\\% sure \\#hash},\n  note     = {5% & #}\n}\n"}, "note": "& % # are escaped in title, venue and abstract, but not twice"}
{"input": {"paper": {"key": "Hinton2012-ab", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey E", "Srivastava, Nitish"], "tags": [], "fields": {"lightkone-id": "abc", "pages": "3", "lightkone-color": "red"}}}, "output": {"text": "@article{Hinton2012-ab,\n  title  = {{Improving neural networks by preventing co-adaptation}},\n  author = {Hinton, Geoffrey E and Srivastava, Nitish},\n  pages  = {3}\n}\n"}, "note": "lightkone-private fields are not written"}
{"input": {"paper": {"key": "Hinton2012-ab", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey E", "Srivastava, Nitish"], "tags": [], "fields": {"archiveprefix_extra": "x"}}}, "output": {"text": "@article{Hinton2012-ab,\n  title               = {{Improving neural networks by preventing co-adaptation}},\n  author              = {Hinton, Geoffrey E and Srivastava, Nitish},\n  archiveprefix_extra = {x}\n}\n"}, "note": "the longest name sets the alignment"}
{"input": {"paper": {"key": "Hinton2012-ab", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey E", "Srivastava, Nitish"], "tags": [], "fields": {}, "year": 0}}, "output": {"text": "@article{Hinton2012-ab,\n  title  = {{Improving neural networks by preventing co-adaptation}},\n  author = {Hinton, Geoffrey E and Srivastava, Nitish},\n  year   = {0}\n}\n"}, "note": "year zero is still written"}
{"input": {"paper": {"key": "Hinton2012-ab", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey E", "Srivastava, Nitish"], "tags": [], "fields": {"zeta": "1", "alpha": "2", "title": "Dup title"}}}, "output": {"text": "@article{Hinton2012-ab,\n  title  = {{Improving neural networks by preventing co-adaptation}},\n  author = {Hinton, Geoffrey E and Srivastava, Nitish},\n  zeta   = {1},\n  alpha  = {2},\n  title  = {Dup title}\n}\n"}, "note": "fields keep their given order and are not deduplicated"}
{"input": {"paper": {"key": "Hinton2012-ab", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "tags": [], "fields": {}, "venue": "Monatshefte für Mathematik"}}, "output": {"text": "@article{Hinton2012-ab,\n  title   = {{Über formal unentscheidbare Sätze}},\n  author  = {Gödel, Kurt},\n  journal = {Monatshefte für Mathematik}\n}\n"}, "note": "unicode passes through"}
{"input": {"paper": {"key": "Hinton2012-ab", "type": "article", "title": "", "authors": ["Hinton, Geoffrey E", "Srivastava, Nitish"], "tags": [], "fields": {}}}, "output": {"text": "@article{Hinton2012-ab,\n  title  = {{}},\n  author = {Hinton, Geoffrey E and Srivastava, Nitish}\n}\n"}, "note": "an empty title is still written"}
{"input": {"paper": {"key": "Hinton2012-ab", "type": "article", "title": "The {\\TeX}book", "authors": ["Hinton, Geoffrey E", "Srivastava, Nitish"], "tags": [], "fields": {}, "abstract": "See $x^2$"}}, "output": {"text": "@article{Hinton2012-ab,\n  title    = {{The {\\TeX}book}},\n  author   = {Hinton, Geoffrey E and Srivastava, Nitish},\n  abstract = {See $x^2$}\n}\n"}, "note": "braces and LaTeX in values are written as they are"}
{"input": {"paper": {"key": "", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey E", "Srivastava, Nitish"], "tags": [], "fields": {}}}, "output": {"text": "@article{,\n  title  = {{Improving neural networks by preventing co-adaptation}},\n  author = {Hinton, Geoffrey E and Srivastava, Nitish}\n}\n"}, "note": "an empty key"}
{"input": {"paper": {"key": "Hinton2012-ab", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey E", "Srivastava, Nitish"], "tags": ["machine learning", "to read", "physics"], "fields": {}}}, "output": {"text": "@article{Hinton2012-ab,\n  title    = {{Improving neural networks by preventing co-adaptation}},\n  author   = {Hinton, Geoffrey E and Srivastava, Nitish},\n  keywords = {machine learning;to read;physics}\n}\n"}, "note": "tags are joined with ;"}
{"input": {"paper": {"key": "Hinton2012-ab", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey E", "Srivastava, Nitish"], "tags": [], "fields": {}, "abstract": "First line.\nSecond line."}}, "output": {"text": "@article{Hinton2012-ab,\n  title    = {{Improving neural networks by preventing co-adaptation}},\n  author   = {Hinton, Geoffrey E and Srivastava, Nitish},\n  abstract = {First line.\nSecond line.}\n}\n"}, "note": "multi-line abstract is written as it is"}
```

## components/bibtex-export/versions/1/properties.py

```python
"""Behavioral properties for lightkone/bibtex-export.

Each property checks one rule of the description on generated papers whose
values have no newlines, so an entry can be read back line by line.
"""

import re

from hypothesis import given, strategies as st

from schema import Input, Paper

SAFE = st.text(st.characters(codec="utf-8", exclude_characters="\n\r{}\\", exclude_categories=["Cs", "Cc"]), max_size=20)
SPECIAL = st.lists(st.sampled_from(["a", "b c", "&", "%", "#", "\\&", "\\%", "\\#", "50", " "]), max_size=6).map("".join)
WORDS = st.text("abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=15)
NAMES = st.sampled_from(["pages", "volume", "publisher", "month", "journal", "booktitle", "lightkone-id", "lightkone-x", "note", "isbn"])
LINE = re.compile(r"^  (\S+)( *) = \{(.*)\}(,?)$")


@st.composite
def papers(draw, text=SAFE):
    return Paper(
        key=draw(st.text("abcdefghijklmnopqrstuvwxyzABC0123456789:-_", max_size=12)),
        type=draw(st.sampled_from(["article", "inproceedings", "incollection", "book", "misc", ""])),
        title=draw(text),
        authors=draw(st.lists(st.sampled_from(["Hinton, Geoffrey", "others", "LIGO Collaboration", "Plato", "Others", ""]), max_size=4)),
        year=draw(st.none() | st.integers(0, 3000)),
        venue=draw(st.none() | text),
        doi=draw(st.none() | SAFE),
        arxiv=draw(st.none() | st.sampled_from(["", "2101.00001", "hep-th/9711200"])),
        url=draw(st.none() | SAFE),
        abstract=draw(st.none() | text),
        tags=draw(st.lists(st.sampled_from(["ml", "to read", "", "a;b"]), max_size=3)),
        file=draw(st.none() | SAFE),
        fields=draw(st.dictionaries(NAMES, SAFE, max_size=4)),
    )


def write(impl, p: Paper) -> str:
    return impl(Input(paper=p)).text


def lines(text: str) -> list[tuple[str, str]]:
    """The (name, value) pairs of an entry written as the description says."""
    body = text.split("\n")[1:-2]
    out = []
    for i, line in enumerate(body):
        m = LINE.match(line)
        assert m, f"not a field line: {line!r}"
        assert (m.group(4) == ",") == (i < len(body) - 1), "lines are joined by ',\\n'"
        out.append((m.group(1), m.group(3)))
    return out


def escaped(s: str) -> str:
    return re.sub(r"\\?([&%#])", r"\\\1", s)


def present(v) -> bool:
    return v is not None and v != ""


@given(p=papers())
def test_entry_frame(impl, p):
    text = write(impl, p)
    assert text.startswith(f"@{p.type or 'misc'}{{{p.key},\n")
    assert text.endswith("\n}\n")


@given(p=papers())
def test_names_are_aligned(impl, p):
    text = write(impl, p)
    body = text.split("\n")[1:-2]
    width = max(len(n) for n, _ in lines(text))
    assert all(line.index(" = {") == 2 + width for line in body)


@given(p=papers())
def test_fields_appear_in_order_when_present(impl, p):
    venue_field = "booktitle" if p.type in ("inproceedings", "incollection") else "journal"
    expected = ["title"]
    expected += ["author"] if p.authors else []
    expected += ["year"] if p.year is not None else []
    expected += [venue_field] if present(p.venue) and not p.fields.get(venue_field) else []
    expected += ["doi"] if present(p.doi) else []
    expected += ["eprint", "archiveprefix"] if present(p.arxiv) else []
    expected += ["url"] if present(p.url) else []
    expected += ["abstract"] if present(p.abstract) else []
    expected += ["keywords"] if ";".join(p.tags) else []
    expected += ["file"] if present(p.file) else []
    expected += [k for k, _ in kept_fields(p)]
    assert [n for n, _ in lines(write(impl, p))] == expected


def kept_fields(p: Paper) -> list[tuple[str, str]]:
    return [(k, v) for k, v in p.fields.items() if v and not k.startswith("lightkone-")]


@given(p=papers())
def test_values_are_written_as_given(impl, p):
    got = lines(write(impl, p))
    named = dict(got)
    if p.year is not None:
        assert named["year"] == str(p.year)
    for name in ("doi", "url", "file"):
        if present(getattr(p, name)):
            assert named[name] == getattr(p, name)
    if present(p.arxiv):
        assert named["eprint"] == p.arxiv and named["archiveprefix"] == "arXiv"
    kept = kept_fields(p)
    assert got[len(got) - len(kept):] == kept


@given(p=papers(text=SPECIAL))
def test_title_venue_and_abstract_are_escaped(impl, p):
    got = dict(lines(write(impl, p)))
    assert got["title"] == "{" + escaped(p.title) + "}"
    venue_field = "booktitle" if p.type in ("inproceedings", "incollection") else "journal"
    if present(p.venue) and not p.fields.get(venue_field):
        assert got[venue_field] == escaped(p.venue)
    if present(p.abstract):
        assert got["abstract"] == escaped(p.abstract)


@given(p=papers())
def test_authors_and_keywords(impl, p):
    got = dict(lines(write(impl, p)))
    joined = " and ".join(a if "," in a or a == "others" else "{" + a + "}" for a in p.authors)
    assert got.get("author", "") == joined
    assert got.get("keywords", "") == ";".join(p.tags)
```

## components/bibtex-export/versions/1/schema.py

```python
"""Interface for lightkone/bibtex-export."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

FieldName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_.:+-]*$")]


class Paper(BaseModel):
    """The fields of a lightkone paper that the BibTeX writer reads."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(description="Citation key.")
    type: str = Field(description="Entry type in lower case; empty means misc.")
    title: str
    authors: list[str] = Field(description="'Last, First' strings or whole names, in order.")
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv: str | None = None
    url: str | None = None
    abstract: str | None = None
    tags: list[str] = Field(default_factory=list)
    file: str | None = None
    fields: dict[FieldName, str] = Field(default_factory=dict, description="Other BibTeX fields, in order.")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper: Paper


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(description="The BibTeX entry, ending with a newline.")
```

## components/bibtex-export/versions/1/schema/input.json

```json
{
  "$defs": {
    "Paper": {
      "additionalProperties": false,
      "description": "The fields of a lightkone paper that the BibTeX writer reads.",
      "properties": {
        "abstract": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Abstract"
        },
        "arxiv": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Arxiv"
        },
        "authors": {
          "description": "'Last, First' strings or whole names, in order.",
          "items": {
            "type": "string"
          },
          "title": "Authors",
          "type": "array"
        },
        "doi": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Doi"
        },
        "fields": {
          "description": "Other BibTeX fields, in order.",
          "patternProperties": {
            "^[a-z][a-z0-9_.:+-]*$": {
              "type": "string"
            }
          },
          "title": "Fields",
          "type": "object"
        },
        "file": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "File"
        },
        "key": {
          "description": "Citation key.",
          "title": "Key",
          "type": "string"
        },
        "tags": {
          "items": {
            "type": "string"
          },
          "title": "Tags",
          "type": "array"
        },
        "title": {
          "title": "Title",
          "type": "string"
        },
        "type": {
          "description": "Entry type in lower case; empty means misc.",
          "title": "Type",
          "type": "string"
        },
        "url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Url"
        },
        "venue": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Venue"
        },
        "year": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Year"
        }
      },
      "required": [
        "key",
        "type",
        "title",
        "authors"
      ],
      "title": "Paper",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "paper": {
      "$ref": "#/$defs/Paper"
    }
  },
  "required": [
    "paper"
  ],
  "title": "Input",
  "type": "object"
}
```

## components/bibtex-export/versions/1/schema/output.json

```json
{
  "additionalProperties": false,
  "properties": {
    "text": {
      "description": "The BibTeX entry, ending with a newline.",
      "title": "Text",
      "type": "string"
    }
  },
  "required": [
    "text"
  ],
  "title": "Output",
  "type": "object"
}
```

## components/bibtex-export/versions/1/symbolon.toml

```toml
[contract]
id = "lightkone/bibtex-export"
version = 1
title = "Write a lightkone paper as a BibTeX entry"
description = """
Writes one paper as the BibTeX entry lightkone puts in library.bib and in
the .bib files it syncs for Overleaf. The output must match byte for byte,
because those files are diffed and committed.

Shape:
  @<type>{<key>,
    <name> = {<value>},
    ...
    <name> = {<value>}
  }
followed by a newline. Each field line is two spaces, the field name padded
with spaces to the length of the longest name in the entry, " = {", the
value, and "}"; lines are joined by ",\\n". type is "misc" when empty.

Fields, in this order, each written only when its value is present and not
empty:
  title     always written, wrapped in an extra pair of braces: {{Title}}
  author    authors joined by " and "; an author containing a comma, or
            exactly "others", is written as is, any other is wrapped in
            braces so BibTeX keeps it whole: {LIGO Collaboration}
  year      the number
  journal   the venue, or booktitle instead when type is "inproceedings" or
            "incollection"; left out when fields already has a non-empty
            value under that name
  doi
  eprint, archiveprefix   the arxiv id and "arXiv", when arxiv is present
  url
  abstract
  keywords  tags joined by ";"
  file
  then every entry of fields in its given order, except names that start
  with "lightkone-" (private to lightkone). Names are not deduplicated.

Escaping: in title, venue and abstract, every & % or # not already preceded
by a backslash gets one. Nothing else is escaped or changed.
"""
regenerability = "disposable"
license = "Proprietary (kausalflow)"
authors = ["kausalflow/lightkone"]

[entrypoint]
function = "run"

[requires]
network = []
credentials = []
state = []
permissions = []

[spec]
seed = 0
max_examples = 200
timeout_seconds = 300
```

## components/bibtex-import/versions/1/examples.jsonl

```json
{"input": {"text": "@article{Hinton2012-ab,\n  title         = \"{Improving neural networks by preventing co-adaptation of feature detectors}\",\n  author        = \"Hinton, Geoffrey E and Srivastava, Nitish and Krizhevsky, Alex\",\n  journal       = \"arXiv [cs.NE]\",\n  year          =  2012,\n  month         =  jul,\n  eprint        = \"1207.0580\",\n  archivePrefix = \"arXiv\",\n  primaryClass  = \"cs.NE\",\n  keywords      = \"ml;dropout\",\n  file          = \"All Papers/H/Hinton et al. 2012 - Improving neural networks.pdf\"\n}"}, "output": {"papers": [{"key": "Hinton2012-ab", "type": "article", "title": "Improving neural networks by preventing co-adaptation of feature detectors", "authors": ["Hinton, Geoffrey E", "Srivastava, Nitish", "Krizhevsky, Alex"], "year": 2012, "venue": "arXiv [cs.NE]", "arxiv": "1207.0580", "tags": ["ml", "dropout"], "file": "All Papers/H/Hinton et al. 2012 - Improving neural networks.pdf", "fields": {"month": "July"}}]}, "note": "Paperpile export with arXiv eprint, month macro and file path"}
{"input": {"text": "@inproceedings{vaswani2017attention,\n  title={Attention is all you need},\n  author={Vaswani, Ashish and Shazeer, Noam and Parmar, Niki and Uszkoreit, Jakob},\n  booktitle={Advances in neural information processing systems},\n  volume={30},\n  year={2017}\n}"}, "output": {"papers": [{"key": "vaswani2017attention", "type": "inproceedings", "title": "Attention is all you need", "authors": ["Vaswani, Ashish", "Shazeer, Noam", "Parmar, Niki", "Uszkoreit, Jakob"], "year": 2017, "venue": "Advances in neural information processing systems", "tags": [], "fields": {"volume": "30"}}]}, "note": "Google Scholar export: booktitle becomes the venue"}
{"input": {"text": "@article{godel1931,\n\tauthor = {G{\\\"o}del, Kurt},\n\ttitle = {{\\\"U}ber formal unentscheidbare S{\\\"a}tze der {P}rincipia {M}athematica und verwandter {S}ysteme {I}},\n\tjournal = {Monatshefte f{\\\"u}r Mathematik und Physik},\n\tyear = {1931},\n\tvolume = {38},\n\tpages = {173--198},\n\tdoi = {10.1007/BF01700692},\n\turl = {https://doi.org/10.1007/BF01700692}\n}"}, "output": {"papers": [{"key": "godel1931", "type": "article", "title": "Über formal unentscheidbare Sätze der Principia Mathematica und verwandter Systeme I", "authors": ["Gödel, Kurt"], "year": 1931, "venue": "Monatshefte für Mathematik und Physik", "doi": "10.1007/BF01700692", "url": "https://doi.org/10.1007/BF01700692", "tags": [], "fields": {"volume": "38", "pages": "173--198"}}]}, "note": "LaTeX accents in braces become Unicode; protective braces go"}
{"input": {"text": "@book{Knuth1984,\n  author    = {Donald E. Knuth},\n  title     = {The \\TeX book},\n  publisher = {Addison-Wesley},\n  year      = {1984},\n  isbn      = {0-201-13447-0}\n}"}, "output": {"papers": [{"key": "Knuth1984", "type": "book", "title": "The \\TeX book", "authors": ["Knuth, Donald E."], "year": 1984, "venue": "Addison-Wesley", "tags": [], "fields": {"publisher": "Addison-Wesley", "isbn": "0-201-13447-0"}}]}, "note": "publisher stands in as venue and stays in fields; unknown macros keep their letters"}
{"input": {"text": "@misc{ligo2016,\n  author = {{LIGO Scientific Collaboration} and {Virgo Collaboration} and Abbott, B. P. and others},\n  title = {Observation of Gravitational Waves from a Binary Black Hole Merger},\n  year = {2016},\n  eprint = {arXiv:1602.03837v2},\n  eprinttype = {arxiv},\n  doi = {https://doi.org/10.1103/PhysRevLett.116.061102}\n}"}, "output": {"papers": [{"key": "ligo2016", "type": "misc", "title": "Observation of Gravitational Waves from a Binary Black Hole Merger", "authors": ["LIGO Scientific Collaboration", "Virgo Collaboration", "Abbott, B. P.", "others"], "year": 2016, "doi": "10.1103/PhysRevLett.116.061102", "arxiv": "1602.03837", "tags": [], "fields": {}}]}, "note": "corporate authors in braces are kept; others; eprinttype; doi URL prefix removed"}
{"input": {"text": "@ARTICLE{Erdos1959,\n  AUTHOR = {Erd\\H{o}s, Paul and R\\'{e}nyi, Alfr\\'ed},\n  TITLE = {On random graphs {I}},\n  JOURNAL = {Publicationes Mathematicae},\n  YEAR = {1959},\n  NOTE = {Reprinted 1976}\n}"}, "output": {"papers": [{"key": "Erdos1959", "type": "article", "title": "On random graphs I", "authors": ["Erdős, Paul", "Rényi, Alfréd"], "year": 1959, "venue": "Publicationes Mathematicae", "tags": [], "notes": "Reprinted 1976", "fields": {}}]}, "note": "upper-case names; \\H and \\' accents; note becomes notes"}
{"input": {"text": "@ARTICLE{Erd\\H{o}s1959,\n  AUTHOR = {Erd\\H{o}s, Paul and R\\'{e}nyi, Alfr\\'ed},\n  TITLE = {On random graphs {I}},\n  JOURNAL = {Publicationes Mathematicae},\n  YEAR = {1959},\n  NOTE = {Reprinted 1976}\n}"}, "output": {"papers": [{"key": "Erd\\H{o}s1959", "type": "article", "title": "On random graphs I", "authors": ["Erdős, Paul", "Rényi, Alfréd"], "year": 1959, "venue": "Publicationes Mathematicae", "tags": [], "notes": "Reprinted 1976", "fields": {}}]}, "note": "braces in a key are part of the key"}
{"input": {"text": "@string{prl = \"Physical Review Letters\"}\n@string{ PRD = {Physical Review D} }\n@article{a, title = {One}, journal = prl, year = 2001}\n@article{b, title = {Two}, journal = PRD # \", Part \" # {2}, year = \"circa 1999\"}"}, "output": {"papers": [{"key": "a", "type": "article", "title": "One", "authors": [], "year": 2001, "venue": "Physical Review Letters", "tags": [], "fields": {}}, {"key": "b", "type": "article", "title": "Two", "authors": [], "year": 1999, "venue": "Physical Review D, Part 2", "tags": [], "fields": {}}]}, "note": "@string macros, case-insensitive, with # concatenation; year from the first four digits"}
{"input": {"text": "@comment{jabref-meta: databaseType:bibtex;}\n@preamble{ \"\\newcommand{\\noopsort}[1]{}\" }\n% a line comment\n@misc{x1, title = {Kept}}"}, "output": {"papers": [{"key": "x1", "type": "misc", "title": "Kept", "authors": [], "tags": [], "fields": {}}]}, "note": "@comment and @preamble are not entries"}
{"input": {"text": "@comment{@article{inside, title = {Found inside a comment}}}\n@misc{after, title = {After}}"}, "output": {"papers": [{"key": "inside", "type": "article", "title": "Found inside a comment", "authors": [], "tags": [], "fields": {}}, {"key": "after", "type": "misc", "title": "After", "authors": [], "tags": [], "fields": {}}]}, "note": "scanning continues inside @comment, so an entry there is read"}
{"input": {"text": "@article(paren2020,\n  title = \"Entries may use parentheses\",\n  author = \"Jane Doe and John Q. Public\"\n)"}, "output": {"papers": [{"key": "paren2020", "type": "article", "title": "Entries may use parentheses", "authors": ["Doe, Jane", "Public, John Q."], "tags": [], "fields": {}}]}, "note": "parenthesised entry; First Last names flip"}
{"input": {"text": "@misc{notitle, author = {Nobody}}\n@misc{emptytitle, title = {}}\n@misc{spaces, title = {   }}\n@misc{, title = {No key}}"}, "output": {"papers": [{"key": "", "type": "misc", "title": "No key", "authors": [], "tags": [], "fields": {}}]}, "note": "entries without a title are dropped, even with an empty one; a missing key is kept as empty"}
{"input": {"text": "@article{ws,\n  title = {A title\n     broken   over\n  lines},\n  abstract = {First line.\n  Second line with {\\em emphasis} and \\emph{more} and 50\\% off \\& \\$5.}\n}"}, "output": {"papers": [{"key": "ws", "type": "article", "title": "A title broken over lines", "authors": [], "abstract": "First line. Second line with \\em emphasis and more and 50% off & $5.", "tags": [], "fields": {}}]}, "note": "whitespace collapses; \\emph unwraps; escaped specials"}
{"input": {"text": "@article{latex,\n  title = {Na\\\"{\\i}ve {\\ss}tra{\\ss}e, \\o{}resund, {\\AE}sir, \\l{}\\'od\\'z and \\c{c}a va},\n  author = {M\\\"uller, J\\\"org and Nu\\~{n}ez, Pe\\~na},\n  journal = {Caf\\'e \\& Croissant}\n}"}, "output": {"papers": [{"key": "latex", "type": "article", "title": "Naïve ßtraße, øresund, Æsir, łódź and ça va", "authors": ["Müller, Jörg", "Nuñez, Peña"], "venue": "Café & Croissant", "tags": [], "fields": {}}]}, "note": "accents without braces, on \\i, \\ss, \\o, \\AE, \\l, cedilla"}
{"input": {"text": "@article{kw,\n  title = {Keywords},\n  keywords = {Machine Learning, physics; doi:10.1/abc; URL: http://x.org; arXiv:2101.00001; ISBN:123; https://example.org; {Quantum} Fields}\n}"}, "output": {"papers": [{"key": "kw", "type": "article", "title": "Keywords", "authors": [], "tags": ["Machine Learning", "physics", "Quantum Fields"], "fields": {}}]}, "note": "keywords split on , and ; with identifiers dropped"}
{"input": {"text": "@article{arxurl,\n  title = {From a URL},\n  url = {https://arxiv.org/abs/2106.09685v3?context=cs}\n}\n@article{arxpdf,\n  title = {From a PDF URL},\n  url = {http://arXiv.org/pdf/hep-th/9711200v1.pdf}\n}\n@article{arxid, title = {arxivid field}, arxivid = {1312.6114}}\n@article{bare, title = {Bare new-style eprint}, eprint = {2203.02155}}\n@article{other, title = {Other eprint}, eprint = {hep-th/9711200}}"}, "output": {"papers": [{"key": "arxurl", "type": "article", "title": "From a URL", "authors": [], "arxiv": "2106.09685", "url": "https://arxiv.org/abs/2106.09685v3?context=cs", "tags": [], "fields": {}}, {"key": "arxpdf", "type": "article", "title": "From a PDF URL", "authors": [], "arxiv": "hep-th/9711200", "url": "http://arXiv.org/pdf/hep-th/9711200v1.pdf", "tags": [], "fields": {}}, {"key": "arxid", "type": "article", "title": "arxivid field", "authors": [], "arxiv": "1312.6114", "tags": [], "fields": {}}, {"key": "bare", "type": "article", "title": "Bare new-style eprint", "authors": [], "arxiv": "2203.02155", "tags": [], "fields": {}}, {"key": "other", "type": "article", "title": "Other eprint", "authors": [], "tags": [], "fields": {"eprint": "hep-th/9711200"}}]}, "note": "arXiv ids from url, arxivid and bare eprints; old-style eprint without prefix stays in fields"}
{"input": {"text": "@article{dup,\n  title = {First},\n  title = {Second},\n  Pages = {1-2},\n  pages = {3-4}\n}"}, "output": {"papers": [{"key": "dup", "type": "article", "title": "Second", "authors": [], "tags": [], "fields": {"pages": "3-4"}}]}, "note": "a later field replaces an earlier one"}
{"input": {"text": "@article{malformed,\n  title = {Survives},\n  this is not a field,\n  = {no name},\n  volume = 7,\n  note\n}"}, "output": {"papers": [{"key": "malformed", "type": "article", "title": "Survives", "authors": [], "tags": [], "fields": {"volume": "7"}}]}, "note": "malformed fields are skipped, and the fields after them are read"}
{"input": {"text": "@article{editor, title = {Edited}, editor = {Ada Lovelace and Charles Babbage}}\n@book{both, title = {Both}, author = {Real Author}, editor = {An Editor}}\n@book{emptyauthor, title = {Empty author}, author = {}, editor = {Not Used}}"}, "output": {"papers": [{"key": "editor", "type": "article", "title": "Edited", "authors": ["Lovelace, Ada", "Babbage, Charles"], "tags": [], "fields": {}}, {"key": "both", "type": "book", "title": "Both", "authors": ["Author, Real"], "tags": [], "fields": {"editor": "An Editor"}}, {"key": "emptyauthor", "type": "book", "title": "Empty author", "authors": [], "tags": [], "fields": {"editor": "Not Used"}}]}, "note": "editor stands in only when there is no author field"}
{"input": {"text": "@article{annote, title = {Annote}, annote = {my notes}, note = {publisher note}}\n@article{emptyfields, title = {Empty}, abstract = {}, doi = {}, url = {}, file = {}, journal = {}}"}, "output": {"papers": [{"key": "annote", "type": "article", "title": "Annote", "authors": [], "tags": [], "notes": "my notes", "fields": {"note": "publisher note"}}, {"key": "emptyfields", "type": "article", "title": "Empty", "authors": [], "url": "", "tags": [], "file": "", "fields": {}}]}, "note": "annote wins over note; empty abstract, doi and venue are absent but empty url and file are kept"}
{"input": {"text": "@article{quoted, title = \"A {\"}quoted{\"} word and {braced \"quote\"}\", author = \"O'Neil, Cathy\"}"}, "output": {"papers": [{"key": "quoted", "type": "article", "title": "A \"quoted\" word and braced \"quote\"", "authors": ["O'Neil, Cathy"], "tags": [], "fields": {}}]}, "note": "quotes inside braces do not end a quoted value"}
{"input": {"text": "@article{nested, title = {Outer {Inner {Deepest}} back}, journal = {J. {\\\"O}sterr.}}"}, "output": {"papers": [{"key": "nested", "type": "article", "title": "Outer Inner Deepest back", "authors": [], "venue": "J. Österr.", "tags": [], "fields": {}}]}, "note": "nested braces"}
{"input": {"text": "@article{year0, title = {Year}, year = {0000}}\n@article{year5, title = {Year}, year = {19999}}\n@article{yearword, title = {Year}, year = {forthcoming}}"}, "output": {"papers": [{"key": "year0", "type": "article", "title": "Year", "authors": [], "year": 0, "tags": [], "fields": {}}, {"key": "year5", "type": "article", "title": "Year", "authors": [], "year": 1999, "tags": [], "fields": {}}, {"key": "yearword", "type": "article", "title": "Year", "authors": [], "tags": [], "fields": {}}]}, "note": "year: first four digits as a number, even 0; no digits means absent"}
{"input": {"text": "@article{unterminated, title = {This value never ends"}, "output": {"papers": [{"key": "unterminated", "type": "article", "title": "This value never ends", "authors": [], "tags": [], "fields": {}}]}, "note": "an unterminated value runs to the end"}
{"input": {"text": ""}, "output": {"papers": []}, "note": "empty text"}
{"input": {"text": "no entries at all, just @ signs @ here"}, "output": {"papers": []}, "note": "an @ not followed by a type and brace is skipped"}
{"input": {"text": "@article{mixedcase, Title = {Mixed}, AUTHOR = {de la Fontaine, Jean and Ludwig van Beethoven}, Journal = {X}, MONTH = dec}"}, "output": {"papers": [{"key": "mixedcase", "type": "article", "title": "Mixed", "authors": ["de la Fontaine, Jean", "Beethoven, Ludwig van"], "venue": "X", "tags": [], "fields": {"month": "December"}}]}, "note": "particles: First Last flips only the last word"}
{"input": {"text": "@article{ids, title = {T}, doi = {HTTP://DX.DOI.ORG/10.5555/abc}, eprint = {ARXIV:2101.00001V2}, archiveprefix = {ArXiv}}"}, "output": {"papers": [{"key": "ids", "type": "article", "title": "T", "authors": [], "doi": "10.5555/abc", "arxiv": "2101.00001V2", "tags": [], "fields": {}}]}, "note": "case-insensitive prefixes; an upper-case version suffix stays"}
{"input": {"text": "@article{k, title={Kept}, junk here, year = 1999, note={also kept}}"}, "output": {"papers": [{"key": "k", "type": "article", "title": "Kept", "authors": [], "year": 1999, "tags": [], "notes": "also kept", "fields": {}}]}, "note": "a malformed field ending at a comma: later fields survive"}
{"input": {"text": "@article{k, title={Kept}, = {x}, year = 1999}\n@book{b, title={Next entry}}"}, "output": {"papers": [{"key": "k", "type": "article", "title": "Kept", "authors": [], "year": 1999, "tags": [], "fields": {}}, {"key": "b", "type": "book", "title": "Next entry", "authors": [], "tags": [], "fields": {}}]}, "note": "a malformed field's braced value is skipped whole, so later fields survive"}
{"input": {"text": "@article{k, title = {A B　C﻿}, author = {Doe, Jane and Roe, R.}}"}, "output": {"papers": [{"key": "k", "type": "article", "title": "A B C", "authors": ["Doe, Jane", "Roe, R."], "tags": [], "fields": {}}]}, "note": "Unicode whitespace (no-break space, line separator, ideographic space, BOM) counts as whitespace"}
{"input": {"text": "@article{k, title={AB\u001fC}}"}, "output": {"papers": [{"key": "k", "type": "article", "title": "AB\u001fC", "authors": [], "tags": [], "fields": {}}]}, "note": "U+0085 and U+001F are not whitespace"}
{"input": {"text": "@article{k, title={From a URL}, url={HTTPS://ARXIV.ORG/ABS/2106.09685V3}}"}, "output": {"papers": [{"key": "k", "type": "article", "title": "From a URL", "authors": [], "arxiv": "2106.09685", "url": "HTTPS://ARXIV.ORG/ABS/2106.09685V3", "tags": [], "fields": {}}]}, "note": "the arXiv URL match ignores case, version suffix included"}
{"input": {"text": "@article{k, title={From a PDF URL}, url={https://arxiv.org/pdf/2106.09685v2.PDF}}"}, "output": {"papers": [{"key": "k", "type": "article", "title": "From a PDF URL", "authors": [], "arxiv": "2106.09685", "url": "https://arxiv.org/pdf/2106.09685v2.PDF", "tags": [], "fields": {}}]}, "note": "an upper-case .PDF suffix is removed too"}
{"input": {"text": "@article{k, title={Empty values}, file = {}, url = \"\"}"}, "output": {"papers": [{"key": "k", "type": "article", "title": "Empty values", "authors": [], "url": "", "tags": [], "file": "", "fields": {}}]}, "note": "empty url and file stay as empty strings"}
{"input": {"text": "@art icle{k, title={Lost}}\n@misc{m, title={Found}}"}, "output": {"papers": [{"key": "m", "type": "misc", "title": "Found", "authors": [], "tags": [], "fields": {}}]}, "note": "a no-break space ends the entry type, so the first entry is skipped"}
{"input": {"text": "@article{y, title = {Two-digit year}, year = {99}}\n@article{z, title = {Year in words}, year = {circa 1999}}"}, "output": {"papers": [{"key": "y", "type": "article", "title": "Two-digit year", "authors": [], "tags": [], "fields": {}}, {"key": "z", "type": "article", "title": "Year in words", "authors": [], "year": 1999, "tags": [], "fields": {}}]}, "note": "year needs four digits in a row: 99 gives no year; circa 1999 gives 1999"}
{"input": {"text": "@inproceedings{a, title={A}, journal={}, booktitle={NeurIPS}}\n@inproceedings{b, title={B}, journal={ {} }, booktitle={ICML}, publisher={PMLR}}"}, "output": {"papers": [{"key": "a", "type": "inproceedings", "title": "A", "authors": [], "venue": "NeurIPS", "tags": [], "fields": {}}, {"key": "b", "type": "inproceedings", "title": "B", "authors": [], "venue": "ICML", "tags": [], "fields": {"publisher": "PMLR"}}]}, "note": "an empty journal does not hide the booktitle; the booktitle becomes the venue and leaves the fields"}
{"input": {"text": "@book{c, title={C}, journal={}, booktitle={  }, publisher={MIT Press}}\n@article{d, title={D}, journal={JMLR}, booktitle={NeurIPS}}\n@misc{e, title={E}, journal={}, booktitle={}}"}, "output": {"papers": [{"key": "c", "type": "book", "title": "C", "authors": [], "venue": "MIT Press", "tags": [], "fields": {"publisher": "MIT Press"}}, {"key": "d", "type": "article", "title": "D", "authors": [], "venue": "JMLR", "tags": [], "fields": {"booktitle": "NeurIPS"}}, {"key": "e", "type": "misc", "title": "E", "authors": [], "tags": [], "fields": {}}]}, "note": "empty journal and booktitle fall through to the publisher, which stays in the fields; a booktitle not used as the venue stays too; all empty means no venue"}
```

## components/bibtex-import/versions/1/properties.py

```python
"""Behavioral properties for lightkone/bibtex-import.

Entries are generated as data, rendered as BibTeX in the many ways exporters
write it (braces or quotes, any field-name case, odd spacing, parentheses,
trailing commas), and the drafts must come back as the description says.
Generated values avoid LaTeX, so plain() leaves them alone; LaTeX and the
messier corners are pinned by the examples.
"""

from hypothesis import given, strategies as st

from schema import Draft, Input

WORD = st.text("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_size=1, max_size=8)
TEXT = st.lists(WORD, min_size=1, max_size=5).map(" ".join)
KEY = st.text("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:_-", min_size=1, max_size=12)
GAP = st.sampled_from(["", " ", "  ", "\n", "\n  ", "\t"])
NAME = st.text("abcdefghijklmnopqrstuvwxyz", min_size=2, max_size=8).map(str.capitalize).filter(lambda w: w.lower() not in ("and", "others"))


def run(impl, text: str) -> list[Draft]:
    return impl(Input(text=text)).papers


def collapse(s: str) -> str:
    return " ".join(s.split())


@st.composite
def value(draw, v: str) -> str:
    """One way an exporter writes the value v."""
    if v.isdigit() and draw(st.booleans()):
        return v
    if draw(st.booleans()):
        return "{" + v + "}"
    return '"' + v + '"'


@st.composite
def entry_text(draw, type_: str, key: str, fields: list[tuple[str, str]]) -> str:
    """Render one entry. Field names get a random case; values a random style."""
    paren = draw(st.booleans())
    open_, close = ("(", ")") if paren else ("{", "}")
    parts = []
    for name, v in fields:
        name = "".join(c.upper() if draw(st.booleans()) else c for c in name)
        parts.append(f"{draw(GAP)}{name}{draw(GAP)}={draw(GAP)}{draw(value(v))}")
    body = ",".join(parts) + ("," if draw(st.booleans()) else "") + draw(GAP)
    return f"@{type_}{draw(GAP)}{open_}{draw(GAP)}{key},{body}{close}"


@st.composite
def simple_entry(draw):
    """(BibTeX text, expected draft) for an entry with ordinary fields."""
    type_ = draw(st.sampled_from(["article", "ARTICLE", "InProceedings", "misc", "book"]))
    key = draw(KEY)
    title = draw(TEXT)
    names = draw(st.lists(st.tuples(st.lists(NAME, min_size=0, max_size=2), NAME), max_size=4))
    comma_style = draw(st.booleans())
    rendered = [f"{last}, {' '.join(first)}" if comma_style and first else " ".join([*first, last]) for first, last in names]
    authors = [f"{last}, {' '.join(first)}" if first else last for first, last in names]
    year = draw(st.none() | st.integers(1000, 9999))
    venue_field = draw(st.sampled_from(["journal", "booktitle", None]))
    venue = draw(TEXT) if venue_field else None
    extra = draw(st.dictionaries(st.sampled_from(["pages", "volume", "number", "publisher", "isbn", "series"]), TEXT, max_size=3))
    fields = [("title", title)]
    if rendered:
        fields.append(("author", draw(st.sampled_from([" and ", " AND ", "\nand "])).join(rendered)))
    if year is not None:
        fields.append(("year", str(year)))
    if venue_field:
        fields.append((venue_field, venue))
    fields += list(extra.items())
    fields = draw(st.permutations(fields))
    if venue is None and "publisher" in extra:
        venue = extra["publisher"]
    expected = Draft(
        key=key, type=type_.lower(), title=title, authors=authors, year=year, venue=venue,
        tags=[], fields={k: collapse(v) for k, v in extra.items()},
    )
    return draw(entry_text(type_, key, fields)), expected


@given(entries=st.lists(simple_entry(), max_size=4), junk=st.lists(st.sampled_from(["", "\n\n", "% a comment\n", "text between entries\n"]), min_size=5, max_size=5))
def test_well_formed_entries_become_drafts(impl, entries, junk):
    text = junk[0] + "".join(t + junk[i % 4 + 1] for i, (t, _) in enumerate(entries))
    assert run(impl, text) == [d for _, d in entries]


@given(entries=st.lists(simple_entry(), min_size=1, max_size=3), drop=st.data())
def test_entries_without_a_title_are_left_out(impl, entries, drop):
    keep = drop.draw(st.lists(st.booleans(), min_size=len(entries), max_size=len(entries)))
    text = ""
    for (t, d), k in zip(entries, keep):
        text += (t if k else f"@misc{{{d.key}, note = {{no title here}}}}") + "\n"
    assert [p.key for p in run(impl, text)] == [d.key for (_, d), k in zip(entries, keep) if k]


@given(e=simple_entry(), wrapper=st.sampled_from(["@comment{{{0}}}", "@preamble{{\"{0}\"}}", "@COMMENT {{{0}}}"]), note=TEXT)
def test_comments_and_preambles_are_not_entries(impl, e, wrapper, note):
    text, draft = e
    assert run(impl, wrapper.format(note) + "\n" + text) == [draft]


@given(name=st.text("abcdefghij", min_size=3, max_size=6), v=TEXT, suffix=TEXT, key=KEY, upper=st.booleans())
def test_string_macros_and_concatenation(impl, name, v, suffix, key, upper):
    use = name.upper() if upper else name
    text = f'@string{{{name} = "{v}"}}\n@article{{{key}, title = {{T}}, journal = {use} # " {suffix}"}}'
    assert run(impl, text)[0].venue == f"{v} {suffix}"


@given(month=st.sampled_from(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]), key=KEY, upper=st.booleans())
def test_month_macros(impl, month, key, upper):
    full = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
            "November", "December"][["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"].index(month)]
    papers = run(impl, f"@misc{{{key}, title = {{T}}, month = {month.upper() if upper else month}}}")
    assert papers[0].fields["month"] == full


@given(key=KEY, pieces=st.lists(st.tuples(WORD, GAP), min_size=1, max_size=6))
def test_whitespace_in_values_collapses(impl, key, pieces):
    raw = "".join(w + (g or " ") for w, g in pieces)
    papers = run(impl, f"@misc{{{key}, title = {{{raw}}}, howpublished = {{  {raw}  }}}}")
    assert papers[0].title == collapse(raw) and papers[0].fields["howpublished"] == collapse(raw)


@given(key=KEY, a=TEXT, b=TEXT)
def test_later_fields_replace_earlier_ones(impl, key, a, b):
    papers = run(impl, f"@misc{{{key}, title = {{{a}}}, title = {{{b}}}, pages = {{{a}}}, PAGES = {{{b}}}}}")
    assert papers[0].title == b and papers[0].fields == {"pages": b}


@given(key=KEY, corp=TEXT.filter(lambda t: "and" not in t.lower().split()), name=NAME)
def test_braced_names_and_others_are_kept(impl, key, corp, name):
    papers = run(impl, f"@misc{{{key}, title = {{T}}, author = {{{{{corp}}} and Ada {name} and others}}}}")
    assert papers[0].authors == [corp, f"{name}, Ada", "others"]


@given(key=KEY, ed=st.lists(NAME, min_size=1, max_size=3))
def test_editors_stand_in_for_missing_authors(impl, key, ed):
    papers = run(impl, f"@book{{{key}, title = {{T}}, editor = {{{' and '.join(ed)}}}}}")
    assert papers[0].authors == ed and "editor" not in papers[0].fields


@given(key=KEY, doi=st.from_regex(r"10\.[0-9]{4,5}/[a-z0-9.]{1,10}", fullmatch=True),
       prefix=st.sampled_from(["", "https://doi.org/", "http://dx.doi.org/", "HTTPS://DOI.ORG/"]))
def test_doi_loses_its_resolver_prefix(impl, key, doi, prefix):
    assert run(impl, f"@article{{{key}, title = {{T}}, doi = {{{prefix}{doi}}}}}")[0].doi == doi


ARXIV = st.from_regex(r"[0-9]{4}\.[0-9]{4,5}", fullmatch=True)


@given(key=KEY, aid=ARXIV, version=st.sampled_from(["", "v1", "v12"]), how=st.sampled_from(["eprint", "arxivid", "url-abs", "url-pdf", "bare"]))
def test_arxiv_ids_are_found(impl, key, aid, version, how):
    fields = {
        "eprint": f"eprint = {{arXiv:{aid}{version}}}, archivePrefix = {{arXiv}}, primaryClass = {{cs.LG}}",
        "arxivid": f"arxivid = {{{aid}{version}}}",
        "url-abs": f"url = {{https://arxiv.org/abs/{aid}{version}}}",
        "url-pdf": f"url = {{https://arxiv.org/pdf/{aid}{version}.pdf}}",
        "bare": f"eprint = {{{aid}{version}}}",
    }[how]
    p = run(impl, f"@article{{{key}, title = {{T}}, {fields}}}")[0]
    assert p.arxiv == aid
    assert not {"eprint", "archiveprefix", "primaryclass", "arxivid"} & set(p.fields)


@given(key=KEY, eprint=st.from_regex(r"[a-z]{3,6}/[0-9]{3}", fullmatch=True))
def test_other_eprints_stay_in_fields(impl, key, eprint):
    p = run(impl, f"@article{{{key}, title = {{T}}, eprint = {{{eprint}}}}}")[0]
    assert p.arxiv is None and p.fields == {"eprint": eprint}


@given(key=KEY, tags=st.lists(TEXT, min_size=1, max_size=4), seps=st.sampled_from([";", ",", "; ", " , "]),
       ids=st.lists(st.sampled_from(["doi:10.1/x", "URL:http://a.b", "https://x.org", "arXiv:2101.00001", "isbn:123"]), max_size=2))
def test_keywords_become_tags_without_identifiers(impl, key, tags, seps, ids):
    p = run(impl, f"@article{{{key}, title = {{T}}, keywords = {{{seps.join(tags + ids)}}}}}")[0]
    assert p.tags == tags and "keywords" not in p.fields
```

## components/bibtex-import/versions/1/schema.py

```python
"""Interface for lightkone/bibtex-import."""

from pydantic import BaseModel, ConfigDict, Field


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(description="BibTeX, for example the contents of a .bib file.")


class Draft(BaseModel):
    """A paper before the library gives it an id. Absent fields are null."""

    model_config = ConfigDict(extra="forbid")

    key: str
    type: str
    title: str
    authors: list[str]
    year: int | None = None
    venue: str | None = None
    abstract: str | None = None
    doi: str | None = None
    arxiv: str | None = None
    url: str | None = None
    tags: list[str]
    file: str | None = None
    notes: str | None = None
    fields: dict[str, str] = Field(description="Remaining BibTeX fields: lower-cased names, values as written.")


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")

    papers: list[Draft] = Field(description="One draft per entry with a title, in the order they appear.")
```

## components/bibtex-import/versions/1/schema/input.json

```json
{
  "additionalProperties": false,
  "properties": {
    "text": {
      "description": "BibTeX, for example the contents of a .bib file.",
      "title": "Text",
      "type": "string"
    }
  },
  "required": [
    "text"
  ],
  "title": "Input",
  "type": "object"
}
```

## components/bibtex-import/versions/1/schema/output.json

```json
{
  "$defs": {
    "Draft": {
      "additionalProperties": false,
      "description": "A paper before the library gives it an id. Absent fields are null.",
      "properties": {
        "abstract": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Abstract"
        },
        "arxiv": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Arxiv"
        },
        "authors": {
          "items": {
            "type": "string"
          },
          "title": "Authors",
          "type": "array"
        },
        "doi": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Doi"
        },
        "fields": {
          "additionalProperties": {
            "type": "string"
          },
          "description": "Remaining BibTeX fields: lower-cased names, values as written.",
          "title": "Fields",
          "type": "object"
        },
        "file": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "File"
        },
        "key": {
          "title": "Key",
          "type": "string"
        },
        "notes": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Notes"
        },
        "tags": {
          "items": {
            "type": "string"
          },
          "title": "Tags",
          "type": "array"
        },
        "title": {
          "title": "Title",
          "type": "string"
        },
        "type": {
          "title": "Type",
          "type": "string"
        },
        "url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Url"
        },
        "venue": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Venue"
        },
        "year": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Year"
        }
      },
      "required": [
        "key",
        "type",
        "title",
        "authors",
        "tags",
        "fields"
      ],
      "title": "Draft",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "papers": {
      "description": "One draft per entry with a title, in the order they appear.",
      "items": {
        "$ref": "#/$defs/Draft"
      },
      "title": "Papers",
      "type": "array"
    }
  },
  "required": [
    "papers"
  ],
  "title": "Output",
  "type": "object"
}
```

## components/bibtex-import/versions/1/symbolon.toml

```toml
[contract]
id = "lightkone/bibtex-import"
version = 1
title = "Read BibTeX into lightkone paper drafts"
description = """
Reads BibTeX text, as exported by Paperpile, Zotero, JabRef or Google
Scholar, into paper drafts the way lightkone's importer does. It never fails:
malformed parts are skipped. Whitespace below means JavaScript's \\s: tab,
LF, VT, FF, CR, space, U+00A0, U+1680, U+2000-U+200A, U+2028, U+2029,
U+202F, U+205F, U+3000 and U+FEFF (and nothing else: not U+0085 or
U+001C-U+001F). Trimming, collapsing and splitting all use this set.

READING ENTRIES. Scan for "@". Read the entry type (characters up to
whitespace or one of , = { } ( ) " #), lower-cased, then skip whitespace. If
the next character is not "{" or "(", skip that "@". The entry closes with
"}" or ")" to match.
  @comment: skip only the "@"; scanning continues inside the comment.
  @preamble: read one value and ignore it.
  @string{name = value}: define a macro (name lower-cased).
  Any other type: the key is everything up to the first "," or the closing
  character outside braces, trimmed ("Erd\\H{o}s1959" is one key). Then fields "name = value" separated by commas. A
  field name is read like a type and lower-cased; a field without a name or
  "=" is skipped up to the next "," or the entry's closing character, whichever
comes first; braced and quoted values in it are skipped whole, read as VALUES
reads them. Reaching the closing character this way ends the entry. A later field
  with the same name replaces the earlier one. An entry with no key and no
  fields is dropped, and so is any entry whose title is missing or empty.
VALUES are parts joined by "#": {braced} text (nested braces, a backslash
escapes the next character, braces are kept inside), "quoted" text (a quote
inside braces does not end it), digits, or a bare word, which is replaced by
a macro of that name (case-insensitive) or kept as written. Month macros
jan..dec mean January..December. Unterminated values run to the end of the
text. Whitespace runs in a value collapse to one space, and the value is
trimmed.

PLAIN TEXT. plain(v) applies these steps in order, each replacing every
non-overlapping match from left to right:
  1. optional "{", then backslash and one of " ' ` ^ ~ = .  (or one of
     c v u H when followed by whitespace or "{"), optional whitespace,
     optional "{", one ASCII letter or \\i or \\j (the dotless letters, read as
     i and j, when not followed by a letter, digit or "_"), optional "}",
     optional "}"  ->  the
     letter plus the combining mark (U+0308, U+0301, U+0300, U+0302, U+0303,
     U+0304, U+0307, U+0327, U+030C, U+0306, U+030B in that order), NFC.
  2. {\\ss} {\\o} {\\O} {\\ae} {\\AE} {\\l} {\\L} {\\i}, or the same without braces
     when the next character is not an ASCII letter, digit or "_" (one
     following space is consumed)  ->  ß ø Ø æ Æ ł Ł ı.
  3. \\emph{x} \\textit{x} \\textbf{x} \\mathrm{x} \\textrm{x}, x without braces  ->  x.
  4. backslash before one of & % $ # _ { }  ->  that character.
  5. remove every { and } not directly after a backslash.
  6. ~ -> space; collapse whitespace runs to one space; trim.

DRAFT FIELDS from an entry's fields (each one used is removed from
"fields" unless stated):
  key, type   from the entry.
  title       plain(title).
  authors     author, or editor if there is no author field. Split on
              whitespace-"and"-whitespace (any case). For each part: plain
              it and drop it if empty; keep it as is if it contains a comma,
              is "others" (any case) or starts with "{" and ends with "}";
              otherwise move the last space-separated word to the front:
              "Ada King Lovelace" -> "Lovelace, Ada King".
  year        the first run of 4 ASCII digits in year, as a number.
  venue       the first of plain(journal), plain(booktitle), plain(publisher)
              that is not empty, so journal = {} does not hide a booktitle;
              absent when all are empty or missing. journal always leaves
              the fields; booktitle leaves them only when journal was empty;
              publisher never does.
  abstract    plain(abstract); empty means absent.
  doi         with a leading http(s)://doi.org/ or dx.doi.org/ removed
              (case-insensitive); empty means absent.
  url, file   as written; an empty value stays "" rather than absent.
  notes       annote, else note, as written.
  arxiv       arxivid; else eprint when archiveprefix or eprinttype is
              "arxiv" (any case); else the id in an arxiv.org/abs|pdf|html/
              url (matched ignoring case, so a V3 version suffix and .PDF are removed
              too); else eprint when it
              starts with NNNN.NNNN. A leading "arXiv:" and a trailing vN are
              removed. When an arxiv id is found, archiveprefix, eprinttype
              and primaryclass are removed; otherwise eprint stays in fields.
  tags        keywords split on ";" or ",", each plained; empty ones and
              ones starting with doi: url: arxiv: isbn: issn: pmid: pmc:
              (any case) or containing http:// or https:// are dropped.
  fields      every remaining field, raw (collapsed) values.
"""
regenerability = "disposable"
license = "Proprietary (kausalflow)"
authors = ["kausalflow/lightkone"]

[entrypoint]
function = "run"

[requires]
network = []
credentials = []
state = []
permissions = []

[spec]
seed = 0
max_examples = 150
timeout_seconds = 300
```

## components/citation-key/versions/1/examples.jsonl

```json
{"input": {"drafts": [{"title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012}]}, "output": {"keys": ["Hinton2012-in"]}, "note": "surname, year, first letters of the first two long words"}
{"input": {"drafts": [{"title": "Attention is all you need", "authors": ["Vaswani, Ashish"], "year": 2017}]}, "output": {"keys": ["Vaswani2017-an"]}, "note": "short words are skipped: attention, need"}
{"input": {"drafts": [{"title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931}]}, "output": {"keys": ["Godel1931-fu"]}, "note": "accents decompose in the surname but vanish from the title"}
{"input": {"drafts": [{"title": "Deep learning", "authors": ["LeCun, Yann"], "year": 2015}], "taken": ["LeCun2015-dl"]}, "output": {"keys": ["LeCun2015-dl2"]}, "note": "a taken key counts up from 2"}
{"input": {"drafts": [{"title": "Deep learning", "authors": ["LeCun, Yann"], "year": 2015}], "taken": ["LeCun2015-dl", "LeCun2015-dl2", "LeCun2015-dl3"]}, "output": {"keys": ["LeCun2015-dl4"]}, "note": "first free number"}
{"input": {"drafts": [{"title": "Deep learning", "authors": ["LeCun, Yann"], "year": 2015}, {"title": "Deep learning", "authors": ["LeCun, Yann"], "year": 2015}, {"title": "Deep learning", "authors": ["LeCun, Yann"], "year": 2015}]}, "output": {"keys": ["LeCun2015-dl", "LeCun2015-dl2", "LeCun2015-dl3"]}, "note": "drafts in one batch take keys from each other"}
{"input": {"drafts": [{"title": "Imported", "authors": ["Doe, Jane"], "year": 2020, "key": "Doe2020-im"}, {"title": "Imported again", "authors": ["Doe, Jane"], "year": 2020, "key": "Doe2020-im"}]}, "output": {"keys": ["Doe2020-im", "Doe2020-ia"]}, "note": "an arriving key is kept unless taken, then a new key is made"}
{"input": {"drafts": [{"title": "Kept key", "authors": [], "key": "mykey"}], "taken": ["mykey"]}, "output": {"keys": ["Anon-kk"]}, "note": "a taken arriving key is replaced"}
{"input": {"drafts": [{"title": "Empty key", "authors": ["Smith, J"], "year": 2001, "key": ""}]}, "output": {"keys": ["Smith2001-ee"]}, "note": "an empty key is no key"}
{"input": {"drafts": [{"title": "No authors here at all", "authors": []}]}, "output": {"keys": ["Anon-ah"]}, "note": "no authors and no year: Anon"}
{"input": {"drafts": [{"title": "Title", "authors": ["李, 雷"], "year": 2019}]}, "output": {"keys": ["Anon2019-tt"]}, "note": "a surname with no ASCII letters becomes Anon"}
{"input": {"drafts": [{"title": "On it", "authors": ["Plato"], "year": 1}]}, "output": {"keys": ["Plato1-xx"]}, "note": "no comma: the whole name is the surname; no long words: xx"}
{"input": {"drafts": [{"title": "Theory of games", "authors": ["von Neumann, John", "Morgenstern, Oskar"], "year": 1944}]}, "output": {"keys": ["VonNeumann1944-tg"]}, "note": "only the first author counts; the first letter is upper-cased"}
{"input": {"drafts": [{"title": "A study", "authors": ["O'Neil, Cathy"], "year": 2016}]}, "output": {"keys": ["ONeil2016-ss"]}, "note": "punctuation in surnames is dropped; one long word gives its letter twice"}
{"input": {"drafts": [{"title": "X-ray crystallography of DNA's double-helix", "authors": ["Franklin, Rosalind"], "year": 1953}]}, "output": {"keys": ["Franklin1953-xc"]}, "note": "hyphens and apostrophes are removed before splitting"}
{"input": {"drafts": [{"title": "Nets", "authors": ["Łukasiewicz, Jan"], "year": 1920}]}, "output": {"keys": ["Ukasiewicz1920-nn"]}, "note": "Ł has no decomposition, so it is dropped"}
{"input": {"drafts": [{"title": "Year zero", "authors": ["Zed, A"], "year": 0}]}, "output": {"keys": ["Zed0-yz"]}, "note": "year 0 is still written"}
{"input": {"drafts": [{"title": "Two  spaces  between", "authors": ["Ng, Andrew"], "year": 2000}]}, "output": {"keys": ["Ng2000-sb"]}, "note": "double spaces make empty words, which are skipped"}
{"input": {"drafts": [{"title": "Research", "authors": ["Smith, J"], "year": 2010}, {"title": "Research", "authors": ["Smith, K"], "year": 2010}], "taken": ["Smith2010-rr"]}, "output": {"keys": ["Smith2010-rr2", "Smith2010-rr3"]}, "note": "the second gets 3 after the first takes 2"}
```

## components/citation-key/versions/1/properties.py

```python
"""Behavioral properties for lightkone/citation-key."""

import re
import unicodedata

from hypothesis import given, strategies as st

from schema import Draft, Input

SURNAMES = ["Hinton", "Gödel", "de la Fontaine", "O'Neil", "Müller", "Łukasiewicz", "李", "", "smith", "Van der Waals"]
FIRST = ["Geoffrey", "Kurt", "Ada", ""]
TITLE_WORDS = ["Attention", "is", "all", "you", "need", "Über", "café", "deep", "nets", "of", "the", "Naïve", "Bayes", "2012", "x-ray"]


@st.composite
def drafts(draw, with_key=False):
    authors = draw(st.lists(st.tuples(st.sampled_from(SURNAMES), st.sampled_from(FIRST))
                            .map(lambda t: f"{t[0]}, {t[1]}" if t[1] else t[0]), max_size=3))
    return Draft(
        title=" ".join(draw(st.lists(st.sampled_from(TITLE_WORDS), max_size=6))),
        authors=authors,
        year=draw(st.none() | st.integers(1900, 2030)),
        key=draw(st.none() | st.sampled_from(["", "Hinton2012-ab", "mykey", "Godel1931-uf"])) if with_key else None,
    )


def base(d: Draft) -> str:
    raw = d.authors[0].split(",")[0] if d.authors else ""
    last = "".join(c for c in unicodedata.normalize("NFKD", raw) if c.isascii() and c.isalpha()) or "Anon"
    return last[0].upper() + last[1:] + (str(d.year) if d.year is not None else "")


def suffix(d: Draft) -> str:
    words = [w for w in re.sub(r"[^a-z ]", "", d.title.lower()).split(" ") if len(w) > 3]
    if not words:
        return "xx"
    return words[0][0] + (words[1] if len(words) > 1 else words[0])[0]


def keys(impl, ds, taken=()):
    return impl(Input(drafts=ds, taken=list(taken))).keys


@given(d=drafts())
def test_a_key_is_surname_year_and_two_title_letters(impl, d):
    assert keys(impl, [d]) == [f"{base(d)}-{suffix(d)}"]


@given(ds=st.lists(drafts(with_key=True), max_size=8), taken=st.lists(st.sampled_from(["Hinton2012-ab", "mykey", "Anon-xx", "Anon-xx2"]), max_size=3))
def test_keys_are_unique_and_never_taken(impl, ds, taken):
    got = keys(impl, ds, taken)
    assert len(got) == len(ds) and len(set(got)) == len(got) and not set(got) & set(taken)


@given(d=drafts(), n=st.integers(1, 5))
def test_collisions_count_up_from_two(impl, d, n):
    first = f"{base(d)}-{suffix(d)}"
    taken = [first] + [f"{first}{i}" for i in range(2, n + 1)]
    assert keys(impl, [d], taken) == [f"{first}{n + 1}"]


@given(d=drafts(), copies=st.integers(2, 5))
def test_identical_drafts_in_one_batch_get_distinct_keys(impl, d, copies):
    first = f"{base(d)}-{suffix(d)}"
    assert keys(impl, [d] * copies) == [first] + [f"{first}{i}" for i in range(2, copies + 1)]


@given(d=drafts(), key=st.text("abcdefghijABCDEF0123456789:-_", min_size=1, max_size=12), taken=st.booleans())
def test_an_arriving_key_is_kept_when_free(impl, d, key, taken):
    d = d.model_copy(update={"key": key})
    got = keys(impl, [d], [key] if taken else [])[0]
    assert (got == key) != taken


@given(ds=st.lists(drafts(with_key=True), max_size=6))
def test_keys_look_like_keys(impl, ds):
    for k, d in zip(keys(impl, ds), ds):
        assert k == d.key or re.fullmatch(r"[A-Z][A-Za-z]*[0-9]*-[a-z]{2}[0-9]*", k)
```

## components/citation-key/versions/1/schema.py

```python
"""Interface for lightkone/citation-key."""

from pydantic import BaseModel, ConfigDict, Field


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    authors: list[str] = Field(default_factory=list, description="'Last, First' strings or whole names, in order.")
    year: int | None = Field(None, ge=0)
    key: str | None = Field(None, description="A key the paper arrived with, e.g. from an imported .bib file.")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    drafts: list[Draft] = Field(description="New papers, in the order they are added.")
    taken: list[str] = Field(default_factory=list, description="Keys already in the library.")


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keys: list[str] = Field(description="One key per draft, in order.")
```

## components/citation-key/versions/1/schema/input.json

```json
{
  "$defs": {
    "Draft": {
      "additionalProperties": false,
      "properties": {
        "authors": {
          "description": "'Last, First' strings or whole names, in order.",
          "items": {
            "type": "string"
          },
          "title": "Authors",
          "type": "array"
        },
        "key": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "A key the paper arrived with, e.g. from an imported .bib file.",
          "title": "Key"
        },
        "title": {
          "title": "Title",
          "type": "string"
        },
        "year": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Year"
        }
      },
      "required": [
        "title"
      ],
      "title": "Draft",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "drafts": {
      "description": "New papers, in the order they are added.",
      "items": {
        "$ref": "#/$defs/Draft"
      },
      "title": "Drafts",
      "type": "array"
    },
    "taken": {
      "description": "Keys already in the library.",
      "items": {
        "type": "string"
      },
      "title": "Taken",
      "type": "array"
    }
  },
  "required": [
    "drafts"
  ],
  "title": "Input",
  "type": "object"
}
```

## components/citation-key/versions/1/schema/output.json

```json
{
  "additionalProperties": false,
  "properties": {
    "keys": {
      "description": "One key per draft, in order.",
      "items": {
        "type": "string"
      },
      "title": "Keys",
      "type": "array"
    }
  },
  "required": [
    "keys"
  ],
  "title": "Output",
  "type": "object"
}
```

## components/citation-key/versions/1/symbolon.toml

```toml
[contract]
id = "lightkone/citation-key"
version = 1
title = "Give new papers lightkone's citation keys"
description = """
Gives each new paper a BibTeX citation key the way lightkone does when papers
are added, in Paperpile's style: Hinton2012-ip. Keys are unique within the
library, and a key, once given, never changes, so LaTeX documents keep
working.

Drafts are handled in order. Each key given is taken for the drafts after it.

  1. A draft that already has a key (non-empty) that is not taken keeps it.
  2. Otherwise the key is BASE-SUFFIX:
     BASE    the first author's surname (the part before the first comma),
             decomposed with Unicode NFKD, keeping only the ASCII letters
             A-Z and a-z; "Anon" when there is no first author or nothing is
             left. Its first letter is upper-cased, the rest kept as is.
             Then the year, if the draft has one.
     SUFFIX  the title lower-cased, with every character other than a-z and
             space removed (so accented letters disappear, they are not
             decomposed), split on single spaces, keeping words longer than
             3 letters. SUFFIX is the first letter of the first such word and
             the first letter of the second, or of the first again when there
             is only one. With none, "xx".
  3. If BASE-SUFFIX is taken, try BASE-SUFFIX2, BASE-SUFFIX3, ... and use the
     first that is free.
"""
regenerability = "disposable"
license = "Proprietary (kausalflow)"
authors = ["kausalflow/lightkone"]

[entrypoint]
function = "run"

[requires]
network = []
credentials = []
state = []
permissions = []

[spec]
seed = 0
max_examples = 200
timeout_seconds = 300
```

## components/library-file/versions/1/examples.jsonl

```json
{"input": {"text": {"$text": "paperpile-import.json"}}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"p1\",\n   \"key\": \"Vaswani2017-at\",\n   \"type\": \"inproceedings\",\n   \"title\": \"Attention Is All You Need\",\n   \"authors\": [\n    \"Vaswani, Ashish\",\n    \"Shazeer, Noam\"\n   ],\n   \"year\": 2017,\n   \"venue\": \"Advances in Neural Information Processing Systems\",\n   \"arxiv\": \"1706.03762\",\n   \"file\": \"All Papers/VASWANI/Vaswani et al. 2017 - Attention Is All You Need.pdf\",\n   \"tags\": [\n    \"ml\"\n   ],\n   \"added\": \"2024-03-01T09:00:00.000Z\",\n   \"fields\": {},\n   \"folders\": []\n  },\n  {\n   \"id\": \"p2\",\n   \"key\": \"Peskin1995-in\",\n   \"type\": \"book\",\n   \"title\": \"An Introduction to Quantum Field Theory\",\n   \"authors\": [\n    \"Peskin, Michael E.\",\n    \"Schroeder, Daniel V.\"\n   ],\n   \"year\": 1995,\n   \"file\": \"All Papers/MLDS/Physics/QFT/Peskin and Schroeder 1995 - An Introduction to Quantum Field Theory.pdf\",\n   \"tags\": [\n    \"physics\",\n    \"to read\"\n   ],\n   \"added\": \"2024-03-01T09:00:00.000Z\",\n   \"fields\": {},\n   \"folders\": [\n    \"MLDS/Physics/QFT\"\n   ]\n  },\n  {\n   \"id\": \"p3\",\n   \"key\": \"Hinton2012-im\",\n   \"type\": \"article\",\n   \"title\": \"Improving neural networks by preventing co-adaptation of feature detectors\",\n   \"authors\": [\n    \"Hinton, Geoffrey E.\",\n    \"Srivastava, Nitish\"\n   ],\n   \"year\": 2012,\n   \"arxiv\": \"1207.0580\",\n   \"file\": \"All Papers/HINTON/Hinton et al. 2012 - Improving neural networks.pdf; All Papers/MLDS/Reading group/Hinton et al. 2012 - Improving neural networks.pdf\",\n   \"tags\": [],\n   \"added\": \"2024-03-01T09:00:00.000Z\",\n   \"fields\": {\n    \"note\": \"dropout\"\n   },\n   \"folders\": [\n    \"MLDS/Reading group\"\n   ]\n  },\n  {\n   \"id\": \"p4\",\n   \"key\": \"Anon-un\",\n   \"type\": \"article\",\n   \"title\": \"Untitled scan\",\n   \"authors\": [],\n   \"file\": \"All Papers/Other/scan-0042.pdf\",\n   \"tags\": [],\n   \"added\": \"2024-03-01T09:00:00.000Z\",\n   \"fields\": {},\n   \"folders\": []\n  },\n  {\n   \"id\": \"p5\",\n   \"key\": \"LIGO2016-ob\",\n   \"type\": \"article\",\n   \"title\": \"Observation of Gravitational Waves from a Binary Black Hole Merger\",\n   \"authors\": [\n    \"LIGO Scientific Collaboration\",\n    \"others\"\n   ],\n   \"year\": 2016,\n   \"venue\": \"Physical Review Letters\",\n   \"doi\": \"10.1103/PhysRevLett.116.061102\",\n   \"tags\": [],\n   \"added\": \"2024-03-01T09:00:00.000Z\",\n   \"fields\": {\n    \"volume\": \"116\",\n    \"pages\": \"061102\"\n   },\n   \"folders\": []\n  },\n  {\n   \"id\": \"p6\",\n   \"key\": \"Noether1918-in\",\n   \"type\": \"article\",\n   \"title\": \"Invariante Variationsprobleme\",\n   \"authors\": [\n    \"Noether, Emmy\"\n   ],\n   \"year\": 1918,\n   \"venue\": \"Nachrichten von der Gesellschaft der Wissenschaften zu Göttingen\",\n   \"file\": \"Physics/Classics/Noether 1918.pdf;;Physics/Classics/Noether 1918.pdf\",\n   \"tags\": [],\n   \"added\": \"2024-03-01T09:00:00.000Z\",\n   \"fields\": {},\n   \"folders\": [\n    \"Physics/Classics\"\n   ]\n  }\n ]\n}", "bib": "@inproceedings{Vaswani2017-at,\n  title         = {{Attention Is All You Need}},\n  author        = {Vaswani, Ashish and Shazeer, Noam},\n  year          = {2017},\n  booktitle     = {Advances in Neural Information Processing Systems},\n  eprint        = {1706.03762},\n  archiveprefix = {arXiv},\n  keywords      = {ml},\n  file          = {All Papers/VASWANI/Vaswani et al. 2017 - Attention Is All You Need.pdf}\n}\n\n@book{Peskin1995-in,\n  title    = {{An Introduction to Quantum Field Theory}},\n  author   = {Peskin, Michael E. and Schroeder, Daniel V.},\n  year     = {1995},\n  keywords = {physics;to read},\n  file     = {All Papers/MLDS/Physics/QFT/Peskin and Schroeder 1995 - An Introduction to Quantum Field Theory.pdf}\n}\n\n@article{Hinton2012-im,\n  title         = {{Improving neural networks by preventing co-adaptation of feature detectors}},\n  author        = {Hinton, Geoffrey E. and Srivastava, Nitish},\n  year          = {2012},\n  eprint        = {1207.0580},\n  archiveprefix = {arXiv},\n  file          = {All Papers/HINTON/Hinton et al. 2012 - Improving neural networks.pdf; All Papers/MLDS/Reading group/Hinton et al. 2012 - Improving neural networks.pdf},\n  note          = {dropout}\n}\n\n@article{Anon-un,\n  title = {{Untitled scan}},\n  file  = {All Papers/Other/scan-0042.pdf}\n}\n\n@article{LIGO2016-ob,\n  title   = {{Observation of Gravitational Waves from a Binary Black Hole Merger}},\n  author  = {{LIGO Scientific Collaboration} and others},\n  year    = {2016},\n  journal = {Physical Review Letters},\n  doi     = {10.1103/PhysRevLett.116.061102},\n  volume  = {116},\n  pages   = {061102}\n}\n\n@article{Noether1918-in,\n  title   = {{Invariante Variationsprobleme}},\n  author  = {Noether, Emmy},\n  year    = {1918},\n  journal = {Nachrichten von der Gesellschaft der Wissenschaften zu Göttingen},\n  file    = {Physics/Classics/Noether 1918.pdf;;Physics/Classics/Noether 1918.pdf}\n}\n", "foldered": 3}, "note": "a library imported from Paperpile: folders come from the Drive paths; author folders and Other are skipped"}
{"input": {"text": {"$text": "saved.json"}}, "output": {"written": false, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"p1\",\n   \"key\": \"Vaswani2017-at\",\n   \"type\": \"inproceedings\",\n   \"title\": \"Attention Is All You Need\",\n   \"authors\": [\n    \"Vaswani, Ashish\",\n    \"Shazeer, Noam\"\n   ],\n   \"year\": 2017,\n   \"venue\": \"Advances in Neural Information Processing Systems\",\n   \"arxiv\": \"1706.03762\",\n   \"file\": \"All Papers/VASWANI/Vaswani et al. 2017 - Attention Is All You Need.pdf\",\n   \"tags\": [\n    \"ml\"\n   ],\n   \"added\": \"2024-03-01T09:00:00.000Z\",\n   \"fields\": {},\n   \"folders\": []\n  },\n  {\n   \"id\": \"p2\",\n   \"key\": \"Peskin1995-in\",\n   \"type\": \"book\",\n   \"title\": \"An Introduction to Quantum Field Theory\",\n   \"authors\": [\n    \"Peskin, Michael E.\",\n    \"Schroeder, Daniel V.\"\n   ],\n   \"year\": 1995,\n   \"file\": \"All Papers/MLDS/Physics/QFT/Peskin and Schroeder 1995 - An Introduction to Quantum Field Theory.pdf\",\n   \"tags\": [\n    \"physics\",\n    \"to read\"\n   ],\n   \"added\": \"2024-03-01T09:00:00.000Z\",\n   \"fields\": {},\n   \"folders\": [\n    \"MLDS/Physics/QFT\"\n   ]\n  },\n  {\n   \"id\": \"p3\",\n   \"key\": \"Hinton2012-im\",\n   \"type\": \"article\",\n   \"title\": \"Improving neural networks by preventing co-adaptation of feature detectors\",\n   \"authors\": [\n    \"Hinton, Geoffrey E.\",\n    \"Srivastava, Nitish\"\n   ],\n   \"year\": 2012,\n   \"arxiv\": \"1207.0580\",\n   \"file\": \"All Papers/HINTON/Hinton et al. 2012 - Improving neural networks.pdf; All Papers/MLDS/Reading group/Hinton et al. 2012 - Improving neural networks.pdf\",\n   \"tags\": [],\n   \"added\": \"2024-03-01T09:00:00.000Z\",\n   \"fields\": {\n    \"note\": \"dropout\"\n   },\n   \"folders\": [\n    \"MLDS/Reading group\"\n   ]\n  },\n  {\n   \"id\": \"p4\",\n   \"key\": \"Anon-un\",\n   \"type\": \"article\",\n   \"title\": \"Untitled scan\",\n   \"authors\": [],\n   \"file\": \"All Papers/Other/scan-0042.pdf\",\n   \"tags\": [],\n   \"added\": \"2024-03-01T09:00:00.000Z\",\n   \"fields\": {},\n   \"folders\": []\n  },\n  {\n   \"id\": \"p5\",\n   \"key\": \"LIGO2016-ob\",\n   \"type\": \"article\",\n   \"title\": \"Observation of Gravitational Waves from a Binary Black Hole Merger\",\n   \"authors\": [\n    \"LIGO Scientific Collaboration\",\n    \"others\"\n   ],\n   \"year\": 2016,\n   \"venue\": \"Physical Review Letters\",\n   \"doi\": \"10.1103/PhysRevLett.116.061102\",\n   \"tags\": [],\n   \"added\": \"2024-03-01T09:00:00.000Z\",\n   \"fields\": {\n    \"volume\": \"116\",\n    \"pages\": \"061102\"\n   },\n   \"folders\": []\n  },\n  {\n   \"id\": \"p6\",\n   \"key\": \"Noether1918-in\",\n   \"type\": \"article\",\n   \"title\": \"Invariante Variationsprobleme\",\n   \"authors\": [\n    \"Noether, Emmy\"\n   ],\n   \"year\": 1918,\n   \"venue\": \"Nachrichten von der Gesellschaft der Wissenschaften zu Göttingen\",\n   \"file\": \"Physics/Classics/Noether 1918.pdf;;Physics/Classics/Noether 1918.pdf\",\n   \"tags\": [],\n   \"added\": \"2024-03-01T09:00:00.000Z\",\n   \"fields\": {},\n   \"folders\": [\n    \"Physics/Classics\"\n   ]\n  }\n ]\n}", "bib": null, "foldered": 0}, "note": "exactly what lightkone wrote last time: nothing to write"}
{"input": {"text": {"$text": "shared.json"}}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"s1\",\n   \"key\": \"Noether1918-in\",\n   \"type\": \"article\",\n   \"title\": \"Invariante Variationsprobleme\",\n   \"authors\": [\n    \"Noether, Emmy\"\n   ],\n   \"year\": 1918,\n   \"venue\": \"Göttinger Nachrichten\",\n   \"tags\": [\n    \"physics\"\n   ],\n   \"added\": \"2024-03-01T09:00:00.000Z\",\n   \"fields\": {\n    \"lightkone-read\": \"yes\"\n   },\n   \"folders\": [\n    \"Physics/Classics\"\n   ],\n   \"starred\": true,\n   \"notes\": \"Theorem I: symmetries ↔ conserved currents.\\nTheorem II: gauge.\",\n   \"by\": \"Ana\"\n  },\n  {\n   \"id\": \"s2\",\n   \"key\": \"Dirac1928-qu\",\n   \"type\": \"article\",\n   \"title\": \"The Quantum Theory of the Electron\",\n   \"authors\": [\n    \"Dirac, P. A. M.\"\n   ],\n   \"year\": 1928,\n   \"venue\": \"Proc. R. Soc. Lond. A\",\n   \"doi\": \"https://doi.org/10.1098/rspa.1928.0023\",\n   \"file\": \"All Papers/DIRAC/Dirac 1928.pdf\",\n   \"tags\": [],\n   \"added\": \"2024-03-01T09:00:00.000Z\",\n   \"fields\": {},\n   \"trashed\": \"2024-05-02T10:00:00.000Z\",\n   \"folders\": []\n  },\n  {\n   \"id\": \"s3\",\n   \"key\": \"Shannon1948-am\",\n   \"type\": \"article\",\n   \"title\": \"A Mathematical Theory of Communication\",\n   \"authors\": [\n    \"Shannon, C. E.\"\n   ],\n   \"year\": 1948,\n   \"venue\": \"Bell System Technical Journal\",\n   \"tags\": [\n    \"information theory\",\n    \"ml\"\n   ],\n   \"added\": \"2024-03-01T09:00:00.000Z\",\n   \"fields\": {\n    \"volume\": \"27\",\n    \"pages\": \"379--423\"\n   },\n   \"folders\": [],\n   \"opened\": \"2024-06-01T08:00:00.000Z\",\n   \"rating\": 4.5,\n   \"pdf\": \"papers/SHANNON/Shannon 1948 - A Mathematical Theory of Communication.pdf\"\n  }\n ],\n \"bibSync\": [\n  {\n   \"folder\": \"Physics\",\n   \"repo\": \"ana/thesis\",\n   \"path\": \"refs.bib\",\n   \"tex\": \"\",\n   \"aliases\": {\n    \"2\": \"s1\",\n    \"1928\": \"s2\",\n    \"shannon\": \"s3\"\n   }\n  }\n ],\n \"exportedBy\": \"a sync script\"\n}", "bib": "@article{Noether1918-in,\n  title    = {{Invariante Variationsprobleme}},\n  author   = {Noether, Emmy},\n  year     = {1918},\n  journal  = {Göttinger Nachrichten},\n  keywords = {physics}\n}\n\n@article{Shannon1948-am,\n  title    = {{A Mathematical Theory of Communication}},\n  author   = {Shannon, C. E.},\n  year     = {1948},\n  journal  = {Bell System Technical Journal},\n  keywords = {information theory;ml},\n  volume   = {27},\n  pages    = {379--423}\n}\n", "foldered": 0}, "note": "a shared library: bibSync kept, another tool's top-level key kept after it, alias keys that are numbers move first, the trashed paper left out of library.bib"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": []}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": []\n}", "bib": "", "foldered": 0}, "note": "an empty library written compactly is rewritten with an indent of one space"}
{"input": {"text": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": []\n}"}, "output": {"written": false, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": []\n}", "bib": null, "foldered": 0}, "note": "an empty library already in lightkone's layout"}
{"input": {"text": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": []\n}\n"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": []\n}", "bib": "", "foldered": 0}, "note": "a trailing newline is enough to make the save write"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [], \"bibSync\": []}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": []\n}", "bib": "", "foldered": 0}, "note": "an empty bibSync is left out"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 7, \"papers\": []}"}, "raises": "ValueError", "note": "a version above 1 was saved by a newer lightkone: refused, nothing written"}
{"input": {"text": "{\"papers\": [], \"version\": 1, \"format\": \"lightkone-library\"}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": []\n}", "bib": "", "foldered": 0}, "note": "top-level keys are written in lightkone's order"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"a\", \"key\": \"Doe2020-ab\", \"type\": \"article\", \"title\": \"A title\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"file\": \"Reading group/Doe 2020.pdf\"}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"a\",\n   \"key\": \"Doe2020-ab\",\n   \"type\": \"article\",\n   \"title\": \"A title\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"file\": \"Reading group/Doe 2020.pdf\",\n   \"folders\": [\n    \"Reading group\"\n   ]\n  }\n ]\n}", "bib": "@article{Doe2020-ab,\n  title  = {{A title}},\n  author = {Doe, Jane},\n  file   = {Reading group/Doe 2020.pdf}\n}\n", "foldered": 1}, "note": "a path without All Papers still gives its folder"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"a\", \"key\": \"Doe2020-ab\", \"type\": \"article\", \"title\": \"A title\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"file\": \"All Papers/Doe 2020.pdf\"}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"a\",\n   \"key\": \"Doe2020-ab\",\n   \"type\": \"article\",\n   \"title\": \"A title\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"file\": \"All Papers/Doe 2020.pdf\",\n   \"folders\": []\n  }\n ]\n}", "bib": "@article{Doe2020-ab,\n  title  = {{A title}},\n  author = {Doe, Jane},\n  file   = {All Papers/Doe 2020.pdf}\n}\n", "foldered": 0}, "note": "a PDF directly in All Papers is in no folder"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"a\", \"key\": \"Doe2020-ab\", \"type\": \"article\", \"title\": \"A title\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"file\": \"All Papers/ML/Doe 2020.pdf;All Papers/McKay/x.pdf;All Papers/2019/y.pdf;All Papers/Other/z.pdf\"}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"a\",\n   \"key\": \"Doe2020-ab\",\n   \"type\": \"article\",\n   \"title\": \"A title\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"file\": \"All Papers/ML/Doe 2020.pdf;All Papers/McKay/x.pdf;All Papers/2019/y.pdf;All Papers/Other/z.pdf\",\n   \"folders\": [\n    \"ML\",\n    \"McKay\",\n    \"2019\"\n   ]\n  }\n ]\n}", "bib": "@article{Doe2020-ab,\n  title  = {{A title}},\n  author = {Doe, Jane},\n  file   = {All Papers/ML/Doe 2020.pdf;All Papers/McKay/x.pdf;All Papers/2019/y.pdf;All Papers/Other/z.pdf}\n}\n", "foldered": 1}, "note": "a single directory in capitals is kept unless it is an author's surname: ML and 2019 stay folders, McKay is kept, Other is skipped"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"a\", \"key\": \"Doe2020-ab\", \"type\": \"article\", \"title\": \"A title\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"file\": \"All Papers/Other/Sub/z.pdf;All Papers/HINTON/Deep/q.pdf\"}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"a\",\n   \"key\": \"Doe2020-ab\",\n   \"type\": \"article\",\n   \"title\": \"A title\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"file\": \"All Papers/Other/Sub/z.pdf;All Papers/HINTON/Deep/q.pdf\",\n   \"folders\": [\n    \"Other/Sub\",\n    \"HINTON/Deep\"\n   ]\n  }\n ]\n}", "bib": "@article{Doe2020-ab,\n  title  = {{A title}},\n  author = {Doe, Jane},\n  file   = {All Papers/Other/Sub/z.pdf;All Papers/HINTON/Deep/q.pdf}\n}\n", "foldered": 1}, "note": "author and Other folders are skipped only when they are the whole path"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"a\", \"key\": \"Doe2020-ab\", \"type\": \"article\", \"title\": \"A title\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"file\": \"  ; All Papers/A/b/x.pdf ;All Papers/A/b/y.pdf;;All Papers/c/d.pdf\"}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"a\",\n   \"key\": \"Doe2020-ab\",\n   \"type\": \"article\",\n   \"title\": \"A title\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"file\": \"  ; All Papers/A/b/x.pdf ;All Papers/A/b/y.pdf;;All Papers/c/d.pdf\",\n   \"folders\": [\n    \"A/b\",\n    \"c\"\n   ]\n  }\n ]\n}", "bib": "@article{Doe2020-ab,\n  title  = {{A title}},\n  author = {Doe, Jane},\n  file   = {  ; All Papers/A/b/x.pdf ;All Papers/A/b/y.pdf;;All Papers/c/d.pdf}\n}\n", "foldered": 1}, "note": "empty paths skipped, each path trimmed, repeats kept once in order"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"a\", \"key\": \"Doe2020-ab\", \"type\": \"article\", \"title\": \"A title\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"file\": \"All Papers/ X /a.pdf; All Papers/Y/ z /b.pdf\"}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"a\",\n   \"key\": \"Doe2020-ab\",\n   \"type\": \"article\",\n   \"title\": \"A title\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"file\": \"All Papers/ X /a.pdf; All Papers/Y/ z /b.pdf\",\n   \"folders\": [\n    \" X \",\n    \"Y/ z \"\n   ]\n  }\n ]\n}", "bib": "@article{Doe2020-ab,\n  title  = {{A title}},\n  author = {Doe, Jane},\n  file   = {All Papers/ X /a.pdf; All Papers/Y/ z /b.pdf}\n}\n", "foldered": 1}, "note": "only whole paths are trimmed, not each directory"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"a\", \"key\": \"Doe2020-ab\", \"type\": \"article\", \"title\": \"A title\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"file\": \"All Papers/Physics/a.pdf\", \"folders\": []}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"a\",\n   \"key\": \"Doe2020-ab\",\n   \"type\": \"article\",\n   \"title\": \"A title\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"file\": \"All Papers/Physics/a.pdf\",\n   \"folders\": []\n  }\n ]\n}", "bib": "@article{Doe2020-ab,\n  title  = {{A title}},\n  author = {Doe, Jane},\n  file   = {All Papers/Physics/a.pdf}\n}\n", "foldered": 0}, "note": "a paper that already has folders, even none, keeps them"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"a\", \"key\": \"Doe2020-ab\", \"type\": \"article\", \"title\": \"A title\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}}, {\"id\": \"b\", \"key\": \"Doe2020-ab2\", \"type\": \"article\", \"title\": \"A title\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"folders\": [\"X\"]}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"a\",\n   \"key\": \"Doe2020-ab\",\n   \"type\": \"article\",\n   \"title\": \"A title\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"folders\": []\n  },\n  {\n   \"id\": \"b\",\n   \"key\": \"Doe2020-ab2\",\n   \"type\": \"article\",\n   \"title\": \"A title\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"folders\": [\n    \"X\"\n   ]\n  }\n ]\n}", "bib": "@article{Doe2020-ab,\n  title  = {{A title}},\n  author = {Doe, Jane}\n}\n\n@article{Doe2020-ab2,\n  title  = {{A title}},\n  author = {Doe, Jane}\n}\n", "foldered": 0}, "note": "a paper with no file gets an empty folders list, added after its other keys"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"a\", \"key\": \"Doe2020-ab\", \"type\": \"article\", \"title\": \"A title\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"year\": 2017.0, \"extra\": [0.1, 1e+16, 1e+21, 1.5e+300, 1e-07, 1e-06, -0.0, 123456789012345, 2.5, -3]}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"a\",\n   \"key\": \"Doe2020-ab\",\n   \"type\": \"article\",\n   \"title\": \"A title\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"year\": 2017,\n   \"extra\": [\n    0.1,\n    10000000000000000,\n    1e+21,\n    1.5e+300,\n    1e-7,\n    0.000001,\n    0,\n    123456789012345,\n    2.5,\n    -3\n   ],\n   \"folders\": []\n  }\n ]\n}", "bib": "@article{Doe2020-ab,\n  title  = {{A title}},\n  author = {Doe, Jane},\n  year   = {2017}\n}\n", "foldered": 0}, "note": "numbers are written the way JavaScript prints them"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"a\", \"key\": \"Doe2020-ab\", \"type\": \"article\", \"title\": \"A title\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"extra\": {\"b\": 1, \"10\": 2, \"2\": 3, \"01\": 4, \"-1\": 5, \"4294967295\": 6, \"4294967294\": 7, \"1.5\": 8}}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"a\",\n   \"key\": \"Doe2020-ab\",\n   \"type\": \"article\",\n   \"title\": \"A title\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"extra\": {\n    \"2\": 3,\n    \"10\": 2,\n    \"4294967294\": 7,\n    \"b\": 1,\n    \"01\": 4,\n    \"-1\": 5,\n    \"4294967295\": 6,\n    \"1.5\": 8\n   },\n   \"folders\": []\n  }\n ]\n}", "bib": "@article{Doe2020-ab,\n  title  = {{A title}},\n  author = {Doe, Jane}\n}\n", "foldered": 0}, "note": "keys that are array indices are written first, in numeric order"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"a\", \"key\": \"Doe2020-ab\", \"type\": \"article\", \"title\": \"Quote \\\" backslash \\\\ tab \\t newline \\n bell \\u0007 escape \\u001b DEL  line sep   é 漢字 🙂\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"a\",\n   \"key\": \"Doe2020-ab\",\n   \"type\": \"article\",\n   \"title\": \"Quote \\\" backslash \\\\ tab \\t newline \\n bell \\u0007 escape \\u001b DEL  line sep   é 漢字 🙂\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"folders\": []\n  }\n ]\n}", "bib": "@article{Doe2020-ab,\n  title  = {{Quote \" backslash \\ tab \t newline \n bell \u0007 escape \u001b DEL  line sep   é 漢字 🙂}},\n  author = {Doe, Jane}\n}\n", "foldered": 0}, "note": "only quotes, backslashes and control characters are escaped"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"a\", \"key\": \"Doe2020-ab\", \"type\": \"article\", \"title\": \"A title\", \"authors\": [\"Doe, Jane\"], \"tags\": [\"a\", \"b\"], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {\"note\": \"has & and %\", \"lightkone-x\": \"private\"}, \"venue\": \"Venue & Co\", \"doi\": \"10.1/x\", \"starred\": true}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"a\",\n   \"key\": \"Doe2020-ab\",\n   \"type\": \"article\",\n   \"title\": \"A title\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [\n    \"a\",\n    \"b\"\n   ],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {\n    \"note\": \"has & and %\",\n    \"lightkone-x\": \"private\"\n   },\n   \"venue\": \"Venue & Co\",\n   \"doi\": \"10.1/x\",\n   \"starred\": true,\n   \"folders\": []\n  }\n ]\n}", "bib": "@article{Doe2020-ab,\n  title    = {{A title}},\n  author   = {Doe, Jane},\n  journal  = {Venue \\& Co},\n  doi      = {10.1/x},\n  keywords = {a;b},\n  note     = {has & and %}\n}\n", "foldered": 0}, "note": "library.bib is the BibTeX export of each paper"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"a\", \"key\": \"Doe2020-ab\", \"type\": \"book\", \"title\": \"A title\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"trashed\": \"2024-02-02T00:00:00.000Z\"}, {\"id\": \"b\", \"key\": \"Roe1999-xy\", \"type\": \"article\", \"title\": \"Second\", \"authors\": [\"LIGO Collaboration\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"year\": 1999}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"a\",\n   \"key\": \"Doe2020-ab\",\n   \"type\": \"book\",\n   \"title\": \"A title\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"trashed\": \"2024-02-02T00:00:00.000Z\",\n   \"folders\": []\n  },\n  {\n   \"id\": \"b\",\n   \"key\": \"Roe1999-xy\",\n   \"type\": \"article\",\n   \"title\": \"Second\",\n   \"authors\": [\n    \"LIGO Collaboration\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"year\": 1999,\n   \"folders\": []\n  }\n ]\n}", "bib": "@article{Roe1999-xy,\n  title  = {{Second}},\n  author = {{LIGO Collaboration}},\n  year   = {1999}\n}\n", "foldered": 0}, "note": "papers in the trash are left out of library.bib; entries are joined by a newline"}
{"input": {"text": "{\"format\": \"x\", \"format\": \"lightkone-library\", \"papers\": []}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": []\n}", "bib": "", "foldered": 0}, "note": "a repeated key: the last value counts, in the first one's place"}
{"input": {"text": "  \n{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": []}\n\t "}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": []\n}", "bib": "", "foldered": 0}, "note": "whitespace around the JSON is fine"}
{"input": {"text": "nope"}, "raises": "ValueError", "note": "not JSON"}
{"input": {"text": ""}, "raises": "ValueError", "note": "an empty file"}
{"input": {"text": "{\"format\":\"lightkone-library\",\"version\":1,\"papers\":[],\"x\":NaN}"}, "raises": "ValueError", "note": "NaN is not JSON"}
{"input": {"text": "{\"format\":\"lightkone-library\",\"version\":1,\"papers\":[],}"}, "raises": "ValueError", "note": "a trailing comma is not JSON"}
{"input": {"text": "null"}, "raises": "ValueError", "note": "JSON, but not an object"}
{"input": {"text": "[]"}, "raises": "ValueError", "note": "an array is not a library"}
{"input": {"text": "\"lightkone-library\""}, "raises": "ValueError", "note": "a string is not a library"}
{"input": {"text": "{}"}, "raises": "ValueError", "note": "no format"}
{"input": {"text": "{\"format\": \"Lightkone-library\", \"version\": 1, \"papers\": []}"}, "raises": "ValueError", "note": "format must match exactly"}
{"input": {"text": "{\"format\": \"paperpile\", \"papers\": []}"}, "raises": "ValueError", "note": "another app's file"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1}"}, "raises": "ValueError", "note": "no papers"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": {}}"}, "raises": "ValueError", "note": "papers must be a list"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": \"ab\"}"}, "raises": "ValueError", "note": "papers must be a list, not a string"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [null]}"}, "raises": "ValueError", "note": "a paper must be an object"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [3]}"}, "raises": "ValueError", "note": "a paper must be an object, not a number"}
{"input": {"text": "{\"exportedBy\": \"zotero-sync\", \"format\": \"lightkone-library\", \"papers\": [], \"meta\": {\"b\": 2, \"a\": [1, {}]}, \"version\": 1, \"1\": \"index key\"}"}, "output": {"written": true, "library": "{\n \"1\": \"index key\",\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [],\n \"exportedBy\": \"zotero-sync\",\n \"meta\": {\n  \"b\": 2,\n  \"a\": [\n   1,\n   {}\n  ]\n }\n}", "bib": "", "foldered": 0}, "note": "other tools' top-level keys are kept, in the order the file lists them, after format, version, papers and bibSync; a key that is an array index still comes first"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"bibSync\": [], \"papers\": [], \"note\": 0}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [],\n \"note\": 0\n}", "bib": "", "foldered": 0}, "note": "an empty bibSync is dropped but another tool's key is kept, even when its value is 0"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [], \"x\": 1, \"y\": true, \"x\": \"second\"}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [],\n \"x\": \"second\",\n \"y\": true\n}", "bib": "", "foldered": 0}, "note": "a repeated top-level key keeps its last value, in the first one's place"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"t1\", \"key\": \"Trash1\", \"type\": \"misc\", \"title\": \"Paper 1\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"trashed\": false}, {\"id\": \"t2\", \"key\": \"Trash2\", \"type\": \"misc\", \"title\": \"Paper 2\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"trashed\": 0}, {\"id\": \"t3\", \"key\": \"Trash3\", \"type\": \"misc\", \"title\": \"Paper 3\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"trashed\": \"\"}, {\"id\": \"t5\", \"key\": \"Trash5\", \"type\": \"misc\", \"title\": \"Paper 5\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"t1\",\n   \"key\": \"Trash1\",\n   \"type\": \"misc\",\n   \"title\": \"Paper 1\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"trashed\": false,\n   \"folders\": []\n  },\n  {\n   \"id\": \"t2\",\n   \"key\": \"Trash2\",\n   \"type\": \"misc\",\n   \"title\": \"Paper 2\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"trashed\": 0,\n   \"folders\": []\n  },\n  {\n   \"id\": \"t3\",\n   \"key\": \"Trash3\",\n   \"type\": \"misc\",\n   \"title\": \"Paper 3\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"trashed\": \"\",\n   \"folders\": []\n  },\n  {\n   \"id\": \"t5\",\n   \"key\": \"Trash5\",\n   \"type\": \"misc\",\n   \"title\": \"Paper 5\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"folders\": []\n  }\n ]\n}", "bib": "@misc{Trash1,\n  title  = {{Paper 1}},\n  author = {Doe, Jane}\n}\n\n@misc{Trash2,\n  title  = {{Paper 2}},\n  author = {Doe, Jane}\n}\n\n@misc{Trash3,\n  title  = {{Paper 3}},\n  author = {Doe, Jane}\n}\n\n@misc{Trash5,\n  title  = {{Paper 5}},\n  author = {Doe, Jane}\n}\n", "foldered": 0}, "note": "a trashed value that JavaScript counts as false (false, 0, \"\") or no trashed key keeps the paper in library.bib"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"t1\", \"key\": \"Trash1\", \"type\": \"misc\", \"title\": \"Paper 1\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"trashed\": []}, {\"id\": \"t2\", \"key\": \"Trash2\", \"type\": \"misc\", \"title\": \"Paper 2\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"trashed\": {}}, {\"id\": \"t3\", \"key\": \"Trash3\", \"type\": \"misc\", \"title\": \"Paper 3\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"trashed\": true}, {\"id\": \"t4\", \"key\": \"Trash4\", \"type\": \"misc\", \"title\": \"Paper 4\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"trashed\": 1}, {\"id\": \"t5\", \"key\": \"Trash5\", \"type\": \"misc\", \"title\": \"Paper 5\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"trashed\": \"no\"}, {\"id\": \"t6\", \"key\": \"Trash6\", \"type\": \"misc\", \"title\": \"Paper 6\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"t1\",\n   \"key\": \"Trash1\",\n   \"type\": \"misc\",\n   \"title\": \"Paper 1\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"trashed\": [],\n   \"folders\": []\n  },\n  {\n   \"id\": \"t2\",\n   \"key\": \"Trash2\",\n   \"type\": \"misc\",\n   \"title\": \"Paper 2\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"trashed\": {},\n   \"folders\": []\n  },\n  {\n   \"id\": \"t3\",\n   \"key\": \"Trash3\",\n   \"type\": \"misc\",\n   \"title\": \"Paper 3\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"trashed\": true,\n   \"folders\": []\n  },\n  {\n   \"id\": \"t4\",\n   \"key\": \"Trash4\",\n   \"type\": \"misc\",\n   \"title\": \"Paper 4\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"trashed\": 1,\n   \"folders\": []\n  },\n  {\n   \"id\": \"t5\",\n   \"key\": \"Trash5\",\n   \"type\": \"misc\",\n   \"title\": \"Paper 5\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"trashed\": \"no\",\n   \"folders\": []\n  },\n  {\n   \"id\": \"t6\",\n   \"key\": \"Trash6\",\n   \"type\": \"misc\",\n   \"title\": \"Paper 6\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"folders\": []\n  }\n ]\n}", "bib": "@misc{Trash6,\n  title  = {{Paper 6}},\n  author = {Doe, Jane}\n}\n", "foldered": 0}, "note": "any other trashed value puts the paper in the trash, an empty list or object included"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"t1\", \"key\": \"Trash1\", \"type\": \"misc\", \"title\": \"Paper 1\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"trashed\": \"2024-02-01T00:00:00.000Z\"}, {\"id\": \"t2\", \"key\": \"Trash2\", \"type\": \"misc\", \"title\": \"Paper 2\", \"authors\": [\"Doe, Jane\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"trashed\": true}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"t1\",\n   \"key\": \"Trash1\",\n   \"type\": \"misc\",\n   \"title\": \"Paper 1\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"trashed\": \"2024-02-01T00:00:00.000Z\",\n   \"folders\": []\n  },\n  {\n   \"id\": \"t2\",\n   \"key\": \"Trash2\",\n   \"type\": \"misc\",\n   \"title\": \"Paper 2\",\n   \"authors\": [\n    \"Doe, Jane\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"trashed\": true,\n   \"folders\": []\n  }\n ]\n}", "bib": "", "foldered": 0}, "note": "when every paper is in the trash, library.bib is empty"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"a\", \"key\": \"Ka\", \"type\": \"article\", \"title\": \"T\", \"authors\": [\"Hinton, Geoffrey E.\", \"Srivastava, Nitish\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"file\": \"All Papers/HINTON/a.pdf;All Papers/SRIVASTAVA/a.pdf;All Papers/ML/a.pdf;All Papers/DOE/a.pdf\"}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"a\",\n   \"key\": \"Ka\",\n   \"type\": \"article\",\n   \"title\": \"T\",\n   \"authors\": [\n    \"Hinton, Geoffrey E.\",\n    \"Srivastava, Nitish\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"file\": \"All Papers/HINTON/a.pdf;All Papers/SRIVASTAVA/a.pdf;All Papers/ML/a.pdf;All Papers/DOE/a.pdf\",\n   \"folders\": [\n    \"ML\",\n    \"DOE\"\n   ]\n  }\n ]\n}", "bib": "@article{Ka,\n  title  = {{T}},\n  author = {Hinton, Geoffrey E. and Srivastava, Nitish},\n  file   = {All Papers/HINTON/a.pdf;All Papers/SRIVASTAVA/a.pdf;All Papers/ML/a.pdf;All Papers/DOE/a.pdf}\n}\n", "foldered": 1}, "note": "any author's surname in capitals is an author folder, not only the first author's; DOE, an author of no paper here, stays a folder"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"a\", \"key\": \"Ka\", \"type\": \"article\", \"title\": \"T\", \"authors\": [], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"file\": \"All Papers/HINTON/a.pdf;All Papers/2019/a.pdf;All Papers/ML/a.pdf;All Papers/Ml/a.pdf\"}, {\"id\": \"b\", \"key\": \"Kb\", \"type\": \"article\", \"title\": \"T\", \"authors\": [\",\", \"\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"file\": \"All Papers/HINTON/b.pdf;All Papers/2019/b.pdf\"}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"a\",\n   \"key\": \"Ka\",\n   \"type\": \"article\",\n   \"title\": \"T\",\n   \"authors\": [],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"file\": \"All Papers/HINTON/a.pdf;All Papers/2019/a.pdf;All Papers/ML/a.pdf;All Papers/Ml/a.pdf\",\n   \"folders\": [\n    \"2019\",\n    \"Ml\"\n   ]\n  },\n  {\n   \"id\": \"b\",\n   \"key\": \"Kb\",\n   \"type\": \"article\",\n   \"title\": \"T\",\n   \"authors\": [\n    \",\",\n    \"\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"file\": \"All Papers/HINTON/b.pdf;All Papers/2019/b.pdf\",\n   \"folders\": [\n    \"2019\"\n   ]\n  }\n ]\n}", "bib": "@article{Ka,\n  title = {{T}},\n  file  = {All Papers/HINTON/a.pdf;All Papers/2019/a.pdf;All Papers/ML/a.pdf;All Papers/Ml/a.pdf}\n}\n\n@article{Kb,\n  title  = {{T}},\n  author = {, and {}},\n  file   = {All Papers/HINTON/b.pdf;All Papers/2019/b.pdf}\n}\n", "foldered": 2}, "note": "with no authors (or only empty surnames), a single directory in capitals with a letter is taken for an author folder; 2019 has no letters and stays"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"a\", \"key\": \"Ka\", \"type\": \"article\", \"title\": \"T\", \"authors\": [\"Stra\\u00dfe, Anna\", \"van der Berg, Jan\", \"O'Neil: X\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"file\": \"All Papers/STRASSE/a.pdf;All Papers/VAN DER BERG/a.pdf;All Papers/O'NEIL - X/a.pdf;All Papers/STRA\\u00dfE/a.pdf;All Papers/hinton/a.pdf\"}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"a\",\n   \"key\": \"Ka\",\n   \"type\": \"article\",\n   \"title\": \"T\",\n   \"authors\": [\n    \"Straße, Anna\",\n    \"van der Berg, Jan\",\n    \"O'Neil: X\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"file\": \"All Papers/STRASSE/a.pdf;All Papers/VAN DER BERG/a.pdf;All Papers/O'NEIL - X/a.pdf;All Papers/STRAßE/a.pdf;All Papers/hinton/a.pdf\",\n   \"folders\": [\n    \"STRAßE\",\n    \"hinton\"\n   ]\n  }\n ]\n}", "bib": "@article{Ka,\n  title  = {{T}},\n  author = {Straße, Anna and van der Berg, Jan and {O'Neil: X}},\n  file   = {All Papers/STRASSE/a.pdf;All Papers/VAN DER BERG/a.pdf;All Papers/O'NEIL - X/a.pdf;All Papers/STRAßE/a.pdf;All Papers/hinton/a.pdf}\n}\n", "foldered": 1}, "note": "author folders are cleaned and upper-cased as pdf-filing does: ß becomes SS, a colon becomes ' - '"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1, \"papers\": [{\"id\": \"a\", \"key\": \"Ka\", \"type\": \"article\", \"title\": \"T\", \"authors\": [\"Ml, Kim\"], \"tags\": [], \"added\": \"2024-01-01T00:00:00.000Z\", \"fields\": {}, \"file\": \"All Papers/ML/a.pdf;All Papers/Physics/ML/a.pdf\"}]}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": [\n  {\n   \"id\": \"a\",\n   \"key\": \"Ka\",\n   \"type\": \"article\",\n   \"title\": \"T\",\n   \"authors\": [\n    \"Ml, Kim\"\n   ],\n   \"tags\": [],\n   \"added\": \"2024-01-01T00:00:00.000Z\",\n   \"fields\": {},\n   \"file\": \"All Papers/ML/a.pdf;All Papers/Physics/ML/a.pdf\",\n   \"folders\": [\n    \"Physics/ML\"\n   ]\n  }\n ]\n}", "bib": "@article{Ka,\n  title  = {{T}},\n  author = {Ml, Kim},\n  file   = {All Papers/ML/a.pdf;All Papers/Physics/ML/a.pdf}\n}\n", "foldered": 1}, "note": "ML is an author folder when an author is called Ml; deeper paths are never author folders"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1.5, \"papers\": []}"}, "raises": "ValueError", "note": "any number above 1 is refused, 1.5 included"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 0, \"papers\": []}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": []\n}", "bib": "", "foldered": 0}, "note": "a version of 0 or below is read and written as 1"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": \"2\", \"papers\": []}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": []\n}", "bib": "", "foldered": 0}, "note": "a version that is not a number is not checked, and is written as 1"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"papers\": []}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": []\n}", "bib": "", "foldered": 0}, "note": "no version at all is read as 1"}
{"input": {"text": "{\"format\": \"lightkone-library\", \"version\": 1.0, \"papers\": []}"}, "output": {"written": true, "library": "{\n \"format\": \"lightkone-library\",\n \"version\": 1,\n \"papers\": []\n}", "bib": "", "foldered": 0}, "note": "1.0 is version 1"}
```

## components/library-file/versions/1/fixtures/paperpile-import.json

```json
{"format": "lightkone-library", "version": 1, "papers": [{"id": "p1", "key": "Vaswani2017-at", "type": "inproceedings", "title": "Attention Is All You Need", "authors": ["Vaswani, Ashish", "Shazeer, Noam"], "year": 2017, "venue": "Advances in Neural Information Processing Systems", "arxiv": "1706.03762", "file": "All Papers/VASWANI/Vaswani et al. 2017 - Attention Is All You Need.pdf", "tags": ["ml"], "added": "2024-03-01T09:00:00.000Z", "fields": {}}, {"id": "p2", "key": "Peskin1995-in", "type": "book", "title": "An Introduction to Quantum Field Theory", "authors": ["Peskin, Michael E.", "Schroeder, Daniel V."], "year": 1995, "file": "All Papers/MLDS/Physics/QFT/Peskin and Schroeder 1995 - An Introduction to Quantum Field Theory.pdf", "tags": ["physics", "to read"], "added": "2024-03-01T09:00:00.000Z", "fields": {}}, {"id": "p3", "key": "Hinton2012-im", "type": "article", "title": "Improving neural networks by preventing co-adaptation of feature detectors", "authors": ["Hinton, Geoffrey E.", "Srivastava, Nitish"], "year": 2012, "arxiv": "1207.0580", "file": "All Papers/HINTON/Hinton et al. 2012 - Improving neural networks.pdf; All Papers/MLDS/Reading group/Hinton et al. 2012 - Improving neural networks.pdf", "tags": [], "added": "2024-03-01T09:00:00.000Z", "fields": {"note": "dropout"}}, {"id": "p4", "key": "Anon-un", "type": "article", "title": "Untitled scan", "authors": [], "file": "All Papers/Other/scan-0042.pdf", "tags": [], "added": "2024-03-01T09:00:00.000Z", "fields": {}}, {"id": "p5", "key": "LIGO2016-ob", "type": "article", "title": "Observation of Gravitational Waves from a Binary Black Hole Merger", "authors": ["LIGO Scientific Collaboration", "others"], "year": 2016, "venue": "Physical Review Letters", "doi": "10.1103/PhysRevLett.116.061102", "tags": [], "added": "2024-03-01T09:00:00.000Z", "fields": {"volume": "116", "pages": "061102"}}, {"id": "p6", "key": "Noether1918-in", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "venue": "Nachrichten von der Gesellschaft der Wissenschaften zu Göttingen", "file": "Physics/Classics/Noether 1918.pdf;;Physics/Classics/Noether 1918.pdf", "tags": [], "added": "2024-03-01T09:00:00.000Z", "fields": {}}]}
```

## components/library-file/versions/1/fixtures/saved.json

```json
{
 "format": "lightkone-library",
 "version": 1,
 "papers": [
  {
   "id": "p1",
   "key": "Vaswani2017-at",
   "type": "inproceedings",
   "title": "Attention Is All You Need",
   "authors": [
    "Vaswani, Ashish",
    "Shazeer, Noam"
   ],
   "year": 2017,
   "venue": "Advances in Neural Information Processing Systems",
   "arxiv": "1706.03762",
   "file": "All Papers/VASWANI/Vaswani et al. 2017 - Attention Is All You Need.pdf",
   "tags": [
    "ml"
   ],
   "added": "2024-03-01T09:00:00.000Z",
   "fields": {},
   "folders": []
  },
  {
   "id": "p2",
   "key": "Peskin1995-in",
   "type": "book",
   "title": "An Introduction to Quantum Field Theory",
   "authors": [
    "Peskin, Michael E.",
    "Schroeder, Daniel V."
   ],
   "year": 1995,
   "file": "All Papers/MLDS/Physics/QFT/Peskin and Schroeder 1995 - An Introduction to Quantum Field Theory.pdf",
   "tags": [
    "physics",
    "to read"
   ],
   "added": "2024-03-01T09:00:00.000Z",
   "fields": {},
   "folders": [
    "MLDS/Physics/QFT"
   ]
  },
  {
   "id": "p3",
   "key": "Hinton2012-im",
   "type": "article",
   "title": "Improving neural networks by preventing co-adaptation of feature detectors",
   "authors": [
    "Hinton, Geoffrey E.",
    "Srivastava, Nitish"
   ],
   "year": 2012,
   "arxiv": "1207.0580",
   "file": "All Papers/HINTON/Hinton et al. 2012 - Improving neural networks.pdf; All Papers/MLDS/Reading group/Hinton et al. 2012 - Improving neural networks.pdf",
   "tags": [],
   "added": "2024-03-01T09:00:00.000Z",
   "fields": {
    "note": "dropout"
   },
   "folders": [
    "MLDS/Reading group"
   ]
  },
  {
   "id": "p4",
   "key": "Anon-un",
   "type": "article",
   "title": "Untitled scan",
   "authors": [],
   "file": "All Papers/Other/scan-0042.pdf",
   "tags": [],
   "added": "2024-03-01T09:00:00.000Z",
   "fields": {},
   "folders": []
  },
  {
   "id": "p5",
   "key": "LIGO2016-ob",
   "type": "article",
   "title": "Observation of Gravitational Waves from a Binary Black Hole Merger",
   "authors": [
    "LIGO Scientific Collaboration",
    "others"
   ],
   "year": 2016,
   "venue": "Physical Review Letters",
   "doi": "10.1103/PhysRevLett.116.061102",
   "tags": [],
   "added": "2024-03-01T09:00:00.000Z",
   "fields": {
    "volume": "116",
    "pages": "061102"
   },
   "folders": []
  },
  {
   "id": "p6",
   "key": "Noether1918-in",
   "type": "article",
   "title": "Invariante Variationsprobleme",
   "authors": [
    "Noether, Emmy"
   ],
   "year": 1918,
   "venue": "Nachrichten von der Gesellschaft der Wissenschaften zu Göttingen",
   "file": "Physics/Classics/Noether 1918.pdf;;Physics/Classics/Noether 1918.pdf",
   "tags": [],
   "added": "2024-03-01T09:00:00.000Z",
   "fields": {},
   "folders": [
    "Physics/Classics"
   ]
  }
 ]
}
```

## components/library-file/versions/1/fixtures/shared.json

```json
{
  "format": "lightkone-library",
  "version": 1,
  "papers": [
    {
      "id": "s1",
      "key": "Noether1918-in",
      "type": "article",
      "title": "Invariante Variationsprobleme",
      "authors": [
        "Noether, Emmy"
      ],
      "year": 1918,
      "venue": "Göttinger Nachrichten",
      "tags": [
        "physics"
      ],
      "added": "2024-03-01T09:00:00.000Z",
      "fields": {
        "lightkone-read": "yes"
      },
      "folders": [
        "Physics/Classics"
      ],
      "starred": true,
      "notes": "Theorem I: symmetries ↔ conserved currents.\nTheorem II: gauge.",
      "by": "Ana"
    },
    {
      "id": "s2",
      "key": "Dirac1928-qu",
      "type": "article",
      "title": "The Quantum Theory of the Electron",
      "authors": [
        "Dirac, P. A. M."
      ],
      "year": 1928,
      "venue": "Proc. R. Soc. Lond. A",
      "doi": "https://doi.org/10.1098/rspa.1928.0023",
      "file": "All Papers/DIRAC/Dirac 1928.pdf",
      "tags": [],
      "added": "2024-03-01T09:00:00.000Z",
      "fields": {},
      "trashed": "2024-05-02T10:00:00.000Z"
    },
    {
      "id": "s3",
      "key": "Shannon1948-am",
      "type": "article",
      "title": "A Mathematical Theory of Communication",
      "authors": [
        "Shannon, C. E."
      ],
      "year": 1948,
      "venue": "Bell System Technical Journal",
      "tags": [
        "information theory",
        "ml"
      ],
      "added": "2024-03-01T09:00:00.000Z",
      "fields": {
        "volume": "27",
        "pages": "379--423"
      },
      "folders": [],
      "opened": "2024-06-01T08:00:00.000Z",
      "rating": 4.5,
      "pdf": "papers/SHANNON/Shannon 1948 - A Mathematical Theory of Communication.pdf"
    }
  ],
  "bibSync": [
    {
      "folder": "Physics",
      "repo": "ana/thesis",
      "path": "refs.bib",
      "tex": "",
      "aliases": {
        "shannon": "s3",
        "1928": "s2",
        "2": "s1"
      }
    }
  ],
  "exportedBy": "a sync script"
}
```

## components/library-file/versions/1/properties.py

```python
"""Behavioral properties for lightkone/library-file.

Libraries are generated the way they arise: imported from Paperpile (Drive
paths, no folders), already saved by lightkone, or edited by other tools
(compact JSON, extra keys). Strings and numbers stay simple here; the
examples pin down escaping and number printing.
"""

import json
import re

from hypothesis import given, strategies as st

from schema import Input

SEGMENTS = ["All Papers", "HINTON", "DOE", "Other", "ML", "Physics", "QFT", "Reading group", "McKay", "2019"]
INDEX = re.compile(r"^(0|[1-9][0-9]*)$")


def clean(s):
    """lightkone/pdf-filing's clean()."""
    s = s.replace("---", "\u2014").replace("--", "\u2013")
    s = re.sub(r'[:/\\?*"<>|]', " - ", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"( - )+", " - ", s)
    return re.sub(r"^[\s-]+|[\s-]+$", "", s)


def author_folders(authors):
    return {f for f in (clean(a.split(",")[0].strip()).upper() for a in authors) if f}


def folders_from(file, authors=()):
    """The folder rule of the description, written out independently."""
    names = author_folders(authors)

    def author_folder(d):
        if d == "Other":
            return True
        return d in names if names else d == d.upper() and d != d.lower()

    out = []
    for path in (file or "").split(";"):
        path = path.strip()
        if not path:
            continue
        dirs = path.split("/")[:-1]
        if dirs[:1] == ["All Papers"]:
            dirs = dirs[1:]
        if not dirs or (len(dirs) == 1 and author_folder(dirs[0])):
            continue
        f = "/".join(dirs)
        if f not in out:
            out.append(f)
    return out


paths = st.lists(st.sampled_from(SEGMENTS), max_size=3).map(lambda d: "/".join(d + ["x.pdf"]))


@st.composite
def paper(draw, i):
    p = {"id": f"p{i}", "key": f"Key{i}", "type": draw(st.sampled_from(["article", "book", "misc"])),
         "title": draw(st.sampled_from(["Gauge fields", "Dropout", "Notes on QFT"])),
         "authors": draw(st.lists(st.sampled_from(["Doe, Jane", "Roe, R.", "Hinton, G. E.", "Ml, Kim"]), max_size=2)),
         "tags": draw(st.lists(st.sampled_from(["ml", "physics"]), unique=True, max_size=2)),
         "added": "2024-01-01T00:00:00.000Z", "fields": {}}
    if draw(st.booleans()):
        p["year"] = draw(st.integers(1900, 2030))
    if draw(st.booleans()):
        p["file"] = ";".join(draw(st.lists(paths, min_size=1, max_size=3)))
    if draw(st.booleans()):
        p["folders"] = draw(st.lists(st.sampled_from(["ML", "Physics/QFT"]), unique=True, max_size=2))
    if draw(st.booleans()):
        p["starred"] = True
    if draw(st.booleans()):
        p["trashed"] = "2024-02-01T00:00:00.000Z"
    return p


@st.composite
def library(draw):
    data = {"format": "lightkone-library", "version": 1,
            "papers": [draw(paper(i)) for i in range(draw(st.integers(0, 4)))]}
    if draw(st.booleans()):
        data["bibSync"] = draw(st.lists(st.just({"folder": "", "repo": "a/b", "path": "refs.bib"}), max_size=1))
    if draw(st.booleans()):
        data["note"] = "kept elsewhere"
    if draw(st.booleans()):
        data = {"source": {"tool": "sync", "at": 3}, **data}
    return data


@st.composite
def stored(draw):
    """(data, text): a library and the text of the file holding it."""
    data = draw(library())
    indent = draw(st.sampled_from([None, 1, 2]))
    return data, json.dumps(data, indent=indent, ensure_ascii=False)


def run(impl, text):
    return impl(Input(text=text))


@given(stored())
def test_saved_file_keeps_exactly_the_library(impl, s):
    data, text = s
    out = json.loads(run(impl, text).library)
    expect = {"format": "lightkone-library", "version": 1, "papers": data["papers"]}
    if data.get("bibSync"):
        expect["bibSync"] = data["bibSync"]
    expect.update((k, v) for k, v in data.items() if k not in ("format", "version", "papers", "bibSync"))
    for p in expect["papers"]:
        p.setdefault("folders", folders_from(p.get("file"), p["authors"]))
    assert out == expect
    assert list(out) == list(expect), "other tools' keys come after lightkone's, in the file's order"


@given(stored())
def test_papers_gain_folders_from_paperpile_paths(impl, s):
    data, text = s
    out = run(impl, text)
    papers = json.loads(out.library)["papers"]
    for before, after in zip(data["papers"], papers):
        assert after["folders"] == before.get("folders", folders_from(before.get("file"), before["authors"]))
        assert list(after)[: len(before)] == list(before), "existing keys keep their order; folders goes last"
    assert out.foldered == sum(1 for p in data["papers"] if "folders" not in p and folders_from(p.get("file"), p["authors"]))


@given(stored())
def test_layout_is_one_space_indented_json(impl, s):
    data, text = s
    out = run(impl, text)
    assert out.library == json.dumps(json.loads(out.library), indent=1, ensure_ascii=False)


@given(stored())
def test_writes_only_when_the_text_changes(impl, s):
    data, text = s
    out = run(impl, text)
    assert out.written == (out.library != text)
    assert (out.bib is None) == (not out.written)
    if not out.written:
        assert out.library == text


@given(stored())
def test_saving_again_writes_nothing(impl, s):
    data, text = s
    first = run(impl, text)
    again = run(impl, first.library)
    assert not again.written and again.library == first.library and again.foldered == 0


@given(library(), st.booleans())
def test_bib_has_one_entry_per_live_paper_in_order(impl, data, pretty):
    text = json.dumps(data) + ("\n" if pretty else "")
    out = run(impl, text)
    assert out.written
    heads = re.findall(r"^@(\w+)\{([^,\n]*),$", out.bib, re.M)
    live = [p for p in data["papers"] if not p.get("trashed")]
    assert heads == [(p["type"] or "misc", p["key"]) for p in live]
    assert (out.bib == "") == (not live)


not_a_library = st.one_of(
    st.sampled_from(["", "nope", "{", "[]", "null", "true", "3", '"x"', "{}", "NaN"]),
    st.builds(lambda f: json.dumps({"format": f, "version": 1, "papers": []}),
              st.sampled_from(["", "lightkone", "Lightkone-library", "lightkone-library ", "paperpile"])),
    st.builds(lambda p: json.dumps({"format": "lightkone-library", "version": 1, **p}),
              st.sampled_from([{}, {"papers": {}}, {"papers": 3}, {"papers": "abc"}, {"papers": [None]}, {"papers": [1, {}]},
                              {"version": 2, "papers": []}, {"version": 1.5, "papers": []}, {"version": 1000, "papers": []}])),
)


@given(not_a_library)
def test_anything_else_is_refused(impl, text):
    try:
        out = run(impl, text)
    except ValueError:
        return
    raise AssertionError(f"accepted a file that is not a lightkone library: {out}")
```

## components/library-file/versions/1/schema.py

```python
"""Interface for lightkone/library-file.

The input is library.json's raw text, because what is being specified is how
lightkone reads and rewrites that file. Text that is not a lightkone library
at all is in scope (it must raise ValueError). A library whose papers lack
the fields lightkone always writes is out of scope: lightkone never produces
one, so Input rejects it.
"""

import json
import math
import re
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, field_validator

FieldName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_.:+-]*$")]
SURROGATE = re.compile(r"[\ud800-\udfff]")


class StoredPaper(BaseModel):
    """A paper as lightkone stores it. Other keys may appear and must be kept."""

    model_config = ConfigDict(extra="allow", strict=True)

    id: str
    key: str
    type: str
    title: str
    authors: list[str]
    year: int | float | None = Field(None, description="A whole number; 2017.0 is read as 2017.")
    venue: str | None = None
    abstract: str | None = None
    doi: str | None = None
    arxiv: str | None = None
    url: str | None = None
    tags: list[str]
    file: str | None = None
    added: str
    folders: list[str] | None = None
    fields: dict[FieldName, str]

    @field_validator("year")
    @classmethod
    def _whole(cls, year):
        if isinstance(year, float) and not year.is_integer():
            raise ValueError("year is a whole number")
        return year


def _check_values(v: Any) -> None:
    if v is None:
        raise ValueError("lightkone never writes null inside a library")
    if isinstance(v, bool):
        return
    if isinstance(v, int) and abs(v) > 2**53:
        raise ValueError("integers beyond 2**53 are not exact in JavaScript")
    if isinstance(v, float) and not math.isfinite(v):
        raise ValueError("numbers too large for a double are out of scope")
    if isinstance(v, str) and SURROGATE.search(v):
        raise ValueError("lone surrogates are out of scope")
    if isinstance(v, dict):
        for k, x in v.items():
            _check_values(k)
            _check_values(x)
    if isinstance(v, list):
        for x in v:
            _check_values(x)


def _not_json(name: str):
    raise ValueError(f"{name} is not JSON")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(description="lightkone/library.json exactly as it is stored.")

    @field_validator("text")
    @classmethod
    def _in_scope(cls, text: str) -> str:
        try:
            data = json.loads(text, parse_constant=_not_json)
        except ValueError:
            return text
        if not (isinstance(data, dict) and data.get("format") == "lightkone-library"):
            return text
        papers = data.get("papers")
        if papers == "":
            raise ValueError('"papers": "" is out of scope (lightkone happens to accept it)')
        if not isinstance(papers, list) or not all(isinstance(p, dict) for p in papers):
            return text
        _check_values(data)
        for p in papers:
            try:
                StoredPaper.model_validate(p)
            except ValidationError as e:
                raise ValueError(f"paper {p.get('id')!r} is not shaped the way lightkone writes papers: {e}") from None
        sync = data.get("bibSync")
        if sync is not None and not (isinstance(sync, list) and all(isinstance(t, dict) for t in sync)):
            raise ValueError("bibSync, when present, is a list of objects")
        return text


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")

    written: bool = Field(description="Whether saving writes anything: false when library.json would not change.")
    library: str = Field(description="The text of library.json after the save.")
    bib: str | None = Field(description="The library.bib written with it; null when nothing is written.")
    foldered: int = Field(ge=0, description="How many papers took their folders from Paperpile's file paths.")
```

## components/library-file/versions/1/schema/input.json

```json
{
  "additionalProperties": false,
  "properties": {
    "text": {
      "description": "lightkone/library.json exactly as it is stored.",
      "title": "Text",
      "type": "string"
    }
  },
  "required": [
    "text"
  ],
  "title": "Input",
  "type": "object"
}
```

## components/library-file/versions/1/schema/output.json

```json
{
  "additionalProperties": false,
  "properties": {
    "bib": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "The library.bib written with it; null when nothing is written.",
      "title": "Bib"
    },
    "foldered": {
      "description": "How many papers took their folders from Paperpile's file paths.",
      "minimum": 0,
      "title": "Foldered",
      "type": "integer"
    },
    "library": {
      "description": "The text of library.json after the save.",
      "title": "Library",
      "type": "string"
    },
    "written": {
      "description": "Whether saving writes anything: false when library.json would not change.",
      "title": "Written",
      "type": "boolean"
    }
  },
  "required": [
    "written",
    "library",
    "bib",
    "foldered"
  ],
  "title": "Output",
  "type": "object"
}
```

## components/library-file/versions/1/symbolon.toml

```toml
[contract]
id = "lightkone/library-file"
version = 1
title = "Read and rewrite lightkone's library.json"
description = """
lightkone/library.json is the library: lightkone's own data, and what other
devices, Claude through MCP, and anyone's scripts read and write. This
contract fixes what lightkone does when it opens that file and saves it
again with nothing else changed (Library.load, then Library.save): which
files it accepts, what it adds, and the exact text it writes.

Input: the file's text. Output:
  written    whether the save writes anything
  library    library.json's text after the save
  bib        lightkone/library.bib, written alongside; null when not written
  foldered   how many papers took their folders from Paperpile paths

Accepting a file. Raise ValueError, writing nothing, when the text is not
JSON, is not an object whose "format" is "lightkone-library", has no
"papers" list, or a paper is not an object. Also raise ValueError when
"version" is a number above 1: the file was saved by a newer lightkone,
which may store things this one would drop. Any other version, or none, is
read as 1.

Folders. Each paper with no "folders" key gets one, from its "file" (a
Paperpile Drive path, or several separated by ";"): for each path, trimmed,
skipping empty ones, take its directories (every segment but the last); drop
a leading "All Papers"; skip it when nothing is left, or when a single
directory is left that is an author folder. Join the rest with "/". Keep the
first of any repeats, in order. A paper with no file gets []. foldered
counts the papers that gained a non-empty list. A paper that already has
"folders", even [], keeps it.

Author folders. Paperpile files a PDF under its first author's surname in
capitals, as lightkone/pdf-filing names the folder; any of the paper's
authors counts, since the author list may have changed since. Let N be the
set of clean(surname(a)) upper-cased, for each author a, leaving out empty
ones (clean and surname as lightkone/pdf-filing defines them; upper-casing
is JavaScript's toUpperCase, so "ß" becomes "SS"). A directory is an author
folder when it is "Other" or is in N. When N is empty there is nothing to
compare, and a directory is an author folder when upper-casing leaves it
unchanged and lower-casing changes it ("HINTON", but not "2019"). So a
user's own "ML" folder is kept unless an author is called Ml.

Writing. The saved file holds format "lightkone-library", version 1, papers,
and bibSync when it is a non-empty list, then every other top-level key of
the input with its value as read, in the input's order: lightkone keeps
other tools' data. written is false only when that text equals the input exactly; then
nothing is written and library is the input.

The text is JavaScript's JSON.stringify with an indent of one space:
  - objects and arrays one entry per line, indented one more space per
    level; ": " after a key; empty ones written {} and []
  - an object's keys keep their order, except keys that are array indices
    ("0", "7", "10"; no sign, no leading zero, below 4294967295) come first,
    in numeric order. A gained "folders" key comes after the existing ones.
  - strings escape " \\ and control characters below U+0020 (\\b \\f \\n
    \\r \\t, others \\u00xx in lower-case hex); nothing else is escaped
  - numbers as JavaScript prints them: integral values below 1e21 as plain
    integers (2017.0 is 2017, -0 is 0, 1e16 is 10000000000000000); others in
    the shortest form that reads back the same, with an exponent written
    e+21 or e-7 for magnitudes from 1e21 up or below 1e-6
  - no newline at the end

library.bib: each paper not in the trash, as lightkone/bibtex-export writes
it (its fields in the order library.json lists them), joined by "\\n". A
paper is in the trash when its "trashed" value is true in JavaScript: any
value but a missing key, false, 0 and "" ([] and {} are in the trash,
and so is "0"). No papers left gives "".
"""
regenerability = "disposable"
license = "Proprietary (kausalflow)"
authors = ["kausalflow/lightkone"]

[entrypoint]
function = "run"

[requires]
network = []
credentials = []
state = []
permissions = []

[spec]
seed = 0
max_examples = 200
timeout_seconds = 300
```

## components/library-merge/versions/1/examples.jsonl

```json
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 0}, "note": "nothing changed anywhere"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z", "notes": "incompleteness"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z", "notes": "incompleteness"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 1}, "note": "a change made elsewhere is taken"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z", "notes": "mine"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z", "notes": "mine"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 0}, "note": "a change made here is kept"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Dropout", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2014, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Dropout", "authors": ["Hinton, Geoffrey"], "year": 2014, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 1}, "note": "different fields of one paper: both kept"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Ours", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Theirs", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z", "starred": true}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Ours", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z", "starred": true}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 1}, "note": "the same field changed both ways: ours wins, their other change is kept"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "math"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics", "to read"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "math", "to read"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 1}, "note": "tags merge as sets: added on either side is in"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["classics", "logic", "to read"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "to read"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 1}, "note": "a tag removed on one side stays removed"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics", "Math"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["History"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Math", "History"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 1}, "note": "folders merge as sets too"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1919, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1919, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 1}, "note": "a field removed here stays removed"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 0}, "note": "deleted here, unchanged there: gone"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z", "notes": "edited there"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z", "notes": "edited there"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 1}, "note": "deleted here but changed there: kept with their change"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 1}, "note": "deleted there, unchanged here: gone"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation", "starred": true}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation", "starred": true}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 0}, "note": "deleted there but changed here: kept"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 0}, "note": "deleted on both sides"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}, {"id": "vaswani17", "key": "Vaswani2017-an", "type": "inproceedings", "title": "Attention is all you need", "authors": ["Vaswani, Ashish"], "year": 2017, "tags": ["ml"], "fields": {}, "added": "2024-04-02T15:45:00.000Z"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}, {"id": "wilson74", "key": "Wilson1974-cq", "type": "article", "title": "Confinement of quarks", "authors": ["Wilson, Kenneth G."], "year": 1974, "tags": ["physics"], "fields": {}, "added": "2024-02-10T10:00:00.000Z"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}, {"id": "wilson74", "key": "Wilson1974-cq", "type": "article", "title": "Confinement of quarks", "authors": ["Wilson, Kenneth G."], "year": 1974, "tags": ["physics"], "fields": {}, "added": "2024-02-10T10:00:00.000Z"}, {"id": "vaswani17", "key": "Vaswani2017-an", "type": "inproceedings", "title": "Attention is all you need", "authors": ["Vaswani, Ashish"], "year": 2017, "tags": ["ml"], "fields": {}, "added": "2024-04-02T15:45:00.000Z"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 1}, "note": "new papers on both sides: theirs first, then ours"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 0}, "note": "order follows theirs"}
{"input": {"ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}, {"id": "vaswani17", "key": "Vaswani2017-an", "type": "inproceedings", "title": "Attention is all you need", "authors": ["Vaswani, Ashish"], "year": 2017, "tags": ["ml"], "fields": {}, "added": "2024-04-02T15:45:00.000Z"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z", "notes": "x"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}, {"id": "vaswani17", "key": "Vaswani2017-an", "type": "inproceedings", "title": "Attention is all you need", "authors": ["Vaswani, Ashish"], "year": 2017, "tags": ["ml"], "fields": {}, "added": "2024-04-02T15:45:00.000Z"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 0}, "note": "no base: ours wins for every paper both have"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}, {"folder": "", "repo": "kausalflow/thesis", "path": "all.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}]}, "fromThem": 0}, "note": "bibSync changed on both sides: ours wins, and an empty list is left out"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "Physics", "repo": "kausalflow/qft", "path": "q.bib", "branch": "main"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "Physics", "repo": "kausalflow/qft", "path": "q.bib", "branch": "main"}]}, "fromThem": 0}, "note": "bibSync changed only there: theirs"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {"pages": "1-18"}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {"volume": "1"}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {"pages": "1-18"}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 0}, "note": "fields is one value, not merged inside: ours wins"}
{"input": {"base": {"$fixture": "base.json"}, "ours": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "T", "authors": ["Hinton, Geoffrey"], "year": 2012, "tags": ["ml"], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "theirs": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "Improving neural networks by preventing co-adaptation", "authors": ["Hinton, Geoffrey"], "year": 1, "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}}, "output": {"file": {"format": "lightkone-library", "version": 1, "papers": [{"id": "hinton12", "key": "Hinton2012-in", "type": "article", "title": "T", "authors": ["Hinton, Geoffrey"], "year": 1, "tags": [], "folders": ["ML"], "fields": {}, "added": "2024-03-01T09:00:00.000Z"}, {"id": "godel31", "key": "Godel1931-fu", "type": "article", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931, "tags": ["logic", "classics"], "fields": {"volume": "38"}, "added": "2024-01-15T12:00:00.000Z"}, {"id": "noether18", "key": "Noether1918-iv", "type": "article", "title": "Invariante Variationsprobleme", "authors": ["Noether, Emmy"], "year": 1918, "tags": ["physics"], "folders": ["Physics"], "fields": {}, "added": "2024-01-16T12:00:00.000Z", "notes": "symmetry and conservation"}], "bibSync": [{"folder": "ML", "repo": "kausalflow/paper", "path": "refs.bib"}]}, "fromThem": 1}, "note": "tags missing on one side are an empty list"}
```

## components/library-merge/versions/1/fixtures/base.json

```json
{
 "format": "lightkone-library",
 "version": 1,
 "papers": [
  {
   "id": "hinton12",
   "key": "Hinton2012-in",
   "type": "article",
   "title": "Improving neural networks by preventing co-adaptation",
   "authors": [
    "Hinton, Geoffrey"
   ],
   "year": 2012,
   "tags": [
    "ml"
   ],
   "folders": [
    "ML"
   ],
   "fields": {},
   "added": "2024-03-01T09:00:00.000Z"
  },
  {
   "id": "godel31",
   "key": "Godel1931-fu",
   "type": "article",
   "title": "Über formal unentscheidbare Sätze",
   "authors": [
    "Gödel, Kurt"
   ],
   "year": 1931,
   "tags": [
    "logic",
    "classics"
   ],
   "fields": {
    "volume": "38"
   },
   "added": "2024-01-15T12:00:00.000Z"
  },
  {
   "id": "noether18",
   "key": "Noether1918-iv",
   "type": "article",
   "title": "Invariante Variationsprobleme",
   "authors": [
    "Noether, Emmy"
   ],
   "year": 1918,
   "tags": [
    "physics"
   ],
   "folders": [
    "Physics"
   ],
   "fields": {},
   "added": "2024-01-16T12:00:00.000Z",
   "notes": "symmetry and conservation"
  }
 ],
 "bibSync": [
  {
   "folder": "ML",
   "repo": "kausalflow/paper",
   "path": "refs.bib"
  }
 ]
}
```

## components/library-merge/versions/1/properties.py

```python
"""Behavioral properties for lightkone/library-merge.

Libraries are generated as a base plus independent edits on each side, the
way two devices diverge: fields changed or removed, tags and folders added or
taken away, papers added or deleted.
"""

import copy
import json

from hypothesis import given, strategies as st

from schema import Input, Library

IDS = ["a", "b", "c", "d", "e"]
TAGS = ["ml", "physics", "to read", "qft"]
FOLDERS = ["ML", "Physics", "Physics/QFT"]


def same(x, y) -> bool:
    return json.dumps(x, sort_keys=True) == json.dumps(y, sort_keys=True)


@st.composite
def paper(draw, pid):
    p = {"id": pid, "title": draw(st.sampled_from(["Attention", "Dropout", "Gauge fields", "Untitled"])),
         "tags": draw(st.lists(st.sampled_from(TAGS), unique=True, max_size=3))}
    if draw(st.booleans()):
        p["year"] = draw(st.integers(2000, 2024))
    if draw(st.booleans()):
        p["folders"] = draw(st.lists(st.sampled_from(FOLDERS), unique=True, max_size=2))
    if draw(st.booleans()):
        p["notes"] = draw(st.sampled_from(["read twice", "check eq. 3"]))
    return p


@st.composite
def library(draw):
    ids = draw(st.lists(st.sampled_from(IDS), unique=True, max_size=4))
    return {"papers": [draw(paper(i)) for i in ids]}


@st.composite
def edited(draw, lib, fields=("title", "year", "notes", "starred")):
    """A copy of lib after a few edits on one device."""
    out = copy.deepcopy(lib)
    for _ in range(draw(st.integers(0, 3))):
        op = draw(st.sampled_from(["field", "drop-field", "tag", "untag", "add", "remove"]))
        papers = out["papers"]
        if op == "add":
            free = [i for i in IDS if i not in {p["id"] for p in papers}]
            if free:
                papers.append(draw(paper(draw(st.sampled_from(free)))))
            continue
        if not papers:
            continue
        p = draw(st.sampled_from(papers))
        if op == "remove":
            papers.remove(p)
        elif op == "field":
            k = draw(st.sampled_from(fields))
            p[k] = {"title": "Edited title", "year": 1999, "notes": "new note", "starred": True}[k]
        elif op == "drop-field":
            p.pop(draw(st.sampled_from(["year", "notes", "starred"])), None)
        elif op == "tag":
            t = draw(st.sampled_from(TAGS))
            if t not in p["tags"]:
                p["tags"].append(t)
        elif op == "untag" and p["tags"]:
            p["tags"].remove(draw(st.sampled_from(p["tags"])))
    return out


def merge(impl, base, ours, theirs):
    out = impl(Input(base=None if base is None else Library(**base), ours=Library(**ours), theirs=Library(**theirs)))
    return out.file.papers, out.fromThem


def by_id(lib):
    return {p["id"]: p for p in lib["papers"]}


@given(lib=library())
def test_nothing_changed_merges_to_itself(impl, lib):
    assert merge(impl, lib, lib, lib) == (lib["papers"], 0)


@given(data=st.data(), base=library())
def test_changes_made_only_elsewhere_are_taken_whole(impl, data, base):
    theirs = data.draw(edited(base))
    papers, from_them = merge(impl, base, base, theirs)
    assert papers == theirs["papers"]
    ours, mine = by_id(base), by_id(theirs)
    assert from_them == sum(not same(mine.get(i), ours.get(i)) for i in dict.fromkeys([*mine, *ours]))


@given(data=st.data(), base=library())
def test_changes_made_only_here_are_kept(impl, data, base):
    ours = data.draw(edited(base))
    papers, from_them = merge(impl, base, ours, base)
    assert from_them == 0
    kept = by_id(ours)
    order = [i for i in by_id(base) if i in kept] + [i for i in kept if i not in by_id(base)]
    assert [p["id"] for p in papers] == order and all(same(p, kept[p["id"]]) for p in papers)


@given(base=library(), data=st.data())
def test_edits_to_different_fields_both_survive(impl, base, data):
    if not base["papers"]:
        return
    target = data.draw(st.sampled_from(base["papers"]))["id"]
    ours, theirs = copy.deepcopy(base), copy.deepcopy(base)
    by_id(ours)[target]["title"] = "Ours"
    by_id(theirs)[target]["notes"] = "Theirs"
    got = by_id({"papers": merge(impl, base, ours, theirs)[0]})[target]
    assert got["title"] == "Ours" and got["notes"] == "Theirs"


@given(base=library(), data=st.data())
def test_the_same_field_changed_both_ways_keeps_ours(impl, base, data):
    if not base["papers"]:
        return
    target = data.draw(st.sampled_from(base["papers"]))["id"]
    ours, theirs = copy.deepcopy(base), copy.deepcopy(base)
    by_id(ours)[target]["title"], by_id(theirs)[target]["title"] = "Ours", "Theirs"
    by_id(theirs)[target]["year"] = 1900  # a second change there, so neither side equals the base
    got = by_id({"papers": merge(impl, base, ours, theirs)[0]})[target]
    assert got["title"] == "Ours" and got["year"] == 1900


@given(base=library(), data=st.data(), add_o=st.sampled_from(TAGS), add_t=st.sampled_from(TAGS))
def test_tags_merge_as_sets(impl, base, data, add_o, add_t):
    if not base["papers"]:
        return
    target = data.draw(st.sampled_from(base["papers"]))["id"]
    ours, theirs = copy.deepcopy(base), copy.deepcopy(base)
    o, t, b = by_id(ours)[target], by_id(theirs)[target], by_id(base)[target]
    removed = data.draw(st.sampled_from(b["tags"])) if b["tags"] else None
    if removed:
        o["tags"].remove(removed)
    o["tags"] = list(dict.fromkeys(o["tags"] + [add_o]))
    t["tags"] = list(dict.fromkeys(t["tags"] + [add_t]))
    t["title"] = "Theirs too"
    got = by_id({"papers": merge(impl, base, ours, theirs)[0]})[target]["tags"]
    gone = {x for x in b["tags"] if x not in o["tags"] or x not in t["tags"]}
    assert got == [x for x in dict.fromkeys(o["tags"] + t["tags"]) if x not in gone]


@given(base=library(), data=st.data())
def test_a_paper_deleted_here_but_changed_there_survives(impl, base, data):
    if not base["papers"]:
        return
    target = data.draw(st.sampled_from(base["papers"]))["id"]
    ours, theirs = copy.deepcopy(base), copy.deepcopy(base)
    ours["papers"] = [p for p in ours["papers"] if p["id"] != target]
    by_id(theirs)[target]["notes"] = "edited elsewhere"
    assert target in by_id({"papers": merge(impl, base, ours, theirs)[0]})


@given(ours=library(), theirs=library())
def test_without_a_base_every_paper_is_kept_and_ours_wins(impl, ours, theirs):
    papers, _ = merge(impl, None, ours, theirs)
    expected = {**by_id(theirs), **by_id(ours)}
    assert by_id({"papers": papers}) == expected
```

## components/library-merge/versions/1/schema.py

```python
"""Interface for lightkone/library-merge."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Library(BaseModel):
    """A lightkone library.json. Papers are kept as plain JSON objects: merging must keep every field."""

    model_config = ConfigDict(extra="forbid")

    format: Literal["lightkone-library"] = "lightkone-library"
    version: Literal[1] = 1
    papers: list[dict[str, Any]] = Field(description="Each paper has a unique string id and any other fields.")
    bibSync: list[dict[str, Any]] | None = Field(None, description=".bib files kept in sync with GitHub.")

    @field_validator("papers")
    @classmethod
    def _ids(cls, papers):
        ids = [p.get("id") for p in papers]
        if not all(isinstance(i, str) and i for i in ids) or len(set(ids)) != len(ids):
            raise ValueError("every paper needs a unique, non-empty string id")
        if any(v is None for p in papers for v in p.values()):
            raise ValueError("leave a field out rather than setting it to null")
        return papers


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base: Library | None = Field(None, description="The version this device last read or wrote.")
    ours: Library
    theirs: Library


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: Library
    fromThem: int = Field(ge=0, description="How many papers took a change made elsewhere.")
```

## components/library-merge/versions/1/schema/input.json

```json
{
  "$defs": {
    "Library": {
      "additionalProperties": false,
      "description": "A lightkone library.json. Papers are kept as plain JSON objects: merging must keep every field.",
      "properties": {
        "bibSync": {
          "anyOf": [
            {
              "items": {
                "additionalProperties": true,
                "type": "object"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": ".bib files kept in sync with GitHub.",
          "title": "Bibsync"
        },
        "format": {
          "const": "lightkone-library",
          "default": "lightkone-library",
          "title": "Format",
          "type": "string"
        },
        "papers": {
          "description": "Each paper has a unique string id and any other fields.",
          "items": {
            "additionalProperties": true,
            "type": "object"
          },
          "title": "Papers",
          "type": "array"
        },
        "version": {
          "const": 1,
          "default": 1,
          "title": "Version",
          "type": "integer"
        }
      },
      "required": [
        "papers"
      ],
      "title": "Library",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "base": {
      "anyOf": [
        {
          "$ref": "#/$defs/Library"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The version this device last read or wrote."
    },
    "ours": {
      "$ref": "#/$defs/Library"
    },
    "theirs": {
      "$ref": "#/$defs/Library"
    }
  },
  "required": [
    "ours",
    "theirs"
  ],
  "title": "Input",
  "type": "object"
}
```

## components/library-merge/versions/1/schema/output.json

```json
{
  "$defs": {
    "Library": {
      "additionalProperties": false,
      "description": "A lightkone library.json. Papers are kept as plain JSON objects: merging must keep every field.",
      "properties": {
        "bibSync": {
          "anyOf": [
            {
              "items": {
                "additionalProperties": true,
                "type": "object"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": ".bib files kept in sync with GitHub.",
          "title": "Bibsync"
        },
        "format": {
          "const": "lightkone-library",
          "default": "lightkone-library",
          "title": "Format",
          "type": "string"
        },
        "papers": {
          "description": "Each paper has a unique string id and any other fields.",
          "items": {
            "additionalProperties": true,
            "type": "object"
          },
          "title": "Papers",
          "type": "array"
        },
        "version": {
          "const": 1,
          "default": 1,
          "title": "Version",
          "type": "integer"
        }
      },
      "required": [
        "papers"
      ],
      "title": "Library",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "file": {
      "$ref": "#/$defs/Library"
    },
    "fromThem": {
      "description": "How many papers took a change made elsewhere.",
      "minimum": 0,
      "title": "Fromthem",
      "type": "integer"
    }
  },
  "required": [
    "file",
    "fromThem"
  ],
  "title": "Output",
  "type": "object"
}
```

## components/library-merge/versions/1/symbolon.toml

```toml
[contract]
id = "lightkone/library-merge"
version = 1
title = "Merge two edited copies of a lightkone library"
description = """
Before lightkone writes library.json it reads it again. If another device, or
Claude through MCP, saved in the meantime, the two versions are merged
against the version both started from, paper by paper and field by field,
instead of the later save silently winning. Only when both sides changed the
same field differently does this device's edit win.

Inputs: base (what this device last read or wrote; null if none), ours (what
this device holds now), theirs (what is in storage now).

Equality is by value: two papers are the same when they have the same
fields with equal values, in any key order.

Per paper id, with b, o, t its version in base, ours and theirs:
  no b:            o if present, else t
  b, no o:         t if t is present and differs from b, else dropped
  b, no t:         dropped if o equals b, else o
  o equals b:      t
  t equals b:      o
  otherwise        a field-by-field merge of b, o and t:
    tags, folders  (when o or t has the list) kept as sets: every item in o,
                   then every item in t not already listed, minus any item of
                   b that o or t removed
    other fields   t's value if o's equals b's, else o's; a field absent from
                   the chosen side is absent
Order: theirs' ids in theirs' order, then ids only in ours, in ours' order.
Ids only in base are gone.

fromThem counts the ids in that order whose result (a paper, or nothing)
differs from ours' version (a paper, or nothing).

bibSync: theirs' list if ours' equals base's (a missing list counts as
empty), else ours'. It is written only when non-empty.

The result is a library file: format "lightkone-library", version 1.
"""
regenerability = "disposable"
license = "Proprietary (kausalflow)"
authors = ["kausalflow/lightkone"]

[entrypoint]
function = "run"

[requires]
network = []
credentials = []
state = []
permissions = []

[spec]
seed = 0
max_examples = 200
timeout_seconds = 300
```

## components/pdf-filing/versions/1/examples.jsonl

```json
{"input": {"paper": {"id": "new", "title": "Improving neural networks by preventing co-adaptation of feature detectors", "authors": ["Hinton, Geoffrey E", "Srivastava, Nitish", "Krizhevsky, Alex"], "year": 2012}}, "output": {"pdf": "papers/All Papers/HINTON/Hinton et al. 2012 - Improving neural networks by preventing co-adaptation of feature detectors.pdf", "file": "All Papers/HINTON/Hinton et al. 2012 - Improving neural networks by preventing co-adaptation of feature detectors.pdf"}, "note": "three or more authors: et al."}
{"input": {"paper": {"id": "new", "title": "Attention is all you need", "authors": ["Vaswani, Ashish", "Shazeer, Noam"], "year": 2017}}, "output": {"pdf": "papers/All Papers/VASWANI/Vaswani and Shazeer 2017 - Attention is all you need.pdf", "file": "All Papers/VASWANI/Vaswani and Shazeer 2017 - Attention is all you need.pdf"}, "note": "two authors: A and B"}
{"input": {"paper": {"id": "new", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "year": 1931}}, "output": {"pdf": "papers/All Papers/GÖDEL/Gödel 1931 - Über formal unentscheidbare Sätze.pdf", "file": "All Papers/GÖDEL/Gödel 1931 - Über formal unentscheidbare Sätze.pdf"}, "note": "one author; the folder keeps accents in capitals"}
{"input": {"paper": {"id": "new", "title": "Deep learning: a review", "authors": ["LeCun, Yann"], "year": 2015}}, "output": {"pdf": "papers/All Papers/LECUN/LeCun 2015 - Deep learning - a review.pdf", "file": "All Papers/LECUN/LeCun 2015 - Deep learning - a review.pdf"}, "note": "a colon becomes ' - '"}
{"input": {"paper": {"id": "new", "title": "What is a p-value? And/or <why> \"it\" matters*|", "authors": ["Smith, J"], "year": 2001}}, "output": {"pdf": "papers/All Papers/SMITH/Smith 2001 - What is a p-value - And - or - why - - it - matters.pdf", "file": "All Papers/SMITH/Smith 2001 - What is a p-value - And - or - why - - it - matters.pdf"}, "note": "every forbidden character becomes ' - ', and runs collapse"}
{"input": {"paper": {"id": "new", "title": "Pages 1--10 and 1---2", "authors": ["Doe, Jane"], "year": 2020}}, "output": {"pdf": "papers/All Papers/DOE/Doe 2020 - Pages 1–10 and 1—2.pdf", "file": "All Papers/DOE/Doe 2020 - Pages 1–10 and 1—2.pdf"}, "note": "-- and --- become en and em dashes"}
{"input": {"paper": {"id": "new", "title": "An untitled-author preprint", "authors": [], "year": 2021}}, "output": {"pdf": "papers/All Papers/Other/An untitled-author preprint 2021 - An untitled-author preprint.pdf", "file": "All Papers/Other/An untitled-author preprint 2021 - An untitled-author preprint.pdf"}, "note": "no authors: the title stands in for them, folder Other"}
{"input": {"paper": {"id": "new", "title": "", "authors": ["Plato"]}}, "output": {"pdf": "papers/All Papers/PLATO/Plato - Untitled.pdf", "file": "All Papers/PLATO/Plato - Untitled.pdf"}, "note": "empty title becomes Untitled; no year"}
{"input": {"paper": {"id": "new", "title": "Straßen und Wege", "authors": ["Straße, Hans"], "year": 1990}}, "output": {"pdf": "papers/All Papers/STRASSE/Straße 1990 - Straßen und Wege.pdf", "file": "All Papers/STRASSE/Straße 1990 - Straßen und Wege.pdf"}, "note": "ß upper-cases to SS in the folder"}
{"input": {"paper": {"id": "new", "title": "Corporate work", "authors": ["LIGO Scientific Collaboration", "Virgo Collaboration"], "year": 2016}}, "output": {"pdf": "papers/All Papers/LIGO SCIENTIFIC COLLABORATION/LIGO Scientific Collaboration and Vir... 2016 - Corporate work.pdf", "file": "All Papers/LIGO SCIENTIFIC COLLABORATION/LIGO Scientific Collaboration and Vir... 2016 - Corporate work.pdf"}, "note": "names without commas are whole surnames"}
{"input": {"paper": {"id": "new", "title": "A paper by a very long collaboration name indeed", "authors": ["The International Consortium of Very Long Names"], "year": 2019}}, "output": {"pdf": "papers/All Papers/THE INTERNATIONAL CONSORTIUM OF VERY LONG NAMES/The International Consortium of Very ... 2019 - A paper by a very long collaboration name indeed.pdf", "file": "All Papers/THE INTERNATIONAL CONSORTIUM OF VERY LONG NAMES/The International Consortium of Very ... 2019 - A paper by a very long collaboration name indeed.pdf"}, "note": "who longer than 40 is cut to 37 plus ..."}
{"input": {"paper": {"id": "new", "title": "On the electrodynamics of moving bodies, being a very long title that goes on and on well past the limit of what Paperpile allows in a file name", "authors": ["Einstein, Albert"], "year": 1905}}, "output": {"pdf": "papers/All Papers/EINSTEIN/Einstein 1905 - On the electrodynamics of moving bodies, being a very lo ... on and on well past the limit of what Paperpile allows in a file name.pdf", "file": "All Papers/EINSTEIN/Einstein 1905 - On the electrodynamics of moving bodies, being a very lo ... on and on well past the limit of what Paperpile allows in a file name.pdf"}, "note": "a name longer than 146 keeps its start and end around ' ... '"}
{"input": {"paper": {"id": "new", "title": "Duplicate", "authors": ["Doe, Jane"], "year": 2020}, "library": [{"id": "a", "pdf": "papers/All Papers/DOE/Doe 2020 - Duplicate.pdf"}]}, "output": {"pdf": "papers/All Papers/DOE/Doe 2020 - Duplicate (2).pdf", "file": "All Papers/DOE/Doe 2020 - Duplicate (2).pdf"}, "note": "a taken name gets (2)"}
{"input": {"paper": {"id": "new", "title": "Duplicate", "authors": ["Doe, Jane"], "year": 2020}, "library": [{"id": "a", "pdf": "papers/All Papers/DOE/Doe 2020 - Duplicate.pdf"}, {"id": "b", "file": "elsewhere.pdf;All Papers/DOE/Doe 2020 - Duplicate (2).pdf"}]}, "output": {"pdf": "papers/All Papers/DOE/Doe 2020 - Duplicate (3).pdf", "file": "All Papers/DOE/Doe 2020 - Duplicate (3).pdf"}, "note": "file fields with ; list several paths, each taken"}
{"input": {"paper": {"id": "new", "title": "Duplicate", "authors": ["Doe, Jane"], "year": 2020}, "library": [{"id": "new", "pdf": "papers/All Papers/DOE/Doe 2020 - Duplicate.pdf"}]}, "output": {"pdf": "papers/All Papers/DOE/Doe 2020 - Duplicate.pdf", "file": "All Papers/DOE/Doe 2020 - Duplicate.pdf"}, "note": "the paper's own PDF does not count as taken"}
{"input": {"paper": {"id": "new", "title": "Spaces", "authors": ["  Spaced ,  Out  ", ""], "year": 2000}}, "output": {"pdf": "papers/All Papers/SPACED/Spaced 2000 - Spaces.pdf", "file": "All Papers/SPACED/Spaced 2000 - Spaces.pdf"}, "note": "surnames are trimmed; empty authors are skipped in the name"}
{"input": {"paper": {"id": "new", "title": "Empty first", "authors": ["", "Second, B"], "year": 2000}}, "output": {"pdf": "papers/All Papers/Other/Second 2000 - Empty first.pdf", "file": "All Papers/Other/Second 2000 - Empty first.pdf"}, "note": "an empty first author means folder Other, but the name uses the rest"}
{"input": {"paper": {"id": "new", "title": "-Leading and trailing-", "authors": ["-Dash-, A"], "year": 2000}}, "output": {"pdf": "papers/All Papers/DASH/Dash- 2000 - Leading and trailing.pdf", "file": "All Papers/DASH/Dash- 2000 - Leading and trailing.pdf"}, "note": "leading and trailing hyphens are removed by clean"}
{"input": {"paper": {"id": "new", "title": "Trailing slash/", "authors": ["Back\\slash, A"], "year": 2000}}, "output": {"pdf": "papers/All Papers/BACK - SLASH/Back - slash 2000 - Trailing slash.pdf", "file": "All Papers/BACK - SLASH/Back - slash 2000 - Trailing slash.pdf"}, "note": "backslash and slash at the edges"}
```

## components/pdf-filing/versions/1/properties.py

```python
"""Behavioral properties for lightkone/pdf-filing."""

import re

from hypothesis import given, strategies as st

from schema import Filed, Input, Paper

NAMES = ["Hinton, Geoffrey", "Gödel, Kurt", "Straße, Hans", "de la Fontaine, Jean", "LIGO Collaboration", "Smith, J",
         "", " , x", "A/B, Corp", "Wolfram-Smith, Ann"]
WORDS = ["Improving", "neural", "networks:", "a", "study", "of", "x--y", "1---2", "what?", "<html>", "C*", "\"quoted\"",
         "path/to", "Über", "-", "  ", "pipes|"]


@st.composite
def papers(draw, long=False):
    n = draw(st.integers(1, 40 if long else 8))
    return Paper(
        id="new",
        title=" ".join(draw(st.lists(st.sampled_from(WORDS), max_size=n))),
        authors=draw(st.lists(st.sampled_from(NAMES), max_size=5)),
        year=draw(st.none() | st.integers(1900, 2030)),
    )


def file_of(impl, p, library=()):
    return impl(Input(paper=p, library=list(library)))


@given(p=papers(long=True))
def test_pdf_is_the_file_under_papers(impl, p):
    out = file_of(impl, p)
    assert out.pdf == "papers/" + out.file
    assert out.file.startswith("All Papers/") and out.file.endswith(".pdf")
    assert out.file.count("/") == 2


@given(p=papers(long=True))
def test_names_hold_no_forbidden_characters(impl, p):
    name = file_of(impl, p).file.split("/", 2)[2]
    assert not re.search(r'[:\\?*"<>|]', name)
    assert "  " not in name and not name.startswith((" ", "-"))


@given(p=papers())
def test_folder_is_the_first_surname_in_capitals(impl, p):
    folder = file_of(impl, p).file.split("/")[1]
    first = p.authors[0].split(",")[0].strip() if p.authors else ""
    if not first:
        assert folder == "Other"
    else:
        assert folder == folder.upper() and folder != ""


@given(p=papers(long=True))
def test_long_names_are_shortened_around_an_ellipsis(impl, p):
    name = file_of(impl, p).file.split("/", 2)[2][: -len(".pdf")]
    assert len(name.encode("utf-16-le")) // 2 <= 146 + 5


@given(p=papers(), n=st.integers(1, 4), self_listed=st.booleans())
def test_taken_names_count_up_and_own_pdf_is_ignored(impl, p, n, self_listed):
    plain = file_of(impl, p).file
    stem = plain[: -len(".pdf")]
    taken = [Filed(id="a", pdf="papers/" + plain)] + [Filed(id=f"b{i}", file=f"x.pdf; {stem} ({i}).pdf") for i in range(2, n + 1)]
    if self_listed:
        taken.append(Filed(id="new", pdf=f"papers/{stem} ({n + 1}).pdf"))
    assert file_of(impl, p, taken).file == f"{stem} ({n + 1}).pdf"


@given(p=papers())
def test_same_paper_same_place(impl, p):
    assert file_of(impl, p) == file_of(impl, p.model_copy(update={"id": "other"}))
```

## components/pdf-filing/versions/1/schema.py

```python
"""Interface for lightkone/pdf-filing."""

from pydantic import BaseModel, ConfigDict, Field


class Paper(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str
    authors: list[str] = Field(default_factory=list, description="'Last, First' strings or whole names, in order.")
    year: int | None = Field(None, ge=1)


class Filed(BaseModel):
    """A paper already in the library, as far as filing cares."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    pdf: str | None = Field(None, description="Storage key of its PDF, e.g. 'papers/All Papers/A/a.pdf'.")
    file: str | None = Field(None, description="Paperpile file field: paths under papers/, separated by ';'.")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper: Paper
    library: list[Filed] = Field(default_factory=list, description="The library; may include the paper itself.")


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pdf: str = Field(description="Storage key for the PDF: 'papers/' + file.")
    file: str = Field(description="The matching Paperpile file field.")
```

## components/pdf-filing/versions/1/schema/input.json

```json
{
  "$defs": {
    "Filed": {
      "additionalProperties": false,
      "description": "A paper already in the library, as far as filing cares.",
      "properties": {
        "file": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Paperpile file field: paths under papers/, separated by ';'.",
          "title": "File"
        },
        "id": {
          "minLength": 1,
          "title": "Id",
          "type": "string"
        },
        "pdf": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Storage key of its PDF, e.g. 'papers/All Papers/A/a.pdf'.",
          "title": "Pdf"
        }
      },
      "required": [
        "id"
      ],
      "title": "Filed",
      "type": "object"
    },
    "Paper": {
      "additionalProperties": false,
      "properties": {
        "authors": {
          "description": "'Last, First' strings or whole names, in order.",
          "items": {
            "type": "string"
          },
          "title": "Authors",
          "type": "array"
        },
        "id": {
          "minLength": 1,
          "title": "Id",
          "type": "string"
        },
        "title": {
          "title": "Title",
          "type": "string"
        },
        "year": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Year"
        }
      },
      "required": [
        "id",
        "title"
      ],
      "title": "Paper",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "library": {
      "description": "The library; may include the paper itself.",
      "items": {
        "$ref": "#/$defs/Filed"
      },
      "title": "Library",
      "type": "array"
    },
    "paper": {
      "$ref": "#/$defs/Paper"
    }
  },
  "required": [
    "paper"
  ],
  "title": "Input",
  "type": "object"
}
```

## components/pdf-filing/versions/1/schema/output.json

```json
{
  "additionalProperties": false,
  "properties": {
    "file": {
      "description": "The matching Paperpile file field.",
      "title": "File",
      "type": "string"
    },
    "pdf": {
      "description": "Storage key for the PDF: 'papers/' + file.",
      "title": "Pdf",
      "type": "string"
    }
  },
  "required": [
    "pdf",
    "file"
  ],
  "title": "Output",
  "type": "object"
}
```

## components/pdf-filing/versions/1/symbolon.toml

```toml
[contract]
id = "lightkone/pdf-filing"
version = 1
title = "Name and place a paper's PDF the way Paperpile does"
description = """
Decides where a new PDF for a paper is stored. Lightkone files PDFs exactly
as Paperpile files them in Google Drive, so a Paperpile "All Papers" folder
can be copied into a library unchanged:

  pdf  = "papers/" + file
  file = "All Papers/<FOLDER>/<NAME>.pdf"      e.g.
         All Papers/HINTON/Hinton et al. 2012 - Improving neural networks.pdf

clean(s), in order: "---" -> "—" (em dash), "--" -> "–" (en dash); each of
: / \\ ? * " < > | -> " - "; whitespace runs -> one space; runs of " - "
-> one " - "; then remove leading and trailing spaces and hyphens.

surname(a): the part of a before the first comma (all of a if none), trimmed.

FOLDER: clean(surname(first author)) upper-cased; "Other" when there is no
first author or that is empty.

NAME:
  title = clean(title), or "Untitled" if that is empty.
  who   = from the authors' surnames, ignoring empty ones:
          none -> title; one -> "A"; two -> "A and B"; more -> "A et al.".
          If who is longer than 40, keep its first 37 and add "...".
  head  = clean(who + " " + year), or clean(who) when there is no year.
  NAME  = head + " - " + title. If NAME is longer than 146, it becomes its
          first 72 with trailing whitespace removed, then " ... ", then its
          last 69 with leading whitespace removed.
Lengths count UTF-16 code units; v1 defines behaviour only for text without
characters outside the Basic Multilingual Plane (no emoji).

Upper-casing follows Unicode full case mapping (ß -> SS).

Taken names: every OTHER paper in the library (other id) takes its pdf, and
"papers/" + each part of its file split on ";" (trimmed). If papers/<file> is
taken, try NAME + " (2).pdf", " (3).pdf", ... until one is free.
"""
regenerability = "disposable"
license = "Proprietary (kausalflow)"
authors = ["kausalflow/lightkone"]

[entrypoint]
function = "run"

[requires]
network = []
credentials = []
state = []
permissions = []

[spec]
seed = 0
max_examples = 200
timeout_seconds = 300
```

## components/search-query/versions/1/examples.jsonl

```json
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": ""}, "output": {"ids": ["vaswani17", "nodate", "hinton12", "wilson74", "godel31", "noether18", "cafe", "emptytrash"]}, "note": "empty query: every paper outside the trash, newest added first; equal times keep input order"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "   "}, "output": {"ids": ["vaswani17", "nodate", "hinton12", "wilson74", "godel31", "noether18", "cafe", "emptytrash"]}, "note": "whitespace only is the empty query"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "attention"}, "output": {"ids": ["vaswani17", "nodate"]}, "note": "words rank by relevance under the default sort: title 5, author 4, rest 1"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "attention"}, "output": {"ids": ["vaswani17", "nodate"]}, "note": "sort=added with words means relevance"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "year", "query": "attention"}, "output": {"ids": ["vaswani17", "nodate"]}, "note": "an explicit sort keeps its order; missing year sorts as 0"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "networks"}, "output": {"ids": ["hinton12", "vaswani17", "cafe"]}, "note": "title hits outrank hits in abstract or notes"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "neural networks"}, "output": {"ids": ["hinton12", "vaswani17"]}, "note": "every word must match; scores add up"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "\"neural networks\""}, "output": {"ids": ["hinton12", "vaswani17"]}, "note": "a quoted phrase is one word"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "\"networks by\""}, "output": {"ids": ["hinton12"]}, "note": "a phrase matches across words within a field"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "\"hinton, geoffrey ; srivastava\""}, "output": {"ids": ["hinton12"]}, "note": "authors are joined with ' ; '"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "\"dropout hinton2012\""}, "output": {"ids": ["hinton12"]}, "note": "the rest text joins non-empty fields with single spaces: tags, then key"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "cafe"}, "output": {"ids": ["cafe"]}, "note": "accents fold away"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "CAFÉ"}, "output": {"ids": ["cafe"]}, "note": "case and accents fold away in the query too"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "naive"}, "output": {"ids": ["cafe"]}, "note": "naïveté in the title and naive in notes"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "godel"}, "output": {"ids": ["godel31"]}, "note": "author text is folded: Gödel"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "uber"}, "output": {"ids": ["godel31"]}, "note": "Über in a title"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "hinton"}, "output": {"ids": ["hinton12"]}, "note": "author hit"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "hinton2012"}, "output": {"ids": ["hinton12"]}, "note": "the citation key is in the rest text"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "10.1103"}, "output": {"ids": ["wilson74"]}, "note": "doi is in the rest text"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "1706.03762"}, "output": {"ids": ["vaswani17"]}, "note": "arxiv id is in the rest text"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "re:search"}, "output": {"ids": ["godel31"]}, "note": "an unknown field is an ordinary word, colon included"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "foo:bar"}, "output": {"ids": []}, "note": "unknown field that matches nothing"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "\"attention"}, "output": {"ids": []}, "note": "an unmatched quote is part of the word"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "zzz"}, "output": {"ids": []}, "note": "no match"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "tag:ml"}, "output": {"ids": ["vaswani17", "hinton12"]}, "note": "tag filter; the trashed paper with the tag is hidden"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "tag:ML"}, "output": {"ids": ["vaswani17", "hinton12"]}, "note": "tag values fold"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "TAG:ml"}, "output": {"ids": ["vaswani17", "hinton12"]}, "note": "field names are case-insensitive"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "tag:\"to read\""}, "output": {"ids": ["vaswani17"]}, "note": "quoted tag with a space, folded"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "tag:to"}, "output": {"ids": []}, "note": "a tag must match whole, not as a substring"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "tag:cafe"}, "output": {"ids": ["cafe"]}, "note": "tag value with accent folding"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "tag:ml tag:cnn"}, "output": {"ids": []}, "note": "all tags must match"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "tag:\"\""}, "output": {"ids": []}, "note": "an empty tag value matches no paper here"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "author:hinton"}, "output": {"ids": ["hinton12"]}, "note": "author substring"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "author:\"n, g\""}, "output": {"ids": ["hinton12"]}, "note": "author value is a substring of the joined, folded author text"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "author:zoe"}, "output": {"ids": ["cafe"]}, "note": "folded author"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "author:noam author:niki"}, "output": {"ids": ["vaswani17"]}, "note": "every author filter must match"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "year:2017"}, "output": {"ids": ["vaswani17"]}, "note": "exact year"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "year:1900-1975"}, "output": {"ids": ["wilson74", "godel31", "noether18"]}, "note": "inclusive range"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "year:2020-2010"}, "output": {"ids": []}, "note": "a reversed range matches nothing"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "year:1974 year:2017"}, "output": {"ids": ["vaswani17"]}, "note": "only the last year filter counts"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "year:2017 year:1900-2020"}, "output": {"ids": ["vaswani17", "hinton12", "wilson74", "godel31", "noether18", "emptytrash"]}, "note": "only the last year filter counts, whichever form it has"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "year:1900-1950 year:1974"}, "output": {"ids": ["wilson74"]}, "note": "a later exact year replaces an earlier range"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "in:Physics"}, "output": {"ids": ["wilson74", "noether18"]}, "note": "a folder includes its subfolders"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "in:physics/qft/"}, "output": {"ids": ["wilson74"]}, "note": "folder names fold and trailing slashes are ignored"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "in:Phys"}, "output": {"ids": []}, "note": "a folder is not matched by prefix of its name"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "in:\"cafe/ebauches\""}, "output": {"ids": ["cafe"]}, "note": "folders fold accents"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "in:ML in:ML/Regularization"}, "output": {"ids": ["hinton12"]}, "note": "all folder filters must hold"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "has:pdf"}, "output": {"ids": ["vaswani17", "godel31", "noether18"]}, "note": "a PDF in storage or a file from another manager"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "no:pdf"}, "output": {"ids": ["nodate", "hinton12", "wilson74", "noether18", "cafe", "emptytrash"]}, "note": "no:pdf ignores the other manager's file"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "has:abstract"}, "output": {"ids": ["vaswani17", "noether18"]}, "note": "an empty abstract is absent"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "no:abstract"}, "output": {"ids": ["nodate", "hinton12", "wilson74", "godel31", "cafe", "emptytrash"]}, "note": "opposite of has:abstract"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "has:arxiv no:pdf"}, "output": {"ids": ["hinton12"]}, "note": "filters combine"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "has:notes"}, "output": {"ids": ["godel31", "cafe"]}, "note": "notes present"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "no:notes"}, "output": {"ids": ["vaswani17", "nodate", "hinton12", "wilson74", "noether18", "emptytrash"]}, "note": "empty notes count as absent"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "has:PDF"}, "output": {"ids": ["vaswani17", "godel31", "noether18"]}, "note": "has: values are lower-cased"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "has:wings"}, "output": {"ids": ["vaswani17", "nodate", "hinton12", "wilson74", "godel31", "noether18", "cafe", "emptytrash"]}, "note": "unknown has: value is ignored"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "is:starred"}, "output": {"ids": ["hinton12"]}, "note": "starred papers outside the trash"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "is:recent"}, "output": {"ids": ["hinton12", "vaswani17", "wilson74"]}, "note": "opened papers, latest opened first, then newest added"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "is:recent attention"}, "output": {"ids": ["vaswani17"]}, "note": "is:recent orders by opened even with words"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "year", "query": "is:recent"}, "output": {"ids": ["vaswani17", "hinton12", "wilson74"]}, "note": "an explicit sort overrides"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "is:trash"}, "output": {"ids": ["lecun98", "binned"]}, "note": "only trashed papers; an empty trashed field is not trashed"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "is:trash attention"}, "output": {"ids": ["binned"]}, "note": "words within the trash"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "is:trash is:starred"}, "output": {"ids": ["binned"]}, "note": "is: filters combine"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "is:sleepy"}, "output": {"ids": ["vaswani17", "nodate", "hinton12", "wilson74", "godel31", "noether18", "cafe", "emptytrash"]}, "note": "unknown is: value is ignored"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "year", "query": ""}, "output": {"ids": ["cafe", "emptytrash", "vaswani17", "hinton12", "wilson74", "godel31", "noether18", "nodate"]}, "note": "year sort, missing years last"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "opened", "query": ""}, "output": {"ids": ["hinton12", "vaswani17", "wilson74", "nodate", "godel31", "noether18", "cafe", "emptytrash"]}, "note": "opened sort; never-opened papers last by newest added"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "relevance", "query": ""}, "output": {"ids": ["vaswani17", "nodate", "hinton12", "wilson74", "godel31", "noether18", "cafe", "emptytrash"]}, "note": "relevance with no words: newest added first"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "physics classics"}, "output": {"ids": ["noether18"]}, "note": "words can match tags"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "relevance", "query": "ml attention"}, "output": {"ids": ["vaswani17"]}, "note": "words can match in different fields"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "physics"}, "output": {"ids": ["wilson74", "noether18"]}, "note": "equal scores fall back to newest added, not input order"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "tag:physics confinement"}, "output": {"ids": ["wilson74"]}, "note": "filter plus word"}
{"input": {"papers": {"$fixture": "titles.json"}, "sort": "title", "query": ""}, "output": {"ids": ["t25", "t26", "t11", "t13", "t12", "t9", "t10", "t24", "t23", "t2", "t1", "t4", "t3", "t5", "t8", "t6", "t7", "t0", "t19", "t18", "t21", "t15", "t14", "t17", "t16", "t20", "t22"]}, "note": "title sort follows Unicode collation: letters, then accents, then case, lower case first; punctuation before digits before letters"}
{"input": {"papers": {"$fixture": "titles.json"}, "sort": "title", "query": "apple"}, "output": {"ids": ["t2", "t1", "t4", "t3", "t5", "t8", "t6", "t7"]}, "note": "title sort with a word filter"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "year:2017 year:abc"}, "output": {"ids": ["vaswani17"]}, "note": "a year: term that is not a number does not count; the earlier one stays"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "year:abc"}, "output": {"ids": ["vaswani17", "nodate", "hinton12", "wilson74", "godel31", "noether18", "cafe", "emptytrash"]}, "note": "a year: term that is not a number filters nothing"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "year:2017-"}, "output": {"ids": ["vaswani17"]}, "note": "year:2017- means 2017"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "year:-2017"}, "output": {"ids": ["vaswani17", "nodate", "hinton12", "wilson74", "godel31", "noether18", "cafe", "emptytrash"]}, "note": "year:-2017 does not count"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "year:0"}, "output": {"ids": ["vaswani17", "nodate", "hinton12", "wilson74", "godel31", "noether18", "cafe", "emptytrash"]}, "note": "year:0 does not count"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "year:1990-2020-1900"}, "output": {"ids": ["vaswani17", "hinton12", "emptytrash"]}, "note": "parts after the second are ignored"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "year:2020-1990"}, "output": {"ids": []}, "note": "a reversed range matches nothing"}
{"input": {"papers": {"$fixture": "library.json"}, "sort": "added", "query": "year:1990-x"}, "output": {"ids": []}, "note": "a second part that is not a number means the first year only"}
```

## components/search-query/versions/1/fixtures/library.json

```json
[
 {
  "id": "hinton12",
  "key": "Hinton2012-ab",
  "title": "Improving neural networks by preventing co-adaptation",
  "authors": [
   "Hinton, Geoffrey",
   "Srivastava, Nitish"
  ],
  "year": 2012,
  "venue": "arXiv",
  "arxiv": "1207.0580",
  "tags": [
   "ml",
   "Dropout"
  ],
  "added": "2024-03-01T09:00:00.000Z",
  "folders": [
   "ML/Regularization"
  ],
  "starred": true,
  "opened": "2024-06-01T08:00:00.000Z"
 },
 {
  "id": "godel31",
  "key": "Godel1931",
  "title": "Über formal unentscheidbare Sätze",
  "authors": [
   "Gödel, Kurt"
  ],
  "year": 1931,
  "venue": "Monatshefte für Mathematik",
  "tags": [
   "logic",
   "Classics"
  ],
  "added": "2024-01-15T12:00:00.000Z",
  "folders": [
   "Math",
   "Math/Logic"
  ],
  "notes": "incompleteness; see re:search notes",
  "pdf": "pdfs/godel31.pdf"
 },
 {
  "id": "noether18",
  "key": "Noether1918",
  "title": "Invariante Variationsprobleme",
  "authors": [
   "Noether, Emmy"
  ],
  "year": 1918,
  "abstract": "Symmetries imply conservation laws.",
  "tags": [
   "physics",
   "Classics"
  ],
  "added": "2024-01-15T12:00:00.000Z",
  "folders": [
   "Physics"
  ],
  "file": "All Papers/N/Noether 1918.pdf"
 },
 {
  "id": "wilson74",
  "key": "Wilson1974",
  "title": "Confinement of quarks",
  "authors": [
   "Wilson, Kenneth G."
  ],
  "year": 1974,
  "venue": "Physical Review D",
  "doi": "10.1103/PhysRevD.10.2445",
  "tags": [
   "physics",
   "qft",
   "lattice"
  ],
  "added": "2024-02-10T10:00:00.000Z",
  "folders": [
   "Physics/QFT",
   "Physics/QFT/Lattice"
  ],
  "opened": "2024-05-20T07:30:00.000Z"
 },
 {
  "id": "vaswani17",
  "key": "Vaswani2017-xy",
  "title": "Attention is all you need",
  "authors": [
   "Vaswani, Ashish",
   "Shazeer, Noam",
   "Parmar, Niki"
  ],
  "year": 2017,
  "venue": "NeurIPS",
  "arxiv": "1706.03762",
  "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.",
  "tags": [
   "ml",
   "To Read"
  ],
  "added": "2024-04-02T15:45:00.000Z",
  "folders": [
   "ML"
  ],
  "pdf": "pdfs/vaswani17.pdf",
  "opened": "2024-05-20T07:30:00.000Z"
 },
 {
  "id": "lecun98",
  "key": "LeCun1998",
  "title": "Gradient-based learning applied to document recognition",
  "authors": [
   "LeCun, Yann",
   "Bottou, Léon",
   "Bengio, Yoshua",
   "Haffner, Patrick"
  ],
  "year": 1998,
  "venue": "Proceedings of the IEEE",
  "doi": "10.1109/5.726791",
  "tags": [
   "ml",
   "cnn"
  ],
  "added": "2024-03-01T09:00:00.000Z",
  "folders": [
   "ML"
  ],
  "trashed": "2024-06-02T00:00:00.000Z"
 },
 {
  "id": "cafe",
  "key": "Dupont2021",
  "title": "Le café et la naïveté des réseaux",
  "authors": [
   "Dupont, Zoé"
  ],
  "year": 2021,
  "tags": [
   "Café"
  ],
  "added": "2023-12-31T23:59:59.999Z",
  "folders": [
   "Café/Ébauches"
  ],
  "notes": "naive networks"
 },
 {
  "id": "nodate",
  "key": "",
  "title": "Untitled preprint on attention",
  "authors": [],
  "tags": [],
  "added": "2024-04-02T15:45:00.000Z",
  "abstract": "",
  "notes": "",
  "starred": false
 },
 {
  "id": "emptytrash",
  "key": "Smith2020",
  "title": "A paper whose trashed field is empty",
  "authors": [
   "Smith, Jane"
  ],
  "year": 2020,
  "tags": [],
  "added": "2022-07-07T07:07:07.000Z",
  "trashed": "",
  "opened": ""
 },
 {
  "id": "binned",
  "key": "Old2010",
  "title": "Attention in the trash",
  "authors": [
   "Old, Author"
  ],
  "year": 2010,
  "tags": [
   "ml"
  ],
  "added": "2021-01-01T00:00:00.000Z",
  "trashed": "2024-06-03T00:00:00.000Z",
  "starred": true
 }
]
```

## components/search-query/versions/1/fixtures/titles.json

```json
[
 {
  "id": "t0",
  "title": "banana",
  "added": "2024-01-01T00:00:00.000Z",
  "year": 2000
 },
 {
  "id": "t1",
  "title": "Apple",
  "added": "2024-01-02T00:00:00.000Z",
  "year": 2001
 },
 {
  "id": "t2",
  "title": "apple",
  "added": "2024-01-03T00:00:00.000Z",
  "year": 2002
 },
 {
  "id": "t3",
  "title": "Äpple",
  "added": "2024-01-04T00:00:00.000Z",
  "year": 2003
 },
 {
  "id": "t4",
  "title": "äpple",
  "added": "2024-01-05T00:00:00.000Z",
  "year": 2004
 },
 {
  "id": "t5",
  "title": "apple pie",
  "added": "2024-01-06T00:00:00.000Z",
  "year": 2000
 },
 {
  "id": "t6",
  "title": "apple-pie",
  "added": "2024-01-07T00:00:00.000Z",
  "year": 2001
 },
 {
  "id": "t7",
  "title": "applepie",
  "added": "2024-01-08T00:00:00.000Z",
  "year": 2002
 },
 {
  "id": "t8",
  "title": "Apple Pie",
  "added": "2024-01-09T00:00:00.000Z",
  "year": 2003
 },
 {
  "id": "t9",
  "title": "10 things",
  "added": "2024-01-10T00:00:00.000Z",
  "year": 2004
 },
 {
  "id": "t10",
  "title": "2 things",
  "added": "2024-01-11T00:00:00.000Z",
  "year": 2000
 },
 {
  "id": "t11",
  "title": "_private",
  "added": "2024-01-12T00:00:00.000Z",
  "year": 2001
 },
 {
  "id": "t12",
  "title": "(Draft) notes",
  "added": "2024-01-13T00:00:00.000Z",
  "year": 2002
 },
 {
  "id": "t13",
  "title": "\"Quoted\" title",
  "added": "2024-01-14T00:00:00.000Z",
  "year": 2003
 },
 {
  "id": "t14",
  "title": "Über alles",
  "added": "2024-01-15T00:00:00.000Z",
  "year": 2004
 },
 {
  "id": "t15",
  "title": "uber",
  "added": "2024-01-16T00:00:00.000Z",
  "year": 2000
 },
 {
  "id": "t16",
  "title": "Zebra",
  "added": "2024-01-17T00:00:00.000Z",
  "year": 2001
 },
 {
  "id": "t17",
  "title": "zebra",
  "added": "2024-01-18T00:00:00.000Z",
  "year": 2002
 },
 {
  "id": "t18",
  "title": "ćevapi",
  "added": "2024-01-19T00:00:00.000Z",
  "year": 2003
 },
 {
  "id": "t19",
  "title": "cevapi",
  "added": "2024-01-20T00:00:00.000Z",
  "year": 2004
 },
 {
  "id": "t20",
  "title": "Ωmega",
  "added": "2024-01-21T00:00:00.000Z",
  "year": 2000
 },
 {
  "id": "t21",
  "title": "omega",
  "added": "2024-01-22T00:00:00.000Z",
  "year": 2001
 },
 {
  "id": "t22",
  "title": "李",
  "added": "2024-01-23T00:00:00.000Z",
  "year": 2002
 },
 {
  "id": "t23",
  "title": "A",
  "added": "2024-01-24T00:00:00.000Z",
  "year": 2003
 },
 {
  "id": "t24",
  "title": "a",
  "added": "2024-01-25T00:00:00.000Z",
  "year": 2004
 },
 {
  "id": "t25",
  "title": "",
  "added": "2024-01-26T00:00:00.000Z",
  "year": 2000
 },
 {
  "id": "t26",
  "title": "   spaced",
  "added": "2024-01-27T00:00:00.000Z",
  "year": 2001
 }
]
```

## components/search-query/versions/1/properties.py

```python
"""Behavioral properties for lightkone/search-query.

Each property states one rule from the description in symbolon.toml, checked
on small generated libraries whose vocabulary overlaps on purpose: shared
words, accents, mixed case, nested folders, ties in dates.
"""

import unicodedata

from hypothesis import given, strategies as st

from schema import Input, Paper

# Helpers that restate the description. They are the spec, not an implementation hint.


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not 0x300 <= ord(c) <= 0x36F).lower()


def title_text(p: Paper) -> str:
    return fold(p.title)


def author_text(p: Paper) -> str:
    return fold(" ; ".join(p.authors))


def rest_text(p: Paper) -> str:
    parts = [p.abstract, p.venue, " ".join(p.tags), p.key, p.doi, p.arxiv, p.notes]
    return fold(" ".join(x for x in parts if x))


def word_score(p: Paper, word: str) -> int:
    w = fold(word)
    return 5 * (w in title_text(p)) + 4 * (w in author_text(p)) + (w in rest_text(p))


def render(word: str) -> str:
    return f'"{word}"' if " " in word else word


def run(impl, papers, query, sort="added") -> list[str]:
    return impl(Input(papers=papers, query=query, sort=sort)).ids


def newest_first(papers, key=lambda p: p.added):
    """Descending by key; Python's sort is stable, so equal papers keep their input order."""
    return sorted(papers, key=key, reverse=True)


# Generated libraries

TITLE_WORDS = ["alpha", "beta", "Gamma", "café", "Über", "naïve", "networks", "qft", "lattice", "ML"]
AUTHORS = ["Hinton, Geoffrey", "Gödel, Kurt", "Noether, Emmy", "Alpha, Ann", "Müller, Jörg"]
TAGS = ["ml", "ML", "physics", "Café", "to read", "qft"]
FOLDERS = ["Physics", "Physics/QFT", "physics/qft/Lattice", "Math", "Mathematics", "Café/Ébauche"]
TEXTS = ["", "about alpha and beta", "Lattice QFT on networks", "see re:search", "naive café notes", "Gödel"]
TIMES = [f"2024-0{m}-0{d}T10:00:00.000Z" for m in (1, 2, 3) for d in (1, 2)]


def opt(s):
    return st.none() | s


@st.composite
def papers_st(draw, min_size=0, max_size=8, titles=None):
    n = draw(st.integers(min_size, max_size))
    out = []
    for i in range(n):
        title = draw(titles) if titles is not None else " ".join(draw(st.lists(st.sampled_from(TITLE_WORDS), max_size=4)))
        out.append(Paper(
            id=f"p{i}",
            title=title,
            added=draw(st.sampled_from(TIMES)),
            key=draw(st.sampled_from(["", f"Key{i}", "Alpha2020-ab"])),
            authors=draw(st.lists(st.sampled_from(AUTHORS), max_size=3, unique=True)),
            year=draw(opt(st.integers(2015, 2022))),
            venue=draw(opt(st.sampled_from(TEXTS))),
            abstract=draw(opt(st.sampled_from(TEXTS))),
            doi=draw(opt(st.sampled_from(["", "10.1000/alpha", "10.2/xyz"]))),
            arxiv=draw(opt(st.sampled_from(["", "2101.00001"]))),
            tags=draw(st.lists(st.sampled_from(TAGS), max_size=3, unique=True)),
            file=draw(opt(st.sampled_from(["", "All Papers/A/a.pdf"]))),
            pdf=draw(opt(st.sampled_from(["", "pdfs/p.pdf"]))),
            notes=draw(opt(st.sampled_from(TEXTS))),
            folders=draw(opt(st.lists(st.sampled_from(FOLDERS), max_size=2, unique=True))),
            starred=draw(opt(st.booleans())),
            trashed=draw(opt(st.sampled_from(["", "2024-05-01T00:00:00.000Z"]))),
            opened=draw(opt(st.sampled_from(["", *TIMES]))),
        ))
    return out


WORDS = ["alpha", "ALPHA", "alp", "beta", "cafe", "CAFÉ", "uber", "naive", "naïve", "godel", "gödel", "hinton",
         "qft", "lattice", "ml", "net", "alpha beta", "n, g", "re:search", "10.1000", "2101", "key1", "zzz"]
FILTERS = ["tag:ml", "tag:Physics", 'tag:"to read"', "tag:cafe", "author:hinton", "author:godel", "author:\"l, a\"",
           "year:2018", "year:2016-2019", "year:2020-2017", "in:physics", "in:Physics/QFT/", "in:Math", 'in:"cafe/ebauche"',
           "has:pdf", "has:abstract", "has:arxiv", "has:notes", "has:nothing", "no:pdf", "no:abstract", "no:arxiv",
           "no:notes", "is:starred", "is:recent", "is:unknown"]
terms = st.sampled_from(FILTERS) | st.sampled_from(WORDS).map(render)
SORTS = ["added", "year", "title", "relevance", "opened"]


def is_trashed(p: Paper) -> bool:
    return bool(p.trashed)


def satisfies(p: Paper, f: str) -> bool:
    field, _, value = f.partition(":")
    value = value.strip('"')
    if field == "tag":
        return any(fold(t) == fold(value) for t in p.tags)
    if field == "author":
        return fold(value) in author_text(p)
    if field == "year":
        a, _, b = value.partition("-")
        lo, hi = int(a), int(b or a)
        return bool(p.year) and lo <= p.year <= hi
    if field == "in":
        target = fold(value).rstrip("/")
        return any(fold(x) == target or fold(x).startswith(target + "/") for x in p.folders or [])
    if field == "has":
        return {"pdf": bool(p.pdf or p.file), "abstract": bool(p.abstract), "arxiv": bool(p.arxiv),
                "notes": bool(p.notes)}.get(value, True)
    if field == "no":
        return {"pdf": not p.pdf, "abstract": not p.abstract, "arxiv": not p.arxiv,
                "notes": not p.notes}.get(value, True)
    if field == "is":
        return {"starred": bool(p.starred), "recent": bool(p.opened)}.get(value, True)
    raise AssertionError(f)


# Properties


@given(papers=papers_st(), query=st.lists(terms, max_size=3).map(" ".join), sort=st.sampled_from(SORTS))
def test_results_are_distinct_papers_from_the_library(impl, papers, query, sort):
    ids = run(impl, papers, query, sort)
    assert len(ids) == len(set(ids))
    assert set(ids) <= {p.id for p in papers}


@given(papers=papers_st(), query=st.lists(terms, max_size=2).map(" ".join), trash=st.booleans())
def test_trash_shows_only_with_is_trash(impl, papers, query, trash):
    by_id = {p.id: p for p in papers}
    ids = run(impl, papers, ("is:trash " if trash else "") + query)
    assert all(is_trashed(by_id[i]) == trash for i in ids)


@given(papers=papers_st(), a=terms, b=terms, trash=st.booleans())
def test_terms_are_conjunctive(impl, papers, a, b, trash):
    if a.startswith("year:") and b.startswith("year:"):
        return  # only the last year: term counts, see test_only_the_last_year_filter_counts
    prefix = "is:trash " if trash else ""
    both = set(run(impl, papers, f"{prefix}{a} {b}"))
    assert both == set(run(impl, papers, prefix + a)) & set(run(impl, papers, prefix + b))


@given(papers=papers_st(min_size=1), query=st.sampled_from(["", " ", "  \t "]))
def test_empty_query_lists_the_library_newest_first(impl, papers, query):
    expected = [p.id for p in newest_first([p for p in papers if not is_trashed(p)])]
    assert run(impl, papers, query) == expected


@given(papers=papers_st(min_size=1), f=st.sampled_from(FILTERS), trash=st.booleans())
def test_each_filter_selects_what_it_says(impl, papers, f, trash):
    got = set(run(impl, papers, ("is:trash " if trash else "") + f))
    assert got == {p.id for p in papers if is_trashed(p) == trash and satisfies(p, f)}


@given(papers=papers_st(min_size=1), words=st.lists(st.sampled_from(WORDS), min_size=1, max_size=2),
       sort=st.sampled_from(["added", "relevance"]))
def test_words_rank_title_over_author_over_rest(impl, papers, words, sort):
    scored = []
    for p in papers:
        scores = [word_score(p, w) for w in words]
        if not is_trashed(p) and all(scores):
            scored.append((p, sum(scores)))
    by_added = newest_first([p for p, _ in scored])
    rank = {p.id: i for i, p in enumerate(by_added)}
    total = {p.id: s for p, s in scored}
    expected = sorted(rank, key=lambda i: (-total[i], rank[i]))
    assert run(impl, papers, " ".join(render(w) for w in words), sort) == expected


@given(papers=papers_st(), query=st.lists(terms, min_size=1, max_size=3).map(" ".join), sort=st.sampled_from(SORTS))
def test_case_and_accents_in_the_query_do_not_matter(impl, papers, query, sort):
    assert run(impl, papers, query.upper(), sort) == run(impl, papers, query, sort)


@given(papers=papers_st(min_size=1), f=st.sampled_from([""] + FILTERS))
def test_year_sort_puts_later_years_first(impl, papers, f):
    ids = run(impl, papers, f, "year")
    keep = set(ids)
    expected = [p.id for p in newest_first([p for p in papers if p.id in keep], key=lambda p: p.year or 0)]
    assert ids == expected


ASCII_TITLES = st.lists(st.sampled_from(["alpha", "beta", "b", "a1", "zeta 2", "a beta", ""]), max_size=3).map(" ".join)


@given(papers=papers_st(min_size=1, titles=ASCII_TITLES), f=st.sampled_from([""] + FILTERS))
def test_title_sort_is_ascending_and_stable(impl, papers, f):
    ids = run(impl, papers, f, "title")
    keep = set(ids)
    assert ids == [p.id for p in sorted((p for p in papers if p.id in keep), key=lambda p: p.title)]


@given(papers=papers_st(min_size=1), how=st.sampled_from([("", "opened"), ("is:recent", "added"), ("is:recent", "opened")]))
def test_opened_order_and_is_recent(impl, papers, how):
    query, sort = how
    ids = run(impl, papers, query, sort)
    keep = set(ids)
    by_added = newest_first([p for p in papers if p.id in keep])
    assert ids == [p.id for p in newest_first(by_added, key=lambda p: p.opened or "")]


YEARS = [f for f in FILTERS if f.startswith("year:")]


@given(papers=papers_st(min_size=1), first=st.sampled_from(YEARS), last=st.sampled_from(YEARS), word=st.sampled_from(["", "alpha"]))
def test_only_the_last_year_filter_counts(impl, papers, first, last, word):
    assert run(impl, papers, f"{first} {word} {last}") == run(impl, papers, f"{word} {last}")
```

## components/search-query/versions/1/schema.py

```python
"""Interface for lightkone/search-query."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TIMESTAMP = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z$"


class Paper(BaseModel):
    """The fields of a lightkone paper that search reads."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str
    added: str = Field(pattern=TIMESTAMP, description="When it was added, as JavaScript's toISOString writes it.")
    key: str = Field("", description="BibTeX citation key.")
    authors: list[str] = Field(default_factory=list, description="'Last, First' strings, in order.")
    year: int | None = Field(None, ge=1)
    venue: str | None = None
    abstract: str | None = None
    doi: str | None = None
    arxiv: str | None = None
    tags: list[str] = Field(default_factory=list)
    file: str | None = Field(None, description="A PDF path from another reference manager.")
    pdf: str | None = Field(None, description="Storage key of a PDF in the library's own storage.")
    notes: str | None = None
    folders: list[str] | None = Field(None, description="Folder paths like 'Physics/QFT'.")
    starred: bool | None = None
    trashed: str | None = Field(None, description="When it was moved to the trash.")
    opened: str | None = Field(None, pattern=f"^$|{TIMESTAMP}", description="When it was last opened; empty means never.")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    papers: list[Paper] = Field(description="The library, in stored order. Ids are unique.")
    query: str = Field(description="What was typed in the search box.")
    sort: Literal["added", "year", "title", "relevance", "opened"] = "added"

    @model_validator(mode="after")
    def _unique_ids(self) -> "Input":
        if len({p.id for p in self.papers}) != len(self.papers):
            raise ValueError("paper ids must be unique")
        return self


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[str] = Field(description="Ids of the matching papers, in display order.")
```

## components/search-query/versions/1/schema/input.json

```json
{
  "$defs": {
    "Paper": {
      "additionalProperties": false,
      "description": "The fields of a lightkone paper that search reads.",
      "properties": {
        "abstract": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Abstract"
        },
        "added": {
          "description": "When it was added, as JavaScript's toISOString writes it.",
          "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\\.[0-9]{3}Z$",
          "title": "Added",
          "type": "string"
        },
        "arxiv": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Arxiv"
        },
        "authors": {
          "description": "'Last, First' strings, in order.",
          "items": {
            "type": "string"
          },
          "title": "Authors",
          "type": "array"
        },
        "doi": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Doi"
        },
        "file": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "A PDF path from another reference manager.",
          "title": "File"
        },
        "folders": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Folder paths like 'Physics/QFT'.",
          "title": "Folders"
        },
        "id": {
          "minLength": 1,
          "title": "Id",
          "type": "string"
        },
        "key": {
          "default": "",
          "description": "BibTeX citation key.",
          "title": "Key",
          "type": "string"
        },
        "notes": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Notes"
        },
        "opened": {
          "anyOf": [
            {
              "pattern": "^$|^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\\.[0-9]{3}Z$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "When it was last opened; empty means never.",
          "title": "Opened"
        },
        "pdf": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Storage key of a PDF in the library's own storage.",
          "title": "Pdf"
        },
        "starred": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Starred"
        },
        "tags": {
          "items": {
            "type": "string"
          },
          "title": "Tags",
          "type": "array"
        },
        "title": {
          "title": "Title",
          "type": "string"
        },
        "trashed": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "When it was moved to the trash.",
          "title": "Trashed"
        },
        "venue": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Venue"
        },
        "year": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Year"
        }
      },
      "required": [
        "id",
        "title",
        "added"
      ],
      "title": "Paper",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "papers": {
      "description": "The library, in stored order. Ids are unique.",
      "items": {
        "$ref": "#/$defs/Paper"
      },
      "title": "Papers",
      "type": "array"
    },
    "query": {
      "description": "What was typed in the search box.",
      "title": "Query",
      "type": "string"
    },
    "sort": {
      "default": "added",
      "enum": [
        "added",
        "year",
        "title",
        "relevance",
        "opened"
      ],
      "title": "Sort",
      "type": "string"
    }
  },
  "required": [
    "papers",
    "query"
  ],
  "title": "Input",
  "type": "object"
}
```

## components/search-query/versions/1/schema/output.json

```json
{
  "additionalProperties": false,
  "properties": {
    "ids": {
      "description": "Ids of the matching papers, in display order.",
      "items": {
        "type": "string"
      },
      "title": "Ids",
      "type": "array"
    }
  },
  "required": [
    "ids"
  ],
  "title": "Output",
  "type": "object"
}
```

## components/search-query/versions/1/symbolon.toml

```toml
[contract]
id = "lightkone/search-query"
version = 1
title = "Search a paper library with lightkone's query language"
description = """
Filters and orders a list of papers by a query string, as lightkone's search
box does. Returns the ids of the matching papers, in display order.

Query terms are separated by whitespace. A term is one of:

  field:value or field:"quoted value"   a filter (field names are ASCII
                                         letters, digits and _, any case)
  "quoted phrase"                        one word that may contain spaces
  anything else                          one word

Filters (all must hold, except year:, where only the last year: term that
counts applies):
  tag:T       some tag of the paper equals T after folding
  author:A    A is a substring of the folded authors joined with " ; "
  year:Y      year equals Y; year:A-B: A <= year <= B (missing year never matches).
              The value is split at "-": A is the first part, B the second,
              later parts are ignored. When A is not a number, or is 0, the
              term does not count (an earlier year: term stays in force).
              When B is missing, empty, 0 or not a number, B is A. So
              year:2017- means 2017 and year:-2017 does not count. A number
              here is ASCII digits with an optional fraction; other
              spellings are unspecified.
  in:F        the paper is in folder F or a folder inside it ("F/..."),
              compared after folding; trailing slashes on F are ignored
  has:X / no:X  for X in pdf, abstract, arxiv, notes. has:pdf accepts either
              pdf or file; no:pdf looks at pdf only. Unknown X is ignored.
  is:starred, is:recent (has been opened), is:trash. Unknown values are ignored.
Any other field:value term is an ordinary word, including the colon.

Trashed papers appear only with is:trash, and then only trashed papers appear.

Words: every word must be a substring of the paper's folded title (5 points),
folded author text (4 points) or folded rest (1 point): abstract, venue,
tags joined by spaces, key, doi, arxiv and notes, the non-empty ones joined
by single spaces. A paper's score is the sum over words; a paper where any
word scores 0 is left out.

Folding: Unicode NFKD, remove U+0300..U+036F, then lower case. Values of
has:, no: and is: are only lower-cased. Empty strings, false, and missing
fields are all "absent".

Order. sort=added: newest added first, except that a query with is:recent
orders by opened, and otherwise a query with words orders by relevance.
relevance: higher score first, then newest added. year: higher year first,
missing as 0. title: ascending by the Unicode Collation Algorithm
with the CLDR root collation at its default (tertiary) strength, which is
what JavaScript's a.localeCompare(b) does with no locale or options: letters
first, then accents, then case, lower case first ("apple" < "Apple" <
"Äpple" < "banana"); punctuation and spaces are not ignored and sort before
digits, digits before letters. opened: latest opened first, never-opened
last, then newest added. Papers that compare equal keep their input order.

Full-text search is out of scope.
"""
regenerability = "disposable"
license = "Proprietary (kausalflow)"
authors = ["kausalflow/lightkone"]

[entrypoint]
function = "run"

[requires]
network = []
credentials = []
state = []
permissions = []

[spec]
seed = 0
max_examples = 150
timeout_seconds = 300
```

## components/tidy/versions/1/examples.jsonl

```json
{"input": {"papers": [{"id": "a", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "doi": "10.1000/X"}, {"id": "b", "title": "Different title", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "doi": "https://doi.org/10.1000/x"}]}, "output": {"groups": [{"ids": ["a", "b"], "keep": "a", "patch": {"tags": [], "folders": [], "fields": {}, "added": "2024-01-01T00:00:00.000Z"}}]}, "note": "same DOI, written differently"}
{"input": {"papers": [{"id": "a", "title": "One", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "arxiv": "1207.0580"}, {"id": "b", "title": "Two", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "arxiv": "arXiv:1207.0580v3"}]}, "output": {"groups": [{"ids": ["a", "b"], "keep": "a", "patch": {"tags": [], "folders": [], "fields": {}, "added": "2024-01-01T00:00:00.000Z"}}]}, "note": "same arXiv id with prefix and version"}
{"input": {"papers": [{"id": "a", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": []}, {"id": "b", "title": "Improving Neural Networks, by Preventing Co-Adaptation!", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": []}]}, "output": {"groups": [{"ids": ["a", "b"], "keep": "a", "patch": {"tags": [], "folders": [], "fields": {}, "added": "2024-01-01T00:00:00.000Z"}}]}, "note": "long titles match after dropping case and punctuation"}
{"input": {"papers": [{"id": "a", "title": "Deep learning", "authors": ["LeCun, Yann"], "added": "2024-01-01T00:00:00.000Z", "tags": []}, {"id": "b", "title": "Deep Learning", "authors": ["LeCun, Y."], "added": "2024-01-01T00:00:00.000Z", "tags": []}, {"id": "c", "title": "Deep learning", "authors": ["Goodfellow, Ian"], "added": "2024-01-01T00:00:00.000Z", "tags": []}]}, "output": {"groups": [{"ids": ["a", "b"], "keep": "a", "patch": {"tags": [], "folders": [], "fields": {}, "added": "2024-01-01T00:00:00.000Z"}}]}, "note": "short titles also need the same first author"}
{"input": {"papers": [{"id": "a", "title": "Nets", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": []}, {"id": "b", "title": "Nets", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": []}]}, "output": {"groups": [{"ids": ["a", "b"], "keep": "a", "patch": {"tags": [], "folders": [], "fields": {}, "added": "2024-01-01T00:00:00.000Z"}}]}, "note": "a four-letter title is short: it matches with the same first author, here none on both"}
{"input": {"papers": [{"id": "a", "title": "The", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": []}, {"id": "b", "title": "The", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": []}]}, "output": {"groups": []}, "note": "titles of 3 or fewer letters never match"}
{"input": {"papers": [{"id": "a", "title": "Über formal unentscheidbare Sätze", "authors": ["Gödel, Kurt"], "added": "2024-01-01T00:00:00.000Z", "tags": []}, {"id": "b", "title": "Uber formal unentscheidbare Satze", "authors": ["Godel, K"], "added": "2024-01-01T00:00:00.000Z", "tags": []}]}, "output": {"groups": [{"ids": ["a", "b"], "keep": "a", "patch": {"tags": [], "folders": [], "fields": {}, "added": "2024-01-01T00:00:00.000Z"}}]}, "note": "accents are decomposed before comparing"}
{"input": {"papers": [{"id": "a", "title": "First", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "doi": "10.1/a"}, {"id": "b", "title": "Second", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "doi": "10.1/a", "arxiv": "1706.03762"}, {"id": "c", "title": "Third", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "arxiv": "1706.03762v2"}]}, "output": {"groups": [{"ids": ["a", "b", "c"], "keep": "a", "patch": {"tags": [], "folders": [], "fields": {}, "added": "2024-01-01T00:00:00.000Z", "arxiv": "1706.03762"}}]}, "note": "duplicates of duplicates form one group"}
{"input": {"papers": [{"id": "a", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": []}, {"id": "b", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "trashed": "2024-06-01T00:00:00.000Z"}, {"id": "c", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "trashed": ""}]}, "output": {"groups": [{"ids": ["a", "c"], "keep": "a", "patch": {"tags": [], "folders": [], "fields": {}, "added": "2024-01-01T00:00:00.000Z"}}]}, "note": "trashed papers are ignored; an empty trashed is not trashed"}
{"input": {"papers": [{"id": "a", "title": "Alpha", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "doi": "  "}, {"id": "b", "title": "Beta", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "doi": " "}]}, "output": {"groups": []}, "note": "DOIs that are only whitespace give no key, so these two do not match"}
{"input": {"papers": [{"id": "a", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-02-01T00:00:00.000Z", "tags": []}, {"id": "b", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": []}, {"id": "c", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-03-01T00:00:00.000Z", "tags": [], "notes": "mine"}]}, "output": {"groups": [{"ids": ["a", "b", "c"], "keep": "c", "patch": {"tags": [], "folders": [], "notes": "mine", "fields": {}, "added": "2024-01-01T00:00:00.000Z"}}]}, "note": "keeper: notes beat age"}
{"input": {"papers": [{"id": "a", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "notes": "n"}, {"id": "b", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-05-01T00:00:00.000Z", "tags": [], "pdf": "papers/b.pdf"}]}, "output": {"groups": [{"ids": ["a", "b"], "keep": "b", "patch": {"tags": [], "folders": [], "notes": "n", "fields": {}, "added": "2024-01-01T00:00:00.000Z"}}]}, "note": "keeper: a PDF beats notes"}
{"input": {"papers": [{"id": "a", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-02-01T00:00:00.000Z", "tags": []}, {"id": "b", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": []}]}, "output": {"groups": [{"ids": ["a", "b"], "keep": "b", "patch": {"tags": [], "folders": [], "fields": {}, "added": "2024-01-01T00:00:00.000Z"}}]}, "note": "keeper: the oldest"}
{"input": {"papers": [{"id": "a", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": []}, {"id": "b", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": []}]}, "output": {"groups": [{"ids": ["a", "b"], "keep": "a", "patch": {"tags": [], "folders": [], "fields": {}, "added": "2024-01-01T00:00:00.000Z"}}]}, "note": "keeper: library order breaks ties"}
{"input": {"papers": [{"id": "a", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": ["ml"], "folders": ["ML"], "notes": " read twice ", "fields": {"pages": "1", "volume": "2"}}, {"id": "b", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": ["dropout", "ml"], "folders": ["Archive"], "notes": "read twice", "starred": true, "venue": "arXiv", "year": 2012, "fields": {"pages": "9", "note": "x"}, "abstract": "We...", "url": "https://arxiv.org/abs/1207.0580", "opened": "2024-05-01T00:00:00.000Z"}]}, "output": {"groups": [{"ids": ["a", "b"], "keep": "a", "patch": {"tags": ["ml", "dropout"], "folders": ["ML", "Archive"], "notes": "read twice", "starred": true, "fields": {"pages": "1", "note": "x", "volume": "2"}, "added": "2024-01-01T00:00:00.000Z", "abstract": "We...", "url": "https://arxiv.org/abs/1207.0580", "venue": "arXiv", "year": 2012, "opened": "2024-05-01T00:00:00.000Z"}}]}, "note": "the keeper gains tags, folders, star, missing fields; equal notes once"}
{"input": {"papers": [{"id": "a", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "notes": "first"}, {"id": "b", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "notes": "second", "venue": "V1", "fields": {"k": "b"}}, {"id": "c", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "notes": "third", "venue": "V2", "fields": {"k": "c", "z": "c"}}]}, "output": {"groups": [{"ids": ["a", "b", "c"], "keep": "a", "patch": {"tags": [], "folders": [], "notes": "first\n\nsecond\n\nthird", "fields": {"k": "b", "z": "c"}, "added": "2024-01-01T00:00:00.000Z", "venue": "V1"}}]}, "note": "notes join with a blank line; the first other with a value wins"}
{"input": {"papers": [{"id": "a", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "venue": "", "year": null}, {"id": "b", "title": "Improving neural networks by preventing co-adaptation", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "venue": "Kept venue", "year": 2012}]}, "output": {"groups": [{"ids": ["a", "b"], "keep": "a", "patch": {"tags": [], "folders": [], "fields": {}, "added": "2024-01-01T00:00:00.000Z", "venue": "Kept venue", "year": 2012}}]}, "note": "an empty value on the keeper is filled"}
{"input": {"papers": [{"id": "a", "title": "Attention is all you need", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "doi": "10.1/a"}, {"id": "b", "title": "Something else", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "doi": "10.1/b"}, {"id": "c", "title": "Attention Is All You Need", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "doi": "10.1/c"}, {"id": "d", "title": "Something Else Entirely here", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "arxiv": "1"}, {"id": "e", "title": "Something else entirely here!", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": []}]}, "output": {"groups": [{"ids": ["a", "c"], "keep": "a", "patch": {"tags": [], "folders": [], "fields": {}, "added": "2024-01-01T00:00:00.000Z"}}, {"ids": ["d", "e"], "keep": "d", "patch": {"tags": [], "folders": [], "fields": {}, "added": "2024-01-01T00:00:00.000Z"}}]}, "note": "two groups, in the order of their first paper"}
{"input": {"papers": [{"id": "a", "title": "Unique", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": []}, {"id": "b", "title": "Other one", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": []}]}, "output": {"groups": []}, "note": "no duplicates"}
{"input": {"papers": []}, "output": {"groups": []}, "note": "an empty library"}
{"input": {"papers": [{"id": "a", "title": "Same", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "doi": "doi.org/10.1/a"}, {"id": "b", "title": "Different", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "doi": "10.1/a"}]}, "output": {"groups": []}, "note": "a doi.org/ prefix without http is not removed"}
{"input": {"papers": [{"id": "a", "title": "Alpha paper", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "doi": "https://doi.org/", "arxiv": " "}, {"id": "b", "title": "Beta paper", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "doi": "http://dx.doi.org/", "arxiv": "\t"}, {"id": "c", "title": "Gamma paper", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "arxiv": "arXiv:"}, {"id": "d", "title": "Delta paper", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "arxiv": "arxiv:"}]}, "output": {"groups": []}, "note": "a doi that is only the doi.org prefix, or an arXiv id that is only spaces or the arXiv: prefix, gives no key"}
{"input": {"papers": [{"id": "a", "title": "Alpha paper", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "doi": " 10.1000/X "}, {"id": "b", "title": "Beta paper", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "doi": "https://doi.org/10.1000/x"}, {"id": "c", "title": "Gamma paper", "authors": [], "added": "2024-01-01T00:00:00.000Z", "tags": [], "doi": " "}]}, "output": {"groups": [{"ids": ["a", "b"], "keep": "a", "patch": {"tags": [], "folders": [], "fields": {}, "added": "2024-01-01T00:00:00.000Z"}}]}, "note": "a real DOI still matches after trimming and removing the prefix; the blank one stays out"}
```

## components/tidy/versions/1/properties.py

```python
"""Behavioral properties for lightkone/tidy.

Generated libraries reuse a small pool of DOIs, arXiv ids, titles and authors
written in different ways, so duplicates appear by every route: same DOI,
same arXiv id, same long title, same short title and first author, and
chains of these.
"""

import re
import unicodedata

from hypothesis import given, strategies as st

from schema import Input, Paper

DOIS = ["10.1000/ABC", "https://doi.org/10.1000/abc", " 10.1000/abc ", "10.2000/xyz", "http://dx.doi.org/10.2000/XYZ", "doi.org/10.2000/xyz", " ", "  ", "https://doi.org/"]
ARXIV = ["1207.0580", "arXiv:1207.0580v2", "1706.03762", "ARXIV:1706.03762V1", "1706.03762v3", " ", "\t"]
TITLES = ["Improving neural networks by preventing co-adaptation", "Improving Neural Networks by Preventing Co-Adaptation!",
          "Attention is all you need", "Attention Is All You Need", "Über Sätze", "Uber Satze", "Deep learning", "Nets", "A"]
AUTHORS = ["Hinton, Geoffrey", "Vaswani, Ashish", "Gödel, Kurt", "Godel, K.", "LeCun, Yann"]
TIMES = [f"2024-0{m}-0{d}T10:00:00.000Z" for m in (1, 2) for d in (1, 2, 3)]


def opt(s):
    return st.none() | s


@st.composite
def library(draw, max_size=7):
    n = draw(st.integers(0, max_size))
    return [Paper(
        id=f"p{i}",
        title=draw(st.sampled_from(TITLES)),
        authors=draw(st.lists(st.sampled_from(AUTHORS), max_size=2)),
        added=draw(st.sampled_from(TIMES)),
        tags=draw(st.lists(st.sampled_from(["ml", "to read", "classics"]), unique=True, max_size=2)),
        folders=draw(opt(st.lists(st.sampled_from(["ML", "Physics"]), unique=True, max_size=2))),
        doi=draw(opt(st.sampled_from(DOIS))),
        arxiv=draw(opt(st.sampled_from(ARXIV))),
        pdf=draw(opt(st.sampled_from(["", "papers/a.pdf", "papers/b.pdf"]))),
        notes=draw(opt(st.sampled_from(["", " read ", "read", "check eq. 3"]))),
        starred=draw(opt(st.booleans())),
        venue=draw(opt(st.sampled_from(["", "NeurIPS"]))),
        year=draw(opt(st.integers(2010, 2020))),
        trashed=draw(opt(st.sampled_from(["", "2024-06-01T00:00:00.000Z"]))),
        fields=draw(st.dictionaries(st.sampled_from(["pages", "volume"]), st.sampled_from(["1", "2"]), max_size=2)),
    ) for i in range(n)]


def norm_doi(d):
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d.strip().lower())
    return d


def norm_arxiv(a):
    a = re.sub(r"v\d+$", "", re.sub(r"^arxiv:", "", a.strip().lower()))
    return a


def keys(p: Paper) -> list[str]:
    out = []
    if p.doi and norm_doi(p.doi):
        out.append("doi:" + norm_doi(p.doi))
    if p.arxiv and norm_arxiv(p.arxiv):
        out.append("arxiv:" + norm_arxiv(p.arxiv))
    t = re.sub(r"[^a-z0-9]+", "", unicodedata.normalize("NFKD", p.title).lower())
    if len(t) > 20:
        out.append("title:" + t)
    elif len(t) > 3:
        first = (p.authors[0] if p.authors else "").split(",")[0]
        out.append(f"title:{t}:" + re.sub(r"[^a-z]", "", unicodedata.normalize("NFKD", first).lower()))
    return out


def expected_groups(papers):
    live = [p for p in papers if not p.trashed]
    group = {p.id: {p.id} for p in live}
    owner = {}
    for p in live:
        for k in keys(p):
            if k in owner and group[owner[k]] is not group[p.id]:
                merged = group[owner[k]] | group[p.id]
                for i in merged:
                    group[i] = merged
            owner.setdefault(k, p.id)
    seen, out = set(), []
    for p in live:
        g = frozenset(group[p.id])
        if len(g) > 1 and g not in seen:
            seen.add(g)
            out.append([q.id for q in live if q.id in g])
    return out


def tidy(impl, papers):
    return impl(Input(papers=papers)).groups


@given(papers=library())
def test_groups_are_exactly_the_papers_that_share_a_key(impl, papers):
    assert [g.ids for g in tidy(impl, papers)] == expected_groups(papers)


@given(papers=library())
def test_the_keeper_has_a_pdf_then_notes_then_is_oldest(impl, papers):
    by_id = {p.id: p for p in papers}
    for g in tidy(impl, papers):
        group = [by_id[i] for i in g.ids]
        best = min(group, key=lambda p: (not p.pdf, not p.notes, p.added, g.ids.index(p.id)))
        assert g.keep == best.id


@given(papers=library())
def test_the_keeper_gains_what_the_others_have(impl, papers):
    by_id = {p.id: p for p in papers}
    for g in tidy(impl, papers):
        keep = by_id[g.keep]
        others = [by_id[i] for i in g.ids if i != g.keep]
        everyone = [keep, *others]
        assert g.patch.tags == list(dict.fromkeys(t for p in everyone for t in p.tags))
        assert g.patch.folders == list(dict.fromkeys(f for p in everyone for f in p.folders or []))
        notes = list(dict.fromkeys(n.strip() for p in everyone if p.notes and p.notes.strip() for n in [p.notes]))
        assert g.patch.notes == ("\n\n".join(notes) or None)
        assert g.patch.starred == (True if any(p.starred for p in everyone) else None)
        assert g.patch.added == min(p.added for p in everyone)
        for k in ("venue", "year", "pdf", "doi", "arxiv"):
            want = None if getattr(keep, k) else next((getattr(p, k) for p in others if getattr(p, k)), None)
            assert getattr(g.patch, k) == want, k


@given(papers=library())
def test_fields_prefer_the_keeper_then_earlier_papers(impl, papers):
    by_id = {p.id: p for p in papers}
    for g in tidy(impl, papers):
        order = [by_id[g.keep]] + [by_id[i] for i in g.ids if i != g.keep]
        want = {}
        for p in reversed(order):
            want.update(p.fields)
        assert g.patch.fields == want


@given(papers=library())
def test_trash_is_never_grouped(impl, papers):
    trashed = {p.id for p in papers if p.trashed}
    assert not trashed & {i for g in tidy(impl, papers) for i in g.ids}
```

## components/tidy/versions/1/schema.py

```python
"""Interface for lightkone/tidy."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

TIMESTAMP = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z$"


class Paper(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str
    authors: list[str] = Field(default_factory=list)
    added: str = Field(pattern=TIMESTAMP)
    tags: list[str] = Field(default_factory=list)
    folders: list[str] | None = None
    year: int | None = Field(None, ge=1)
    venue: str | None = None
    abstract: str | None = None
    doi: str | None = None
    arxiv: str | None = None
    url: str | None = None
    pdf: str | None = None
    file: str | None = None
    notes: str | None = None
    starred: bool | None = None
    opened: str | None = None
    trashed: str | None = None
    fields: dict[str, str] = Field(default_factory=dict)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    papers: list[Paper] = Field(description="The library, in stored order. Ids are unique.")

    @model_validator(mode="after")
    def _unique_ids(self) -> "Input":
        if len({p.id for p in self.papers}) != len(self.papers):
            raise ValueError("paper ids must be unique")
        return self


class Patch(BaseModel):
    """What the kept paper gains. Absent fields are null."""

    model_config = ConfigDict(extra="forbid")

    tags: list[str]
    folders: list[str]
    notes: str | None = None
    starred: bool | None = None
    fields: dict[str, str]
    added: str
    abstract: str | None = None
    doi: str | None = None
    arxiv: str | None = None
    url: str | None = None
    venue: str | None = None
    year: int | None = None
    pdf: str | None = None
    file: str | None = None
    opened: str | None = None


class Group(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[str] = Field(description="The duplicates, in library order.")
    keep: str = Field(description="Id of the paper to keep.")
    patch: Patch


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")

    groups: list[Group]
```

## components/tidy/versions/1/schema/input.json

```json
{
  "$defs": {
    "Paper": {
      "additionalProperties": false,
      "properties": {
        "abstract": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Abstract"
        },
        "added": {
          "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\\.[0-9]{3}Z$",
          "title": "Added",
          "type": "string"
        },
        "arxiv": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Arxiv"
        },
        "authors": {
          "items": {
            "type": "string"
          },
          "title": "Authors",
          "type": "array"
        },
        "doi": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Doi"
        },
        "fields": {
          "additionalProperties": {
            "type": "string"
          },
          "title": "Fields",
          "type": "object"
        },
        "file": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "File"
        },
        "folders": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Folders"
        },
        "id": {
          "minLength": 1,
          "title": "Id",
          "type": "string"
        },
        "notes": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Notes"
        },
        "opened": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Opened"
        },
        "pdf": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Pdf"
        },
        "starred": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Starred"
        },
        "tags": {
          "items": {
            "type": "string"
          },
          "title": "Tags",
          "type": "array"
        },
        "title": {
          "title": "Title",
          "type": "string"
        },
        "trashed": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Trashed"
        },
        "url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Url"
        },
        "venue": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Venue"
        },
        "year": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Year"
        }
      },
      "required": [
        "id",
        "title",
        "added"
      ],
      "title": "Paper",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "papers": {
      "description": "The library, in stored order. Ids are unique.",
      "items": {
        "$ref": "#/$defs/Paper"
      },
      "title": "Papers",
      "type": "array"
    }
  },
  "required": [
    "papers"
  ],
  "title": "Input",
  "type": "object"
}
```

## components/tidy/versions/1/schema/output.json

```json
{
  "$defs": {
    "Group": {
      "additionalProperties": false,
      "properties": {
        "ids": {
          "description": "The duplicates, in library order.",
          "items": {
            "type": "string"
          },
          "title": "Ids",
          "type": "array"
        },
        "keep": {
          "description": "Id of the paper to keep.",
          "title": "Keep",
          "type": "string"
        },
        "patch": {
          "$ref": "#/$defs/Patch"
        }
      },
      "required": [
        "ids",
        "keep",
        "patch"
      ],
      "title": "Group",
      "type": "object"
    },
    "Patch": {
      "additionalProperties": false,
      "description": "What the kept paper gains. Absent fields are null.",
      "properties": {
        "abstract": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Abstract"
        },
        "added": {
          "title": "Added",
          "type": "string"
        },
        "arxiv": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Arxiv"
        },
        "doi": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Doi"
        },
        "fields": {
          "additionalProperties": {
            "type": "string"
          },
          "title": "Fields",
          "type": "object"
        },
        "file": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "File"
        },
        "folders": {
          "items": {
            "type": "string"
          },
          "title": "Folders",
          "type": "array"
        },
        "notes": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Notes"
        },
        "opened": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Opened"
        },
        "pdf": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Pdf"
        },
        "starred": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Starred"
        },
        "tags": {
          "items": {
            "type": "string"
          },
          "title": "Tags",
          "type": "array"
        },
        "url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Url"
        },
        "venue": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Venue"
        },
        "year": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Year"
        }
      },
      "required": [
        "tags",
        "folders",
        "fields",
        "added"
      ],
      "title": "Patch",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "groups": {
      "items": {
        "$ref": "#/$defs/Group"
      },
      "title": "Groups",
      "type": "array"
    }
  },
  "required": [
    "groups"
  ],
  "title": "Output",
  "type": "object"
}
```

## components/tidy/versions/1/symbolon.toml

```toml
[contract]
id = "lightkone/tidy"
version = 1
title = "Find duplicate papers and merge them"
description = """
Finds papers entered more than once, picks the one to keep, and works out
what the kept paper gains from the others, as lightkone's Tidy panel does.
The others are then moved to the trash by the caller.

DUPLICATES. Papers in the trash (trashed present and non-empty) are ignored.
Each remaining paper has up to three match keys:
  doi    "doi:" + doi trimmed, lower-cased, with a leading http(s)://doi.org/
         or http(s)://dx.doi.org/ removed; no key when that leaves nothing
         (no doi, only whitespace, or only the prefix).
  arxiv  "arxiv:" + arxiv trimmed, lower-cased, without a leading "arxiv:"
         and a trailing vN; no key when that leaves nothing.
  title  t = title decomposed (NFKD), lower-cased, keeping only a-z and 0-9.
         If t is longer than 20: "title:" + t. Else if longer than 3:
         "title:" + t + ":" + the first author's surname (before the first
         comma), decomposed, lower-cased, keeping only a-z. Else no key.
Papers that share a key are duplicates, and so are duplicates of duplicates.
Groups of two or more are reported in the order of their first paper, and
each group lists its papers in library order.

KEEPER. The paper with a pdf; among those, the one with notes; among those,
the earliest added (comparing the timestamps as text); then library order.

PATCH (what the keeper gains), with "others" in group order:
  tags     every tag of the keeper, then of the others, without repeats
  folders  the same for folders
  notes    every distinct trimmed non-empty note, keeper first, joined by a
           blank line; absent if none
  starred  true if any is starred; absent otherwise
  fields   the BibTeX fields of all of them, the keeper's winning, then
           earlier others over later ones
  added    the earliest added
  abstract, doi, arxiv, url, venue, year, pdf, file, opened: when the
           keeper's is absent or empty, the first other's non-empty value
"""
regenerability = "disposable"
license = "Proprietary (kausalflow)"
authors = ["kausalflow/lightkone"]

[entrypoint]
function = "run"

[requires]
network = []
credentials = []
state = []
permissions = []

[spec]
seed = 0
max_examples = 200
timeout_seconds = 300
```
