#!/usr/bin/env python3
"""
Interactive TUI Configuration Wizard for ICC Profile Organizer

Helps users create a good config.yaml file by:
- Scanning their profiles directory
- Identifying which files are detected vs undetected
- Guiding them through mapping undetected files
- Building config.yaml automatically without repetition
- Suggesting patterns based on filename analysis
"""

import os
import sys
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import yaml
import json
from dataclasses import dataclass
from copy import deepcopy

from textual.app import ComposeResult, App
from textual.widgets import Header, Footer, Static, Button, Input, Label, RichLog
from textual.containers import Container, Vertical, Horizontal
from textual.screen import Screen
from textual.binding import Binding
from rich.text import Text
from rich.table import Table
from rich import box

# Import from lib
sys.path.insert(0, str(Path(__file__).parent))
from lib import (
    ConfigManager,
    find_profile_files,
    generate_new_filename,
)
from lib.pattern_matching import format_paper_type


@dataclass
class ProfileFile:
    """Represents a profile file and its detection status"""
    path: Path
    filename: str
    detected: bool = False
    printer: Optional[str] = None
    brand: Optional[str] = None
    paper_type: Optional[str] = None
    matched_pattern: Optional[str] = None
    match_priority: Optional[int] = None


@dataclass
class UserMapping:
    """A user-defined mapping from filename to profile metadata"""
    filename: str
    printer: str
    brand: str
    paper_type: str
    is_pattern: bool = False  # True if this should be converted to a pattern


@dataclass
class PatternReplacement:
    """A pattern-based replacement for detecting printer or brand from filenames"""
    original_text: str  # Text in filename to match
    replacement: str   # What to replace it with (canonical name)
    replacement_type: str  # "printer" or "brand"
    example_filenames: List[str] = None  # Example filenames for this pattern
    
    def __post_init__(self):
        if self.example_filenames is None:
            self.example_filenames = []


@dataclass
class FileGroup:
    """A group of files sharing similar detection characteristics"""
    representative_file: str  # One example filename
    files: List[ProfileFile]  # All files in this group
    detected_printer: Optional[str] = None
    detected_brand: Optional[str] = None
    pattern_similarity: str = ""  # Description of what's similar


class ConfigWizard:
    """Manages configuration building process"""

    def __init__(self, profiles_dir: Optional[Path] = None):
        self.profiles_dir = profiles_dir or Path.cwd()
        self.config_manager = ConfigManager()
        self.config_manager.load()  # Load defaults.yaml and config.yaml
        self.detected_files: List[ProfileFile] = []
        self.undetected_files: List[ProfileFile] = []
        self.user_mappings: List[UserMapping] = []
        self.pattern_replacements: List[PatternReplacement] = []  # Pattern-based replacements
        self.generated_patterns: List[Dict] = []  # Generated filename patterns
        self.printer_names: Dict[str, List[str]] = {}
        self.brand_mappings: Dict[str, List[str]] = {}

    def scan_profiles(self) -> None:
        """Scan the profiles directory and detect all profile files"""
        self.detected_files = []
        self.undetected_files = []

        # Use lib function to find all profile files
        profile_files = find_profile_files(self.profiles_dir)

        # Flatten the dict into a single list
        all_files = []
        for file_list in profile_files.values():
            all_files.extend(file_list)

        # Categorize each file as detected or undetected
        for filepath in all_files:
            filename = filepath.name

            try:
                result = self.config_manager.match_filename(filename)
                if result and all(result):
                    printer, brand, paper_type = result
                    # If brand is "Unknown", try fallback detection
                    if brand == "Unknown":
                        brand = self._try_detect_brand_from_filename(filename)
                    # Treat "Unknown" values as undetected
                    if printer == "Unknown" or brand == "Unknown" or not brand:
                        self.undetected_files.append(
                            ProfileFile(path=filepath, filename=filename, detected=False)
                        )
                    else:
                        profile = ProfileFile(
                            path=filepath,
                            filename=filename,
                            detected=True,
                            printer=printer,
                            brand=brand,
                            paper_type=paper_type,
                        )
                        self.detected_files.append(profile)
                else:
                    self.undetected_files.append(
                        ProfileFile(path=filepath, filename=filename, detected=False)
                    )
            except Exception:
                self.undetected_files.append(
                    ProfileFile(path=filepath, filename=filename, detected=False)
                )

    def get_detection_rate(self) -> Tuple[int, int, float]:
        """Return (detected, total, percentage)"""
        total = len(self.detected_files) + len(self.undetected_files)
        detected = len(self.detected_files)
        percentage = (detected / total * 100) if total > 0 else 0
        return detected, total, percentage

    def group_undetected_files(self) -> List[FileGroup]:
        """
        Group undetected files by their pattern characteristics.
        Files with similar prefixes, extensions, or partial detections are grouped together.
        """
        return self._group_files(self.undetected_files)

    def group_detected_files(self) -> List[FileGroup]:
        """
        Group detected files by their pattern characteristics for review.
        """
        return self._group_files(self.detected_files)

    def _group_files(self, files: List[ProfileFile]) -> List[FileGroup]:
        """
        Group files by their pattern characteristics.
        Files with similar prefixes, extensions, or detections are grouped together.
        """
        groups: Dict[str, FileGroup] = {}

        for profile_file in files:
            filename = profile_file.filename

            # Try to detect what we can (or use already detected values)
            if profile_file.detected:
                detected = {
                    "printer": profile_file.printer,
                    "brand": profile_file.brand,
                    "paper_type": profile_file.paper_type,
                }
            else:
                detected = self._analyze_file(filename)

            # Create a grouping key based on detected patterns
            # Group by: (detected_printer, detected_brand, file_prefix, extension)
            prefix = self._extract_prefix(filename)
            ext = Path(filename).suffix.lower()

            group_key = (
                detected.get("printer"),
                detected.get("brand"),
                prefix,
                ext
            )

            if group_key not in groups:
                # Create new group
                groups[group_key] = FileGroup(
                    representative_file=filename,
                    files=[profile_file],
                    detected_printer=detected.get("printer"),
                    detected_brand=detected.get("brand"),
                    pattern_similarity=self._describe_pattern(prefix, ext, detected)
                )
            else:
                # Add to existing group
                groups[group_key].files.append(profile_file)

        return list(groups.values())

    def _analyze_file(self, filename: str) -> Dict[str, Optional[str]]:
        """Analyze a single filename and return detected fields using ConfigManager"""
        detected = {
            "printer": None,
            "brand": None,
            "paper_type": None,
        }

        # Use ConfigManager's pattern matching - this is the single source of truth
        try:
            result = self.config_manager.match_filename(filename)
            if result and any(result):
                printer, brand, paper_type = result
                # Don't treat "Unknown" as detected
                if printer and printer != "Unknown":
                    detected["printer"] = printer
                if brand and brand != "Unknown":
                    detected["brand"] = brand
                else:
                    # Try to detect brand from filename if pattern matcher returned "Unknown"
                    detected["brand"] = self._try_detect_brand_from_filename(filename)
                if paper_type:
                    detected["paper_type"] = paper_type
        except Exception:
            pass

        return detected

    def _try_detect_brand_from_filename(self, filename: str) -> Optional[str]:
        """Try to detect brand from filename by searching for known brand names"""
        filename_lower = filename.lower()
        
        # Get all known brand names and their aliases
        brand_mappings = self.config_manager.BRAND_NAME_MAPPINGS
        
        # Search for brand names in filename (case-insensitive)
        # Check both canonical names and aliases
        for alias, canonical in brand_mappings.items():
            if alias.lower() in filename_lower:
                return canonical
        
        # Also check paper_brands list for any brands not in mappings
        for brand in self.config_manager.PAPER_BRANDS:
            if brand.lower() in filename_lower:
                return brand
        
        return None

    def _extract_prefix(self, filename: str) -> str:
        """Extract a common prefix from filename (before first space or underscore)"""
        # Remove extension
        name = Path(filename).stem

        # Split on common delimiters
        for delimiter in [' ', '_', '-']:
            if delimiter in name:
                return name.split(delimiter)[0]

        return name

    def _describe_pattern(self, prefix: str, ext: str, detected: Dict) -> str:
        """Create a human-readable description of the pattern"""
        parts = []

        printer = detected.get("printer")
        brand = detected.get("brand")
        
        if printer:
            parts.append(f"Printer: {printer}")
        else:
            parts.append("Printer: Unknown")
            
        if brand:
            parts.append(f"Brand: {brand}")
        else:
            parts.append("Brand: Unknown")
            
        if prefix:
            parts.append(f"Prefix: {prefix}")
        parts.append(f"Type: {ext}")

        return ", ".join(parts) if parts else "Unknown pattern"

    def add_user_mapping(self, mapping: UserMapping) -> None:
        """Add a user-defined mapping"""
        self.user_mappings.append(mapping)

    def add_pattern_replacement(self, replacement: PatternReplacement) -> None:
        """Add a pattern-based replacement for detecting printer or brand"""
        self.pattern_replacements.append(replacement)

    def add_generated_pattern(self, pattern: Dict) -> None:
        """Add a generated filename pattern"""
        self.generated_patterns.append(pattern)


    def _analyze_filename_structure(self, filename: str, printer_orig: Optional[str], 
                                    brand_orig: Optional[str], printer_repl: Optional[str],
                                    brand_repl: Optional[str]) -> Optional[Dict]:
        """Analyze filename structure and create a pattern definition"""
        # Remove extension
        name_without_ext = Path(filename).stem
        original_filename = name_without_ext
        
        # Determine delimiter (space, dash, or underscore)
        delimiter = " "
        if " - " in name_without_ext:
            delimiter = " - "
        elif " -" in name_without_ext:
            delimiter = " -"
        elif "- " in name_without_ext:
            delimiter = "- "
        elif "_" in name_without_ext:
            delimiter = "_"
        elif "-" in name_without_ext:
            delimiter = "-"
        
        # Split by delimiter
        parts = name_without_ext.split(delimiter)
        
        # Find brand and printer text in filename (case-insensitive)
        brand_text_lower = brand_orig.lower() if brand_orig else ""
        printer_text_lower = printer_orig.lower() if printer_orig else ""
        
        # Find start and end positions of brand and printer in the filename
        filename_lower = name_without_ext.lower()
        brand_start = None
        brand_end = None
        printer_start = None
        printer_end = None
        
        if brand_text_lower:
            brand_start = filename_lower.find(brand_text_lower)
            if brand_start >= 0:
                brand_end = brand_start + len(brand_text_lower)
        
        if printer_text_lower:
            printer_start = filename_lower.find(printer_text_lower)
            if printer_start >= 0:
                printer_end = printer_start + len(printer_text_lower)
        
        # Determine paper type position by analyzing what's left
        # Paper type is everything that's not brand or printer
        structure = []
        
        # Determine order: brand first, printer first, or only one
        brand_first = False
        printer_first = False
        
        if brand_start is not None and printer_start is not None:
            brand_first = brand_start < printer_start
            printer_first = printer_start < brand_start
        elif brand_start is not None:
            brand_first = True
        elif printer_start is not None:
            printer_first = True
        
        # Build structure based on what we found
        if brand_first and printer_start is not None:
            # Format: [Brand] [Paper Type] [Printer]
            # Paper type is between brand and printer
            structure.append({"field": "brand", "match_type": "substring"})
            structure.append({"field": "printer", "match_type": "key_search"})
            structure.append({"field": "paper_type", "position": "before_printer"})
        elif printer_first and brand_start is not None:
            # Format: [Printer] [Paper Type] [Brand]
            structure.append({"field": "printer", "match_type": "key_search"})
            structure.append({"field": "brand", "match_type": "substring"})
            structure.append({"field": "paper_type", "position": "remaining"})
        elif brand_start is not None:
            # Only brand found: [Brand] [Paper Type] [Printer?]
            structure.append({"field": "brand", "match_type": "substring"})
            structure.append({"field": "printer", "match_type": "key_search"})
            structure.append({"field": "paper_type", "position": "before_printer"})
        elif printer_start is not None:
            # Only printer found: [Paper Type] [Printer]
            structure.append({"field": "printer", "match_type": "key_search"})
            structure.append({"field": "paper_type", "position": "before_printer"})
        else:
            # Neither found, use fallback
            structure.append({"field": "printer", "match_type": "key_search"})
            structure.append({"field": "paper_type", "position": "remaining"})
        
        # Build structure based on what we found
        # For paper type extraction, we'll use a custom approach that removes both brand and printer
        if brand_first and printer_start is not None:
            # Format: [Brand] [Paper Type] [Printer]
            # Use brand as prefix, then extract paper type before printer
            structure.append({"field": "printer", "match_type": "key_search"})
            structure.append({"field": "paper_type", "position": "before_printer"})
        elif printer_first and brand_start is not None:
            # Format: [Printer] [Paper Type] [Brand]
            structure.append({"field": "printer", "match_type": "key_search"})
            structure.append({"field": "brand", "match_type": "substring"})
            structure.append({"field": "paper_type", "position": "remaining"})
        elif brand_start is not None:
            # Only brand found: [Brand] [Paper Type] [Printer?]
            structure.append({"field": "printer", "match_type": "key_search"})
            structure.append({"field": "paper_type", "position": "before_printer"})
        elif printer_start is not None:
            # Only printer found: [Paper Type] [Printer]
            structure.append({"field": "printer", "match_type": "key_search"})
            structure.append({"field": "paper_type", "position": "before_printer"})
        else:
            # Neither found, use fallback
            structure.append({"field": "printer", "match_type": "key_search"})
            structure.append({"field": "paper_type", "position": "remaining"})
        
        # Determine prefix (if brand is at the start)
        prefix = None
        prefix_case_insensitive = False
        if brand_start == 0 and brand_orig:
            # Brand is at the start - use it as prefix
            # Find the actual brand text in the original (preserving case)
            # Handle multi-word brands
            brand_words = brand_orig.split()
            if len(brand_words) > 1:
                # Multi-word brand - find where it ends in the filename
                # Look for the brand text (case-insensitive) and get the actual text
                brand_lower = brand_orig.lower()
                filename_lower = name_without_ext.lower()
                brand_end_pos = filename_lower.find(brand_lower) + len(brand_lower)
                if brand_end_pos < len(name_without_ext):
                    # Get the actual brand text preserving case
                    actual_brand = name_without_ext[:brand_end_pos]
                    # Check what comes after
                    remaining = name_without_ext[brand_end_pos:].strip()
                    if remaining.startswith(delimiter):
                        prefix = actual_brand + delimiter
                    else:
                        prefix = actual_brand + " "
                else:
                    prefix = brand_orig + delimiter
            else:
                # Single word brand
                brand_match_end = len(brand_orig)
                if brand_match_end < len(name_without_ext):
                    # Check if there's a delimiter after brand
                    if name_without_ext[brand_match_end:brand_match_end+len(delimiter)] == delimiter:
                        prefix = name_without_ext[:brand_match_end] + delimiter
                    else:
                        prefix = name_without_ext[:brand_match_end] + " "
                else:
                    prefix = brand_orig + delimiter
            prefix_case_insensitive = True
        
        # Create pattern name
        pattern_name = f"custom_pattern_{len(self.pattern_replacements)}"
        if brand_repl:
            pattern_name = f"{brand_repl.lower().replace(' ', '_')}_profiles"
        
        # Build pattern
        # Determine if we need to remove manufacturer name from paper type
        remove_manufacturer = None
        if printer_repl:
            # Extract manufacturer name (first word) from printer replacement
            manufacturer_words = ["Canon", "Epson", "HP", "Brother", "Ricoh", "Xerox"]
            for mfg in manufacturer_words:
                if printer_repl.startswith(mfg):
                    remove_manufacturer = mfg
                    break
        
        pattern = {
            "name": pattern_name,
            "priority": 70,  # Lower than MOAB/EPSON but higher than fallback
            "description": f"Custom pattern for {brand_repl or 'unknown'} profiles",
            "prefix": prefix,
            "prefix_case_insensitive": prefix_case_insensitive if prefix else True,
            "delimiter": delimiter.strip() if delimiter.strip() else " ",
            "structure": structure,
            "brand_value": brand_repl if brand_repl else None,
            "paper_type_processing": {
                "format": True,
                "remove_brand": remove_manufacturer,  # Remove manufacturer name from paper type
            }
        }
        
        return pattern

    def build_config_dict(self) -> dict:
        """Build a complete config.yaml structure from user mappings"""
        # Load existing config to merge with new mappings
        existing_config = deepcopy(self.config_manager.config) if self.config_manager.config else {}
        
        config = {
            "printer_names": existing_config.get("printer_names", {}),
            "brand_name_mappings": existing_config.get("brand_name_mappings", {}),
            "paper_brands": existing_config.get("paper_brands", []),
            "printer_remappings": existing_config.get("printer_remappings", {}),
            "filename_patterns": existing_config.get("filename_patterns", []),
        }

        # Ensure we have dicts/lists (not None)
        if config["printer_names"] is None:
            config["printer_names"] = {}
        if config["brand_name_mappings"] is None:
            config["brand_name_mappings"] = {}
        if config["paper_brands"] is None:
            config["paper_brands"] = []
        if config["printer_remappings"] is None:
            config["printer_remappings"] = {}
        if config["filename_patterns"] is None:
            config["filename_patterns"] = []

        # Add pattern-based replacements to printer_names and brand_name_mappings
        for replacement in self.pattern_replacements:
            if replacement.replacement_type == "printer":
                # Add original_text as an alias for replacement (canonical name)
                if replacement.replacement not in config["printer_names"]:
                    config["printer_names"][replacement.replacement] = []
                # Add original_text as an alias if not already present
                if replacement.original_text not in config["printer_names"][replacement.replacement]:
                    config["printer_names"][replacement.replacement].append(replacement.original_text)
            elif replacement.replacement_type == "brand":
                # Add original_text as an alias for replacement (canonical name)
                if replacement.replacement not in config["brand_name_mappings"]:
                    config["brand_name_mappings"][replacement.replacement] = []
                # Add original_text as an alias if not already present
                if replacement.original_text not in config["brand_name_mappings"][replacement.replacement]:
                    config["brand_name_mappings"][replacement.replacement].append(replacement.original_text)
                # Also add to paper_brands if not present
                if replacement.replacement not in config["paper_brands"]:
                    config["paper_brands"].append(replacement.replacement)

        # Extract printer name aliases from user mappings
        for mapping in self.user_mappings:
            if mapping.printer not in config["printer_names"]:
                config["printer_names"][mapping.printer] = []

        # Extract brand aliases from user mappings
        for mapping in self.user_mappings:
            if mapping.brand not in config["brand_name_mappings"]:
                config["brand_name_mappings"][mapping.brand] = [mapping.brand]
            # Also add to paper_brands if not present
            if mapping.brand not in config["paper_brands"]:
                config["paper_brands"].append(mapping.brand)

        # Add generated filename patterns
        for pattern in self.generated_patterns:
            # Check if pattern already exists (by name)
            existing_names = [p.get("name") for p in config["filename_patterns"]]
            if pattern.get("name") not in existing_names:
                config["filename_patterns"].append(pattern)

        # Sort patterns by priority (highest first)
        config["filename_patterns"].sort(key=lambda p: p.get("priority", 0), reverse=True)

        return config

    def save_config(self, output_path: Path = Path("config.yaml")) -> bool:
        """Save the configuration to a YAML file"""
        try:
            config = self.build_config_dict()
            with open(output_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=True)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False


class WelcomeScreen(Screen):
    """Initial welcome and directory selection screen"""

    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(
                Text.from_markup(
                    "[bold cyan]ICC Profile Organizer - Configuration Wizard[/]\n\n"
                    "This wizard will help you create a config.yaml file to organize your ICC profiles.\n\n"
                    "[bold]Features:[/]\n"
                    "• Automatically scan and detect your profiles\n"
                    "• Fix undetected files with smart suggestions\n"
                    "• Create printer and brand mappings without repetition\n"
                    "• Test patterns before saving\n"
                )
            ),
            Button("Start Setup", id="start-setup", variant="primary"),
            Button("Quit", id="quit-btn"),
            id="welcome-container",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events"""
        if event.button.id == "start-setup":
            self.app.push_screen(ScanScreen())
        elif event.button.id == "quit-btn":
            self.app.exit()


class ScanScreen(Screen):
    """Scan profiles and show detection status"""

    BINDINGS = [
        ("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Cancel", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.wizard = None
        self.scan_complete = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("Select profiles directory to scan:"),
            Input(
                value=str(Path.cwd()),
                id="profile_dir_input",
            ),
            Horizontal(
                Button("Scan Directory", id="scan-btn", variant="primary"),
                Button("Back", id="back-btn"),
            ),
            RichLog(id="scan-results"),
            Horizontal(
                Button("Fix Undetected Files", id="fix-btn", variant="primary", disabled=True),
                Button("Done", id="done-btn", disabled=True),
                id="action-buttons",
            ),
            id="scan-options",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events"""
        if event.button.id == "scan-btn":
            self._action_scan()
        elif event.button.id == "back-btn":
            self.app.pop_screen()
        elif event.button.id == "fix-btn":
            if self.wizard:
                # Push screen for both undetected files (fix mode) and detected files (review mode)
                self.app.push_screen(FixUndetectedScreen(self.wizard))
        elif event.button.id == "done-btn":
            self.app.pop_screen()

    def _action_scan(self) -> None:
        """Scan the selected directory"""
        input_widget = self.query_one("#profile_dir_input", Input)
        dir_path = Path(input_widget.value).expanduser()

        if not dir_path.exists():
            self.query_one("#scan-results", RichLog).write(
                Text("❌ Directory does not exist!", style="red")
            )
            return

        # Create wizard and scan
        self.wizard = ConfigWizard(dir_path)
        self.wizard.scan_profiles()

        detected, total, percentage = self.wizard.get_detection_rate()

        results_log = self.query_one("#scan-results", RichLog)
        results_log.clear()

        # Show results
        results_log.write(Text(f"\n📁 Scanned: {dir_path}\n", style="bold cyan"))

        summary_table = Table(title="Detection Summary", box=box.ROUNDED)
        summary_table.add_column("Status", style="cyan")
        summary_table.add_column("Count", style="yellow")
        summary_table.add_row("✓ Detected", str(detected))
        summary_table.add_row("✗ Undetected", str(total - detected))
        summary_table.add_row("Total", str(total))

        results_log.write(summary_table)
        results_log.write(
            Text(
                f"\n📊 Detection Rate: {percentage:.1f}%\n",
                style="bold green" if percentage >= 90 else "yellow",
            )
        )

        # Enable/disable action buttons
        fix_btn = self.query_one("#fix-btn", Button)
        done_btn = self.query_one("#done-btn", Button)

        if total == 0:
            results_log.write(Text("\n✓ No profile files found in this directory.\n", style="yellow"))
            done_btn.disabled = False
        elif self.wizard.undetected_files:
            results_log.write(
                Text(
                    f"\n⚠️  {len(self.wizard.undetected_files)} files need manual mapping\n",
                    style="yellow",
                )
            )

            # Show first few undetected
            results_log.write(Text("Undetected files:\n", style="bold"))
            for i, pf in enumerate(self.wizard.undetected_files[:10]):
                results_log.write(Text(f"  • {pf.filename}\n", style="dim"))

            if len(self.wizard.undetected_files) > 10:
                results_log.write(
                    Text(
                        f"  ... and {len(self.wizard.undetected_files) - 10} more\n",
                        style="dim",
                    )
                )

            results_log.write(Text("\n"))
            results_log.write(
                Text("Ready to fix undetected files? Click 'Fix Undetected Files' below.\n", style="bold")
            )
            fix_btn.disabled = False
        else:
            results_log.write(Text("\n✓ All files detected!\n", style="green"))
            results_log.write(Text("You can review the detections and adjust any mappings if needed.\n", style="dim"))
            fix_btn.disabled = False  # Enable to allow review even if all detected
            fix_btn.label = "Review Detections"


class FixUndetectedScreen(Screen):
    """Interactive screen to fix undetected files by groups"""

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(self, wizard: ConfigWizard):
        super().__init__()
        self.wizard = wizard
        self.current_index = 0
        # If there are undetected files, group those; otherwise group detected files for review
        if wizard.undetected_files:
            self.file_groups = wizard.group_undetected_files()
        else:
            self.file_groups = wizard.group_detected_files()
        self.confirmed_groups: Dict[int, Tuple[str, str]] = {}  # group_index -> (printer, brand)
        self.pattern_replacements: Dict[int, Tuple[str, str, str, str]] = {}  # group_index -> (printer_orig, printer_repl, brand_orig, brand_repl)

    def compose(self) -> ComposeResult:
        yield Header()

        if not self.file_groups:
            yield Container(
                Static(Text("✓ No files to review!", style="green")),
                Button("Done", id="done-btn"),
            )
            return

        current_group = self.file_groups[self.current_index]
        is_review_mode = self.wizard.undetected_files == []  # Review mode if no undetected files

        # Determine button text based on mode
        action_button_text = "Looks Good, Next" if is_review_mode else "Confirm & Next"
        hint_text = "\n💡 These detections look correct. Click 'Looks Good, Next' to continue." if is_review_mode else "\n💡 Paper types will be auto-extracted from each filename"

        yield Container(
            Static(f"Group {self.current_index + 1} of {len(self.file_groups)}", id="group-counter"),
            Vertical(
                Static(Text(f"Pattern: {current_group.pattern_similarity}", style="bold yellow"), id="pattern-display"),
                Static(Text(f"\n{len(current_group.files)} files match this pattern:", style="cyan"), id="file-count"),
                RichLog(id="example-files", max_lines=5),
                Static("", id="detection-display"),
                Vertical(
                    Label("Printer Model:"),
                    Input(id="printer-input"),
                    Label("Paper Brand:"),
                    Input(id="brand-input"),
                    id="mapping-form",
                ),
                Static(Text("\n💡 Optional: Add pattern replacements to help detect similar files", style="bold yellow"), id="pattern-hint"),
                Vertical(
                    Static(Text("Printer Pattern (optional):", style="bold")),
                    Horizontal(
                        Input(id="printer-pattern-orig", placeholder="Text in filename (e.g., PRO-100)"),
                        Static("→", id="arrow1"),
                        Input(id="printer-pattern-repl", placeholder="Replace with (e.g., Canon Pixma PRO-100)"),
                    ),
                    Static(Text("Brand Pattern (optional):", style="bold")),
                    Horizontal(
                        Input(id="brand-pattern-orig", placeholder="Text in filename (e.g., MOAB)"),
                        Static("→", id="arrow2"),
                        Input(id="brand-pattern-repl", placeholder="Replace with (e.g., MOAB)"),
                    ),
                    id="pattern-form",
                ),
                Static(Text(hint_text, style="dim italic"), id="hint"),
                Horizontal(
                    Button("Previous", id="prev-btn"),
                    Button(action_button_text, id="save-next-btn", variant="primary"),
                    Button("Skip Group", id="skip-btn"),
                    Button("Done", id="done-btn"),
                ),
                id="group-editor",
            ),
            id="main-container",
        )
        yield Footer()

    def _update_group_display(self) -> None:
        """Update the display for the current group"""
        current_group = self.file_groups[self.current_index]

        # Show example files
        examples_log = self.query_one("#example-files", RichLog)
        examples_log.clear()
        for i, file in enumerate(current_group.files[:5]):
            examples_log.write(Text(f"  • {file.filename}", style="dim"))
        if len(current_group.files) > 5:
            examples_log.write(Text(f"  ... and {len(current_group.files) - 5} more", style="dim italic"))

        # Show detection status
        detection_text = Text()

        # Check if we have valid detections (not "Unknown")
        has_valid_printer = current_group.detected_printer and current_group.detected_printer != "Unknown"
        has_valid_brand = current_group.detected_brand and current_group.detected_brand != "Unknown"

        if has_valid_printer or has_valid_brand:
            detection_text.append("\n✓ Auto-detected:\n", style="bold green")
            if has_valid_printer:
                detection_text.append(f"  Printer: {current_group.detected_printer}\n", style="cyan")
            if has_valid_brand:
                detection_text.append(f"  Brand: {current_group.detected_brand}\n", style="cyan")

            missing = []
            if not has_valid_printer:
                missing.append("printer")
            if not has_valid_brand:
                missing.append("brand")

            if missing:
                detection_text.append(f"\n⚠ Please specify: {', '.join(missing)}\n", style="yellow")
        else:
            detection_text.append("\n⚠ Could not auto-detect printer or brand\n", style="yellow")
            detection_text.append("Please fill in both fields and add pattern replacements if needed\n", style="dim")

        self.query_one("#detection-display", Static).update(detection_text)

    def on_mount(self) -> None:
        """Initialize the form with auto-detected values"""
        self._update_group_display()

        current_group = self.file_groups[self.current_index]
        is_review_mode = self.wizard.undetected_files == []

        # Check if user previously confirmed this group
        if self.current_index in self.confirmed_groups:
            printer, brand = self.confirmed_groups[self.current_index]
            self.query_one("#printer-input", Input).value = printer
            self.query_one("#brand-input", Input).value = brand
        else:
            # Auto-populate with detected values
            if current_group.detected_printer:
                self.query_one("#printer-input", Input).value = current_group.detected_printer
            if current_group.detected_brand:
                self.query_one("#brand-input", Input).value = current_group.detected_brand

        # Load pattern replacements if previously set
        if self.current_index in self.pattern_replacements:
            printer_orig, printer_repl, brand_orig, brand_repl = self.pattern_replacements[self.current_index]
            self.query_one("#printer-pattern-orig", Input).value = printer_orig
            self.query_one("#printer-pattern-repl", Input).value = printer_repl
            self.query_one("#brand-pattern-orig", Input).value = brand_orig
            self.query_one("#brand-pattern-repl", Input).value = brand_repl

        # Hide pattern form in review mode
        pattern_form = self.query_one("#pattern-form", Vertical)
        pattern_hint = self.query_one("#pattern-hint", Static)
        if is_review_mode:
            pattern_form.display = False
            pattern_hint.display = False
        else:
            pattern_form.display = True
            pattern_hint.display = True

    def _save_current_group(self) -> bool:
        """Save the current group mapping"""
        printer = self.query_one("#printer-input", Input).value.strip()
        brand = self.query_one("#brand-input", Input).value.strip()

        if not all([printer, brand]):
            self.notify("Please fill in printer and brand", severity="error", timeout=3)
            return False

        current_group = self.file_groups[self.current_index]

        # Store the confirmation
        self.confirmed_groups[self.current_index] = (printer, brand)

        # Get pattern replacements (optional)
        printer_pattern_orig = self.query_one("#printer-pattern-orig", Input).value.strip()
        printer_pattern_repl = self.query_one("#printer-pattern-repl", Input).value.strip()
        brand_pattern_orig = self.query_one("#brand-pattern-orig", Input).value.strip()
        brand_pattern_repl = self.query_one("#brand-pattern-repl", Input).value.strip()

        # Store pattern replacements for this group
        self.pattern_replacements[self.current_index] = (
            printer_pattern_orig,
            printer_pattern_repl,
            brand_pattern_orig,
            brand_pattern_repl,
        )

        # Add pattern replacements to wizard if both original and replacement are provided
        # Collect example filenames from this group
        example_filenames = [pf.filename for pf in current_group.files[:5]]  # Use first 5 as examples
        
        if printer_pattern_orig and printer_pattern_repl:
            replacement = PatternReplacement(
                original_text=printer_pattern_orig,
                replacement=printer_pattern_repl,
                replacement_type="printer",
                example_filenames=example_filenames,
            )
            self.wizard.add_pattern_replacement(replacement)

        if brand_pattern_orig and brand_pattern_repl:
            replacement = PatternReplacement(
                original_text=brand_pattern_orig,
                replacement=brand_pattern_repl,
                replacement_type="brand",
                example_filenames=example_filenames,
            )
            self.wizard.add_pattern_replacement(replacement)

        # Generate filename pattern if we have both printer and brand replacements
        if (printer_pattern_orig and printer_pattern_repl and 
            brand_pattern_orig and brand_pattern_repl and example_filenames):
            pattern = self.wizard._analyze_filename_structure(
                example_filenames[0],
                printer_pattern_orig,
                brand_pattern_orig,
                printer_pattern_repl,
                brand_pattern_repl,
            )
            if pattern:
                self.wizard.add_generated_pattern(pattern)

        # Create mappings for all files in this group
        for profile_file in current_group.files:
            # Try to extract paper type from filename using ConfigManager
            detected = self.wizard._analyze_file(profile_file.filename)
            paper_type = detected.get("paper_type")

            # If no paper type detected, use formatted filename stem as fallback
            if not paper_type:
                raw_name = Path(profile_file.filename).stem
                # Use lib function to format the paper type properly
                paper_type = format_paper_type(raw_name)

            mapping = UserMapping(
                filename=profile_file.filename,
                printer=printer,
                brand=brand,
                paper_type=paper_type,
            )
            self.wizard.add_user_mapping(mapping)

        return True

    def _move_to_group(self, index: int) -> None:
        """Move to a specific group index"""
        if not (0 <= index < len(self.file_groups)):
            return

        self.current_index = index

        # Update the display for the new group
        current_group = self.file_groups[self.current_index]

        # Update counter
        self.query_one("#group-counter", Static).update(f"Group {self.current_index + 1} of {len(self.file_groups)}")

        # Update pattern display
        self.query_one("#pattern-display", Static).update(Text(f"Pattern: {current_group.pattern_similarity}", style="bold yellow"))

        # Update file count
        self.query_one("#file-count", Static).update(Text(f"\n{len(current_group.files)} files match this pattern:", style="cyan"))

        # Update the group display (examples and detection status)
        self._update_group_display()

        # Update input fields
        if self.current_index in self.confirmed_groups:
            printer, brand = self.confirmed_groups[self.current_index]
            self.query_one("#printer-input", Input).value = printer
            self.query_one("#brand-input", Input).value = brand
        else:
            # Auto-populate with detected values
            self.query_one("#printer-input", Input).value = current_group.detected_printer or ""
            self.query_one("#brand-input", Input).value = current_group.detected_brand or ""

        # Update pattern replacement fields
        if self.current_index in self.pattern_replacements:
            printer_orig, printer_repl, brand_orig, brand_repl = self.pattern_replacements[self.current_index]
            self.query_one("#printer-pattern-orig", Input).value = printer_orig
            self.query_one("#printer-pattern-repl", Input).value = printer_repl
            self.query_one("#brand-pattern-orig", Input).value = brand_orig
            self.query_one("#brand-pattern-repl", Input).value = brand_repl
        else:
            self.query_one("#printer-pattern-orig", Input).value = ""
            self.query_one("#printer-pattern-repl", Input).value = ""
            self.query_one("#brand-pattern-orig", Input).value = ""
            self.query_one("#brand-pattern-repl", Input).value = ""

        # Show/hide pattern form based on mode
        is_review_mode = self.wizard.undetected_files == []
        pattern_form = self.query_one("#pattern-form", Vertical)
        pattern_hint = self.query_one("#pattern-hint", Static)
        if is_review_mode:
            pattern_form.display = False
            pattern_hint.display = False
        else:
            pattern_form.display = True
            pattern_hint.display = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events"""
        if event.button.id == "save-next-btn":
            self._on_save_next()
        elif event.button.id == "prev-btn":
            if self.current_index > 0:
                self._move_to_group(self.current_index - 1)
        elif event.button.id == "skip-btn":
            # Skip this group and move to next
            if self.current_index + 1 < len(self.file_groups):
                self._move_to_group(self.current_index + 1)
            else:
                self.app.pop_screen()
                self.app.push_screen(ReviewScreen(self.wizard))
        elif event.button.id == "cancel-btn":
            self.app.pop_screen()
        elif event.button.id == "done-btn":
            self.app.pop_screen()

    def _on_save_next(self) -> None:
        """Save current group and move to next"""
        if not self._save_current_group():
            return

        if self.current_index + 1 < len(self.file_groups):
            self._move_to_group(self.current_index + 1)
        else:
            # All done
            self.app.pop_screen()
            self.app.push_screen(ReviewScreen(self.wizard))


class ReviewScreen(Screen):
    """Review mappings before saving"""

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, wizard: ConfigWizard):
        super().__init__()
        self.wizard = wizard

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("Review Your Mappings:", id="title"),
            RichLog(id="review-log"),
            Horizontal(
                Button("Save config.yaml", id="save-btn", variant="primary"),
                Button("Edit More", id="edit-more-btn"),
                Button("Cancel", id="cancel-btn"),
            ),
            id="review-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Display the mappings review"""
        log = self.query_one("#review-log", RichLog)

        if not self.wizard.user_mappings and not self.wizard.pattern_replacements:
            log.write(Text("No mappings defined yet.", style="yellow"))
            return

        # Show pattern replacements first
        if self.wizard.pattern_replacements:
            log.write(Text("\n🔧 Pattern Replacements:\n", style="bold cyan"))
            
            printer_replacements = [r for r in self.wizard.pattern_replacements if r.replacement_type == "printer"]
            brand_replacements = [r for r in self.wizard.pattern_replacements if r.replacement_type == "brand"]
            
            if printer_replacements:
                log.write(Text("\n  Printer Patterns:\n", style="bold yellow"))
                for replacement in printer_replacements:
                    log.write(Text(f"    {replacement.original_text} → {replacement.replacement}\n", style="dim"))
            
            if brand_replacements:
                log.write(Text("\n  Brand Patterns:\n", style="bold yellow"))
                for replacement in brand_replacements:
                    log.write(Text(f"    {replacement.original_text} → {replacement.replacement}\n", style="dim"))
            
            log.write(Text("\n"))

        if not self.wizard.user_mappings:
            return

        # Group by printer and brand
        grouped = {}
        for mapping in self.wizard.user_mappings:
            key = (mapping.printer, mapping.brand)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(mapping)

        log.write(Text(f"\n📝 Total File Mappings: {len(self.wizard.user_mappings)}\n", style="bold cyan"))

        # Track existing filenames for deduplication
        existing_names = {}

        for (printer, brand), mappings in sorted(grouped.items()):
            log.write(Text(f"\n{printer} → {brand}:\n", style="bold"))
            for m in mappings:
                # Get file extension
                ext = Path(m.filename).suffix.lstrip('.')

                # Generate the new standardized filename using lib function
                new_filename = generate_new_filename(m.printer, m.brand, m.paper_type, ext, existing_names)

                # Show old → new on same line
                mapping_line = Text()
                mapping_line.append(f"  • {m.filename}", style="dim")
                mapping_line.append(" → ", style="yellow")
                mapping_line.append(f"{new_filename}\n", style="cyan")
                log.write(mapping_line)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events"""
        if event.button.id == "save-btn":
            if self.wizard.save_config():
                self.app.notify("✓ config.yaml saved successfully!", timeout=5)
                self.app.pop_screen()
                self.app.pop_screen()
                self.app.push_screen(SuccessScreen(self.wizard))
            else:
                self.app.notify("Error saving config.yaml", severity="error", timeout=5)
        elif event.button.id == "edit-more-btn":
            self.app.pop_screen()
        elif event.button.id == "cancel-btn":
            self.app.pop_screen()


class SuccessScreen(Screen):
    """Success confirmation screen"""

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, wizard: ConfigWizard):
        super().__init__()
        self.wizard = wizard

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(
                Text.from_markup(
                    "[bold green]✓ Configuration Complete![/]\n\n"
                    f"Saved {len(self.wizard.user_mappings)} mappings to config.yaml\n\n"
                    "You can now run:\n"
                    "  python organize_profiles.py [--execute]\n\n"
                    "to organize your profiles!"
                )
            ),
            Button("Done", id="done-btn", variant="primary"),
            id="success-container",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events"""
        if event.button.id == "done-btn":
            self.app.exit()


class WizardApp(App):
    """Main Textual application"""

    TITLE = "ICC Profile Organizer - Configuration Wizard"
    BINDINGS = [
        ("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Cancel", show=False),
    ]

    def on_mount(self) -> None:
        self.push_screen(WelcomeScreen())


def main():
    """Run the wizard"""
    app = WizardApp()
    app.run()


if __name__ == "__main__":
    main()
