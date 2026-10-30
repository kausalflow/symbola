---
name: symbola-build
description: Find and build software from a Symbola pack (symbola.sh). Use when the user shares a symbola.sh pack link or an owner/name pack id, asks to build, rebuild or upgrade a pack (update a build to its latest version), or wants a pack for some kind of software.
---

# Building software from a Symbola pack

A pack on [symbola.sh](https://symbola.sh) is a piece of software shipped as its
decisions: a product description (`PRODUCT.md`), a brief, assumptions, the
decisions a builder could get wrong, and components with examples and checks.
You build the software from the pack, in the language the user wants.

## Find a pack

If the user has no pack yet, read https://symbola.sh/llms.txt (one line per
pack) or https://symbola.sh/catalog.json, and suggest the packs that fit. A
pack's own page is `https://symbola.sh/packs/<owner>/<name>/`.

## Build it

Every pack has its exact steps at
`https://symbola.sh/packs/<owner>/<name>/llms.txt`, under "Build this pack".
Fetch that file and follow it: it names the pack's components and anything
special about them. Ask the user only for the language if they have not named
one. In outline:

1. Install the CLI (Python 3.11+): `uv tool install symbola` (or
   `pipx install symbola`). Not `pip install symbolon`: that PyPI name is
   another project.
2. Download the pack: `symbola pull <owner>/<name> --dest spec`. A pack page
   link works in place of the id.
3. Read `spec/AGENTS.md` and follow it. Build only from `spec/`: don't look for
   the original product's source, the registry repository (it holds holdout
   tests) or other builds. If the pack has `spec/PRODUCT.md`, build that whole
   product in the user's stack, with the components as its core, not a demo
   page around the components.
4. Build each component in its own folder and run its checks as you go,
   fixing what fails:

       symbola impl-init impl/<component> --contract spec/components/<component>/versions/<n>
       symbola test spec/components/<component>/versions/<n> impl/<component>

5. When every component passes, run `symbola keygen` once, then
   `symbola attest spec/components/<component>/versions/<n> impl/<component> -o attestations/<component>.json`
   for each component. On macOS, attest needs Docker running; `symbola test`
   runs the same checks without it.

You are done when every flow in `spec/PRODUCT.md` works and attest reports
PASSED for every component. Write open questions and the readings you chose in
`NOTES.md`. When you depart from the pack on purpose, because the user asked for it, add
an entry to `overrides.toml` beside `spec/` (`[[override]]` with `id`, the
decision id, `reason`, and optionally `instead`), so a later upgrade keeps it.

Packs released before the CLI was renamed say
`symbolon <command>`: run `symbola <command>` instead. Every command is
described at https://kausalflow.github.io/symbola/cli/.

## Upgrade a build

When the user asks to update a build to the pack's latest version, run
`symbola upgrade` beside `spec/`. If it says "up to date", tell the user. If
not, it unpacks the new version into `spec.new/` and writes `UPGRADE.md`;
follow it:

1. Change only what the new version changes, and leave the rest of the build,
   including the user's own changes, as it is.
2. Make the build follow each changed or added decision, except decisions in
   `overrides.toml`. Where the new version changes a decision the build
   overrides, ask the user whether to keep the override.
3. Re-run the checks of each changed component against `spec.new/`, fix what
   fails, and re-pin it with `symbola impl-init <impl> --contract <contract> --repin`.
4. Check the flows in `PRODUCT.md` that changed.
5. Replace `spec/` with `spec.new/`, attest the changed components again, and
   add what you changed to `NOTES.md`.
