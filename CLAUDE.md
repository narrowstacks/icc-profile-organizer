# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ICC Profile Organizer** is a Python utility that intelligently organizes ICC color profiles, EMX/EMY2 files, and PDFs by printer model and paper brand. It renames files to a standardized format and organizes them into a hierarchical folder structure, making profile selection easier in applications like Adobe Creative Suite.

Key features:

- Flexible pattern-based filename parsing to extract printer and paper information
- Configurable brand/printer name normalization and remapping
- Interactive TUI for configuration management (config_wizard.py)
- Command-line interface for batch organization (organize_profiles.py)
- PDF duplicate detection via SHA-256 hashing
- Optional system profile installation (macOS/Windows)

## Architecture

The project uses a `src/` layout: the importable package is
`src/icc_profile_organizer/`, containing the two CLI modules and the `lib/`
core-library subpackage. The CLI modules import the library via
`from icc_profile_organizer.lib import ...`.

### Core Modules (src/icc_profile_organizer/lib/)

- **pattern_matching.py** - Unified pattern matching engine. Defines `FilenamePattern`, `PatternVariant`, `PatternMatcher`, and the module-level `format_paper_type()`. Patterns are sorted by priority and evaluated sequentially.
- **config_manager.py** - Loads two-tier configuration (packaged defaults.yaml → cwd config.yaml override). Builds the PatternMatcher and exposes `match_filename()` plus the flattened name mappings (`PRINTER_NAMES`, `BRAND_NAME_MAPPINGS`, `PAPER_BRANDS`, `PRINTER_REMAPPINGS`).
- **icc_utils.py** - ICCProfileUpdater class for reading/writing ICC profile descriptions
- **file_scanning.py** - find_profile_files() finds ICC/ICM/EMY2 files in a directory tree
- **filename_utils.py** - generate_new_filename() constructs standardized output names (filename parsing lives in ConfigManager.match_filename())
- **file_operations.py** - execute_copy_operations() performs actual file copying with directory creation
- **pdf_utils.py** - PDF duplicate detection using SHA-256 hashing (hash_file, find_pdf_duplicates, is_duplicate_file, get_duplicate_paths, delete_duplicate_files)
- **printer_utils.py** - Interactive printer selection for multi-printer profiles, printer remapping application
- **system_profiles.py** - OS-specific profile installation (macOS ColorSync, Windows system directory)
- **user_preferences.py** - JSON-based persistence of user's interactive choices
- **reporting.py** - Summary output formatting

### Entry Points

Both are exposed as console scripts via `[project.scripts]` (run with
`uv run icc-organizer` / `uv run icc-config-wizard`).

- **src/icc_profile_organizer/organize_profiles.py** (`icc-organizer`) - Main CLI. Creates ProfileOrganizer instance, runs analysis, prompts for interactive decisions, executes operations
- **src/icc_profile_organizer/config_wizard.py** (`icc-config-wizard`) - Interactive TUI for configuration building (currently WIP). Scans profiles, identifies undetected files, guides pattern creation

The shipped **defaults.yaml** lives inside the package
(`src/icc_profile_organizer/defaults.yaml`) and is loaded via
`importlib.resources`. The optional user **config.yaml** is read from the
current working directory.

## Configuration System

Configuration is two-tier:

1. **defaults.yaml** - Shipped defaults with printer aliases, brand mappings, paper brands, printer remappings, and filename patterns
2. **config.yaml** - User overrides (optional, same structure as defaults)

Configuration is loaded via ConfigManager.load() which merges defaults with overrides, then initializes PatternMatcher.

Pattern matching is priority-based (higher priority evaluated first). Each pattern defines:

- Prefix and delimiter
- Field definitions (which parts extract printer/brand/paper type)
- Paper type processing (CamelCase formatting, brand removal)
- Optional variants (for prefixes with multiple forms)

## Common Development Tasks

### Running the Organizer

```bash
# Preview changes (dry-run)
uv run icc-organizer ./profiles

# Execute changes
uv run icc-organizer ./profiles --execute

# Interactive mode (for multi-printer profiles)
uv run icc-organizer ./profiles --interactive --execute

# Custom output directory
uv run icc-organizer ./profiles --output-dir ./custom --execute

# Detailed output (file-by-file instead of summary)
uv run icc-organizer ./profiles --detailed

# Copy to system profiles
uv run icc-organizer ./profiles --execute --system-profiles

# Only profiles (skip PDFs)
uv run icc-organizer ./profiles --profiles-only --execute

# Only PDFs (skip profiles)
uv run icc-organizer ./profiles --pdfs-only --execute
```

### Configuration Wizard (TUI)

```bash
uv run icc-config-wizard
```

Currently WIP. Provides:

- Scan profiles and detect undetected files
- Fix undetected files by creating mappings/patterns
- Edit configuration interactively
- Preview organization before execution

### Building and Installing

This project uses [uv](https://docs.astral.sh/uv/) with the `uv_build` backend.

```bash
# Sync the environment (creates .venv, installs deps, writes/updates uv.lock)
uv sync

# Add or remove a dependency (updates pyproject.toml and uv.lock)
uv add <package>
uv remove <package>

# Build distribution (sdist + wheel into dist/)
uv build

# Install the built distribution elsewhere with uv (or pip)
uv pip install dist/icc_profile_organizer-*.whl
```

### Dependencies

Dependencies are declared in `pyproject.toml` (`[project.dependencies]`) and
pinned in `uv.lock`. There is no `requirements.txt`.

- PyYAML >= 6.0 - Configuration file parsing
- Pillow >= 12.0.0 - ICC profile description manipulation
- textual >= 6.5.0 - TUI framework for config_wizard
- rich >= 14.2.0 - Colored console output

## Testing Strategy

There are no automated tests in the repository currently. Manual testing is done by:

1. Creating test profile files with various naming schemes
2. Running organize_profiles.py in dry-run mode to preview changes
3. Validating output organization and filename generation

When adding features or fixing bugs:

- Test with profiles directory containing representative files
- Run both dry-run and execute modes
- Verify ICC profile descriptions are updated correctly
- Test interactive mode with multi-printer profiles
- Test on both macOS and Windows for system profile installation

## Key Implementation Details

### Pattern Matching Flow

1. User calls organize_profiles.py with profiles directory
2. ProfileOrganizer.run() calls find_profile_files() to scan directory
3. For each profile, extract_printer_and_paper_info() uses ConfigManager's PatternMatcher
4. PatternMatcher.match() evaluates patterns in priority order until match found
5. generate_new_filename() creates standardized output filename
6. If --interactive and multiple printers detected, get_printer_name_interactive() prompts user
7. UserPreferences.save_choice() persists selection to .profile_preferences.json
8. execute_copy_operations() copies files with new names to organized-profiles/

### Multi-Printer Profile Handling

Some profiles work with multiple printers. When detected:

- If --interactive flag: prompt user to select canonical printer name
- If user previously chose printer for same file: use saved preference
- If not interactive: use find_printer_candidates() to pick first match

### PDF Duplicate Detection

Uses hash_file() to SHA-256 hash all PDFs. Duplicates grouped by hash in pdf_duplicates dict. Prompts user for each group to keep one copy, deletes others.

### System Profile Installation

Checks OS (CURRENT_OS in system_profiles.py):

- macOS: Copy to ~/Library/ColorSync/Profiles or /Library/ColorSync/Profiles (with sudo)
- Windows: Copy to system Colors directory (requires admin privileges)

## Logging

All operations logged to profile_organizer.log at root level. ConfigManager also sets up logging for its own operations. Log level defaults to INFO, can be controlled via logging configuration.

## File Organization Output Structure

```text
organized-profiles/
├── {Printer Name}/
│   └── {Paper Brand}/
│       └── {Standardized Filename}.icc
└── PDFs/
    └── {Printer Name}/
        └── {PDF files}
```

For Windows system profiles: flat structure (profiles directly in system directory) due to Windows ColorSync limitations.

### ast-grep vs ripgrep (quick guidance)

**Use `ast-grep` when structure matters.** It parses code and matches AST nodes, so results ignore comments/strings, understand syntax, and can **safely rewrite** code.

- Refactors/codemods: rename APIs, change import forms, rewrite call sites or variable kinds.
- Policy checks: enforce patterns across a repo (`scan` with rules + `test`).
- Editor/automation: LSP mode; `--json` output for tooling.

**Use `ripgrep` when text is enough.** It's the fastest way to grep literals/regex across files.

- Recon: find strings, TODOs, log lines, config values, or non‑code assets.
- Pre-filter: narrow candidate files before a precise pass.

### Rule of thumb

- Need correctness over speed, or you'll **apply changes** → start with `ast-grep`.
- Need raw speed or you're just **hunting text** → start with `rg`.
- Often combine: `rg` to shortlist files, then `ast-grep` to match/modify with precision.

### ast-grep Best Practices for Claude Code

**Always start with read-only exploration** before attempting rewrites:

```bash
# Step 1: Search (non-destructive)
ast-grep run -l python -p 'PATTERN' /Users/aaron/GitHub/icc-profile-organizer

# Step 2: Get structured data with --json
ast-grep run -l python -p 'PATTERN' --json /Users/aaron/GitHub/icc-profile-organizer

# Step 3: Only after confirming matches, do rewrites with -r and -U flags
ast-grep run -l python -p 'PATTERN' -r 'REPLACEMENT' -U /Users/aaron/GitHub/icc-profile-organizer
```

**Why this matters for this codebase:**

- ICC Profile Organizer has well-structured Python code with clear function/class boundaries
- ast-grep can reliably find method calls (`$X.method()`), function calls (`function_name($_)`), assignments, and imports
- Meta-variables (e.g., `$X`, `$Y`) capture matched parts with exact line/column positions for later verification
- The `--json` output includes range information useful for validation before making changes

### Pattern Reference & Examples

| Pattern | What It Matches | Example Matches |
|---------|-----------------|-----------------|
| `import $_` | All imports (captures module name) | `import sys`, `import logging` |
| `$X.load()` | Method calls to `.load()` on any object | `config_manager.load()` |
| `$X.execute($$$)` | Method calls with arguments | Any `.execute()` call |
| `$_($FUNC)` | Function calls (captures function name) | `find_profile_files(self.profiles_dir)` |
| `$X = $_.$Y()` | Assignments with chained methods | `self.output_dir = Path(output_dir).resolve()` |
| `def $_($$$):` | Function definitions (captures name + args) | All `def` statements |

**Meta-variable syntax:**

- `$_` = single node wildcard (matches one thing)
- `$$$` = multiple nodes wildcard (matches zero or more things)
- `$X`, `$Y`, `$FUNC` = named captures (accessible in `--json` output via `metaVariables`)

### Snippets

Find structured code (ignores comments/strings):

```bash
ast-grep run -l python -p 'import $X'
```

Find specific function calls with line numbers:

```bash
ast-grep run -l python -p 'find_profile_files($_)' /Users/aaron/GitHub/icc-profile-organizer
```

Get JSON with meta-variable data for programmatic processing:

```bash
ast-grep run -l python -p '$X.load()' --json /Users/aaron/GitHub/icc-profile-organizer
```

Codemod (rename functions) — **only after verifying matches**:

```bash
ast-grep run -l python -p 'def old_name($ARGS)' -r 'def new_name($ARGS)' -U
```

Quick textual hunt:

```bash
rg -n 'print\(' -t py
```

Combine speed + precision:

```bash
rg -l -t py 'old_function\(' | xargs ast-grep run -l python -p 'old_function($A)' -r 'new_function($A)' -U
```

### Mental model

- Unit of match: `ast-grep` = node; `rg` = line.

- False positives: `ast-grep` low; `rg` depends on your regex.
- Rewrites: `ast-grep` first-class; `rg` requires ad‑hoc sed/awk and risks collateral edits.
- Safe workflow: `ast-grep run` (search) → verify with `--json` → `ast-grep run -r -U` (rewrite)
