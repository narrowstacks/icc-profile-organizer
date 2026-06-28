# ICC Profile Organizer

A smart tool that automatically organizes ICC color profiles, EMX/EMY2 files, and PDFs by printer model and paper brand. Supports flexible configuration, automatic filename parsing, and system profile installation.

Instead of ICC profiles with names like `MOAB Anasazi Canvas PRO-100 MPP.icc`, you will end up with a name like `Canon Pixma PRO-100 - MOAB - Anasazi Canvas.icc`.

This is helpful for businesses or users with multiple printers, in particular those using Adobe products, whose print dialog color profile selection menu is woefully inadequate for those who have multiple printers and use various brands of paper with those printers.

Instead of having an unorganized list ordered by what the paper brand's file naming scheme is, this tool provides an easily readable list of profiles in alphabetical order, ordered by printer manufacturer, printer model, and paper brand in that order.

**📖 [Detailed Configuration Guide →](configuration.md)**

## What It Does

- **Copies** files to `organized-profiles/` (or specified output folder) (original `profiles/` stays unchanged)
- **Standardizes** filenames and ICC profile description names to: `Printer Name - Paper Brand - Paper Type [N].icc`
- **Organizes** into folders: `organized-profiles/Printer/Brand/filename`
- **Normalizes** brand names (`cifa` → `Canson`, `HFA` → `Hahnemuehle`, etc.)
- **Detects** and removes duplicate PDFs via SHA-256 hashing
- **Handles** multi-printer profiles interactively or via preferences

Supports profiles from MOAB, Canson, Hahnemuehle, Red River, EPSON, and more. See [Configuration Guide](configuration.md) for pattern matching details and customization.

## Installation

This project uses [uv](https://docs.astral.sh/uv/) to manage the Python
environment and dependencies.

### Install uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Set up the project

```bash
# Create the virtual environment and install all dependencies from
# pyproject.toml (pinned by uv.lock)
uv sync
```

uv creates and manages the `.venv` for you — there's no need to manually create
or activate a virtual environment. Prefix commands with `uv run` to execute them
inside the project environment.

## Quick Start

### Preview changes (dry-run mode)

Replace `./profiles` with the location of your folder of ICC profiles. The entire directory's contents and folders will be scanned, so no need to put all files in one folder.

```bash
uv run icc-organizer ./profiles
```

### Apply changes

```bash
uv run icc-organizer ./profiles --execute
```

### Interactive mode

Interactive mode will ask you if you want to consolidate the names of a printer type, if an ICC profile states that it's for multiple printers. An example would be the Epson SureColor P7570 and P9570 often sharing identical ICC profiles, but you likely don't own both printers.

```bash
uv run icc-organizer ./profiles --interactive --execute
```

## Command-Line Options

**Common options:**

```bash
# Dry-run preview (safe, no changes)
uv run icc-organizer ./profiles

# Execute changes
uv run icc-organizer ./profiles --execute

# Interactive mode (for multi-printer profiles)
uv run icc-organizer ./profiles --interactive --execute

# Custom output directory
uv run icc-organizer ./profiles --output-dir ./custom-dir --execute

# Detailed file-by-file output
uv run icc-organizer ./profiles --detailed

# Copy to system ICC profile directory
uv run icc-organizer ./profiles --execute --system-profiles
```

**Additional options:** `--profiles-only`, `--pdfs-only`, `--quiet`, `--skip-desc-update`

See the [Configuration Guide](configuration.md) for complete command-line reference.

## Interactive TUI (Config Wizard) - VERY WORK IN PROGRESS

Build and manage configuration interactively instead of manually editing `config.yaml`:

```bash
uv run icc-config-wizard
```

**Features (WIP):**

- **Scan Profiles** - Auto-detect printer/brand from filenames, see detection rate
- **Fix Undetected** - Create mappings for unrecognized profiles with smart suggestions
- **Edit Configuration** - Manage printer names, brand mappings, and remappings
- **Preview Organization** - See how files will be organized before executing

> **Note:** The config wizard TUI is still in early development. The core organization tool (`organize_profiles.py`) is stable and fully featured. The TUI is an optional convenience tool for building configuration, but manual YAML editing is fully supported and reliable.

The TUI includes smart features like pattern reuse and auto-processing to minimize manual work. See the [Configuration Guide](configuration.md) for detailed documentation.

## Output Structure

```text
organized-profiles/
├── Canon Pixma PRO-100/
│   ├── Canson/
│   │   └── Canon Pixma PRO-100 - Canson - Aqua 240.icc
│   └── Moab/
│       └── Canon Pixma PRO-100 - Moab - Anasazi Canvas.icc
├── Epson P900/
│   └── Moab/
└── PDFs/
    ├── Canon Pixma PRO-100/
    └── Epson P900/
```

Original `profiles/` directory remains unchanged.

## System ICC Profile Installation

Copy organized profiles to your system's ICC directory to make them available to all applications.

### macOS

Two options:

- **System directory** (requires admin): `/Library/ColorSync/Profiles`
- **User directory** (no admin): `~/Library/ColorSync/Profiles`

```bash
# Will prompt for system or user directory
uv run icc-organizer ./profiles --execute --system-profiles

# Or use sudo for system directory
sudo uv run icc-organizer ./profiles --execute --system-profiles
```

### Windows

Requires administrator privileges:

```bash
# Run Command Prompt/PowerShell as Administrator, then:
   uv run icc-organizer ./profiles --execute --system-profiles
```

**Note:** Windows uses a flat structure (due to Windows not reading folders inside of the colors directory); macOS preserves folder organization.

## Troubleshooting

**"Could not parse" warnings:**

- Use the TUI's "Fix Undetected" feature or check `profile_organizer.log`
- See [Configuration Guide](configuration.md) for adding custom patterns

**System profile directory issues:**

- **macOS**: Use user directory (`~/Library/ColorSync/Profiles`) or run with `sudo` for system directory
- **Windows**: Run Command Prompt/PowerShell as Administrator

**Multi-printer files:**

- Use `--interactive` mode to set preferences
- Preferences stored in `.profile_preferences.json`

**Profiles not showing in applications:**

- Restart the application or log out/restart your system

See [Configuration Guide](configuration.md) for advanced troubleshooting.

## Logging

All operations are logged to `profile_organizer.log`.
