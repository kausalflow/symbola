# Symbolon

**Trustable contracts between agents.** A contract is a precise, content-addressed promise. Evidence that someone kept it can be checked by anyone.

Agents increasingly call tools, run code they generated, and rebuild software on someone's behalf. Each of those is an implicit promise that something behaves a certain way. Symbolon writes the promise down in a form a machine can check, and records signed evidence that a specific implementation kept it.

Software capabilities are the first vertical. A contract specifies a capability, and any implementation, hand-written or AI-generated, in any language, is checked against it.

<div class="grid cards" markdown>

-   :lucide-rocket: **Get started**

    ---

    Install the CLI, validate a seed contract, and watch a plausible implementation fail it.

    [:octicons-arrow-right-24: Getting started](getting-started.md)

-   :lucide-book-open: **Concepts**

    ---

    Contracts, implementations, attestations, spec packs, and how digests tie them together.

    [:octicons-arrow-right-24: Concepts](concepts.md)

-   :lucide-terminal: **CLI reference**

    ---

    Every `symbola` command and its options.

    [:octicons-arrow-right-24: CLI](cli.md)

-   :lucide-file-code: **Formats**

    ---

    The contract, implementation, attestation and spec pack formats.

    [:octicons-arrow-right-24: Contract format](CONTRACT_FORMAT.md)

</div>

## The idea in one example

```console
$ symbola test contracts/core/date-parse/versions/1 examples/impls/date-parse-strptime
...
✗ test_iso_requires_two_digit_month_and_day
    AssertionError
    Failing test case: test_iso_requires_two_digit_month_and_day(
        impl=impl,
        d=datetime.date(2000, 1, 1),  # or any other generated value
    )

FAIL  2 of 21 checks failed

$ symbola test contracts/core/date-parse/versions/1 examples/impls/date-parse-strict
PASS  21 checks
```

The first implementation looks right and passes the obvious examples, but it accepts `2000-1-1` as an ISO date. The contract's properties catch it. The second, independently written implementation passes the same contract. Neither implementation matters on its own: the contract, and the evidence that something passed it, are the asset.

## What is in the repository

| | |
| --- | --- |
| **Contract format** | A directory with a manifest, a pydantic schema, examples and hypothesis properties. Identified by a SHA-256 digest of its contents. |
| **Validation** | `symbola validate` checks structure, schema drift, examples, and that the spec is not vacuous. |
| **Testing** | `symbola test` runs a contract's spec against an implementation in Python or any language that speaks a JSON line protocol. |
| **Attestations** | `symbola attest` runs the spec in a sandbox and writes a signed in-toto attestation; `symbola verify --rerun` reproduces it. |
| **Spec packs** | Product-level contracts: a brief, assumptions, obligations, and component contracts. `symbola pack validate` checks them. |
| **Seeds and a pilot** | Three seed contracts and the [lightkone pilot](lightkone-pilot.md), a spec pack extracted from a real product and rebuilt by an AI from the pack alone. |
