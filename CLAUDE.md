# CLAUDE.md

Guidance for agents working in this repository. `AGENTS.md` is a symlink to
this file. User-facing docs: [README.md](README.md) (usage) and
[configuration.md](configuration.md) (full config/pattern reference).

## What this tool does

`icc-organizer` copies ICC/ICM printer profiles, their EMY2/AM1X media
presets (and vendor PDFs) from a
messy source tree into `Printer/Brand/` folders, renaming each file **and its
embedded ICC description** to:

```
<Printer> - <Brand> - <Paper Type>.icc      e.g.  Epson P7570 - Ilford - Gold Fibre Silk.icc
```

The point is a readable, alphabetically grouped list in Photoshop/Lightroom
print dialogs. Source files are never modified; the only deletion is of
byte-identical duplicate PDFs in the source tree.

## Layout

```
src/icc_profile_organizer/
  organize_profiles.py   CLI (`icc-organizer`): scan → match → rename → copy → update descriptions
  config_wizard.py       TUI (`icc-config-wizard`), WIP; manual YAML editing is the reliable path
  defaults.yaml          shipped printer aliases / brands / remappings (NO filename patterns)
  lib/pattern_matching.py  PatternMatcher, format_paper_type(), split_paper_code()
  lib/pattern_types.py     FilenamePattern / FieldDefinition / PaperTypeProcessing dataclasses
  lib/printer_keys.py      PrinterKeyIndex: bounded, longest-wins printer alias lookup
  lib/config_manager.py    loads defaults.yaml + ./config.yaml (+ vendor-legends), builds the matcher
  lib/…                    file scanning, copy, PDF hashing, ICC description rewrite, ColorSync install
config.yaml              user overrides — in this repo it is where ALL filename patterns live
vendor-legends/*.yaml    long paper-code legends (Ilford, Innova, PermaJet, Red River) pulled
                         into patterns via `code_map_file`
docs/vendor-filename-survey.md  what each vendor's download actually looks like (Sept 2026)
profiles/                source profiles (gitignored, user data)
organized-profiles/      output (gitignored, regenerable)
profile_organizer.log    written to the cwd on every run
```

Run everything with `uv run …` after `uv sync`. Tooling is uv + `uv_build`;
there is no `requirements.txt`.

## Config: what is not obvious from reading it

- **`config.yaml` replaces top-level keys wholesale.** If it defines
  `printer_names`, the packaged `printer_names` are ignored entirely, not
  merged. Consequence: a new printer alias or brand must be added to **both**
  `config.yaml` and `src/icc_profile_organizer/defaults.yaml` (the shared
  section of both files is identical; keep it that way).
- **Printer aliases are bounded, case-insensitive substrings; longest wins.**
  `P900` matches `EpP900`/`OEMSCP900` but never `P9000`; `PRO-1000` beats
  `PRO-100`. Aliases may contain the delimiter (`CANpro-2_4_6_21_41_61`).
  So one spelling per token is enough — no case variants needed.
- **Family tokens map to the smallest model**, `printer_remappings` collapse
  onto owned printers (`P7570-9570`, `x400`, `EPP700`, `PRO-2000-6000`).
- **Paper names must be ASCII** — the ICC `desc` tag writer replaces anything
  else with `?` and the verify step (description == stem) then fails.
  `Albrecht Duerer`, `Hahnemuehle`.
- **Printer-less names get their printer from the folder.** emy2/am1x
  presets like `RR Polar Matte.am1` resolve via the vendor zip's folder name
  (`organize_profiles._printer_from_parent_dirs`). Keep downloads in their
  own folder under `profiles/`; a flat dump loses that.
- **Filename patterns come from exactly one place.** `config.yaml`'s
  `filename_patterns` if present, else the hardcoded list in
  `config_manager._build_default_pattern_matcher()`. `defaults.yaml` carries
  none. New patterns go in `config.yaml`.
- Output dir defaults to a sibling of the *source* dir
  (`<source>/../organized-profiles`), despite what `--help` says.
- `printer_remappings` collapse printers the user does not own into one they
  do (P7500/P9500 → P7570, P700 → P900). Keep that: one folder per physical
  printer.
- `.profile_preferences.json` / `.profile_choices.json` in the source dir
  remember `--interactive` answers.

## Naming conventions (enforced by config, not code)

- Paper type is the **vendor's marketing name**, title case, with the brand
  stripped (`Photo Rag 308`, not `Hahnemuehle Photo Rag 308`).
- Weights stay as bare numbers (`Smooth Cotton Sprite 280`), never `280gsm`.
- **Driver media codes are dropped** (`…_PGPP250`, `MPP`, `MK`/`PK`). The
  filename identifies the paper; the media setting lives in the vendor's PDF.
- Printer folders use the short established style: `Epson P7570`,
  `Canon Pixma PRO-100`, `Canon iPF6450`, `Canon imagePROGRAF PRO-2000`.
  When a vendor ships one profile set for a family (PRO-2000/4000/6000…), the
  canonical name is whichever model the user owns — ask.
- Abbreviated vendor codes (Ilford `GPGFS`) resolve through a per-pattern
  `code_map`; see configuration.md → *Paper Code Maps*.

## Playbook: the user hands you a folder of new profiles

This is the task this repo exists for. Work through every step; the job is
done when the dry run shows **zero `Could not parse` / `Unknown` entries**
and the execute run has been verified.

1. **Dry-run first, always.**
   `uv run icc-organizer <dir> --detailed --profiles-only` and read every
   line. Anything landing in `Unknown/`, or a paper type that is still a
   code, is unparsed.
2. **Find the vendor's legend before inventing names.** In order:
   embedded ICC descriptions (`PIL.ImageCms.ImageCmsProfile(f).profile.profile_description`),
   a PDF bundled with the download, then the vendor's profile-download page
   (their per-printer listing is authoritative — e.g. Ilford's picker is an
   iframe at `ilford.com/ilford-profiles/get-related-profiles.php`; the
   installation PDF's legend was incomplete). Use the vendor's names verbatim.
3. **Teach the config, in this order of preference:** a printer alias
   (`printer_names`, both files) → a brand alias (both files; also used by
   `brand_search`) → a `code_map` entry on an existing pattern (or in its
   `vendor-legends/<vendor>.yaml`) → a `strip_regex` → a new
   `filename_patterns` entry. A new pattern needs `prefix` (or
   `prefix_regex`), `delimiter`, a `structure`, and `brand_value`; copy the
   closest existing one. Priority: vendor-prefixed patterns 74–100,
   prefix-less `require_code_map` patterns 71–72, fallback is 10. Before
   inventing a pattern, check `docs/vendor-filename-survey.md` — every major
   vendor's shape is already there.
4. **Regression-check the existing corpus.** Capture
   `uv run icc-organizer ./profiles --detailed --profiles-only 2>&1 | grep -E ' -> |Could not' | sort`
   before and after your change (use `git stash` for "before") and `diff`
   them. The only acceptable differences are the new files.
5. **Merge and execute.** Move the new folder under `profiles/`, then
   `uv run icc-organizer ./profiles --execute --no-system-profiles-prompt`.
   Copies overwrite in place, so re-running over everything is safe.
6. **Verify the output**, not just the log: every new file opens with
   `ImageCms`, its `profile_description` equals its filename stem, and no
   `[2]` collision suffixes appeared.
7. **Install for the user if asked.** `--system-profiles` prompts on stdin
   (`1` system / `2` user); from an agent, `cp -p` the new
   `<Printer>/<Brand>/` folders into `~/Library/ColorSync/Profiles/`
   preserving the layout (that is what the installer does on macOS). Copy
   only what is new; never touch other people's profiles in there.
8. **Commit config + code + docs.** `profiles/` and `organized-profiles/`
   are ignored and must stay that way. Record the vendor legend source in
   the pattern's comment so the next agent can re-derive it.

## Verification

There is no test suite. The regression diff in step 4 is the test; run it for
any change to `pattern_matching.py`, `printer_keys.py`, `config_manager.py`,
or the YAML. For a wider check, the Sept 2026 vendor corpus (~14k filenames)
can be rebuilt with the fetch recipes in `docs/vendor-filename-survey.md` and
run through `ConfigManager.match_filename()`. For
code paths that copy, run `--execute` against a scratch copy of `profiles/`
into a scratch `--output-dir` and confirm `Files copied == Files processed`
and the on-disk counts match.

## Quality gates

Format before lint before run. Keep modules under ~300 lines where
practical. No secrets, no `.env`, nothing from `profiles/` in git.
