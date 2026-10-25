# Mutants for the lightkone pilot

Plausible wrong versions of the python-1 rebuild, one concern each, used to
measure how much the lightkone pack's components reject. They live here,
outside the pack, so adding them does not change the components' digests.
The pack is in [kausalflow/symbola-registry](https://github.com/kausalflow/symbola-registry); run these from a clone of it next to this repository.

```
symbola mutants ../symbola-registry/packs/kausalflow/lightkone/versions/1/components/search-query/versions/1 --mutants examples/mutants/lightkone/search-query
symbola mutants ../symbola-registry/packs/kausalflow/lightkone/versions/1/components/bibtex-export/versions/1 --mutants examples/mutants/lightkone/bibtex-export
symbola mutants ../symbola-registry/packs/kausalflow/lightkone/versions/1/components/bibtex-import/versions/1 --mutants examples/mutants/lightkone/bibtex-import
```

Result on 2026-10-22: search-query kills 8 of 9; the survivor (`m02`) is
exactly the behaviour obligation `search.year-malformed` leaves open.
bibtex-export kills 7 of 7.

bibtex-import kills 7 of 8. The survivor (`m08`) reads a two- or three-digit
year such as `99` as a number. The description says the year is "the first run
of 4 ASCII digits", so `99` should give no year, but no example or property
checks it. That is a gap in the pack, left undocumented here on purpose so the
command keeps failing until the pack gains a check.
