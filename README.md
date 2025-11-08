# ICC Profile Organizer

A smart tool that automatically organizes ICC color profiles, EMX/EMY2 files, and PDFs by printer model and paper brand, with support for flexible printer name mappings and profile remappings.

## Setup

### Using a Virtual Environment (Recommended)

It's recommended to use a Python virtual environment to isolate dependencies:

```bash
# Create a virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### Quick Install

Without a virtual environment:

```bash
pip install -r requirements.txt
```

> **Note:** The script can run without these dependencies, but features like configuration file support (PyYAML) and image metadata reading (Pillow) will be unavailable.

## Quick Start

### Preview changes (dry-run mode, no files changed or moved)

```bash
python3 organize_profiles.py ./profiles
```

### Apply changes

```bash
python3 organize_profiles.py ./profiles --execute
```

### Interactive mode (for multi-printer profiles)

```bash
python3 organize_profiles.py ./profiles --interactive
```

## Interactive TUI (Config Builder)

### Build Configuration Interactively

Instead of manually editing `config.yaml`, use the interactive Terminal User Interface to build and manage your configuration:

```bash
python3 profile_config_tui.py
```

### Features

The TUI provides four main screens:

#### 1. **Scan Profiles** 📁
- Browse to your profiles folder
- Auto-detects all ICC/ICM/EMY2 files
- Displays extracted printer, brand, and paper type information
- Shows preview of how files will be renamed
- Saves discovered mappings to your config

#### 2. **Edit Configuration** ⚙️
- **Printer Names tab**: Manage printer aliases and canonical names
- **Brand Mappings tab**: Normalize brand variations (cifa → Canson, etc.)
- **Paper Brands tab**: Manage recognized paper brands
- **Printer Remappings tab**: Define which printers map to others
- Full YAML editing with syntax highlighting
- Real-time save to `config.yaml`

#### 3. **Fix Undetected Profiles** 🔧
When scanning, profiles that don't match known patterns are highlighted as "undetected". The TUI helps you define mappings for these:
- Shows detection rate and summary of undetected profiles
- Click "Fix Undetected" to create bindings for new printers/brands
- Smart pattern extraction suggests printer/brand names from filenames
- **Smart mapping reuse**: Once you define a mapping for a printer pattern (e.g., "PRO100"), it automatically applies to all other profiles with the same pattern
- Shows "[💾 Using saved mapping for 'PRO100']" when reusing cached mappings
- **Full auto-processing**: When BOTH printer AND brand are cached, the TUI:
  - Auto-extracts paper type from filename (e.g., "Canvas Matte" from `CANON_PRO100_Canvas_Matte.icc`)
  - Automatically saves the profile without any user interaction
  - Shows "[⚡ Auto-processing: 'PRO100' (printer + brand cached)]"
  - Moves to next profile instantly
- Three ways to process:
  - **Save Mapping**: Define one profile, move to next
  - **Apply to All**: Auto-apply current mapping to all remaining profiles with same printer pattern (fast bulk processing)
  - **Skip**: Move to next without saving
- **Preview screen**: After processing all profiles, see a summary table showing:
  - All mappings with printer, brand, and extracted paper type
  - Which profiles were auto-processed vs manually defined (⚡ vs ✓)
  - Total count breakdown before saving to config.yaml
- New mappings are saved directly to `config.yaml`
- Summary shows breakdown: "✓ Saved 25 mapping(s) (5 manual + 20 auto-processed)"

#### 4. **Preview Organization** 👁️
- Enter a profiles folder path
- See a tree view of how files will be organized
- Displays final filenames: `Printer - Brand - Type.icc`
- Organize into: `organized-profiles/Printer/Brand/filename`
- Preview without making changes

#### 5. **Keyboard Navigation**
- Arrow keys: Navigate menus and tables
- Tab/Shift+Tab: Move between fields
- Enter: Confirm selections
- Escape: Go back to previous screen
- Ctrl+S: Save configuration (in editor)
- Q: Quit application

### Example Workflow

1. Start the TUI:
   ```bash
   python3 profile_config_tui.py
   ```

2. Click "Scan Profiles" to auto-detect profiles in a folder
   - Select your `./profiles` directory
   - Review auto-detected printer/brand assignments
   - See detection rate (e.g., "✓ 75/100 detected (75.0%) | ⚠️ 25 undetected")

3. **(NEW)** If there are undetected profiles:
   - Click "Fix Undetected" to create mappings for unknown printers/brands
   - Review smart suggestions extracted from filenames
   - For the first profile of each pattern:
     - Enter printer name, brand, and paper type
     - Click **"Apply to All"** to auto-apply to all remaining profiles with same pattern
     - Example: Define "CANON_PRO100_Canvas.icc" → "Canon Pixma PRO-100" / "Moab"
     - All other "CANON_PRO100_*.icc" profiles automatically get the same mapping
   - For subsequent patterns:
     - If both printer AND brand are cached from a previous pattern:
       - TUI shows "[⚡ Auto-processing: 'PRO100' (printer + brand cached)]"
       - Paper type is auto-extracted from filename
       - Profile is automatically saved without any user input
       - Instantly moves to next profile
     - Otherwise, follow same process as step 1
   - Result example with 50 profiles:
     - You define 3 printer patterns manually
     - 47 profiles auto-processed automatically (94% automation)
   - **Preview screen** shows before final save:
     - Table with all mappings
     - Clearly marks which were auto-processed (⚡) vs manual (✓)
     - Breakdown: "Total: 50 | Manual: 3 | Auto-Processed: 47"
   - Click "Save & Done" to save all mappings to config.yaml

4. After fixing undetected profiles:
   - Click "Save & Next" to see the preview
   - The preview screen shows the final organized structure

5. Optional: Go back to "Edit Config" to manually adjust:
   - Printer aliases
   - Brand name mappings
   - Remapping rules

6. Use the updated configuration with the main organizer:
   ```bash
   python3 organize_profiles.py ./profiles --execute
   ```

### Quick Reference

```bash
# Start interactive config builder
python3 profile_config_tui.py

# Start with custom config path
python3 profile_config_tui.py --config /path/to/config.yaml

# Get help
python3 profile_config_tui.py --help
```

## What It Does

- **Copies** files to `organized-profiles/` (original `profiles/` stays unchanged)
- **Standardizes** filenames to: `Printer Name - Paper Brand - Paper Type [N].icc`
- **Organizes** into folders: `organized-profiles/Printer/Brand/filename`
- **Normalizes** brand names (`cifa` → `Canson`, `HFA` → `Hahnemuehle`, etc.)
- **Detects** and removes duplicate PDFs via SHA-256 hashing
- **Handles** multi-printer profiles interactively or via preferences

## Configuration

The organizer uses an optional `config.yaml` file for:

1. **Printer Name Mappings** - Consolidate aliases to canonical names

   ```yaml
   printer_names:
     Canon Pixma PRO-100:
       - PRO-100
       - Pro-100
       - CanPro-100
       - pixmapro100
   ```

2. **Brand Name Mappings** - Normalize paper brand variations

   ```yaml
   brand_name_mappings:
     Canson:
       - cifa
       - CIFA
       - canson
   ```

3. **Paper Brands** - List of recognized brands

   ```yaml
   paper_brands:
     - Moab
     - Canson
     - Hahnemuehle
   ```

4. **Printer Remappings** - Remap profiles to a different printer
   ```yaml
   printer_remappings:
     "Epson SureColor P700": "Epson SureColor P900"
   ```

5. **Filename Patterns** - Generalized pattern matching for parsing various filename formats

## Generalized Filename Pattern Matching

The organizer uses a flexible pattern-based system to parse filenames. This allows you to define how profiles from different manufacturers are parsed without modifying any Python code.

### How It Works

The system evaluates filename patterns in **priority order** (highest priority first). When a pattern matches, it extracts:
- **Printer name** - Matched against your configured printer aliases
- **Paper brand** - Matched and normalized using brand mappings
- **Paper type** - Extracted and formatted (CamelCase separation, brand removal)

### Default Patterns

The organizer comes with built-in patterns for common formats:

#### 1. **MOAB Profiles** (Priority: 100)
Handles MOAB brand profiles with positional paper type extraction.

**Format:** `MOAB [PaperType...] [Printer] [Code]`

**Examples:**
- `MOAB Anasazi Canvas PRO-100 MPP.icc` → Printer: Canon Pixma PRO-100, Brand: MOAB, Type: Anasazi Canvas
- `MOAB Lasal Gloss Matte P7570-P9570 ECM.icc` → Printer: Epson P7570, Brand: MOAB, Type: Lasal Gloss Matte
- `MOAB+Lasal+Gloss+PRO-100+OGP.icc` → Printer: Canon Pixma PRO-100, Brand: MOAB, Type: Lasal Gloss

**Features:**
- Case-insensitive prefix matching (handles "MOAB", "Moab", "moab")
- Plus signs automatically normalized to spaces
- Handles hyphenated printer models (e.g., P7570-P9570)

#### 2. **EPSON SC- EMY2 Files** (Priority: 90)
Handles EPSON SureColor EMY2 documentation files.

**Format:** `EPSON SC-[Model] [Brand] [PaperType...]`

**Example:**
- `EPSON SC-P900 Moab Entrada Rag Bright 190.icc` → Printer: Epson P900, Brand: MOAB, Type: Entrada Rag Bright 190

#### 3. **Canson/CIFA Profiles** (Priority: 80)
Handles Canson/CIFA profiles with underscore-delimited structure.

**Format:** `cifa_[Printer]_[PaperType...]`

**Example:**
- `cifa_pixmapro100_baryta2_310.icc` → Printer: Canon Pixma PRO-100, Brand: Canson, Type: Baryta 2 310

**Features:**
- Underscore-delimited fields
- "cifa" automatically normalized to "Canson"

#### 4. **Hahnemuehle (HFA) Profiles** (Priority: 85)
Handles Hahnemuehle profiles with multiple prefix variants.

**Format:** `HFA[Variant]_[Printer]_[MK/PK]_[PaperType...]`

**Variants:** `HFA_`, `HFAPhoto_`, `HFAMetallic_`

**Examples:**
- `HFA_Can6450_MK_PhotoRag308.icc` → Printer: Canon iPF6450, Brand: Hahnemuehle, Type: Photo Rag 308
- `HFAPhoto_EpsSC-P900_PK_GlossyFine.icc` → Printer: Epson P900, Brand: Hahnemuehle, Type: Glossy Fine

**Features:**
- Multiple prefix variants automatically detected
- Hahnemuehle brand name removed from paper type strings
- MK/PK markers automatically stripped from output

#### 5. **Red River Papers** (Priority: 75)
Handles Red River Papers profiles for multiple printer models with flexible format variations.

**Format:** `RR [PaperType...] [PrinterInfo]`

**Supported Printer Models:**
- **Epson P7570 & P9570** - `RR [Type] Ep 7570-9570` or `RR [Type] P9570 P7570`
- **Epson P900** - `RR [Type] EpP900` or `RR [Type] Ep P900` or `RR [Type] Ep SureColor P900`
- **Canon Pixma PRO-100** - `RR [Type] CanPRO-100` or `RR [Type] Can PRO-100`
- **Canon iPF6400** - `RR [Type] Can IPF6400` or `RR [Type] Can iPFX400`

**Examples:**
- `RR Arctic Polar Luster Ep 7570-9750.icc` → Printer: Epson P7570, Brand: Red River, Type: Arctic Polar Luster
- `RR Palo Duro Matte Canvas P9570 P7570.icc` → Printer: Epson P7570, Brand: Red River, Type: Palo Duro Matte Canvas
- `RR Arctic Polar Luster EpP900.icc` → Printer: Epson P900, Brand: Red River, Type: Arctic Polar Luster
- `RR Palo Duro Baryta CanPRO-100.icc` → Printer: Canon Pixma PRO-100, Brand: Red River, Type: Palo Duro Baryta
- `RR APLuster Can iPFX400.icc` → Printer: Canon iPF6450, Brand: Red River, Type: AP Luster Can

**Features:**
- "RR" prefix detection (not case-insensitive as it's distinctive)
- Flexible printer format handling across all supported models
- Removes "Ep" prefix from paper types
- Supports hyphenated and space-separated printer models
- Handles both manufacturer prefixes (Ep, Can) and explicit printer models
- Automatically maps generic iPFX400 to Canon iPF6450

#### 6. **Fallback Printer Detection** (Priority: 10)
Last resort pattern that searches for any printer key in the filename.

**Format:** `[AnyText][PrinterKey][AnyText]`

**Example:**
- Any filename containing a known printer key (case-insensitive substring match)

### Adding Custom Patterns

You can add new filename patterns to `config.yaml` without modifying Python code. Patterns are defined in the `filename_patterns` section:

```yaml
filename_patterns:
  - name: my_custom_format
    priority: 75                      # Process after MOAB/EPSON, before CIFA
    description: "My custom format"
    prefix: "PREFIX_"                 # Pattern prefix to match
    prefix_case_insensitive: true     # If true, match any case variant
    delimiter: "_"                    # Field separator character
    structure:                        # How to extract fields after prefix
      - field: printer
        position: 0                   # First part is printer
      - field: paper_type
        position: "1+"                # Rest are paper type
    brand_value: "MyBrand"            # Fixed brand for this pattern
    paper_type_processing:
      format: true                    # Apply CamelCase separation
      remove_brand: null              # Optional: remove brand name from paper type
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
  - **remove_brand** (string or null): Brand name to strip from paper type (e.g., "Hahnemuehle")

#### Field Definition Options

Fields in the structure can specify extraction in multiple ways:

```yaml
structure:
  # Fixed position extraction
  - field: printer
    position: 0              # Extract part at index 0

  # Position ranges
  - field: paper_type
    position: "2+"           # Extract parts from index 2 onward

  # Special positions
  - field: paper_type
    position: "before_printer"   # Everything before the printer key

  - field: code
    position: "after_printer"    # Everything after the printer key

  # Search-based extraction
  - field: printer
    match_type: "key_search"     # Search parts for printer keys

  - field: printer
    match_type: "substring"      # Case-insensitive substring search

  - field: paper_type
    position: "remaining"        # Everything except the found printer key
```

### Prefix Variants (for patterns like HFA)

Some patterns need multiple prefix options:

```yaml
- name: hfa_profiles
  prefix: "HFA"                    # Main prefix indicator
  variants:                        # Multiple variant prefixes
    - prefix: "HFAMetallic_"
      prefix_length: 12            # Characters to remove from filename
    - prefix: "HFAPhoto_"
      prefix_length: 9
    - prefix: "HFA_"
      prefix_length: 4
```

### Processing Order

Patterns are evaluated in order of priority (highest first). The first pattern that matches is used. Example:

```
1. MOAB Profiles (priority: 100)
2. EPSON SC- (priority: 90)
3. HFA (priority: 85)
4. CIFA (priority: 80)
5. Red River Papers (priority: 75)
6. Fallback (priority: 10)
```

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
    priority: 75                      # Between EPSON and HFA
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

### Fallback Behavior

If `config.yaml` is missing or PyYAML isn't installed, the organizer automatically uses built-in defaults. PyYAML is included in `requirements.txt`, so install it via:

```bash
pip install -r requirements.txt
```

## Command-Line Options

```bash
# View help
python3 organize_profiles.py --help

# Dry-run preview
python3 organize_profiles.py ./profiles

# Execute changes
python3 organize_profiles.py ./profiles --execute

# Specify custom output directory
python3 organize_profiles.py ./profiles --output-dir ./my-organized-profiles --execute

# Interactive mode
python3 organize_profiles.py ./profiles --interactive

# Detailed output
python3 organize_profiles.py ./profiles --detailed

# Only organize profiles (skip PDFs)
python3 organize_profiles.py ./profiles --profiles-only --execute

# Only organize PDFs (skip profiles)
python3 organize_profiles.py ./profiles --pdfs-only --execute

# Suppress output
python3 organize_profiles.py ./profiles --quiet

# Copy to system ICC profile directory (prompts if available)
python3 organize_profiles.py ./profiles --execute --system-profiles

# Skip the system profile prompt
python3 organize_profiles.py ./profiles --execute --no-system-profiles-prompt
```

## Multi-Printer Profile Handling

Some profiles work with multiple printers (e.g., `MOAB Anasazi Canvas Matte P7570-P9570 ECM.icc`).

### How it works:

1. First time seeing a combo, you're prompted to choose a printer
2. Your choice is saved as a global rule in `.profile_preferences.json`
3. Future files with the same combo use your choice automatically

Example `.profile_preferences.json`:

```json
{
  "P7570-P9570": "Epson SureColor P7570",
  "P900-P950": "Epson SureColor P900"
}
```

## Output Structure

```
organized-profiles/
├── Canon Pixma PRO-100/
│   ├── Canson/
│   │   ├── Canon Pixma PRO-100 - Canson - aqua240.icc
│   │   └── ...
│   └── Moab/
│       ├── Canon Pixma PRO-100 - Moab - Anasazi Canvas.icc
│       └── ...
├── Epson SureColor P900/
│   ├── Canson/
│   └── Moab/
└── PDFs/
    ├── Canon Pixma PRO-100/
    ├── Epson SureColor P900/
    └── ...
```

Your original `profiles/` directory remains unchanged.

## System ICC Profile Directory Support

After organizing profiles, you can automatically copy them to your system's ICC profile directory, making them available to all applications.

### macOS - Choose Your Installation Scope

On macOS, you have two options:

**Option 1: System Directory** (requires admin)

- Path: `/Library/ColorSync/Profiles`
- Profiles available to all users on the computer
- Requires `sudo` or admin password
- Recommended for shared computers

**Option 2: User Directory** (no admin needed)

- Path: `~/Library/ColorSync/Profiles`
- Profiles available only to your user account
- No admin privileges required
- Recommended for personal use

#### macOS Usage:

```bash
# Normal flow - prompts you to choose system or user directory
python3 organize_profiles.py ./profiles --execute

# Output will show:
# ICC Profile Directory Options
# 1. System Directory (requires admin)
#    Path: /Library/ColorSync/Profiles
# 2. User Directory (no admin needed)
#    Path: ~/Library/ColorSync/Profiles
# Choose directory (1/2) or 'skip':
```

If you choose the system directory and don't have permission, the program will suggest:

```bash
sudo python3 organize_profiles.py ./profiles --execute --system-profiles
```

#### macOS: Set Ownership (Optional One-Time Setup)

To avoid needing `sudo` every time, you can change directory ownership:

```bash
# Change system color profiles directory to your user
sudo chown -R $(whoami) /Library/ColorSync/Profiles

# Verify ownership changed
ls -ld /Library/ColorSync/Profiles
```

After this, you can copy profiles without `sudo`.

### Windows - Administrator Required

On Windows, the system ICC profile directory requires administrator privileges:

**System Directory Path:** `C:\Windows\System32\spool\drivers\color`

#### Windows Usage:

```bash
# Without admin - will error with clear instructions
python3 organize_profiles.py ./profiles --execute --system-profiles

# Output will show:
# Elevated Privileges Required
# ERROR: Cannot write to Windows system ICC profile directory
# Path: C:\Windows\System32\spool\drivers\color
# This directory requires Administrator privileges.
# To fix this, please:
#   1. Open Command Prompt or PowerShell as Administrator
#   2. Run the program again with the --system-profiles flag
```

#### Windows: Run with Admin Privileges

1. **Open Command Prompt or PowerShell as Administrator:**

   - Press `Win + X` and select "Command Prompt (Admin)" or "PowerShell (Admin)"
   - Or: Right-click Command Prompt/PowerShell → "Run as administrator"

2. **Run the script:**

   ```bash
   python organize_profiles.py ./profiles --execute --system-profiles
   ```

3. **Note:** Profiles are copied to a flat structure (no subdirectories) as required by Windows.

### Command-Line Flags for System Profiles

- `--system-profiles` - Automatically copy to system ICC directory without prompting
- `--no-system-profiles-prompt` - Skip the system profile prompt entirely
- Default behavior (no flags) - Prompts if system directory is accessible

### Profile Directory Organization

The programs respects each OS's requirements:

**macOS:** Preserves your organized folder structure

```
~/Library/ColorSync/Profiles/
├── Canon Pixma PRO-100/
│   ├── Canson/
│   │   ├── Canon Pixma PRO-100 - Canson - aqua240.icc
│   │   └── ...
│   └── Moab/
└── Epson P900/
    └── ...
```

**Windows:** Uses flat structure (no subdirectories)

```
C:\Windows\System32\spool\drivers\color\
├── Canon Pixma PRO-100 - Canson - aqua240.icc
├── Canon Pixma PRO-100 - Moab - Anasazi Canvas.icc
├── Epson P900 - Moab - Entrada Rag.icc
└── ...
```

## Features

✅ **Interactive TUI** - Build and manage configuration with an easy-to-use terminal interface
✅ **Generalized Pattern Matching** - Define custom filename parsing patterns in config.yaml without code changes
✅ **Smart Parsing** - Auto-detects and parses profiles from MOAB, EPSON, Canson, Hahnemuehle, and custom formats
✅ **Flexible Field Extraction** - Position-based, range-based, and search-based field extraction
✅ **Duplicate Handling** - SHA-256 hash-based PDF duplicate detection
✅ **Multi-Printer Support** - Interactive or rule-based handling
✅ **System Profile Installation** - Copy organized profiles to system ICC directories (macOS & Windows)
✅ **Safe Operations** - Dry-run by default, no modifications without `--execute`
✅ **Flexible Configuration** - Optional YAML config with sensible defaults and pattern definitions
✅ **Detailed Logging** - All operations logged to `profile_organizer.log`

## Troubleshooting

**"Could not parse" warnings:**

- Some files may not be automatically recognized
- Check `profile_organizer.log` for details

**Multi-printer files keep prompting:**

- Verify `.profile_preferences.json` exists and contains the rule
- Try deleting preference files and recreating rules

**Want to change a printer choice:**

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

**Permission denied when copying to user directory (macOS):**

- Ensure the `~/Library/ColorSync` directory exists and you own it
- The script will create it automatically if it doesn't exist
- If issues persist, create it manually: `mkdir -p ~/Library/ColorSync/Profiles`

## Logging

All operations are logged to `profile_organizer.log` with timestamps and detailed information.
