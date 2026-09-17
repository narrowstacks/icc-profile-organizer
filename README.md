# ICC Profile Organizer

Turns a pile of vendor-named printer profiles into a clean, readable library.

```
MOAB Anasazi Canvas PRO-100 MPP.icc        →  Canon Pixma PRO-100/MOAB/Canon Pixma PRO-100 - MOAB - Anasazi Canvas.icc
ILFORD_EPSCX500_GPGFS_PGPP250.icc          →  Epson P7570/Ilford/Epson P7570 - Ilford - Gold Fibre Silk.icc
HFA_Can6450_MK_PhotoRag308.icc             →  Canon iPF6450/Hahnemuehle/Canon iPF6450 - Hahnemuehle - Photo Rag 308.icc
```

Epson `.emy2` and Canon `.am1x`/`.am1` media presets that ship next to the
profiles are renamed the same way and filed beside them (never edited or
installed). Both the filename **and the description embedded in the ICC file** are
rewritten, so the print dialog in Photoshop, Lightroom, etc. shows one
alphabetical list grouped by printer, then paper brand, then paper — instead
of whatever abbreviation scheme each paper vendor happened to use.

Ships with parsers for MOAB, Canson Infinity, Hahnemuehle, Red River, ILFORD,
Awagami, Breathing Color, Innova, PermaJet and Fotospeed naming schemes plus
the Epson and Canon driver profile sets, and knows ~90 printers' worth of
vendor spellings (`EpP900`, `OEMSCP900`, `P7570-9570`, `x400`, …). Anything
else is a few lines of YAML away ([configuration.md](configuration.md)); the
survey of every vendor's naming lives in
[docs/vendor-filename-survey.md](docs/vendor-filename-survey.md).

## Install

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone git@github.com:narrowstacks/icc-profile-organizer.git
cd icc-profile-organizer
uv sync
```

## Use

```bash
# 1. Preview. Nothing is written. Read the output for "Could not parse" / Unknown.
uv run icc-organizer ~/Downloads/new-profiles --detailed

# 2. Do it. Output goes to a sibling folder: ~/Downloads/organized-profiles
uv run icc-organizer ~/Downloads/new-profiles --execute

# 3. Optionally install into ColorSync (prompts: 1 = /Library, 2 = ~/Library)
uv run icc-organizer ~/Downloads/new-profiles --execute --system-profiles
```

The source folder is scanned recursively and left untouched, except that
byte-identical duplicate PDFs are removed. Re-running is safe: copies
overwrite in place.

Useful flags: `--output-dir`, `--interactive` (choose a printer when one
profile lists several, e.g. P7570/P9570), `--profiles-only`, `--pdfs-only`,
`--skip-desc-update`, `--no-system-profiles-prompt`. `--help` has the rest.

### Output layout

```
organized-profiles/
├── Canon Pixma PRO-100/
│   ├── Ilford/   Canon Pixma PRO-100 - Ilford - Gold Fibre Silk.icc
│   └── MOAB/     Canon Pixma PRO-100 - MOAB - Anasazi Canvas.icc
├── Epson P7570/
│   └── Ilford/   …
└── PDFs/
    └── Epson P7570/   vendor instruction sheets, deduplicated
```

macOS ColorSync keeps this folder structure. Windows' colour directory does not
read subfolders, so `--system-profiles` flattens it there.

## Let an agent do it

This repo is written to be driven by a coding agent (Claude Code, Codex, Cursor
agent, …). [`CLAUDE.md`](CLAUDE.md) / `AGENTS.md` contains a step-by-step
playbook for the whole job — parsing a new vendor's naming scheme, verifying
nothing else regressed, executing, and installing — so you can hand over a
folder and a sentence.

Open the agent in a clone of this repo and say something like:

```
Organize the profiles in ~/Downloads/canson_profiles and install them
for my Epson P7570. Follow the playbook in CLAUDE.md.
```

What a good run looks like: the agent dry-runs, notices any files it can't
name, goes and finds the vendor's legend (embedded descriptions, the bundled
PDF, the vendor's download page), teaches `config.yaml` the new scheme,
proves the existing library is unaffected, then executes and verifies the
result. It should ask you one thing at most: which printer you own when a
vendor ships one profile set for a whole family.

If it produces `Unknown - Unknown - …` files, it skipped the legend step —
point it back at CLAUDE.md.

## Configure

Two YAML files, same schema:

- `src/icc_profile_organizer/defaults.yaml` — shipped printer aliases,
  brands, printer remappings.
- `config.yaml` (repo root) — your overrides **and all filename patterns**.
  A key defined here replaces the packaged one entirely.

The pieces you'll touch:

| Key                 | Does                                                                  |
| ------------------- | --------------------------------------------------------------------- |
| `printer_names`     | canonical printer → every alias vendors use (`EpsSC-P900`, `p900`, …) |
| `printer_remappings`| fold printers you don't own into one you do (`Epson P9500 → P7570`)   |
| `brand_name_mappings` | `cifa` → Canson, `HFA` → Hahnemuehle, …                             |
| `filename_patterns` | how to split a vendor's filename into printer / brand / paper         |
| `code_map`          | per-pattern lookup for abbreviated papers (`GPGFS` → Gold Fibre Silk) |

Full reference, worked examples and the pattern engine's rules:
[configuration.md](configuration.md).

## Troubleshooting

- **`Could not parse` / files under `Unknown/`** — the filename scheme is not
  configured yet. Check `profile_organizer.log`, then add an alias or
  pattern ([configuration.md](configuration.md)), or hand it to an agent.
- **Keeps asking which printer** — run once with `--interactive`; answers are
  saved next to the source files in `.profile_preferences.json`.
- **Profiles don't appear in the app** — restart the app; for
  `/Library/ColorSync/Profiles` you need `sudo`, `~/Library/…` you don't.
- **Config wizard** (`uv run icc-config-wizard`) is an early WIP TUI; editing
  the YAML by hand is the supported path.

## License

MIT — see [LICENSE](LICENSE).
