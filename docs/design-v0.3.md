# Symbolon — Product Design Document

**Status:** Draft v0.3 (formerly Strand)
**Date:** 2026-10-21
**One-liner:** Trustable contracts between agents: a commitment anyone can check, backed by evidence anyone can verify. Software capabilities are the first vertical.

*The name.* A symbolon was an ancient Greek token broken in two. Each party kept one half, and matching the halves proved the agreement. It is also the root of the word "symbol." Here, the contract is one half and the evidence that someone kept it is the other.

### Changes since v0.2

- **Vision broadened.** Contracts are now commitments between any parties, such as agents, software, services, and the humans they act for. Software capability contracts, the whole of v0.2, become the first vertical and the MVP (sections 1, 3, 4, 9).
- **One general model.** Every contract kind uses the same primitives: parties, obligations, evidence, ledger, trust set, and counterexample. Only how the evidence is collected differs by kind (4.2, 4.3).
- **Product contracts and a business model.** Specs and conformance suites become something you can sell, including to enterprises, while attestations stay public and unbuyable (6, 12).
- **Spec lifecycle and AI authoring protocol.** Authors extract a spec from software they built. Users find, download, and fork it, and AI revises it under an enforced authoring protocol. Only a human key publishes (6.5, 6.6).
- **Governance section.** This covers who stores contracts, who may change them, and how disputes resolve (8).
- **Standards reuse.** Attestations use the in-toto format and Sigstore-style signing and transparency instead of a custom format (7).
- **Renamed.** "Strand" collides with AWS Strands Agents.

---

## 1. Summary

Agents increasingly act for people and for each other. They call tools, run code they generated, hire other agents, and spend money on someone's behalf. Each of these is an implicit promise: this tool parses dates correctly, this agent will only touch the files I allowed, this service deletes my data after 30 days. Today none of those promises is written down in a checkable form, and none leaves verifiable evidence that it was kept.

Symbolon makes them explicit. A **contract** is a versioned, content-addressed statement of obligations between parties. An **attestation** is signed evidence that a specific party met those obligations in a specific case. A public **ledger** accumulates attestations and verified violations, so trust is earned from a record rather than asserted. Parties agree on contract digests, not on code, vendors, or reputations.

The first vertical is software capabilities. Here the obligations can be checked before execution by running a spec against an implementation in a sandbox. That is the most testable kind of promise, and it is where agents already rebuild things constantly.

## 2. Problem

**Promises between agents are implicit.** When agent A delegates to agent B, uses tool C, or relies on service D, the expectations are buried in prompts, docs, or terms of service. They cannot be compared, checked, or enforced.

**There is no portable track record.** An agent, a tool, or an implementation that behaved well yesterday leaves no evidence a stranger can verify today. Code generated fresh for each call has no history at all.

**Coordination fails silently.** Two agents interoperate only if they agree on behavior. When nobody declares that behavior, divergence stays invisible until something breaks.

**Single points of trust are fragile.** Ecosystems that depend on one implementation or one vendor inherit its failures, as in the left-pad incident or a compromised package. Contracts with many independently attested implementations do not.

Existing pieces each cover a slice. Tool and MCP registries cover discovery. Pact covers API contracts between services. SLSA, in-toto, and Sigstore cover build provenance. Tessl covers specs as the source of code. None of them combines a checkable obligation, independent evidence, and a public record of violations for agent-to-agent trust.

## 3. Thesis

What can be regenerated cheaply, like code, glue, and even whole agents, should be treated as disposable. What cannot be regenerated is **access** (credentials, legal agreements), **state** (data, histories), and **track record** (evidence that promises were kept). The durable asset is the promise and its evidence.

Trust between agents should therefore rest on three things: a precise promise, evidence that does not depend on trusting the party making the promise, and a public record of every verified violation.

## 4. Core model

### 4.1 Primitives

| Primitive | What it is |
| --- | --- |
| **Contract** | Immutable, content-addressed set of obligations. It has roles (who promises and who relies), an interface, and a spec saying how each obligation is checked. |
| **Party** | Anything that can hold a key and take a role: an implementation, an agent, a service, a runner, a human principal. |
| **Obligation** | A checkable predicate. Example: "for every valid input, output matches the schema and properties"; "no network call outside the declared hosts"; "every write emits an audit event". |
| **Evidence / attestation** | A signed statement that a party met (or violated) obligations in a specific case, in in-toto format. |
| **Ledger** | The append-only record per contract and per party: attestations, verified counterexamples, deprecations, successor links. |
| **Trust set** | The verifier keys a caller accepts evidence from. |
| **Counterexample** | A concrete, reproducible case where a party violated an obligation. It is the only accepted form of complaint. |

### 4.2 Contract kinds

All kinds share the primitives. They differ in **when** and **how** evidence is produced, and that sets the order of the roadmap.

| Kind | Example | Evidence | Verifiability | Phase |
| --- | --- | --- | --- | --- |
| **Capability** | Parse dates across locales | Pre-execution: spec run against implementation in sandbox | Strong, reproducible | 1 (MVP) |
| **Product** | A full app with features, security and audit requirements | Pre-execution: composed capability contracts plus end-to-end acceptance, security, and audit suites | Strong for what is tested | 2 |
| **Interaction** | Agent A and agent B exchange messages in a defined protocol | Recorded transcripts checked against the protocol, both parties co-signing | Medium | 3 |
| **Mandate** | Agent acts for a human within scope, spend, and data limits | Runtime receipts from an enforcing gateway, plus audit | Medium; depends on the enforcement point | 3 |
| **Service** | Hosted service promises data retention, latency, uptime | Runtime monitoring by third-party verifiers | Weaker; observational | 4 |

The rule for ordering: start where evidence is strongest and the cost of a wrong verdict is lowest. Earn the right to the harder kinds with a working counterexample loop.

### 4.3 Evidence strength

Not all evidence is equal, so attestations declare their kind and callers weigh them:

1. **Reproducible:** any verifier given the same digests gets the same result. Capability and product contracts with pure specs.
2. **Co-signed:** both parties sign the same record. Interaction contracts.
3. **Enforced:** a trusted enforcement point signs what it allowed and blocked. Mandate contracts.
4. **Observed:** a third party saw it happen, but cannot replay it. Service contracts and anything with network access.

### 4.4 Ranking

Wherever several parties can fulfil the same contract, ranking uses only published evidence:

1. number of distinct trusted verifiers that attested the party;
2. verified counterexamples against it (fewer is better);
3. age of its first trusted attestation.

Raw attestation count is never an input, because it is free to inflate. There is no sponsored placement and no opaque score, and money never buys evidence.

## 5. First vertical: software capability contracts

This section carries v0.2 forward. Section numbers in brackets refer to v0.2, where the detail is unchanged.

### 5.1 Capability contract

Identified by digest: SHA-256 over a deterministic archive of the contract directory. The alias is `namespace/name@version`. Namespaces are bound to a publisher key, and versions are integers; any change to the schema or spec bumps the version.

It contains a JSON Schema interface (canonical; pydantic is authoring sugar), an entrypoint signature (MVP: synchronous `run(input) -> output`), and a behavioral spec. The spec has three parts: examples as data, derandomized hypothesis properties, and an optional reference implementation used only as an oracle. It also declares external requirements (credentials by name, network hosts, state, permissions), a regenerability class, and provenance including the license. [v0.2 4.1]

### 5.2 Implementation

A directory of source code, a manifest naming the target contract digest, and a pinned lockfile. Its identity is the digest of all three. Generated implementations record the generator in the manifest. [v0.2 4.2]

### 5.3 Attestation and reproducibility

The runner executes the spec against the implementation in a sandbox: no network unless declared, resource limits, a pinned environment digest, and derandomized tests. Both the implementation and the contract's test code are untrusted and run inside the sandbox. The result is an in-toto attestation signed by the runner. Each attestation carries the contract and implementation digests, test results with seed and budget, a resource profile, the environment digest, and runner and submitter identity. [v0.2 4.3, 4.4]

### 5.4 Regenerability

- **Disposable:** any trusted-attested implementation is acceptable, and callers may regenerate at will.
- **Pinned:** callers converge on one implementation digest chosen by ranking; generation is allowed only when none exists.
- **Sovereign:** reserved. It is effectively a service contract and comes in phase 4. [v0.2 4.7]

### 5.5 Resolution

`resolve(contract, version)` returns a local path plus the backing attestation. Loading the code is a separate, explicit step under the caller's policy. For disposable contracts with nothing attested, resolution generates an implementation, attests it, and caches it. Expected latency is under a second when cached, and tens of seconds to minutes for generate-then-attest. [v0.2 4.8]

## 6. Product contracts (phase 2)

A product contract specifies a whole application well enough that any capable AI can build it, a buyer can customize it, and anyone can check the result. The motivating case is a project like lightkone: rebuilding it from scratch today takes many rounds of human iteration.

### 6.1 Structure

- **Composition:** a graph of capability contracts, referenced by digest.
- **Acceptance suite:** end-to-end scenarios over the composed product.
- **Security suite:** a full role × action authorization matrix, with each cell tested. It also includes input fuzzing, a declared network allowlist checked in the sandbox, a dependency policy, and a threat model where each threat maps to at least one test.
- **Audit suite:** required audit events as testable obligations. Example: "every state-changing request emits an event with actor, action, target and timestamp."
- **Non-functional notes:** UX, performance, and operations guidance that is not yet testable, clearly marked as such.

### 6.2 Making a spec replicable by any AI

A spec is only as good as its weakest untested behavior. The method for closing the gap:

1. Two or three different AI systems build independently from the spec.
2. Each build runs the full suites.
3. Wherever builds pass but behave differently, the spec is missing an obligation. Add a test that pins the intended behavior.
4. Repeat until independent builds converge.

The convergence result is published evidence of spec quality: the number of independent builds that pass, and the remaining known divergences.

### 6.3 What a spec cannot guarantee

UX quality, performance under real load, and novel vulnerabilities outside the tested threat model. A product contract states this plainly, and passing it means "meets every tested obligation", nothing more.

### 6.4 Customization

Buyers fork with lineage. Their changes become new contract versions, and conformance to the parent contract's suites can still be checked and attested.

### 6.5 Spec lifecycle: extract, find, download, revise, publish

The loop a person runs, with AI doing most of the work:

1. **Extract.** An author points Symbolon at software they built. An AI reads the code and observes its behavior, then proposes a product contract: the composition, the schemas, the examples, and the acceptance, security, and audit suites. The original software is the reference oracle. The spec must pass against it, and it must fail the vacuity stubs. The author reviews it and publishes.
2. **Find.** Users search the registry by capability, contract kind, and evidence. Results show convergence results, counterexample counts, lineage, and license, never a popularity score.
3. **Download.** `pull` fetches the contract by digest with its suites and evidence, and verifies signatures locally. Any AI tool can build from it, and the build is checked with `attest`.
4. **Revise.** A user forks and asks an AI to change the spec, for example to add a feature or tighten security. The AI must follow the authoring protocol (6.6).
5. **Publish.** The new version passes `validate`, and the convergence loop if it is a product contract. It carries a changelog and lineage to its parent, and is signed by the human owner of the namespace. AI may draft and check a version, but only a human key can publish it.

### 6.6 Authoring protocol for AI

The guidelines AI follows are themselves a published, versioned contract: the **authoring protocol**. They are machine-readable rules, not prose advice. Symbolon serves it to any AI as an MCP server or agent skill, and `validate` enforces it, so a version that breaks the rules cannot be published whichever AI wrote it.

The protocol requires that:

- every new or changed behavior comes with at least one example or property that pins it down;
- a revision never deletes an existing test without a recorded reason, and deleting one makes the change breaking;
- every security-relevant feature updates the authorization matrix and threat model;
- every state-changing feature declares its audit events;
- the changelog states, per change, whether behavior changed, and which tests prove it;
- the spec passes against the reference implementation and fails the vacuity stubs;
- for product contracts, the convergence loop (6.2) ran, and its result is attached.

Because the protocol is a contract, it has its own versions and its own counterexamples. If a spec that followed it still turns out to be weak, that counts against the protocol, and its next version tightens the rules.

## 7. Architecture

| Component | Role |
| --- | --- |
| **Contract store** | Immutable contracts addressed by digest, with aliases. A git repository at first. |
| **Verifiers** | Produce evidence. For capability and product contracts, these are sandboxed attestation runners. Later kinds add transcript checkers, enforcement gateways, and monitors. Each verifier has a published key. |
| **Ledger** | Append-only record of attestations and counterexamples. It mirrors to a Sigstore-style transparency log so that history cannot be rewritten quietly. |
| **Resolver** | Selects a party for a contract using the caller's trust set and the ranking rules. For capability contracts, it falls back to generation when allowed. |
| **Counterexample service** | Accepts violation reports, replays them through a verifier, and records the result. |

Formats reuse standards: JSON Schema for interfaces, in-toto statements for attestations, Ed25519 or Sigstore keyless signing, and SHA-256 content addressing. The novelty is in what gets signed and how the record is used, not in the cryptography.

## 8. Governance

**Storage.** Publishers sign contracts with their namespace key and push them to the registry. Contracts are content-addressed, so anyone may mirror them, and a mirror is verifiable. Storage is not a trust point.

**Change.** Only the namespace key holder can publish new versions. Nobody can amend a published contract.

**Disputes.** The spec is the only arbiter.

- If a counterexample makes the current spec fail, it is objectively valid. It is recorded against the party, and against the verifier that attested it.
- If the spec passes it, it is a proposal. The author may adopt it in a new version, or anyone may fork with it. Adoption follows evidence.
- Symbolon does not adjudicate intent.

**Registry operator.** Handles only namespace disputes (squatting, abandoned namespaces) and legal takedowns, under a published policy. Every action is logged in the ledger. Federation (section 15) removes the single operator.

## 9. Users

**Phase 1:** agent developers who want capabilities without hard dependencies; agents as runtime callers of `resolve`; contract authors.
**Phase 2:** product teams and enterprises that buy or commission product contracts to build and customize applications with their own AI tools.
**Phase 3 and later:** operators of multi-agent systems who need agents to keep promises to each other and to the humans they act for.

Non-users for now: end consumers and anyone whose primary need is credential management.

## 10. Product surfaces

- **CLI and Python package (phase 1):** `init`, `validate` (including the vacuity check), `attest`, `resolve`, `publish`, `report`, and later `fork`. [v0.2 6.1]
- **Registry:** a git repository first, with layout `contracts/`, `ledger/`, `implementations/`, `attestations/`, `verifiers/`. A hosted index and API come later. [v0.2 6.2]
- **Runtime library:** `resolve()` with an in-process cache, a configurable trust set, and an optional local runner. [v0.2 6.3]
- **Contract studio (phase 2):** tooling for authoring product contracts and running the multi-AI convergence loop in 6.2. Adds `extract` (spec from existing software), `search`, and `pull` (6.5).
- **Authoring protocol server (phase 2):** an MCP server or agent skill that hands any AI the authoring protocol and checks drafts against it (6.6).

## 11. MVP scope (phase 1)

Unchanged from v0.2 section 8:

1. Contract format, `init`, `validate`, and three seed contracts (`core/date-parse`, `core/csv-to-records`, `core/unit-convert`).
2. Implementation format and `attest` with a container sandbox and in-toto output.
3. End-to-end slice: one implementation attested on two machines with identical results.
4. Git registry, `publish`, lookup-only `resolve` with a trust set.
5. Generate-then-attest for disposable contracts.
6. 10 to 20 pure seed contracts; counterexample reporting.

Success: an outside agent resolves a seed contract and gets a working implementation; a third-party runner reproduces the attestation; at least one outside developer chooses `resolve` over in-house generation and can say why.

## 12. Business model

- **Free:** public contracts, public attestations, the open-source CLI and runner.
- **Paid, phase 1 to 2:** private registries and a hosted canonical runner (metered attestation).
- **Paid, phase 2:** product contracts. Buyers pay for the conformance suites, convergence evidence, and maintained updates. The prose spec copies as easily as code; the suites and the ongoing record are the product.
- **Enterprise:** private namespaces, commissioned product contracts, on-premises runners.

**Invariant:** evidence is never for sale. Ranking stays purely evidence-based and fully published, regardless of who pays for what.

## 13. Non-goals

Symbolon is not a credential manager, a package manager replacement, an agent framework, a general code-generation product, or a legal contract platform. It does not host long-running customer services. It does not verify properties beyond what a contract's spec states. Payments between agents are out of scope; mandate contracts may describe spend limits, but Symbolon does not move money.

## 14. Risks and open questions

- **The spec is the real product.** Weak specs attest bad implementations. Mitigations: the vacuity check, reference oracles, the counterexample loop, and multi-AI convergence (6.2).
- **Tests do not cover security.** State it plainly. Product contracts narrow the gap through explicit security suites, but cannot close it.
- **Malicious contracts and verifiers.** Contract code runs sandboxed. Verifiers are weighted by trust set and penalized by verified counterexamples.
- **Scope creep.** The broader vision is a direction, not the MVP. Phase gates: move to the next contract kind only after the previous one shows a working counterexample loop and outside adoption.
- **Weaker evidence in later phases.** Interaction, mandate, and service contracts rely on co-signed, enforced, or observed evidence. Callers must see the evidence strength, never a single green check.
- **Spec piracy.** Specs are easy to copy. The paid value is the maintained suites, the evidence, and the updates, so treat the prose as marketing.
- **Demand.** Agents may prefer to generate and test locally. The MVP demand test checks this before anything else scales.
- **Name.** Trademark and domain checks still to do (see section 16).

## 15. Longer-term direction

Contracts that compose across kinds. For example, a product contract whose deployment carries a mandate contract for the agents operating it. Other directions: cross-language implementations, record/replay so networked capabilities become reproducible, federation of registries and verifiers across organizations, and a standard way for agents to present their ledger history to each other before collaborating.

## 16. Naming

"Strand" is retired because of AWS Strands Agents. Symbolon was chosen on 2026-10-21. Quick web checks on 2026-10-21 (not trademark or domain searches):

| Name | Meaning | Collision found |
| --- | --- | --- |
| **Symbolon** (chosen 2026-10-21) | Greek token split between two parties; matching halves proves the agreement | None notable in software or AI |
| **Chirograph** | Medieval deed written twice on one sheet and cut apart; the matching cut proves authenticity | None in software |
| **Syngraph** | Greek for a written contract signed by both parties | None notable |
| Tessera | Roman token of a pact | Taken: Google's transparency-log library, same space |
| Countersign | Second signature confirming a first | Taken: an existing npm MCP package |
| Warrant | Guarantee | Taken: an authorization startup |
| Surety | Guarantee of another's obligation | Crowded by surety-bond insurance software |

## 17. Glossary

**Contract.** An immutable, content-addressed set of obligations between roles, with a spec saying how each is checked.
**Party.** A key-holding participant: implementation, agent, service, verifier, or human principal.
**Obligation.** A checkable predicate within a contract.
**Attestation.** Signed evidence that a party met or violated obligations, with a declared evidence strength.
**Evidence strength.** Reproducible, co-signed, enforced, or observed.
**Ledger.** The append-only record of attestations and verified counterexamples.
**Counterexample.** A reproducible case of a violated obligation; the only accepted form of complaint.
**Trust set.** The verifier keys a caller accepts.
**Capability / product / interaction / mandate / service contract.** The contract kinds, in roadmap order.
**Resolve.** For capability contracts: return an attested implementation, generating one if permitted.
**Vacuity check.** Validation proving a spec rejects trivial implementations.
