# Configuration Guide

This guide covers the configuration system for the ICC Profile Organizer, including the `config.yaml` structure, filename pattern matching, and advanced features.

**Quick Links:**

- [Back to README](README.md) - Installation and quick start
- [Configuration Structure](#configuration-structure)
- [Filename Pattern Matching](#filename-pattern-matching)
- [Features](#features)

## Configuration Structure

The organizer uses a two-tier configuration system:

1. **`defaults.yaml`** - Base configuration with default printer names, brands, and mappings
2. **`config.yaml`** (optional) - Your custom overrides and filename patterns

If `config.yaml` is not present, the organizer will use the defaults from `defaults.yaml`. Any values in `config.yaml` will override the corresponding defaults.

### defaults.yaml

The `defaults.yaml` file contains the base configuration that ships with the organizer. It includes:

- **Printer name mappings** - Common printer aliases for Canon, Epson, and other brands
- **Brand name mappings** - Variations for Canson, Hahnemuehle, MOAB, etc.
- **Paper brands** - List of recognized paper manufacturers
- **Printer remappings** - Consolidation rules for similar printer models

You can edit `defaults.yaml` to add your own defaults, or create a `config.yaml` file to override specific values without modifying the defaults.

**Tip:** Keep `defaults.yaml` as your baseline configuration and use `config.yaml` for project-specific or temporary overrides.

### 1. Printer Name Mappings

Consolidate printer aliases to canonical names. This allows the organizer to recognize various ways a printer might be named in profile filenames.

```yaml
printer_names:
  Canon Pixma PRO-100:
    - PRO-100
    - Pro-100
    - CanPro-100
    - pixmapro100
  Epson P900:
    - P900
    - SC-P900
    - EpsSC-P900
    - p900
```

### 2. Brand Name Mappings

Normalize paper brand variations to canonical names.

```yaml
brand_name_mappings:
  Canson:
    - cifa
    - CIFA
    - canson
  Hahnemuehle:
    - HFA
    - hfa
  MOAB:
    - MOAB
    - Moab
    - moab
```

### 3. Paper Brands

List of recognized paper brands.

```yaml
paper_brands:
  - Moab
  - Canson
  - Hahnemuehle
  - Red River
```

### 4. Printer Remappings

Remap profiles from one printer to another. Useful for consolidating similar printer models or when upgrading equipment.

```yaml
printer_remappings:
  "Epson P700": "Epson P900"
  "Canon iPF8400": "Canon iPF6450"
```

### 5. Filename Patterns

Define how to parse different filename formats. See [Filename Pattern Matching](#filename-pattern-matching) below for details.

## Filename Pattern Matching

The organizer uses a flexible pattern-based system to parse filenames. Patterns are evaluated in **priority order** (highest first).

### How It Works

When a pattern matches, it extracts:

- **Printer name** - Matched against configured printer aliases
- **Paper brand** - Matched and normalized using brand mappings
- **Paper type** - Extracted and formatted (CamelCase separation, brand removal)

### Default Patterns

#### 1. MOAB Profiles (Priority: 100)

Handles MOAB brand profiles with positional paper type extraction.

**Format:** `MOAB [PaperType...] [Printer] [Code]`

**Examples:**

- `MOAB Anasazi Canvas PRO-100 MPP.icc` → Printer: Canon Pixma PRO-100, Brand: MOAB, Type: Anasazi Canvas
- `MOAB Lasal Gloss Matte P7570-P9570 ECM.icc` → Printer: Epson P7570, Brand: MOAB, Type: Lasal Gloss Matte
- `MOAB+Lasal+Gloss+PRO-100+OGP.icc` → Printer: Canon Pixma PRO-100, Brand: MOAB, Type: Lasal Gloss

**Features:**

- Case-insensitive prefix matching
- Plus signs automatically normalized to spaces
- Handles hyphenated printer models

#### 2. EPSON SC- EMY2 Files (Priority: 90)

Handles EPSON SureColor EMY2 documentation files.

**Format:** `EPSON SC-[Model] [Brand] [PaperType...]`

**Example:**

- `EPSON SC-P900 Moab Entrada Rag Bright 190.icc` → Printer: Epson P900, Brand: MOAB, Type: Entrada Rag Bright 190

#### 3. Canson/CIFA Profiles (Priority: 80)

Handles Canson/CIFA profiles with underscore-delimited structure.

**Format:** `cifa_[Printer]_[PaperType...]`

**Example:**

- `cifa_pixmapro100_baryta2_310.icc` → Printer: Canon Pixma PRO-100, Brand: Canson, Type: Baryta 2 310

**Features:**

- Underscore-delimited fields
- "cifa" automatically normalized to "Canson"

#### 4. Hahnemuehle (HFA) Profiles (Priority: 85)

Handles Hahnemuehle profiles with multiple prefix variants.

**Format:** `HFA[Variant]_[Printer]_[MK/PK]_[PaperType...]`

**Variants:** `HFA_`, `HFAPhoto_`, `HFAMetallic_`

**Examples:**

- `HFA_Can6450_MK_PhotoRag308.icc` → Printer: Canon iPF6450, Brand: Hahnemuehle, Type: Photo Rag 308
- `HFAPhoto_EpsSC-P900_PK_GlossyFine.icc` → Printer: Epson P900, Brand: Hahnemuehle, Type: Glossy Fine

**Features:**

- Multiple prefix variants automatically detected
- Hahnemuehle brand name removed from paper type strings
- MK/PK markers automatically stripped

#### 5. Red River Papers (Priority 75-74)

Handles Red River Papers profiles and documentation files.

**Format (ICC Profiles):** `RR [PaperType...] [PrinterInfo]`

**Format (EMY2 Documentation):** `Red River Paper_RR [PaperType]`

**Supported Printer Models:**

- Epson P7570 & P9570 - `RR [Type] Ep 7570-9570` or `RR [Type] P9570 P7570`
- Epson P900 - `RR [Type] EpP900` or `RR [Type] Ep P900`
- Canon Pixma PRO-100 - `RR [Type] CanPRO-100` or `RR [Type] Can PRO-100`
- Canon iPF6400 - `RR [Type] Can IPF6400` or `RR [Type] Can iPFX400`

**Examples:**

- `RR Arctic Polar Luster Ep 7570-9750.icc` → Printer: Epson P7570, Brand: Red River, Type: Arctic Polar Luster
- `RR Palo Duro Matte Canvas P9570 P7570.icc` → Printer: Epson P7570, Brand: Red River, Type: Palo Duro Matte Canvas
- `Red River Paper_RR Aurora Natural 250.emy2` → Printer: Unknown, Brand: Red River, Type: Aurora Natural 250

#### 6. Fallback Printer Detection (Priority: 10)

Last resort pattern that searches for any printer key in the filename.

**Format:** `[AnyText][PrinterKey][AnyText]`

### Adding Custom Patterns

You can add new filename patterns to `config.yaml`. Patterns are defined in the `filename_patterns` section:

```yaml
filename_patterns:
  - name: my_custom_format
    priority: 75 # Process after MOAB/EPSON, before CIFA
    description: "My custom format"
    prefix: "PREFIX_" # Pattern prefix to match
    prefix_case_insensitive: true # Match any case variant
    delimiter: "_" # Field separator character
    structure: # How to extract fields after prefix
      - field: printer
        position: 0 # First part is printer
      - field: paper_type
        position: "1+" # Rest are paper type
    brand_value: "MyBrand" # Fixed brand for this pattern
    paper_type_processing:
      format: true # Apply CamelCase separation
      remove_brand: null # Optional: remove brand name from paper type
```

### Pattern Structure Reference

#### Pattern Definition Fields

- **name** (string, required): Unique identifier for the pattern
- **priority** (int, required): Processing order (higher = earlier). Range: 0-100
- **description** (string): Human-readable description
- **prefix** (string or null): Text the filename must start with; null for no prefix requirement
- **prefix_case_insensitive** (bool): Whether prefix matching ignores case
- **delimiter** (string): Character used to split filename parts (default: " ")
- **variants** (list): Multiple prefix options for same pattern (used by HFA pattern)
- **structure** (list): Field definitions specifying how to extract printer, brand, paper_type
- **brand_value** (string or null): Fixed brand for this pattern; null to extract from filename
- **paper_type_processing** (object):
  - **format** (bool): Apply CamelCase separation and title case formatting
  - **remove_brand** (string or null): Brand name to strip from paper type

#### Field Definition Options

Fields in the structure can specify extraction in multiple ways:

```yaml
structure:
  # Fixed position extraction
  - field: printer
    position: 0 # Extract part at index 0

  # Position ranges
  - field: paper_type
    position: "2+" # Extract parts from index 2 onward

  # Special positions
  - field: paper_type
    position: "before_printer" # Everything before the printer key

  - field: code
    position: "after_printer" # Everything after the printer key

  # Search-based extraction
  - field: printer
    match_type: "key_search" # Search parts for printer keys

  - field: printer
    match_type: "substring" # Case-insensitive substring search

  - field: paper_type
    position: "remaining" # Everything except the found printer key
```

### Prefix Variants

Some patterns need multiple prefix options:

```yaml
- name: hfa_profiles
  prefix: "HFA" # Main prefix indicator
  variants: # Multiple variant prefixes
    - prefix: "HFAMetallic_"
      prefix_length: 12 # Characters to remove from filename
    - prefix: "HFAPhoto_"
      prefix_length: 9
    - prefix: "HFA_"
      prefix_length: 4
```

### Processing Order

Patterns are evaluated in order of priority (highest first). Example:

1. MOAB Profiles (priority: 100)
2. EPSON SC- (priority: 90)
3. HFA (priority: 85)
4. CIFA (priority: 80)
5. Red River Papers (priority: 75)
6. Fallback (priority: 10)

### Automatic Processing

Once a pattern matches, the organizer automatically:

1. **Normalizes printer names** - Uses `printer_names` mappings
2. **Normalizes brand names** - Uses `brand_name_mappings`
3. **Formats paper type** - CamelCase separation, brand removal if configured
4. **Applies remappings** - Uses `printer_remappings` to consolidate printers

### Example: Adding a Canon MP Series Pattern

Suppose you have Canon MP printer profiles with naming like:

`MP4000_PhotoProGloss_120.icc` → Canon imagePROGRAF MP4000, Brand: Unknown, Type: Photo Pro Gloss 120

Add this pattern to `config.yaml`:

```yaml
filename_patterns:
  # ... existing patterns ...

  - name: canon_mp_profiles
    priority: 75 # Between EPSON and HFA
    description: "Canon imagePROGRAF MP series"
    prefix: "MP"
    prefix_case_insensitive: false
    delimiter: "_"
    structure:
      - field: printer
        position: 0
      - field: paper_type
        position: "1+"
    brand_value: "Unknown"
    paper_type_processing:
      format: true
```

Then add the printer to your `printer_names`:

```yaml
printer_names:
  Canon imagePROGRAF MP4000:
    - MP4000
    - MP4000S
  Canon imagePROGRAF MP6000:
    - MP6000
```

## Multi-Printer Profile Handling

Some profiles work with multiple printers (e.g., `MOAB Anasazi Canvas Matte P7570-P9570 ECM.icc`).

### How Multi-Printer Handling Works

1. First time seeing a combo, you're prompted to choose a printer (in interactive mode)
2. Your choice is saved as a global rule in `.profile_preferences.json`
3. Future files with the same combo use your choice automatically

Example `.profile_preferences.json`:

```json
{
  "P7570-P9570": "Epson P7570",
  "P900-P950": "Epson P900"
}
```

### Interactive Mode

Use the `--interactive` flag to enable prompting for multi-printer profiles:

```bash
python3 organize_profiles.py ./profiles --interactive
```

## Command-Line Options Reference

Complete list of command-line options:

```bash
# View help
python3 organize_profiles.py --help

# Basic operations
python3 organize_profiles.py ./profiles                          # Dry-run preview
python3 organize_profiles.py ./profiles --execute                # Execute changes
python3 organize_profiles.py ./profiles --interactive            # Interactive mode

# Output control
python3 organize_profiles.py ./profiles --output-dir ./custom-dir --execute
python3 organize_profiles.py ./profiles --detailed               # Show each file transformation
python3 organize_profiles.py ./profiles --quiet                  # Suppress output

# Selective processing
python3 organize_profiles.py ./profiles --profiles-only --execute  # Only profiles
python3 organize_profiles.py ./profiles --pdfs-only --execute      # Only PDFs

# ICC profile descriptions
python3 organize_profiles.py ./profiles --skip-desc-update --execute  # Skip description update

# System profile installation
python3 organize_profiles.py ./profiles --execute --system-profiles           # Copy to system
python3 organize_profiles.py ./profiles --execute --no-system-profiles-prompt  # Skip prompt
```

## Features

✅ **Interactive TUI** - Build and manage configuration with an easy-to-use terminal interface

✅ **Generalized Pattern Matching** - Define custom filename parsing patterns in config.yaml without code changes

✅ **Smart Parsing** - Auto-detects and parses profiles from MOAB, EPSON, Canson, Hahnemuehle, Red River, and custom formats

✅ **Flexible Field Extraction** - Position-based, range-based, and search-based field extraction

✅ **Duplicate Handling** - SHA-256 hash-based PDF duplicate detection

✅ **Multi-Printer Support** - Interactive or rule-based handling

✅ **System Profile Installation** - Copy organized profiles to system ICC directories (macOS & Windows)

✅ **Safe Operations** - Dry-run by default, no modifications without `--execute`

✅ **Flexible Configuration** - Optional YAML config with sensible defaults and pattern definitions

✅ **Detailed Logging** - All operations logged to `profile_organizer.log`

## Advanced Troubleshooting

### "Could not parse" warnings

- Some files may not be automatically recognized
- Check `profile_organizer.log` for details
- Use the TUI's "Fix Undetected" feature to create mappings
- Or add a custom pattern to `config.yaml`

### Multi-printer files keep prompting

- Verify `.profile_preferences.json` exists and contains the rule
- Try deleting preference files and recreating rules
- Use `--interactive` mode to set preferences

### Want to change a printer choice

- Edit `.profile_preferences.json` directly
- Or delete the file and rerun with `--interactive`

### System Profile Directory Issues

**macOS: "No write permission" when choosing system directory:**

- The system directory `/Library/ColorSync/Profiles` requires admin access
- Choose option 2 (User Directory) instead, which doesn't require admin
- Or run with `sudo`: `sudo python3 organize_profiles.py ./profiles --execute --system-profiles`
- One-time setup to avoid sudo: `sudo chown -R $(whoami) /Library/ColorSync/Profiles`

**Windows: "Elevated Privileges Required" error:**

- Windows requires administrator privileges to write to the system profile directory
- Right-click Command Prompt/PowerShell → "Run as administrator"
- Then run: `python organize_profiles.py ./profiles --execute --system-profiles`

**Profiles aren't showing up in applications after copying:**

- macOS: Restart the application or restart your computer
- Windows: Some applications cache profiles on startup; restart them
- Try logging out and back in (macOS) or restarting (Windows) for guaranteed refresh

## Fallback Behavior

If `config.yaml` is missing or PyYAML isn't installed, the organizer automatically uses built-in defaults. PyYAML is included in `requirements.txt`, so install it via:

```bash
pip install -r requirements.txt
```
