#!/usr/bin/env python3
"""
Interactive TUI for building and editing ICC profile configuration.
Allows scanning profiles, configuring mappings, and previewing organization.
"""

import sys
import re
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    print("Warning: PyYAML not available. Install with: pip install PyYAML")

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button, Input, Label, DataTable, Header, Footer,
    TextArea, Tabs, TabPane, Tree, OptionList
)
from textual.widgets.option_list import Option
from textual.binding import Binding

# Import existing profile organizer components
sys.path.insert(0, str(Path(__file__).parent))
from organize_profiles import ProfileOrganizer


def extract_potential_printer_name(filename: str) -> Optional[str]:
    """
    Extract potential printer name from filename.
    Looks for common patterns like printer models.
    """
    # Remove extension and common delimiters
    name = Path(filename).stem.replace('+', ' ').replace('_', ' ')

    # Common printer patterns
    patterns = [
        r'(Canon|Epson|HP|Brother|Ricoh|Xerox|Konica)\s*(\w+[\s\w]*?)(?:\s[-–]|\s\d|\.)',
        r'(P\d{3,4}|PRO[-\d]+|iPF\d+|SC-P\d+)',
        r'([A-Z][a-z]+\s+[A-Z][\w\s]*?)(?:\s[-–]|\s\d|$)',
    ]

    for pattern in patterns:
        match = re.search(pattern, name)
        if match:
            return match.group(1).strip()

    # Fallback: first few words that look like a model
    words = name.split()
    if words:
        return words[0]

    return None


def extract_potential_brand(filename: str) -> Optional[str]:
    """
    Extract potential brand name from filename.
    Looks for common paper brand names (not printer names or paper types).

    Distinguishes between:
    - Paper BRANDS: moab, canson, cifa, hahnemuehle, hfa, etc.
    - Printer NAMES: epson, canon, hp, brother, ricoh (should not be returned)
    - Paper TYPES: baryta, rag, lustre, matte, gloss, semi-gloss (should not be returned)
    """
    name = filename.lower().replace('_', ' ').replace('+', ' ')

    # Paper BRANDS (first priority - check at start of filename)
    # These are actual paper manufacturers
    brands = ['moab', 'canson', 'cifa', 'hahnemuehle', 'hfa']

    # Paper TYPE keywords (exclude from brand detection)
    # These are finish/texture descriptors, not brands
    paper_types = ['baryta', 'rag', 'lustre', 'matte', 'gloss', 'semi-gloss']

    # Printer/manufacturer keywords (exclude from brand detection)
    # These are printer/camera manufacturers, not paper brands
    printers = ['epson', 'canon', 'hp', 'brother', 'ricoh', 'nikon']

    # First: Check if filename STARTS with a known brand (highest priority)
    for brand in brands:
        if name.startswith(brand + ' ') or name.startswith(brand + '_'):
            return brand.capitalize() if brand != 'hfa' else 'Hahnemuehle'

    # Second: Look for brand keywords anywhere in filename
    # (excluding paper types and printer names)
    for brand in brands:
        if brand in name:
            # Make sure it's not part of a paper type or printer name
            is_isolated = True
            # Check if it's a substring of another word we should ignore
            for exclude in paper_types + printers:
                if brand in exclude or exclude in brand:
                    is_isolated = False
                    break

            if is_isolated:
                return brand.capitalize() if brand != 'hfa' else 'Hahnemuehle'

    return None


def extract_paper_type_from_filename(filename: str, printer_pattern: Optional[str] = None) -> Optional[str]:
    """
    Extract paper type from filename by removing known patterns.
    Looks for words between printer pattern and extension.
    """
    name = Path(filename).stem.replace('_', ' ').replace('+', ' ')

    # Remove printer pattern if provided
    if printer_pattern:
        # Remove printer pattern (case-insensitive)
        pattern_lower = printer_pattern.lower()
        name_lower = name.lower()
        if pattern_lower in name_lower:
            idx = name_lower.find(pattern_lower)
            # Get text after printer pattern
            name = name[idx + len(printer_pattern):].strip()

    # Common words to remove/clean
    remove_words = ['icc', 'profile', 'canon', 'epson', 'hp', 'brother', 'ricoh']
    words = [w for w in name.split() if w.lower() not in remove_words and len(w) > 1]

    if words:
        return ' '.join(words)

    return None


def group_undetected_by_pattern(undetected: List[Dict]) -> Dict[str, List[Dict]]:
    """Group undetected profiles by extracted printer pattern."""
    grouped = {}

    for profile in undetected:
        printer = extract_potential_printer_name(profile['filename'])
        key = printer or 'Unknown'

        if key not in grouped:
            grouped[key] = []
        grouped[key].append(profile)

    return grouped


class ConfigManager:
    """Manages loading and saving config.yaml files."""

    DEFAULT_CONFIG = {
        'printer_names': {},
        'brand_name_mappings': {},
        'paper_brands': [],
        'printer_remappings': {}
    }

    def __init__(self, config_path: Optional[str] = None):
        """Initialize config manager."""
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path(__file__).parent / 'config.yaml'
        self.config = self.load()

    def load(self) -> Dict:
        """Load config from file or return defaults."""
        if self.config_path.exists() and YAML_AVAILABLE:
            try:
                with open(self.config_path, 'r') as f:
                    config = yaml.safe_load(f) or {}
                    # Ensure all sections exist
                    for key, default_val in self.DEFAULT_CONFIG.items():
                        if key not in config:
                            config[key] = default_val
                    return config
            except Exception as e:
                print(f"Warning: Could not load config: {e}")
                return self.DEFAULT_CONFIG.copy()
        return self.DEFAULT_CONFIG.copy()

    def save(self) -> bool:
        """Save config to file."""
        if not YAML_AVAILABLE:
            print("Error: PyYAML required to save config")
            return False

        try:
            with open(self.config_path, 'w') as f:
                yaml.safe_dump(self.config, f, default_flow_style=False, sort_keys=False)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def get_printer_names(self) -> Dict[str, List[str]]:
        """Get printer names mapping."""
        return self.config.get('printer_names', {})

    def set_printer_names(self, names: Dict[str, List[str]]):
        """Set printer names mapping."""
        self.config['printer_names'] = names

    def get_brand_mappings(self) -> Dict[str, List[str]]:
        """Get brand name mappings."""
        return self.config.get('brand_name_mappings', {})

    def set_brand_mappings(self, mappings: Dict[str, List[str]]):
        """Set brand name mappings."""
        self.config['brand_name_mappings'] = mappings

    def get_paper_brands(self) -> List[str]:
        """Get paper brands list."""
        return self.config.get('paper_brands', [])

    def set_paper_brands(self, brands: List[str]):
        """Set paper brands list."""
        self.config['paper_brands'] = brands

    def get_printer_remappings(self) -> Dict[str, str]:
        """Get printer remappings."""
        return self.config.get('printer_remappings', {})

    def set_printer_remappings(self, remappings: Dict[str, str]):
        """Set printer remappings."""
        self.config['printer_remappings'] = remappings


def scan_profiles_for_detection(folder_path: str) -> tuple[Dict[str, int], Dict[str, int]]:
    """
    Scan a folder of profiles and extract detected printer patterns and brands.

    Returns:
        Tuple of (detected_printers dict, detected_brands dict)
        Each dict maps detected value -> count of occurrences
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        return {}, {}

    detected_printers = {}
    detected_brands = {}

    # Find all profile files
    profile_extensions = ('*.icc', '*.icm', '*.emy2')
    for ext in profile_extensions:
        for profile_file in folder.rglob(ext):
            filename = profile_file.name

            # Extract printer pattern
            printer = extract_potential_printer_name(filename)
            if printer:
                detected_printers[printer] = detected_printers.get(printer, 0) + 1

            # Extract brand
            brand = extract_potential_brand(filename)
            if brand:
                detected_brands[brand] = detected_brands.get(brand, 0) + 1

    return detected_printers, detected_brands


class WelcomeScreen(Screen):
    """Welcome screen with main menu options."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the welcome screen."""
        yield Header()
        yield Container(
            Vertical(
                Label("ICC Profile Config Builder", id="title"),
                Label("", id="subtitle"),
                Label("", id="spacer"),
                Button("📁 Scan Profiles", id="btn-scan", variant="primary"),
                Button("🔗 Configure Mappings", id="btn-mappings"),
                Button("⚙️  Edit Config", id="btn-edit"),
                Button("👁️  Preview Organization", id="btn-preview"),
                Button("❌ Exit", id="btn-exit", variant="error"),
                id="menu-container"
            ),
            id="welcome-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        """When mounted, set focus to first button."""
        self.query_one("#btn-scan", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "btn-scan":
            self.app.push_screen(ScanScreen())
        elif button_id == "btn-mappings":
            self.app.push_screen(MappingConfigStartScreen())
        elif button_id == "btn-edit":
            self.app.push_screen(ConfigEditorScreen())
        elif button_id == "btn-preview":
            self.app.push_screen(PreviewScreen())
        elif button_id == "btn-exit":
            self.app.exit()


class ScanScreen(Screen):
    """Screen for scanning ICC profiles in a directory."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    def __init__(self):
        """Initialize scan screen."""
        super().__init__()
        self.config_manager = ConfigManager()
        self.organizer = None
        self.profiles = []
        self.undetected_profiles = []
        self.detected_count = 0
        self.folder_path = None

    def compose(self) -> ComposeResult:
        """Compose the scan screen."""
        yield Header()
        yield Container(
            Vertical(
                Label("Scan ICC Profiles", id="title"),
                Horizontal(
                    Label("Profile Folder:", id="folder-label"),
                    Input(id="folder-input", placeholder="/path/to/profiles"),
                ),
                Button("Browse & Scan", id="btn-scan-dir", variant="primary"),
                Label("", id="scan-status"),
                Vertical(
                    DataTable(id="profiles-table"),
                    id="table-container"
                ),
                Label("", id="detection-summary"),
                Button("Fix Undetected", id="btn-fix-undetected"),
                Button("Save & Next", id="btn-save-mappings"),
                Button("Back", id="btn-back"),
                id="scan-container"
            ),
            id="main-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        """When mounted, set up the data table."""
        table = self.query_one("#profiles-table", DataTable)
        table.add_columns(
            "Filename",
            "Detected Printer",
            "Brand",
            "Paper Type",
            "Preview Name"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "btn-scan-dir":
            self.scan_profiles()
        elif button_id == "btn-fix-undetected":
            if self.undetected_profiles:
                self.app.push_screen(UndetectedAnalyzerScreen(
                    self.undetected_profiles,
                    self.config_manager,
                    self.organizer,
                    self.folder_path
                ))
            else:
                self.query_one("#detection-summary", Label).update("[yellow]No undetected profiles[/yellow]")
        elif button_id == "btn-save-mappings":
            self.save_mappings()
        elif button_id == "btn-back":
            self.app.pop_screen()

    def scan_profiles(self) -> None:
        """Scan profiles in the selected directory."""
        folder_input = self.query_one("#folder-input", Input)
        folder_path = folder_input.value

        if not folder_path:
            self.query_one("#scan-status", Label).update("[red]Please enter a folder path[/red]")
            return

        try:
            folder_path = Path(folder_path).resolve()
            if not folder_path.exists():
                self.query_one("#scan-status", Label).update(f"[red]Folder not found: {folder_path}[/red]")
                return

            self.folder_path = folder_path

            # Initialize organizer with the profiles directory
            self.organizer = ProfileOrganizer(
                str(folder_path),
                dry_run=True,
                verbose=False
            )

            # Find all ICC profile files
            profile_files = self.organizer._find_profile_files()
            all_files = []
            for file_list in profile_files.values():
                all_files.extend(file_list)

            if not all_files:
                self.query_one("#scan-status", Label).update("[yellow]No ICC profiles found in folder[/yellow]")
                return

            # Populate table with profiles and track undetected
            table = self.query_one("#profiles-table", DataTable)
            table.clear()

            self.profiles = []
            self.undetected_profiles = []
            self.detected_count = 0

            for file_path in sorted(all_files):
                printer, brand, paper_type = self.organizer.extract_printer_and_paper_info(file_path.name)

                preview_name = f"{printer} - {brand} - {paper_type}" if printer and brand else "❌ Undetected"

                table.add_row(
                    file_path.name,
                    printer or "Unknown",
                    brand or "Unknown",
                    paper_type or "Unknown",
                    preview_name,
                    key=str(file_path)
                )

                profile_info = {
                    'path': str(file_path),
                    'filename': file_path.name,
                    'printer': printer,
                    'brand': brand,
                    'paper_type': paper_type
                }
                self.profiles.append(profile_info)

                # Track undetected profiles
                if not printer or not brand:
                    self.undetected_profiles.append(profile_info)
                else:
                    self.detected_count += 1

            # Update detection summary
            total = len(all_files)
            undetected = len(self.undetected_profiles)
            detection_rate = (self.detected_count / total * 100) if total > 0 else 0

            summary = f"[green]✓ {self.detected_count}/{total} detected[/green] ({detection_rate:.1f}%)"
            if undetected > 0:
                summary += f" | [yellow]⚠️ {undetected} undetected[/yellow]"

            self.query_one("#detection-summary", Label).update(summary)
            self.query_one("#scan-status", Label).update(f"[green]Scan complete[/green]")

        except Exception as e:
            self.query_one("#scan-status", Label).update(f"[red]Error: {str(e)}[/red]")

    def save_mappings(self) -> None:
        """Save extracted mappings to config."""
        if not self.profiles:
            self.query_one("#scan-status", Label).update("[red]Please scan profiles first[/red]")
            return

        # Extract unique printers and brands
        printers = set()
        brands = set()

        for profile in self.profiles:
            if profile['printer']:
                printers.add(profile['printer'])
            if profile['brand']:
                brands.add(profile['brand'])

        # Update config with discovered items
        # (In a real implementation, we'd add these as aliases to existing mappings)
        current_brands = set(self.config_manager.get_paper_brands())
        current_brands.update(brands)
        self.config_manager.set_paper_brands(list(current_brands))

        self.config_manager.save()
        self.query_one("#scan-status", Label).update("[green]✓ Mappings saved[/green]")

        # Move to preview screen
        self.app.push_screen(PreviewScreen(self.organizer))

    def action_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()


class UndetectedAnalyzerScreen(Screen):
    """Screen for analyzing and creating mappings for undetected profiles."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, undetected_profiles: List[Dict], config_manager: ConfigManager,
                 organizer: ProfileOrganizer, folder_path: Path):
        """Initialize undetected analyzer screen."""
        super().__init__()
        self.undetected_profiles = undetected_profiles
        self.config_manager = config_manager
        self.organizer = organizer
        self.folder_path = folder_path
        self.grouped = group_undetected_by_pattern(undetected_profiles)

    def compose(self) -> ComposeResult:
        """Compose the analyzer screen."""
        yield Header()
        yield Container(
            Vertical(
                Label("Fix Undetected Profiles", id="title"),
                Label("", id="summary-label"),
                ScrollableContainer(
                    OptionList(id="undetected-list"),
                    id="list-container"
                ),
                Label("", id="status-label"),
                Horizontal(
                    Button("Create Mappings", id="btn-create-mappings", variant="primary"),
                    Button("Back", id="btn-back"),
                ),
                id="analyzer-container"
            ),
            id="main-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        """When mounted, populate the undetected list."""
        summary = f"Found {len(self.undetected_profiles)} undetected profiles"
        self.query_one("#summary-label", Label).update(summary)

        option_list = self.query_one("#undetected-list", OptionList)

        # Add grouped items
        for printer_pattern, profiles in sorted(self.grouped.items()):
            option_list.add_option(
                Option(f"[{printer_pattern}] {len(profiles)} profile(s)", id=printer_pattern)
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "btn-create-mappings":
            self.app.push_screen(CreateMappingsScreen(
                self.undetected_profiles,
                self.config_manager,
                self.organizer,
                self.grouped
            ))
        elif button_id == "btn-back":
            self.app.pop_screen()

    def action_back(self) -> None:
        """Go back to scan screen."""
        self.app.pop_screen()


class CreateMappingsScreen(Screen):
    """Screen for creating manual mappings for undetected profiles."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(self, undetected_profiles: List[Dict], config_manager: ConfigManager,
                 organizer: ProfileOrganizer, grouped: Dict[str, List[Dict]]):
        """Initialize create mappings screen."""
        super().__init__()
        self.undetected_profiles = undetected_profiles
        self.config_manager = config_manager
        self.organizer = organizer
        self.grouped = grouped
        self.current_group_idx = 0
        self.mappings = {}  # Store user-defined mappings by filename
        self.pattern_mappings = {}  # Cache mappings by printer pattern
        self.auto_applied_count = 0  # Track auto-applied mappings
        self.current_pattern = None  # Current profile's extracted pattern
        self.auto_processed_profiles = []  # Profiles auto-processed without user input
        self.current_auto_processed = False  # Is current profile auto-processed?

    def compose(self) -> ComposeResult:
        """Compose the create mappings screen."""
        yield Header()
        yield Container(
            Vertical(
                Label("Create Mappings for Undetected Profiles", id="title"),
                Label("", id="progress-label"),
                Label("", id="filename-label"),
                Label("", id="pattern-status-label"),
                Horizontal(
                    Label("Printer:", id="printer-label-text"),
                    Input(id="printer-input", placeholder="e.g., Canon Pixma PRO-100"),
                ),
                Horizontal(
                    Label("Brand:", id="brand-label-text"),
                    Input(id="brand-input", placeholder="e.g., Moab, Canson"),
                ),
                Horizontal(
                    Label("Paper Type:", id="paper-label-text"),
                    Input(id="paper-input", placeholder="e.g., Canvas, Matte"),
                ),
                Label("", id="status-label"),
                Horizontal(
                    Button("Save Mapping", id="btn-save-mapping", variant="primary"),
                    Button("Skip", id="btn-skip"),
                    Button("Apply to All", id="btn-apply-all"),
                ),
                Horizontal(
                    Button("Done", id="btn-done"),
                    Button("Back", id="btn-back"),
                ),
                id="mappings-container"
            ),
            id="main-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        """When mounted, show first undetected profile."""
        self.show_current_profile()

    def show_current_profile(self) -> None:
        """Display current undetected profile for mapping."""
        if self.current_group_idx >= len(self.undetected_profiles):
            # All profiles processed, show preview screen
            self.show_preview()
            return

        profile = self.undetected_profiles[self.current_group_idx]
        total = len(self.undetected_profiles)
        progress = f"Profile {self.current_group_idx + 1} of {total}"

        self.query_one("#progress-label", Label).update(progress)
        self.query_one("#filename-label", Label).update(f"File: {profile['filename']}")

        # Extract printer pattern from filename
        self.current_pattern = extract_potential_printer_name(profile['filename'])

        # Pre-fill with suggested values
        suggested_printer = self.current_pattern
        suggested_brand = extract_potential_brand(profile['filename'])
        suggested_paper_type = extract_paper_type_from_filename(profile['filename'], self.current_pattern)

        # Check if we have a cached mapping for this printer pattern
        pattern_status = ""
        self.current_auto_processed = False

        if self.current_pattern and self.current_pattern in self.pattern_mappings:
            cached = self.pattern_mappings[self.current_pattern]
            suggested_printer = cached.get('printer', suggested_printer)
            suggested_brand = cached.get('brand', suggested_brand)
            pattern_status = f"[yellow]💾 Using saved mapping for '{self.current_pattern}'[/yellow]"

            # Check if BOTH printer and brand are cached (complete mapping)
            if cached.get('printer') and cached.get('brand'):
                # Both are cached! Auto-process this profile
                self.current_auto_processed = True
                pattern_status = f"[green]⚡ Auto-processing: '{self.current_pattern}' (printer + brand cached)[/green]"

                # Auto-save this mapping
                self.mappings[profile['filename']] = {
                    'printer': suggested_printer,
                    'brand': suggested_brand,
                    'paper_type': suggested_paper_type or ""
                }
                self.auto_processed_profiles.append({
                    'filename': profile['filename'],
                    'printer': suggested_printer,
                    'brand': suggested_brand,
                    'paper_type': suggested_paper_type
                })

                # Move to next profile immediately
                self.query_one("#pattern-status-label", Label).update(pattern_status)
                self.query_one("#status-label", Label).update(f"[green]✓ Auto-processed[/green]")
                self.next_profile()
                return

        self.query_one("#printer-input", Input).value = suggested_printer or ""
        self.query_one("#brand-input", Input).value = suggested_brand or ""
        self.query_one("#paper-input", Input).value = suggested_paper_type or ""

        self.query_one("#pattern-status-label", Label).update(pattern_status)
        self.query_one("#status-label", Label).update("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "btn-save-mapping":
            self.save_current_mapping()
        elif button_id == "btn-skip":
            self.next_profile()
        elif button_id == "btn-apply-all":
            self.apply_to_all_remaining()
        elif button_id == "btn-done":
            self.save_and_close()
        elif button_id == "btn-back":
            self.app.pop_screen()

    def save_current_mapping(self) -> None:
        """Save the current mapping and move to next."""
        printer_input = self.query_one("#printer-input", Input)
        brand_input = self.query_one("#brand-input", Input)
        paper_input = self.query_one("#paper-input", Input)

        printer = printer_input.value.strip()
        brand = brand_input.value.strip()
        paper_type = paper_input.value.strip()

        if not printer or not brand:
            self.query_one("#status-label", Label).update("[red]Please enter printer and brand[/red]")
            return

        profile = self.undetected_profiles[self.current_group_idx]
        self.mappings[profile['filename']] = {
            'printer': printer,
            'brand': brand,
            'paper_type': paper_type
        }

        # Cache this mapping by printer pattern for reuse
        if self.current_pattern:
            self.pattern_mappings[self.current_pattern] = {
                'printer': printer,
                'brand': brand
            }

        self.query_one("#status-label", Label).update(f"[green]✓ Saved: {printer} / {brand}[/green]")
        self.next_profile()

    def apply_to_all_remaining(self) -> None:
        """Apply current mapping to all remaining profiles with same printer pattern."""
        printer_input = self.query_one("#printer-input", Input)
        brand_input = self.query_one("#brand-input", Input)
        paper_input = self.query_one("#paper-input", Input)

        printer = printer_input.value.strip()
        brand = brand_input.value.strip()
        paper_type = paper_input.value.strip()

        if not printer or not brand:
            self.query_one("#status-label", Label).update("[red]Please enter printer and brand[/red]")
            return

        # Cache this mapping by printer pattern
        if self.current_pattern:
            self.pattern_mappings[self.current_pattern] = {
                'printer': printer,
                'brand': brand
            }

        # Apply to current profile
        profile = self.undetected_profiles[self.current_group_idx]
        self.mappings[profile['filename']] = {
            'printer': printer,
            'brand': brand,
            'paper_type': paper_type
        }

        # Apply to all remaining profiles with same printer pattern
        applied_count = 1
        for i in range(self.current_group_idx + 1, len(self.undetected_profiles)):
            profile = self.undetected_profiles[i]
            profile_pattern = extract_potential_printer_name(profile['filename'])

            # Only auto-apply if patterns match
            if profile_pattern and profile_pattern == self.current_pattern:
                self.mappings[profile['filename']] = {
                    'printer': printer,
                    'brand': brand,
                    'paper_type': paper_type
                }
                applied_count += 1
                self.auto_applied_count += 1

        status = f"[green]✓ Applied to {applied_count} profile(s) with pattern '{self.current_pattern}'[/green]"
        self.query_one("#status-label", Label).update(status)

        # Skip to next different pattern
        self.current_group_idx += applied_count - 1
        self.next_profile()

    def next_profile(self) -> None:
        """Move to next undetected profile."""
        self.current_group_idx += 1
        if self.current_group_idx < len(self.undetected_profiles):
            self.show_current_profile()
        else:
            self.query_one("#status-label", Label).update("[green]✓ All profiles processed[/green]")

    def save_and_close(self) -> None:
        """Save all mappings to config and close."""
        if not self.mappings:
            self.query_one("#status-label", Label).update("[yellow]No mappings to save[/yellow]")
            return

        # Show preview instead of saving directly
        self.show_preview()

    def action_back(self) -> None:
        """Go back."""
        self.app.pop_screen()

    def show_preview(self) -> None:
        """Show preview screen of all mappings before saving."""
        self.app.push_screen(PreviewMappingsScreen(
            self.mappings,
            self.auto_processed_profiles,
            self.config_manager,
            self.auto_applied_count
        ))

    def action_save(self) -> None:
        """Save current mapping."""
        self.save_and_close()


class PreviewMappingsScreen(Screen):
    """Screen to preview all mappings before final save."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, mappings: Dict, auto_processed: List, config_manager: ConfigManager,
                 auto_applied_count: int):
        """Initialize preview screen."""
        super().__init__()
        self.mappings = mappings
        self.auto_processed = auto_processed
        self.config_manager = config_manager
        self.auto_applied_count = auto_applied_count

    def compose(self) -> ComposeResult:
        """Compose the preview screen."""
        yield Header()
        yield Container(
            Vertical(
                Label("Preview: Mapping Summary", id="title"),
                Label("", id="summary-label"),
                ScrollableContainer(
                    DataTable(id="preview-table"),
                    id="table-container"
                ),
                Label("", id="status-label"),
                Horizontal(
                    Button("Save & Done", id="btn-save", variant="primary"),
                    Button("Back", id="btn-back"),
                ),
                id="preview-container"
            ),
            id="main-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        """When mounted, populate the preview table."""
        # Create table
        table = self.query_one("#preview-table", DataTable)
        table.add_columns(
            "Filename",
            "Printer",
            "Brand",
            "Paper Type",
            "Status"
        )

        # Add mappings to table
        manual_count = 0
        auto_count = 0

        for filename, mapping in sorted(self.mappings.items()):
            # Check if this was auto-processed
            is_auto = any(p['filename'] == filename for p in self.auto_processed)
            status = "Auto-Processed ⚡" if is_auto else "Manual ✓"

            table.add_row(
                Path(filename).name[:30],
                mapping['printer'][:25],
                mapping['brand'][:15],
                mapping.get('paper_type', '')[:20],
                status,
                key=filename
            )

            if is_auto:
                auto_count += 1
            else:
                manual_count += 1

        # Update summary
        total = len(self.mappings)
        summary = f"Total mappings: {total} | Manual: {manual_count} | Auto-processed: {auto_count}"
        if self.auto_applied_count > 0:
            summary += f" | Auto-applied patterns: {self.auto_applied_count}"

        self.query_one("#summary-label", Label).update(summary)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "btn-save":
            self.save_all_mappings()
        elif button_id == "btn-back":
            self.app.pop_screen()

    def save_all_mappings(self) -> None:
        """Save all mappings to config and close."""
        if not self.mappings:
            self.query_one("#status-label", Label).update("[yellow]No mappings to save[/yellow]")
            return

        # Add new printer names to config
        printer_names = self.config_manager.get_printer_names()
        for filename, mapping in self.mappings.items():
            printer = mapping['printer']
            if printer not in printer_names:
                exists = any(p == printer for p in printer_names.values())
                if not exists:
                    key = Path(filename).stem.split('_')[0].split('-')[0]
                    printer_names[printer] = [key]

        self.config_manager.set_printer_names(printer_names)

        # Add new brands
        paper_brands = set(self.config_manager.get_paper_brands())
        for mapping in self.mappings.values():
            paper_brands.add(mapping['brand'])
        self.config_manager.set_paper_brands(list(paper_brands))

        # Save config
        self.config_manager.save()

        # Show summary
        total = len(self.mappings)
        manual = total - len(self.auto_processed)
        auto = len(self.auto_processed)
        summary = f"[green]✓ Saved {total} mapping(s) ({manual} manual + {auto} auto-processed)[/green]"
        self.query_one("#status-label", Label).update(summary)

        # Return to scan screen
        self.app.pop_screen()
        self.app.pop_screen()

    def action_back(self) -> None:
        """Go back to mapping screen."""
        self.app.pop_screen()


class ConfigEditorScreen(Screen):
    """Screen for editing config.yaml sections."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(self):
        """Initialize config editor screen."""
        super().__init__()
        self.config_manager = ConfigManager()

    def compose(self) -> ComposeResult:
        """Compose the config editor screen."""
        yield Header()
        yield Container(
            Vertical(
                Label("Edit Configuration", id="title"),
                Tabs(
                    TabPane("Printer Names", id="tab-printers"),
                    TabPane("Brand Mappings", id="tab-brands"),
                    TabPane("Paper Brands", id="tab-papers"),
                    TabPane("Printer Remappings", id="tab-remappings"),
                    id="config-tabs"
                ),
                Label("", id="editor-status"),
                Horizontal(
                    Button("Save", id="btn-save", variant="primary"),
                    Button("Back", id="btn-back"),
                ),
                id="editor-container"
            ),
            id="main-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        """Set up tab contents."""
        tabs = self.query_one("#config-tabs", Tabs)

        # Printer Names tab
        printer_names = self.config_manager.get_printer_names()
        printer_text = self.dict_to_yaml(printer_names)
        tabs.query_one("#tab-printers").mount(
            TextArea(printer_text, id="printers-area", language="yaml")
        )

        # Brand Mappings tab
        brand_mappings = self.config_manager.get_brand_mappings()
        brand_text = self.dict_to_yaml(brand_mappings)
        tabs.query_one("#tab-brands").mount(
            TextArea(brand_text, id="brands-area", language="yaml")
        )

        # Paper Brands tab
        paper_brands = self.config_manager.get_paper_brands()
        paper_text = '\n'.join(f"- {brand}" for brand in paper_brands)
        tabs.query_one("#tab-papers").mount(
            TextArea(paper_text, id="papers-area", language="yaml")
        )

        # Printer Remappings tab
        remappings = self.config_manager.get_printer_remappings()
        remapping_text = self.dict_to_yaml(remappings)
        tabs.query_one("#tab-remappings").mount(
            TextArea(remapping_text, id="remappings-area", language="yaml")
        )

    def dict_to_yaml(self, data: Dict) -> str:
        """Convert dict to YAML string for display."""
        if isinstance(data, dict) and all(isinstance(v, list) for v in data.values()):
            # Hierarchical format: canonical: [aliases]
            lines = []
            for canonical, aliases in data.items():
                lines.append(f"{canonical}:")
                for alias in aliases:
                    lines.append(f"  - {alias}")
            return '\n'.join(lines)
        elif isinstance(data, dict):
            # Flat format
            lines = []
            for key, val in data.items():
                lines.append(f'"{key}": "{val}"')
            return '\n'.join(lines)
        return str(data)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "btn-save":
            self.action_save()
        elif button_id == "btn-back":
            self.app.pop_screen()

    def action_save(self) -> None:
        """Save configuration changes."""
        try:
            if self.config_manager.save():
                self.query_one("#editor-status", Label).update("[green]✓ Configuration saved[/green]")
            else:
                self.query_one("#editor-status", Label).update("[red]Failed to save configuration[/red]")
        except Exception as e:
            self.query_one("#editor-status", Label).update(f"[red]Error: {str(e)}[/red]")

    def action_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()


class PreviewScreen(Screen):
    """Screen for previewing how profiles will be organized."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, organizer: Optional[ProfileOrganizer] = None):
        """Initialize preview screen."""
        super().__init__()
        self.organizer = organizer
        self.config_manager = ConfigManager()

    def compose(self) -> ComposeResult:
        """Compose the preview screen."""
        yield Header()
        yield Container(
            Vertical(
                Label("Organization Preview", id="title"),
                Label("Folder:", id="folder-label"),
                Input(id="preview-folder-input", placeholder="/path/to/profiles"),
                Button("Generate Preview", id="btn-generate", variant="primary"),
                ScrollableContainer(
                    Tree("organization-root", id="preview-tree"),
                    id="tree-container"
                ),
                Label("", id="preview-status"),
                Button("Back", id="btn-back"),
                id="preview-container"
            ),
            id="main-container"
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "btn-generate":
            self.generate_preview()
        elif button_id == "btn-back":
            self.app.pop_screen()

    def generate_preview(self) -> None:
        """Generate and display organization preview."""
        folder_input = self.query_one("#preview-folder-input", Input)
        folder_path = folder_input.value

        if not folder_path:
            self.query_one("#preview-status", Label).update("[red]Please enter a folder path[/red]")
            return

        try:
            folder_path = Path(folder_path).resolve()
            if not folder_path.exists():
                self.query_one("#preview-status", Label).update(f"[red]Folder not found[/red]")
                return

            # Create organizer for preview
            organizer = ProfileOrganizer(
                str(folder_path),
                dry_run=True,
                verbose=False
            )

            # Find all profiles
            profile_files = organizer._find_profile_files()
            all_files = []
            for file_list in profile_files.values():
                all_files.extend(file_list)

            if not all_files:
                self.query_one("#preview-status", Label).update("[yellow]No profiles found[/yellow]")
                return

            # Build organization structure
            tree = self.query_one("#preview-tree", Tree)
            tree.clear()

            from collections import defaultdict
            structure = defaultdict(lambda: defaultdict(list))

            for file_path in all_files:
                printer, brand, paper_type = organizer.extract_printer_and_paper_info(file_path.name)

                if printer and brand:
                    new_filename = f"{printer} - {brand} - {paper_type}.{file_path.suffix.lstrip('.')}"
                    structure[printer][brand].append(new_filename)

            # Populate tree
            root = tree.root
            for printer in sorted(structure.keys()):
                printer_node = root.add(f"📁 {printer}")
                for brand in sorted(structure[printer].keys()):
                    brand_node = printer_node.add(f"📂 {brand}")
                    for filename in structure[printer][brand]:
                        brand_node.add(f"📄 {filename}")

            status = f"[green]✓ Preview generated for {len(all_files)} files[/green]"
            self.query_one("#preview-status", Label).update(status)

        except Exception as e:
            self.query_one("#preview-status", Label).update(f"[red]Error: {str(e)}[/red]")

    def action_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()


class MappingConfigStartScreen(Screen):
    """Screen to select a folder and start mapping configuration."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the screen."""
        yield Header()
        yield Container(
            Vertical(
                Label("Configure Printer & Brand Mappings", id="title"),
                Label("Select a folder containing ICC profiles to analyze", id="subtitle"),
                Label("", id="spacer"),
                Horizontal(
                    Label("Folder path:", id="label"),
                    Input(id="folder-input", placeholder="/path/to/profiles"),
                ),
                Button("Scan & Configure", id="btn-scan", variant="primary"),
                Button("Back", id="btn-back"),
                Label("", id="status-label"),
                id="container"
            ),
            id="mapping-start-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        """When mounted, set focus to input."""
        self.query_one("#folder-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-scan":
            folder_path = self.query_one("#folder-input", Input).value.strip()
            if not folder_path:
                self.query_one("#status-label", Label).update("[red]Please enter a folder path[/red]")
                return

            folder = Path(folder_path)
            if not folder.is_dir():
                self.query_one("#status-label", Label).update("[red]Folder does not exist[/red]")
                return

            # Scan for detected printers and brands
            detected_printers, detected_brands = scan_profiles_for_detection(folder_path)

            if not detected_printers and not detected_brands:
                self.query_one("#status-label", Label).update("[yellow]No profiles found in folder[/yellow]")
                return

            # Move to printer mapping screen
            self.app.push_screen(
                PrinterMappingScreen(detected_printers, detected_brands, folder_path)
            )

        elif event.button.id == "btn-back":
            self.app.pop_screen()

    def action_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()


class PrinterMappingScreen(Screen):
    """Screen for configuring printer name mappings."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    def __init__(
        self,
        detected_printers: Dict[str, int],
        detected_brands: Dict[str, int],
        folder_path: str
    ):
        """Initialize with detected values."""
        super().__init__()
        self.detected_printers = detected_printers
        self.detected_brands = detected_brands
        self.folder_path = folder_path
        self.printer_mappings = {}  # Maps detected pattern -> canonical name
        self.printer_inputs = {}  # Maps detected name -> Input widget

    def compose(self) -> ComposeResult:
        """Compose the screen."""
        yield Header()
        yield Container(
            Vertical(
                Label("Configure Printer Name Mappings", id="title"),
                Label(
                    f"Detected {len(self.detected_printers)} unique printer patterns",
                    id="subtitle"
                ),
                Label("", id="spacer"),
                ScrollableContainer(
                    *self._create_printer_mapping_widgets(),
                    id="mappings-container"
                ),
                Horizontal(
                    Button("Next: Configure Brands", id="btn-next", variant="primary"),
                    Button("Skip", id="btn-skip"),
                    Button("Back", id="btn-back"),
                    id="button-row"
                ),
                id="container"
            ),
            id="printer-mapping-container"
        )
        yield Footer()

    def _create_printer_mapping_widgets(self) -> list:
        """Create widgets for mapping each detected printer."""
        widgets = []

        for detected, count in sorted(self.detected_printers.items(), key=lambda x: -x[1]):
            # Create input and store reference
            input_widget = Input(
                placeholder="Map to canonical name (or leave empty to auto-detect)",
                id=f"printer-input-{id(detected)}"  # Use object id for unique, safe selector
            )
            self.printer_inputs[detected] = input_widget

            widgets.append(
                Horizontal(
                    Label(f"{detected} ({count})"),
                    input_widget,
                    id=f"printer-row-{id(detected)}"
                )
            )

        return widgets

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-next":
            # Collect mappings from stored input references
            for detected, input_widget in self.printer_inputs.items():
                canonical = input_widget.value.strip()
                if canonical:
                    self.printer_mappings[detected] = canonical

            # Move to brand mapping
            self.app.push_screen(
                BrandMappingScreen(
                    self.detected_brands,
                    self.printer_mappings,
                    self.folder_path
                )
            )

        elif event.button.id == "btn-skip":
            # Skip printer mapping, go to brand mapping
            self.app.push_screen(
                BrandMappingScreen(
                    self.detected_brands,
                    {},
                    self.folder_path
                )
            )

        elif event.button.id == "btn-back":
            self.app.pop_screen()

    def action_back(self) -> None:
        """Go back to previous screen."""
        self.app.pop_screen()


class BrandMappingScreen(Screen):
    """Screen for configuring brand name mappings."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    def __init__(
        self,
        detected_brands: Dict[str, int],
        printer_mappings: Dict[str, str],
        folder_path: str
    ):
        """Initialize with detected values."""
        super().__init__()
        self.detected_brands = detected_brands
        self.printer_mappings = printer_mappings
        self.folder_path = folder_path
        self.brand_mappings = {}  # Maps detected brand -> canonical name
        self.brand_inputs = {}  # Maps detected brand -> Input widget

    def compose(self) -> ComposeResult:
        """Compose the screen."""
        yield Header()
        yield Container(
            Vertical(
                Label("Configure Brand Name Mappings", id="title"),
                Label(
                    f"Detected {len(self.detected_brands)} unique paper brands",
                    id="subtitle"
                ),
                Label("", id="spacer"),
                ScrollableContainer(
                    *self._create_brand_mapping_widgets(),
                    id="mappings-container"
                ),
                Horizontal(
                    Button("Save Mappings", id="btn-save", variant="primary"),
                    Button("Skip", id="btn-skip"),
                    Button("Back", id="btn-back"),
                    id="button-row"
                ),
                Label("", id="status-label"),
                id="container"
            ),
            id="brand-mapping-container"
        )
        yield Footer()

    def _create_brand_mapping_widgets(self) -> list:
        """Create widgets for mapping each detected brand."""
        widgets = []

        for detected, count in sorted(self.detected_brands.items(), key=lambda x: -x[1]):
            # Create input and store reference
            input_widget = Input(
                placeholder="Map to canonical name (or leave empty to auto-detect)",
                id=f"brand-input-{id(detected)}"  # Use object id for unique, safe selector
            )
            self.brand_inputs[detected] = input_widget

            widgets.append(
                Horizontal(
                    Label(f"{detected} ({count})"),
                    input_widget,
                    id=f"brand-row-{id(detected)}"
                )
            )

        return widgets

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-save":
            # Collect mappings from stored input references
            for detected, input_widget in self.brand_inputs.items():
                canonical = input_widget.value.strip()
                if canonical:
                    self.brand_mappings[detected] = canonical

            # Save to config
            self._save_mappings()

        elif event.button.id == "btn-skip":
            # Just go back to welcome
            self.app.pop_screen()

        elif event.button.id == "btn-back":
            self.app.pop_screen()

    def _save_mappings(self) -> None:
        """Save the configured mappings to config.yaml."""
        config_manager = ConfigManager()

        # Save printer mappings
        if self.printer_mappings:
            printer_names = config_manager.get_printer_names()
            for detected, canonical in self.printer_mappings.items():
                if canonical not in printer_names:
                    printer_names[canonical] = []
                if detected not in printer_names[canonical]:
                    printer_names[canonical].append(detected)
            config_manager.set_printer_names(printer_names)

        # Save brand mappings
        if self.brand_mappings:
            brand_mappings = config_manager.get_brand_mappings()
            for detected, canonical in self.brand_mappings.items():
                if canonical not in brand_mappings:
                    brand_mappings[canonical] = []
                if detected not in brand_mappings[canonical]:
                    brand_mappings[canonical].append(detected)
            config_manager.set_brand_mappings(brand_mappings)

        # Save config file
        if config_manager.save():
            self.query_one("#status-label", Label).update(
                "[green]✓ Mappings saved to config.yaml[/green]"
            )
            # Go back after a brief moment
            self.app.pop_screen()
        else:
            self.query_one("#status-label", Label).update(
                "[red]Error saving config[/red]"
            )

    def action_back(self) -> None:
        """Go back to previous screen."""
        self.app.pop_screen()


class ProfileConfigTUI:
    """Main TUI application."""

    def __init__(self):
        """Initialize the TUI application."""
        from textual.app import App

        class ConfigApp(App):
            """The main Textual application."""

            CSS = """
            Screen {
                layout: vertical;
            }

            #title {
                width: 100%;
                height: 1;
                content-align: center middle;
                background: $accent;
                color: $text;
                text-style: bold;
                padding: 1;
            }

            #subtitle {
                width: 100%;
                height: 1;
                content-align: center middle;
                color: $text-muted;
            }

            #spacer {
                height: 2;
            }

            #welcome-container {
                width: 100%;
                height: auto;
            }

            #menu-container {
                width: 40;
                height: auto;
                align: center middle;
                border: solid $accent;
                padding: 2;
            }

            #menu-container Button {
                width: 100%;
                margin-bottom: 1;
            }

            #scan-container {
                width: 100%;
                height: auto;
            }

            #folder-input {
                width: 1fr;
                margin-right: 1;
            }

            #table-container {
                width: 100%;
                height: 1fr;
                margin: 1 0;
            }

            #profiles-table {
                width: 100%;
                height: 100%;
            }

            #scan-status {
                width: 100%;
                margin: 1 0;
                padding: 1;
                border: solid $accent;
            }

            #config-tabs {
                width: 100%;
                height: 1fr;
                margin: 1 0;
            }

            #editor-status {
                width: 100%;
                margin: 1 0;
                padding: 1;
                border: solid $accent;
            }

            #tree-container {
                width: 100%;
                height: 1fr;
                border: solid $accent;
                margin: 1 0;
            }

            #preview-status {
                width: 100%;
                padding: 1;
                border: solid $accent;
            }
            """

            BINDINGS = [
                Binding("q", "quit", "Quit"),
            ]

            def on_mount(self) -> None:
                """When app starts, show welcome screen."""
                self.push_screen(WelcomeScreen())

        self.app = ConfigApp()

    def run(self):
        """Run the TUI application."""
        self.app.run()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Interactive TUI for ICC Profile Configuration'
    )
    parser.add_argument(
        '--config',
        help='Path to config.yaml file'
    )

    args = parser.parse_args()

    # Initialize config manager with custom path if provided
    if args.config:
        ConfigManager.config_path = Path(args.config)

    # Run the TUI
    tui = ProfileConfigTUI()
    tui.run()


if __name__ == '__main__':
    main()
