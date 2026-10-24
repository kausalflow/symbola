# Pack registry

The registry is a static website. A folder of packs (`packs/<owner>/<name>/versions/<n>/`)
is turned into plain files that any web host can serve, and `symbolon pull` reads
them. There is no server. Only the **latest** version of each pack is published;
older versions stay in the registry's folders and git history so that attestations
naming them can still be re-checked.

## Making a pack

```
symbolon pack init acme/invoice-desk          # creates spec/ next to your code
symbolon pack validate spec
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

The repository ships a Claude Code skill, [`skills/symbolon-pack/SKILL.md`](https://github.com/kausalflow/symbolon/blob/main/skills/symbolon-pack/SKILL.md).
Copy it into your project's `.claude/skills/` (or point another coding tool at it
from your `AGENTS.md`). It tells the agent to update `spec/` in the same change as
the code whenever you make a decision a builder could not have guessed, state a
fact about the world, or leave something open, and to run `pack validate` after
each change.

## Releasing

```
symbolon release spec --registry ../registry/packs     # in a clone of the registry
```

`release` validates the pack, sets its manifest version to the next free number,
copies it to `packs/<owner>/<name>/versions/<n>/`, and appends the version's
digest to `packs/<owner>/<name>/digests.txt`. Releasing unchanged content does
nothing. Then commit and open a pull request.

There are no publisher keys. Who may release under an owner is decided by who
can merge into the registry; once packs move to their publishers' own
repositories as GitHub Releases, GitHub's provenance attestation will identify
the publisher and `pull` will check it (distribution design v0.5, section 5.2).
Ed25519 keys are only for runners that sign attestations.

## Submission checks

```
symbolon site check packs
```

CI runs this on every pull request. It builds the whole registry (so every latest
version must pass `pack validate`, match its manifest id, and hold no holdout
files) and checks that every version listed in a pack's `digests.txt` still has
that digest, so a released version cannot be edited in place. Packs without a
`digests.txt` get a warning.

## Building the site

```
symbolon site build packs --out site-registry [--base-url https://…/registry]
```

For each pack, it validates the latest version (the build fails if any pack is
invalid) and writes:

```
index.json                                 every pack: id, version, title, license, digest, tarball sha256, summary, files
llms.txt                                   one line per pack, for agents
packs/<owner>/<name>/
  latest.tar.gz                            the pack folder, byte-identical on every build
  latest.sha256                            sha256 of the tarball
  pack.md                                  brief, assumptions, obligations, manifest, and a list of the parts
  parts/<component>-v<n>.md                one component's contract, schemas and tests
  parts/<component>-v<n>.tar.gz            that component's contract folder, for `symbolon attest`
  llms.txt                                 the pack's files, for agents
  files/…                                  every file of the pack, raw
  evidence.json                            every attestation beside the pack, checked at build time
  attestations/…                           the attestation files and runner keys, to re-check
  by-digest/<digest>.tar.gz                each older version that some attestation names
```

`index.json` also carries each pack's evidence summary (components with a passing
build, distinct builds, distinct runners, invalid attestations) and its `older`
attested versions.

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

`registry-site/` is an [Astro](https://astro.build) site over those files, with
[Pagefind](https://pagefind.app) search built at the same time, so it needs no server.
It adds a catalog page with search, a page per pack (brief, assumptions, obligations
by status, download links, file tree), and a rendered view of every file under
`packs/<owner>/<name>/view/<file>/`.

```
registry-site/build.sh OUT ORIGIN BASE     # e.g. site/registry https://kausalflow.github.io /symbolon/registry
```

runs `symbolon site build` into `registry-site/public/`, then `astro build` and
`pagefind`, and copies the result to `OUT`. The docs workflow runs it on every push
to `main` and publishes the result at <https://kausalflow.github.io/symbolon/registry/>;
PR previews get their own copy.

## Pulling a pack

```
symbolon pull acme/invoice-desk [--registry URL-or-folder] [--dest DIR] [--digest DIGEST]
```

`pull` takes no version: the registry serves only the latest. The one exception is
re-checking evidence: `symbolon pull <id> --digest <pack digest>` downloads an
older version that some attestation names (the pack page links its digest). It downloads the
tarball, checks its sha256 against `latest.sha256` and `index.json`, unpacks it,
and checks the unpacked folder's digest against `index.json`. These checks catch a
broken download, not a dishonest host: the publisher is not verified until packs
carry GitHub provenance. The registry defaults to `$SYMBOLON_REGISTRY`, or the kausalflow site.

An agent that only needs to read a pack can fetch `packs/<owner>/<name>/pack.md`
instead and skip unpacking. It holds everything that applies to the whole pack and
links one `parts/` file per component, so the agent reads only the components it
builds and no file is too big for one read. Data files such as `examples.jsonl`
show their first lines in the part and link the raw file under `files/`.

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
[`store/`](https://github.com/kausalflow/symbolon/tree/main/store). The pack page
shows a Buy button; after paying through Stripe, the buyer gets a license token:

```
symbolon pull acme/invoice-desk --token sym_…      # or set SYMBOLON_LICENSE
```

`site build` refuses a priced pack unless it is given `--private-out` and
`--store-url`. Deployment steps are in `store/README.md`.

