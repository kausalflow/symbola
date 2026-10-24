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
symbolon keygen                                        # once: your publisher key
symbolon release spec --registry ../registry/packs     # in a clone of the registry
```

`release` validates the pack, sets its manifest version to the next free number,
copies it to `packs/<owner>/<name>/versions/<n>/`, and writes
`packs/<owner>/<name>/signatures/<n>.json`, a DSSE envelope over
`{pack, version, digest}`. Releasing unchanged content does nothing. The first
release under an owner writes `packs/<owner>/publisher.pub`; after that, only the
same key can release under that owner. Then commit and open a pull request.

## Submission checks

```
symbolon site check packs
```

CI runs this on every pull request. It builds the whole registry (so every latest
version must pass `pack validate`, match its manifest id, and hold no holdout
files) and, for owners with a `publisher.pub`, checks that the latest version's
signature matches its digest. Owners without a key are reported as unsigned, a
warning for now.

## Building the site

```
symbolon site build packs --out site-registry [--key publisher.key] [--base-url https://…/registry]
```

For each pack, it validates the latest version (the build fails if any pack is
invalid) and writes:

```
index.json                                 every pack: id, version, title, license, digest, tarball sha256, summary, files
llms.txt                                   one line per pack, for agents
packs/<owner>/<name>/
  latest.tar.gz                            the pack folder, byte-identical on every build
  latest.sha256                            sha256 of the tarball
  latest.sig.json                          with --key: a DSSE envelope over {pack, version, digest, tarball_sha256}
  pack.md                                  the whole pack in one Markdown file
  llms.txt                                 the pack's files, for agents
  files/…                                  every file of the pack, raw
```

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
symbolon pull acme/invoice-desk [--registry URL-or-folder] [--dest DIR] [--trust publisher.pub]
```

`pull` takes no version: the registry serves only the latest. It downloads the
tarball, checks its sha256 against `latest.sha256` and `index.json`, unpacks it,
and checks the unpacked folder's digest against `index.json`. With `--trust`, it
also requires a valid signature from that public key over the same digest and
sha256. The registry defaults to `$SYMBOLON_REGISTRY`, or the kausalflow site.

An agent that only needs to read a pack can fetch `packs/<owner>/<name>/pack.md`
instead and skip unpacking.
