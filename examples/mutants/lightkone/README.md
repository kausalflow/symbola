# Mutants for the lightkone pilot

Plausible wrong versions of the python-1 rebuild, one concern each, used to
measure how much the lightkone pack's components reject. They live here,
outside the pack, so adding them does not change the components' digests.

```
symbolon mutants packs/kausalflow/lightkone/1/components/search-query/1 --mutants examples/mutants/lightkone/search-query
symbolon mutants packs/kausalflow/lightkone/1/components/bibtex-export/1 --mutants examples/mutants/lightkone/bibtex-export
```

Result on 2026-10-22: search-query kills 8 of 9; the survivor (`m02`) is
exactly the behaviour obligation `search.year-malformed` leaves open.
bibtex-export kills 7 of 7. bibtex-import has no mutants yet.
