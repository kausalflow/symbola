# Pack registry

The registry is a static website. A folder of packs (`packs/<owner>/<name>/versions/<n>/`)
is turned into plain files that any web host can serve, and `symbola pull` reads
them. There is no server. Only the **latest** version of each pack is published;
older versions stay in the registry's folders and git history so that attestations
naming them can still be re-checked.

## Three ways to make a pack

| You have | Use | Start with |
| --- | --- | --- |
| A product that already works | `symbola extract`: an agent reads the code and drafts the pack, checked against the original | `symbola extract ./my-product --pack you/my-product` |
| A product you are building now | The [`symbola-pack`](https://github.com/kausalflow/symbola/blob/main/skills/symbola-pack/SKILL.md) skill: your agent records decisions as you make them | `npx skills add kausalflow/symbola --skill symbola-pack` |
| An idea, no code yet | The [`symbola-decide`](https://github.com/kausalflow/symbola/blob/main/skills/symbola-decide/SKILL.md) skill: your agent asks you multiple-choice questions and writes the pack | `npx skills add kausalflow/symbola --skill symbola-decide` |

All three end in the same pack format and the same `symbola publish`. Before publishing,
build the pack once from the pack alone (`symbola replicate spec --builds 1`) and publish
with `--evidence`; a pack without it is listed as having no passing build.

## Making a pack

```
symbola pack init acme/invoice-desk          # creates spec/ next to your code
symbola pack validate spec
```

`pack init` writes a manifest, a `BRIEF.md` with the three required headings, an
`obligations.toml` with one open placeholder, a placeholder assumption, an empty
`components/` and an `AGENTS.md`. It passes `pack validate` as it stands. The
generated `AGENTS.md` also tells the publisher's own coding agent to keep the pack
current while it builds: record each choice the user makes that a builder could
not have guessed as an obligation with a check, and each fact about the world as an
assumption.

Holdout tests must stay **outside** the pack folder. `site build` refuses a pack that
contains a `holdout` path.

## Keeping a pack while you build

The repository ships an agent skill, [`skills/symbola-pack/SKILL.md`](https://github.com/kausalflow/symbola/blob/main/skills/symbola-pack/SKILL.md).
Install it with `npx skills add kausalflow/symbola --skill symbola-pack` (or copy it
into your project's `.claude/skills/`, or point another coding tool at it from your
`AGENTS.md`). It tells the agent to update `spec/` in the same change as
the code whenever you make a decision a builder could not have guessed, state a
fact about the world, or leave something open, and to run `pack validate` after
each change.

## Deciding before building

A pack needs no code: a decision's check can be an example line, an input and the
output the publisher wants. The [`symbola-decide`](https://github.com/kausalflow/symbola/blob/main/skills/symbola-decide/SKILL.md)
skill has the publisher's coding agent interview them instead. It writes `PRODUCT.md`
and `BRIEF.md` from a description, then asks only where good builders would choose
differently, as multiple-choice questions with a concrete input, kept in
`spec/.symbolon/questions.toml` (not published):

```
symbola pack questions spec                          # what is still unanswered
symbola pack answer spec search.year-is-publication-year a
```

`pack answer` turns each answer into an obligation and the example line that checks
it, so the pack stays in format whatever the agent writes. Install the skill with
`npx skills add kausalflow/symbola --skill symbola-decide`; the Claude Code plugin
includes it.

## Publishing from symbola.sh

Sign in at <https://symbola.sh/publish/> with GitHub, or from a terminal:

```
symbola login              # GitHub device sign-in; saves a token in ~/.config/symbolon/
symbola publish spec       # validates locally, uploads, and follows the request
```

To show on the pack's page that it builds, publish the attestations of a test build
with it. `symbola replicate` hands the pack alone to a fresh coding agent and attests
what it builds:

```
symbola keygen                                         # once
symbola replicate spec --builds 1 -o spec/.symbolon/test-build
symbola publish spec --evidence spec/.symbolon/test-build/attestations
```

Each attestation must name a component of the pack as it is now; the registry places
them beside the pack. Without evidence the page says no build has passed yet.

Your GitHub login is your namespace, so you publish `<login>/<name>`; organisations
that installed the Symbola GitHub app (or where your membership is public) are
namespaces too. The registry's publish workflow runs `release` and `site check` on
the upload and opens a pull request as the Symbola bot. New versions of a pack
merge when CI passes; a namespace's first pack waits once for a moderator. In CI,
put a token in `SYMBOLON_PUBLISH_TOKEN` instead of running `login`.

The account page (<https://symbola.sh/account/>) lists your packs and requests,
edits your publisher profile and support links, revokes CLI tokens, and asks for
a pack to be removed. `symbola logout` forgets the local token.

Publishing by pull request, below, still works and needs no account.

## Releasing

```
symbola release spec --registry ../symbola-registry/packs   # in a clone of kausalflow/symbola-registry
```

`release` validates the pack, sets its manifest version to the next free number,
copies it to `packs/<owner>/<name>/versions/<n>/`, and appends the version's
digest to `packs/<owner>/<name>/digests.txt`. Releasing unchanged content does
nothing. Then commit and open a pull request.

A release is also how you ship an upgrade, and it needs nothing extra from you:
`release` prints what changed since the last version, and the site shows it on the
pack's page (see [Upgrading a build](#upgrading-a-build)).

There are no publisher keys. Who may release under an owner is decided by who
can merge into the registry; once packs move to their publishers' own
repositories as GitHub Releases, GitHub's provenance attestation will identify
the publisher and `pull` will check it (distribution design v0.5, section 5.2).
Ed25519 keys are only for runners that sign attestations.

## Submission checks

```
symbola site check packs
```

CI runs this on every pull request. It builds the whole registry (so every latest
version must pass `pack validate`, match its manifest id, and hold no holdout
files) and checks that every version listed in a pack's `digests.txt` still has
that digest, so a released version cannot be edited in place. Packs without a
`digests.txt` get a warning.

## Building the site

```
symbola site build packs --out site-registry [--base-url https://…/registry]
```

For each pack, it validates the latest version (the build fails if any pack is
invalid) and writes:

```
index.json                                 every pack: id, version, title, license, digest, tarball sha256, summary, files
llms.txt                                   one line per pack, for agents, and where to find build steps
packs/<owner>/<name>/
  latest.tar.gz                            the pack folder, byte-identical on every build
  latest.sha256                            sha256 of the tarball
  pack.md                                  brief, assumptions, obligations, manifest, and a list of the parts
  parts/<component>-v<n>.md                one component's contract, schemas and tests
  parts/<component>-v<n>.tar.gz            that component's contract folder, for `symbola attest`
  llms.txt                                 build steps for a coding agent, then the pack's files
  files/…                                  every file of the pack, raw
  evidence.json                            every attestation beside the pack, checked at build time
  attestations/…                           the attestation files and runner keys, to re-check
  by-digest/<digest>.tar.gz                each older version that some attestation names
```

`index.json` also carries each pack's evidence summary (components with a passing
build, distinct builds, distinct runners, invalid attestations) and its `older`
attested versions.

Static hosts cap the number of files per site (Cloudflare Pages: 20,000 on the
free plan), and the list above grows with every file of every pack. With
`--files-out DIR --files-url URL`, only `index.json`, `llms.txt` and each pack's
`pack.md` and `llms.txt` stay in `--out`; everything else is written to `DIR`, to
upload to a bucket served at `URL`. Links in `pack.md`, the parts and `llms.txt`
then point straight at `URL`, `index.json` names it as `files_url`, and
`symbola pull` downloads from there. The site can redirect the old paths to the
bucket so older CLIs keep working.

## Evidence

Attestations sit beside the pack in `packs/<owner>/<name>/attestations/`, with
the runners' public keys as `*.pub`. For each one, `site build` checks the
signature, checks that the runner's key is published there, and finds the pack
version whose component has the attested contract digest. The pack page shows
an Evidence table: build, result, which version it covers, runner, and a link to
the file. An attestation that fails a check is shown as invalid, never dropped.
The catalog sorts packs by their evidence.

The pack digest is the contract framing ([CONTRACT_FORMAT.md](CONTRACT_FORMAT.md))
over the pack folder with the header `symbolon-pack-v1\n`.

## The site

The packs live in [kausalflow/symbola-registry](https://github.com/kausalflow/symbola-registry).
The website is built from them by `spikinglabs/symbolon-store` and hosted on
Cloudflare Pages at <https://symbola.sh/>. It is an [Astro](https://astro.build)
site over the files above, with [Pagefind](https://pagefind.app) search built at the
same time, so it needs no server. It adds a catalog page with search, a page per
pack (brief, assumptions, obligations by status, evidence, publisher, download
links, file tree), and a rendered view of every file under
`packs/<owner>/<name>/view/<file>/`.

```
site/build.sh OUT ORIGIN BASE     # in spikinglabs/symbolon-store, e.g. dist-site https://symbola.sh /
```

clones the registry, runs `symbola site build` over its packs, then `astro build`
and `pagefind`, and copies the result to `OUT`. Cloudflare runs it on every push to
the site's repository, and the registry's CI triggers it after every merge to its
`main`. Both repositories pin the CLI they use in `.symbolon-version`, so a CLI
change reaches the registry and the site when those pins move.

## Pulling a pack

```
symbola pull acme/invoice-desk [--registry URL-or-folder] [--dest DIR] [--digest DIGEST]
```

`pull` also takes the pack's page link (`symbola pull https://symbola.sh/packs/acme/invoice-desk/`),
and then pulls from the registry that serves the page. It prints the commands to start
building. `pull` takes no version: the registry serves only the latest. The one exception is
re-checking evidence: `symbola pull <id> --digest <pack digest>` downloads an
older version that some attestation names (the pack page links its digest). It downloads the
tarball, checks its sha256 against `latest.sha256` and `index.json`, unpacks it,
and checks the unpacked folder's digest against `index.json`. These checks catch a
broken download, not a dishonest host: the publisher is not verified until packs
carry GitHub provenance. The registry defaults to `$SYMBOLON_REGISTRY`, or <https://symbola.sh>.

An agent that only needs to read a pack can fetch `packs/<owner>/<name>/pack.md`
instead and skip unpacking. It holds everything that applies to the whole pack and
links one `parts/` file per component, so the agent reads only the components it
builds and no file is too big for one read. Data files such as `examples.jsonl`
show their first lines in the part and link the raw file under `files/`.

## Upgrading a build

When a pack has more than one version, the site lists what its latest version
changed, worked out from the two version folders: decisions (obligations) and
assumptions matched by id, components whose contract changed and which of their
files, and a diff of each top-level document such as `PRODUCT.md`. It is written as
`changes.json` and `changes.md` beside the pack, summed up in `index.json` and the
pack's `llms.txt`. `symbola changes OLD NEW` prints the same report for any two pack
folders.

A builder who already built from an earlier version runs, beside their `spec/`:

```
symbola upgrade [SPEC=spec] [--dest spec.new] [--impl impl] [--overrides overrides.toml]
```

It pulls the latest version into `spec.new/` and compares it with `spec/`, the
version the build came from, so the registry does not need to keep that version.
If nothing changed it says so and removes `spec.new/`. Otherwise it writes
`UPGRADE.md`: the changes, the commands that re-check and re-pin each changed
component, and steps for the agent. The agent changes only what the new version
changes, then replaces `spec/` with `spec.new/` and attests again.

A build may depart from the pack on purpose. Record each departure in
`overrides.toml`, by decision id, so an upgrade keeps it:

```toml
[[override]]
id = "search.trash"
reason = "Our library has no trash; deleted papers are gone."
instead = "is:trash matches nothing."
```

`UPGRADE.md` marks each override, and `upgrade` warns when the new version changes
or removes a decision the build overrides, so the agent asks the user instead of
silently undoing the override or ignoring the publisher's change.

## Publisher and support links

Every pack page says who publishes it and links their profile, the owner's GitHub
page unless the manifest says otherwise. Publishers who want to be paid for their
work can add up to five support links (Buy Me a Coffee, GitHub Sponsors, Ko-fi,
and so on), which the page shows as buttons:

```toml
[publisher]
name = "Acme Labs"                       # defaults to the owner
url = "https://acme.example"             # defaults to https://github.com/<owner>
support = [
  { label = "Buy me a coffee", url = "https://buymeacoffee.com/acme" },
  { label = "GitHub Sponsors", url = "https://github.com/sponsors/acme" },
]
```

Links must be `https://`. Money goes straight to the publisher; the registry
takes nothing and handles no payments.

A publisher profile edited on the account page is saved as `publishers/<owner>.toml`
in the registry and wins over `[publisher]` in the manifest, which is frozen with
each released version. It takes the same fields plus a short `bio`.

## Selling a pack

**Not switched on.** For now every pack in the registry is public and free, and
publishers monetize through support links. The code below stays in place for a
later stage.


Add a price to the pack manifest:

```toml
[listing]
price = 1900        # minor units: 19.00
currency = "eur"
```

A priced pack previews only its brief: the site shows the brief, assumptions,
obligations, manifest, evidence and sha256, and `pack.md` names the components
without including them. Add `preview = "full"` under `[listing]` to publish
everything anyway. Its tarball is written to `--private-out` instead of the
public site and is served by the store, a Cloudflare Worker in
`spikinglabs/symbolon-store` (private). The pack page
shows a Buy button; after paying through Stripe, the buyer gets a license token:

```
symbola pull acme/invoice-desk --token sym_…      # or set SYMBOLON_LICENSE
```

`site build` refuses a priced pack unless it is given `--private-out` and
`--store-url`. Deployment steps are in that repository's README.

