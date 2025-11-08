# ICC Profile Organizer

A smart tool that automatically organizes ICC color profiles, EMX/EMY2 files, and PDFs by printer model and paper brand. Supports flexible configuration, automatic filename parsing, and system profile installation.

**📖 [Detailed Configuration Guide →](configuration.md)**

## Installation

### Using a Virtual Environment (Recommended)

#### MacOS

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux


# Install dependencies
pip install -r requirements.txt
```

#### Windows

```bash
# Create and activate virtual environment
python3 -m venv venv
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### Quick Install

```bash
pip install -r requirements.txt
```

## Quick Start

### Preview changes (dry-run mode)

```bash
python3 organize_profiles.py ./profiles
```

### Apply changes

```bash
python3 organize_profiles.py ./profiles --execute
```

### Interactive mode

```bash
python3 organize_profiles.py ./profiles --interactive --execute
```

## Interactive TUI (Config Wizard) - VERY WORK IN PROGRESS

Build and manage configuration interactively instead of manually editing `config.yaml`:

```bash
python3 config_wizard.py
```

**Features (WIP):**

- **Scan Profiles** - Auto-detect printer/brand from filenames, see detection rate
- **Fix Undetected** - Create mappings for unrecognized profiles with smart suggestions
- **Edit Configuration** - Manage printer names, brand mappings, and remappings
- **Preview Organization** - See how files will be organized before executing

> **Note:** The config wizard TUI is still in early development. The core organization tool (`organize_profiles.py`) is stable and fully featured. The TUI is an optional convenience tool for building configuration, but manual YAML editing is fully supported and reliable.

The TUI includes smart features like pattern reuse and auto-processing to minimize manual work. See the [Configuration Guide](configuration.md) for detailed documentation.

## What It Does

- **Copies** files to `organized-profiles/` (original `profiles/` stays unchanged)
- **Standardizes** filenames to: `Printer Name - Paper Brand - Paper Type [N].icc`
- **Organizes** into folders: `organized-profiles/Printer/Brand/filename`
- **Normalizes** brand names (`cifa` → `Canson`, `HFA` → `Hahnemuehle`, etc.)
- **Detects** and removes duplicate PDFs via SHA-256 hashing
- **Handles** multi-printer profiles interactively or via preferences

Supports profiles from MOAB, Canson, Hahnemuehle, Red River, EPSON, and more. See [Configuration Guide](configuration.md) for pattern matching details and customization.

## Command-Line Options

**Common options:**

```bash
# Dry-run preview (safe, no changes)
python3 organize_profiles.py ./profiles

# Execute changes
python3 organize_profiles.py ./profiles --execute

# Interactive mode (for multi-printer profiles)
python3 organize_profiles.py ./profiles --interactive --execute

# Custom output directory
python3 organize_profiles.py ./profiles --output-dir ./custom-dir --execute

# Detailed file-by-file output
python3 organize_profiles.py ./profiles --detailed

# Copy to system ICC profile directory
python3 organize_profiles.py ./profiles --execute --system-profiles
```

**Additional options:** `--profiles-only`, `--pdfs-only`, `--quiet`, `--skip-desc-update`

See the [Configuration Guide](configuration.md) for complete command-line reference.

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
python3 organize_profiles.py ./profiles --execute --system-profiles

# Or use sudo for system directory
sudo python3 organize_profiles.py ./profiles --execute --system-profiles
```

### Windows

Requires administrator privileges:

```bash
# Run Command Prompt/PowerShell as Administrator, then:
   python organize_profiles.py ./profiles --execute --system-profiles
```

**Note:** Windows uses a flat structure; macOS preserves folder organization.

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
