#!/usr/bin/env python3
"""
ICC Profile, EMX/EMY2, and PDF Organizer
Renames and organizes color profiles and documentation by Printer and Paper Brand.
"""

import os
import sys
import shutil
import hashlib
import json
import struct
import platform
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict
import logging
from datetime import datetime
from dataclasses import dataclass, field

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    print("Warning: PyYAML not available. Install with: pip install PyYAML")

try:
    from PIL import Image
    from PIL.TiffImagePlugin import IFDRational
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: PIL not available. Install with: pip install Pillow")


# System ICC profile paths by OS
SYSTEM_ICC_PATHS = {
    'Darwin': {
        'system': Path('/Library/ColorSync/Profiles'),
        'user': Path.home() / 'Library' / 'ColorSync' / 'Profiles',
    },
    'Windows': Path('C:\\Windows\\System32\\spool\\drivers\\color'),
}

# Detect current OS
CURRENT_OS = platform.system()
SYSTEM_ICC_PATH = SYSTEM_ICC_PATHS.get(CURRENT_OS)


class ICCProfileUpdater:
    """Handle reading and updating ICC profile descriptions."""

    # ASCII signature at start of ICC files
    ICC_SIGNATURE = b'acsp'

    # Tag signature for description
    DESC_TAG = b'desc'

    def __init__(self, verbose: bool = True):
        """Initialize the updater."""
        self.verbose = verbose

    def log(self, message: str):
        """Log a message."""
        if self.verbose:
            print(message)

    def read_icc_profile(self, file_path: Path) -> Optional[bytes]:
        """Read ICC profile file."""
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            self.log(f"Error reading {file_path}: {e}")
            return None

    def write_icc_profile(self, file_path: Path, data: bytes) -> bool:
        """Write ICC profile file."""
        try:
            with open(file_path, 'wb') as f:
                f.write(data)
            return True
        except Exception as e:
            self.log(f"Error writing {file_path}: {e}")
            return False

    def validate_header(self, data: bytes) -> bool:
        """Validate ICC profile header."""
        if len(data) < 128:
            return False
        try:
            # Check for ICC signature at offset 36
            signature = data[36:40]
            return signature == self.ICC_SIGNATURE
        except Exception:
            return False

    def find_tag(self, data: bytes, tag_sig: bytes) -> Optional[Tuple[int, int]]:
        """
        Find tag in ICC profile.
        Returns tuple of (offset, size) or None if not found.
        """
        # Parse tag table at offset 128
        if len(data) < 132:
            return None

        try:
            tag_count = struct.unpack('>I', data[128:132])[0]

            # Each tag entry is 12 bytes: signature (4) + offset (4) + size (4)
            for i in range(tag_count):
                entry_offset = 132 + (i * 12)

                if entry_offset + 12 > len(data):
                    break

                entry_sig = data[entry_offset:entry_offset + 4]
                tag_offset = struct.unpack('>I', data[entry_offset + 4:entry_offset + 8])[0]
                tag_size = struct.unpack('>I', data[entry_offset + 8:entry_offset + 12])[0]

                if entry_sig == tag_sig:
                    return (tag_offset, tag_size)

            return None
        except Exception:
            return None

    def update_description_tag(self, data: bytes, new_description: str) -> Optional[bytes]:
        """
        Update the description tag in an ICC profile.

        The desc tag structure:
        - Bytes 0-3: Tag signature ('desc')
        - Bytes 4-7: Reserved (0)
        - Bytes 8-11: ASCII description length (including null terminator)
        - Bytes 12+: ASCII description
        """
        try:
            # Find existing desc tag
            tag_info = self.find_tag(data, self.DESC_TAG)

            if not tag_info:
                return None

            old_offset, old_size = tag_info

            # Create new desc tag data
            # Limit description to ASCII, max 255 chars
            desc_ascii = new_description.encode('ascii', errors='replace')[:255]

            # Create the desc tag structure
            desc_data = self.DESC_TAG  # 4 bytes: 'desc'
            desc_data += b'\x00\x00\x00\x00'  # 4 bytes: reserved

            desc_length = len(desc_ascii) + 1  # +1 for null terminator
            desc_data += struct.pack('>I', desc_length)  # 4 bytes: length
            desc_data += desc_ascii  # description
            desc_data += b'\x00'  # null terminator

            # Pad to multiple of 4 bytes (ICC requirement)
            padding = (4 - (len(desc_data) % 4)) % 4
            desc_data += b'\x00' * padding

            new_size = len(desc_data)

            # If new data is same size or smaller than old, we can safely replace
            if new_size <= old_size:
                # Pad the new data to match old size
                if new_size < old_size:
                    desc_data += b'\x00' * (old_size - new_size)

                # Simple replacement
                new_data = data[:old_offset] + desc_data + data[old_offset + old_size:]
                return new_data

            else:
                # New description is too long to fit in-place
                # Truncate to fit
                max_desc_len = old_size - 12  # 12 bytes for header, rest for description
                if max_desc_len <= 0:
                    return None

                desc_ascii = new_description.encode('ascii', errors='replace')[:max_desc_len - 1]

                desc_data = self.DESC_TAG
                desc_data += b'\x00\x00\x00\x00'
                desc_length = len(desc_ascii) + 1
                desc_data += struct.pack('>I', desc_length)
                desc_data += desc_ascii
                desc_data += b'\x00'

                # Pad to old size
                padding = old_size - len(desc_data)
                if padding > 0:
                    desc_data += b'\x00' * padding

                new_data = data[:old_offset] + desc_data + data[old_offset + old_size:]
                return new_data

        except Exception:
            return None

    def process_profile(self, file_path: Path) -> bool:
        """
        Process a single ICC profile file.
        Returns True if successful, False otherwise.
        """
        # Get the filename without extension as the new description
        new_description = file_path.stem

        # Read the profile
        profile_data = self.read_icc_profile(file_path)
        if not profile_data:
            return False

        # Validate header
        if not self.validate_header(profile_data):
            return False

        # Update description
        updated_data = self.update_description_tag(profile_data, new_description)
        if not updated_data:
            return False

        # Write back
        if self.write_icc_profile(file_path, updated_data):
            return True

        return False

    def process_directory(self, directory: Path, verbose: bool = True) -> Tuple[int, int]:
        """
        Process all ICC profiles in a directory recursively.
        Returns tuple of (processed, successful).
        """
        # Find all ICC files
        icc_files = list(directory.rglob('*.icc'))
        icm_files = list(directory.rglob('*.icm'))

        # Filter out macOS resource forks
        icc_files = [f for f in icc_files if '._' not in f.name]
        icm_files = [f for f in icm_files if '._' not in f.name]

        all_files = icc_files + icm_files

        if verbose:
            print(f"  Updating descriptions for {len(all_files)} profile files...")

        processed = 0
        successful = 0

        for file_path in sorted(all_files):
            processed += 1
            if self.process_profile(file_path):
                successful += 1

        return processed, successful


# ============================================================================
# Pattern Matching System - Dataclasses for generalized filename parsing
# ============================================================================

@dataclass
class FieldDefinition:
    """Defines a field in a filename pattern."""
    field: str  # "printer", "paper_type", "brand", etc.
    position: Optional[Any] = None  # Index, "before_printer", "after_printer", "1+", "remaining", etc.
    match_type: Optional[str] = None  # "key_search", "substring", etc.


@dataclass
class PatternVariant:
    """Variant prefix for patterns with multiple prefix options (like HFA variants)."""
    prefix: str
    prefix_length: int


@dataclass
class PaperTypeProcessing:
    """Configuration for paper type formatting."""
    format: bool = False  # Apply CamelCase separation
    remove_brand: Optional[str] = None  # Brand name to remove from paper type


@dataclass
class FilenamePattern:
    """Complete pattern definition for parsing a filename format."""
    name: str
    priority: int
    description: str
    prefix: Optional[str]
    prefix_case_insensitive: bool
    delimiter: str
    structure: List[FieldDefinition]
    brand_value: Optional[str]
    paper_type_processing: PaperTypeProcessing
    variants: List[PatternVariant] = field(default_factory=list)

    def __lt__(self, other):
        """Enable sorting by priority (higher priority first)."""
        return self.priority > other.priority


class PatternMatcher:
    """Unified pattern matching engine for filename parsing."""

    def __init__(self, patterns: List[FilenamePattern], printer_names: Dict[str, str],
                 brand_name_mappings: Dict[str, str], format_paper_type_fn):
        """
        Initialize the pattern matcher.

        Args:
            patterns: List of FilenamePattern objects, sorted by priority
            printer_names: Dict mapping printer keys to canonical names
            brand_name_mappings: Dict mapping brand variants to canonical names
            format_paper_type_fn: Function to format paper type strings
        """
        self.patterns = sorted(patterns)  # Sort by priority (higher first)
        self.printer_names = printer_names
        self.brand_name_mappings = brand_name_mappings
        self.format_paper_type = format_paper_type_fn

    def match(self, filename: str) -> Optional[Tuple[Optional[str], Optional[str], Optional[str]]]:
        """
        Try to match filename against patterns.

        Returns:
            Tuple of (printer_name, paper_brand, paper_type) or None if no match
        """
        name_without_ext = Path(filename).stem

        # Apply preprocessing
        name_without_ext = name_without_ext.replace('+', ' ')

        # Try each pattern in priority order
        for pattern in self.patterns:
            result = self._try_pattern(name_without_ext, pattern)
            if result:
                return result

        return None

    def _try_pattern(self, filename: str, pattern: FilenamePattern) -> Optional[Tuple[str, str, str]]:
        """Try to match filename against a specific pattern."""
        # Check prefix match
        if pattern.prefix is not None:
            if pattern.variants:
                # Try variant prefixes
                prefix_match = None
                prefix_len = 0
                for variant in pattern.variants:
                    if pattern.prefix_case_insensitive:
                        if filename.lower().startswith(variant.prefix.lower()):
                            prefix_match = variant.prefix
                            prefix_len = variant.prefix_length
                            break
                    else:
                        if filename.startswith(variant.prefix):
                            prefix_match = variant.prefix
                            prefix_len = variant.prefix_length
                            break

                if not prefix_match:
                    return None

                # Remove prefix and parse
                remaining = filename[prefix_len:]
            else:
                # Single prefix
                if pattern.prefix_case_insensitive:
                    if not filename.upper().startswith(pattern.prefix.upper()):
                        return None
                    remaining = filename[len(pattern.prefix):]
                else:
                    if not filename.startswith(pattern.prefix):
                        return None
                    remaining = filename[len(pattern.prefix):]
        else:
            # No prefix requirement (fallback pattern)
            remaining = filename

        # Split remaining part by delimiter
        parts = remaining.split(pattern.delimiter)

        # Extract fields based on structure
        extracted = {}
        for field_def in pattern.structure:
            value = self._extract_field(parts, field_def, filename, pattern)
            if value is not None:
                extracted[field_def.field] = value

        # Validate we got required fields
        if 'printer' not in extracted:
            return None

        # Get paper brand
        if pattern.brand_value is not None:
            brand = pattern.brand_value
        elif 'brand' in extracted:
            brand = extracted['brand']
        else:
            brand = 'Unknown'

        # Normalize brand
        brand = self._normalize_brand(brand)

        # Get paper type
        paper_type = extracted.get('paper_type', 'Unknown')

        # Format paper type if needed
        if pattern.paper_type_processing.format:
            remove_brand = pattern.paper_type_processing.remove_brand
            paper_type = self.format_paper_type(paper_type, remove_brand=remove_brand)

        return extracted['printer'], brand, paper_type

    def _extract_field(self, parts: List[str], field_def: FieldDefinition,
                      filename: str, pattern: FilenamePattern) -> Optional[str]:
        """Extract a field value based on field definition."""
        if field_def.match_type == 'key_search':
            # Search through printer keys
            for printer_key in self.printer_names.keys():
                for i, part in enumerate(parts):
                    if part.lower() == printer_key.lower() or \
                       part == printer_key or \
                       printer_key.lower() in part.lower():
                        return self.printer_names.get(printer_key, printer_key)
            return None

        elif field_def.match_type == 'substring':
            # Find printer key via case-insensitive substring
            filename_lower = filename.lower()
            best_match = None
            best_key = None
            for printer_key in self.printer_names.keys():
                if printer_key.lower() in filename_lower:
                    if best_key is None or len(printer_key) > len(best_key):
                        best_key = printer_key
                        best_match = self.printer_names.get(printer_key, printer_key)
            return best_match

        elif isinstance(field_def.position, int):
            # Fixed position
            if 0 <= field_def.position < len(parts):
                part = parts[field_def.position]
                # If this is a printer field, try to look it up in printer names
                if field_def.field == 'printer':
                    # Try exact match first
                    if part in self.printer_names:
                        return self.printer_names[part]
                    # Try case-insensitive match
                    for key, value in self.printer_names.items():
                        if part.lower() == key.lower():
                            return value
                        # Also try substring match for keys like "SC-P900" matching "P900"
                        if key.lower() in part.lower() or part.lower() in key.lower():
                            return value
                    # If no match found, return the raw part (might match later in pipeline)
                    return part
                return part
            return None

        elif field_def.position == "before_printer":
            # Everything before the printer key
            for i, part in enumerate(parts):
                for printer_key in self.printer_names.keys():
                    if part.lower() == printer_key.lower() or printer_key.lower() in part.lower():
                        return pattern.delimiter.join(parts[:i])
            return None

        elif field_def.position == "after_printer":
            # Everything after the printer key
            for i, part in enumerate(parts):
                for printer_key in self.printer_names.keys():
                    if part.lower() == printer_key.lower() or printer_key.lower() in part.lower():
                        if i + 1 < len(parts):
                            return pattern.delimiter.join(parts[i + 1:])
            return None

        elif isinstance(field_def.position, str) and field_def.position.endswith('+'):
            # Range: "1+" or "2+"
            try:
                start_idx = int(field_def.position[:-1])
                if start_idx < len(parts):
                    return pattern.delimiter.join(parts[start_idx:])
            except ValueError:
                pass
            return None

        elif field_def.position == "remaining":
            # Everything except printer key
            filename_lower = filename.lower()
            best_key = None
            for printer_key in self.printer_names.keys():
                if printer_key.lower() in filename_lower:
                    if best_key is None or len(printer_key) > len(best_key):
                        best_key = printer_key
            if best_key:
                # Remove the printer key from filename
                result = filename_lower.replace(best_key.lower(), '').strip()
                return result
            return None

        return None

    def _normalize_brand(self, brand: str) -> str:
        """Normalize brand name using mappings."""
        if brand in self.brand_name_mappings:
            return self.brand_name_mappings[brand]
        return brand


class ProfileOrganizer:
    """Organizes ICC profiles, EMX files, and PDFs."""

    # Default configuration values (fallback if config.yaml not found)
    DEFAULT_PRINTER_NAMES = {
        'PRO-100': 'Canon Pixma PRO-100',
        'Pro-100': 'Canon Pixma PRO-100',
        'pro-100': 'Canon Pixma PRO-100',
        'pixmapro100': 'Canon Pixma PRO-100',
        'pro100': 'Canon Pixma PRO-100',
        'CanPro-100': 'Canon Pixma PRO-100',
        'CanPro100': 'Canon Pixma PRO-100',
        'canpro-100': 'Canon Pixma PRO-100',
        'canpro100': 'Canon Pixma PRO-100',
        'CANPRO-100': 'Canon Pixma PRO-100',
        'CANPRO100': 'Canon Pixma PRO-100',
        'Can6450': 'Canon iPF6450',
        'Can8400': 'Canon iPF8400',
        'iPF6450': 'Canon iPF6450',
        'ipf6450': 'Canon iPF6450',
        'iPf6450': 'Canon iPF6450',  # Lowercase 'f' variant
        'ipf6400': 'Canon iPF6450',  # Alternative naming
        'IPF6400': 'Canon iPF6450',  # Red River Paper uses IPF6400
        'iPFX400': 'Canon iPF6450',  # Red River Paper uses iPFX400 as generic placeholder
        'P700': 'Epson P700',
        'P900': 'Epson P900',
        'SC-P700': 'Epson P700',
        'SC-P900': 'Epson P900',
        'EpsSC-P700': 'Epson P700',
        'EpsSC-P900': 'Epson P900',
        'EpsSC-P7570': 'Epson P7570',
        'EpsSC-P9500': 'Epson P9500',
        'p900': 'Epson P900',
        'P7570': 'Epson P7570',
        'SC-P7570': 'Epson P7570',
        'p7570': 'Epson P7570',
        'EpsSC-P7570': 'Epson P7570',
        'Epson SureColor P7570': 'Epson P7570',
        'P7500': 'Epson P7500',
        'SC-P7500': 'Epson P7500',
        'p7500': 'Epson P7500',
        'P9570': 'Epson P9570',
        'SC-P9570': 'Epson P9570',
    }

    # Default paper brands
    DEFAULT_PAPER_BRANDS = ['Moab', 'Canson', 'Hahnemuehle']

    # Default brand name mappings
    DEFAULT_BRAND_NAME_MAPPINGS = {
        'cifa': 'Canson',
        'CIFA': 'Canson',
        'canson': 'Canson',
        'Canson': 'Canson',
        'HFA': 'Hahnemuehle',
        'hfa': 'Hahnemuehle',
        'Hahnemuehle': 'Hahnemuehle',
        'hahnemuehle': 'Hahnemuehle',
        'MOAB': 'MOAB',
        'Moab': 'MOAB',
        'moab': 'MOAB',
    }

    # Default printer remappings (consolidate similar printers)
    DEFAULT_PRINTER_REMAPPINGS = {
        'Canon iPF8400': 'Canon iPF6450',
        'Epson P700': 'Epson P900',
        'Epson P7500': 'Epson P7570',
        'Epson P9500': 'Epson P7570',
        'Epson SureColor P7570': 'Epson P7570',
    }

    def __init__(self, profiles_dir: str, output_dir: str = None, dry_run: bool = True, verbose: bool = False, interactive: bool = False, detailed: bool = False, update_descriptions: bool = True):
        """
        Initialize the organizer.

        Args:
            profiles_dir: Path to source /profiles directory
            output_dir: Path to output directory (default: ./organized-profiles)
            dry_run: If True, don't actually move files, just preview
            verbose: If True, print detailed information (deprecated, use detailed)
            interactive: If True, prompt user for multi-printer profiles
            detailed: If True, show each file transformation; if False, show summary only
            update_descriptions: If True, update ICC profile descriptions to match filenames
        """
        self.profiles_dir = Path(profiles_dir).resolve()

        # Set output directory (default to organized-profiles sibling)
        if output_dir is None:
            self.output_dir = self.profiles_dir.parent / 'organized-profiles'
        else:
            self.output_dir = Path(output_dir).resolve()

        self.dry_run = dry_run
        self.verbose = verbose or detailed  # Keep verbose for logging, use detailed for UI
        self.interactive = interactive
        self.detailed = detailed
        self.update_descriptions = update_descriptions

        # Setup logging
        self.setup_logging()

        # Load configuration from config.yaml
        self._load_config()

        # Storage for file operations
        self.operations = []  # List of (old_path, new_path) tuples
        self.pdf_duplicates = defaultdict(list)  # Hash -> list of paths
        self.files_renamed = []
        self.files_deleted = []

        # Cache for user choices on multi-printer files (per-file)
        self.choices_cache_path = self.profiles_dir.parent / '.profile_choices.json'
        self.user_choices = self._load_choices_cache()

        # Global preferences for printer conflicts (e.g., when P7570 and P9570 appear together)
        self.preferences_path = self.profiles_dir.parent / '.profile_preferences.json'
        self.global_preferences = self._load_global_preferences()

        # Track selected system profile directory
        self.selected_system_profile_path = None

        if not self.profiles_dir.exists():
            self.log(f"Error: {self.profiles_dir} does not exist", level='ERROR')
            sys.exit(1)

    def setup_logging(self):
        """Setup logging configuration."""
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler('profile_organizer.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def log(self, message: str, level: str = 'INFO'):
        """Log a message."""
        if self.verbose:
            print(message)
        getattr(self.logger, level.lower())(message)

    def _load_config(self):
        """Load configuration from config.yaml, fallback to defaults."""
        config_path = Path(__file__).parent / 'config.yaml'

        if config_path.exists() and YAML_AVAILABLE:
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f) or {}

                # Load and flatten printer names from canonical_name: [aliases] format
                printer_names_raw = config.get('printer_names', {})
                self.PRINTER_NAMES = self._flatten_mapping(printer_names_raw)

                # Load paper brands
                self.PAPER_BRANDS = config.get('paper_brands', self.DEFAULT_PAPER_BRANDS)

                # Load and flatten brand name mappings from canonical_name: [aliases] format
                brand_mappings_raw = config.get('brand_name_mappings', {})
                self.BRAND_NAME_MAPPINGS = self._flatten_mapping(brand_mappings_raw)

                # Load printer remappings (optional)
                self.PRINTER_REMAPPINGS = config.get('printer_remappings', {})

                # Load filename patterns and build PatternMatcher
                patterns_raw = config.get('filename_patterns', [])
                self._build_pattern_matcher(patterns_raw)

                self.log(f"Loaded configuration from {config_path}")
                return
            except Exception as e:
                self.log(f"Warning: Could not load config.yaml: {e}", level='WARNING')

        # Use defaults if config not found or couldn't be parsed
        self.PRINTER_NAMES = self.DEFAULT_PRINTER_NAMES
        self.PAPER_BRANDS = self.DEFAULT_PAPER_BRANDS
        self.BRAND_NAME_MAPPINGS = self.DEFAULT_BRAND_NAME_MAPPINGS
        self.PRINTER_REMAPPINGS = self.DEFAULT_PRINTER_REMAPPINGS
        self._build_default_pattern_matcher()

    def _flatten_mapping(self, mapping: Dict[str, List[str]]) -> Dict[str, str]:
        """
        Convert a hierarchical mapping from canonical: [aliases] format to flat dict.

        Input:  {'Canonical Name': ['alias1', 'alias2']}
        Output: {'alias1': 'Canonical Name', 'alias2': 'Canonical Name'}
        """
        flat = {}
        for canonical_name, aliases in mapping.items():
            if isinstance(aliases, list):
                for alias in aliases:
                    flat[alias] = canonical_name
            else:
                # Handle case where value is a string instead of list (shouldn't happen in new format)
                flat[aliases] = canonical_name
        return flat

    def _build_pattern_matcher(self, patterns_raw: List[Dict[str, Any]]):
        """Build PatternMatcher from config YAML patterns."""
        try:
            patterns = []
            for pattern_dict in patterns_raw:
                pattern = self._parse_pattern_dict(pattern_dict)
                if pattern:
                    patterns.append(pattern)

            if patterns:
                self.pattern_matcher = PatternMatcher(patterns, self.PRINTER_NAMES,
                                                      self.BRAND_NAME_MAPPINGS, self._format_paper_type)
                self.log(f"Loaded {len(patterns)} filename patterns")
            else:
                self.log("No valid patterns found in config, using defaults", level='WARNING')
                self._build_default_pattern_matcher()
        except Exception as e:
            self.log(f"Error building pattern matcher: {e}", level='WARNING')
            self._build_default_pattern_matcher()

    def _parse_pattern_dict(self, pattern_dict: Dict[str, Any]) -> Optional[FilenamePattern]:
        """Parse a pattern dictionary from YAML and return a FilenamePattern object."""
        try:
            # Parse structure
            structure_raw = pattern_dict.get('structure', [])
            structure = []
            for field_dict in structure_raw:
                field_def = FieldDefinition(
                    field=field_dict.get('field'),
                    position=field_dict.get('position'),
                    match_type=field_dict.get('match_type')
                )
                structure.append(field_def)

            # Parse variants
            variants = []
            for variant_dict in pattern_dict.get('variants', []):
                variant = PatternVariant(
                    prefix=variant_dict.get('prefix'),
                    prefix_length=variant_dict.get('prefix_length')
                )
                variants.append(variant)

            # Parse paper type processing
            ptp_raw = pattern_dict.get('paper_type_processing', {})
            paper_type_processing = PaperTypeProcessing(
                format=ptp_raw.get('format', False),
                remove_brand=ptp_raw.get('remove_brand')
            )

            # Create pattern
            pattern = FilenamePattern(
                name=pattern_dict.get('name'),
                priority=pattern_dict.get('priority', 50),
                description=pattern_dict.get('description', ''),
                prefix=pattern_dict.get('prefix'),
                prefix_case_insensitive=pattern_dict.get('prefix_case_insensitive', False),
                delimiter=pattern_dict.get('delimiter', ' '),
                structure=structure,
                brand_value=pattern_dict.get('brand_value'),
                paper_type_processing=paper_type_processing,
                variants=variants
            )

            return pattern
        except Exception as e:
            self.log(f"Error parsing pattern {pattern_dict.get('name', 'unknown')}: {e}", level='WARNING')
            return None

    def _build_default_pattern_matcher(self):
        """Build a default PatternMatcher with hardcoded patterns for fallback."""
        patterns = [
            # MOAB pattern
            FilenamePattern(
                name='moab_profiles',
                priority=100,
                description='MOAB brand profiles',
                prefix='MOAB ',
                prefix_case_insensitive=True,
                delimiter=' ',
                structure=[
                    FieldDefinition('paper_type', position='before_printer'),
                    FieldDefinition('printer', match_type='key_search'),
                    FieldDefinition('code', position='after_printer'),
                ],
                brand_value='MOAB',
                paper_type_processing=PaperTypeProcessing(format=True),
            ),
            # EPSON SC- pattern
            FilenamePattern(
                name='epson_sc_files',
                priority=90,
                description='EPSON SC-P### EMY2 files',
                prefix='EPSON SC-',
                prefix_case_insensitive=False,
                delimiter=' ',
                structure=[
                    FieldDefinition('printer', position=0),
                    FieldDefinition('brand', position=1),
                    FieldDefinition('paper_type', position='2+'),
                ],
                brand_value=None,
                paper_type_processing=PaperTypeProcessing(format=True),
            ),
            # CIFA pattern
            FilenamePattern(
                name='cifa_profiles',
                priority=80,
                description='Canson/CIFA profiles',
                prefix='cifa_',
                prefix_case_insensitive=True,
                delimiter='_',
                structure=[
                    FieldDefinition('printer', position=0),
                    FieldDefinition('paper_type', position='1+'),
                ],
                brand_value='Canson',
                paper_type_processing=PaperTypeProcessing(format=True),
            ),
            # HFA pattern
            FilenamePattern(
                name='hfa_profiles',
                priority=85,
                description='Hahnemuehle HFA profiles',
                prefix='HFA',
                prefix_case_insensitive=False,
                delimiter='_',
                structure=[
                    FieldDefinition('printer', position=0),
                    FieldDefinition('mk_pk', position=1),
                    FieldDefinition('paper_type', position='2+'),
                ],
                brand_value='Hahnemuehle',
                paper_type_processing=PaperTypeProcessing(format=True, remove_brand='Hahnemuehle'),
                variants=[
                    PatternVariant('HFAMetallic_', 12),
                    PatternVariant('HFAPhoto_', 9),
                    PatternVariant('HFA_', 4),
                ],
            ),
            # Red River Papers pattern
            FilenamePattern(
                name='red_river_profiles',
                priority=75,
                description='Red River Papers Epson profiles',
                prefix='RR ',
                prefix_case_insensitive=False,
                delimiter=' ',
                structure=[
                    FieldDefinition('paper_type', position='before_printer'),
                    FieldDefinition('printer', match_type='key_search'),
                ],
                brand_value='Red River',
                paper_type_processing=PaperTypeProcessing(format=True, remove_brand='Ep'),
            ),
            # Fallback pattern
            FilenamePattern(
                name='fallback_printer_detection',
                priority=10,
                description='Fallback printer detection',
                prefix=None,
                prefix_case_insensitive=True,
                delimiter=' ',
                structure=[
                    FieldDefinition('printer', match_type='substring'),
                    FieldDefinition('paper_type', position='remaining'),
                ],
                brand_value='Unknown',
                paper_type_processing=PaperTypeProcessing(format=True),
            ),
        ]

        self.pattern_matcher = PatternMatcher(patterns, self.PRINTER_NAMES,
                                              self.BRAND_NAME_MAPPINGS, self._format_paper_type)
        self.log("Using default pattern matcher")

    def _normalize_brand_name(self, brand: str) -> str:
        """Normalize brand names using the mappings."""
        if brand in self.BRAND_NAME_MAPPINGS:
            return self.BRAND_NAME_MAPPINGS[brand]
        return brand

    def _format_paper_type(self, paper_type: str, remove_brand: Optional[str] = None) -> str:
        """
        Format paper type by separating CamelCase and optionally removing brand names.

        Args:
            paper_type: The paper type string to format
            remove_brand: Optional brand name to remove (e.g., "Hahnemuehle")

        Example: "PhotoLuster260" -> "Photo Luster 260"
                 "HahnemuehlePhotoLuster260" -> "Photo Luster 260" (with remove_brand="Hahnemuehle")
                 "aqua310" -> "Aqua 310"
        """
        import re

        cleaned = paper_type

        # Remove brand name if specified (case-insensitive)
        if remove_brand:
            cleaned = re.sub(re.escape(remove_brand), '', cleaned, flags=re.IGNORECASE)

        # Replace underscores and plus signs with spaces
        cleaned = cleaned.replace('_', ' ').replace('+', ' ')

        # Separate CamelCase by inserting spaces before capital letters
        # This pattern matches: capital letter followed by lowercase letters
        cleaned = re.sub(r'([A-Z][a-z]+)', r' \1', cleaned)

        # Also handle numbers: insert space before number sequences that come after letters
        cleaned = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', cleaned)

        # Clean up multiple spaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # Title case: capitalize first letter of each word
        if cleaned:
            cleaned = ' '.join(word[0].upper() + word[1:] if word else word
                              for word in cleaned.split())

        return cleaned

    def _load_choices_cache(self) -> Dict:
        """Load user choices from cache file."""
        if self.choices_cache_path.exists():
            try:
                with open(self.choices_cache_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.log(f"Warning: Could not load choices cache: {e}", level='WARNING')
        return {}

    def _save_choices_cache(self):
        """Save user choices to cache file."""
        try:
            with open(self.choices_cache_path, 'w') as f:
                json.dump(self.user_choices, f, indent=2)
        except Exception as e:
            self.log(f"Warning: Could not save choices cache: {e}", level='WARNING')

    def _load_global_preferences(self) -> Dict:
        """Load global printer preferences from file."""
        if self.preferences_path.exists():
            try:
                with open(self.preferences_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.log(f"Warning: Could not load preferences: {e}", level='WARNING')
        return {}

    def _save_global_preferences(self):
        """Save global printer preferences to file."""
        try:
            with open(self.preferences_path, 'w') as f:
                json.dump(self.global_preferences, f, indent=2)
        except Exception as e:
            self.log(f"Warning: Could not save preferences: {e}", level='WARNING')

    def _find_printer_candidates(self, filename: str) -> List[Tuple[str, str]]:
        """
        Find all possible printer names in a filename.
        Returns list of (printer_key, printer_name) tuples.
        Only returns unique printer names (deduplicates by full_name).
        """
        name_lower = filename.lower()
        candidates_dict = {}  # full_name -> longest_key mapping

        for key, full_name in self.PRINTER_NAMES.items():
            key_lower = key.lower()
            if key_lower in name_lower:
                # Keep track of the longest matching key for each printer name
                # (to avoid duplicates like "pro100" and "pixmapro100" both matching)
                if full_name not in candidates_dict or len(key) > len(candidates_dict[full_name][0]):
                    candidates_dict[full_name] = (key, full_name)

        # Return unique printer names only
        return list(candidates_dict.values())

    def _get_preference_key(self, candidates: List[Tuple[str, str]]) -> str:
        """
        Create a sorted key for printer candidates to use as a preference rule.
        Example: candidates with P7570 and P9570 -> "P7570-P9570" or "P9570-P7570" (sorted)
        """
        keys = sorted([key for key, _ in candidates])
        return "-".join(keys)

    def _check_global_preference(self, candidates: List[Tuple[str, str]]) -> Optional[str]:
        """
        Check if there's a global preference rule for these candidates.
        Returns the preferred printer name, or None if no preference exists.
        """
        pref_key = self._get_preference_key(candidates)
        if pref_key in self.global_preferences:
            preferred_name = self.global_preferences[pref_key]
            return preferred_name
        return None

    def _prompt_for_printer(self, filename: str, candidates: List[Tuple[str, str]]) -> str:
        """
        Prompt user to choose printer when multiple printers are detected.
        Creates a global rule for future files with the same printer combo.
        Returns the chosen printer name.
        """
        print("\n" + "=" * 60)
        print(f"Multiple printers detected in: {filename}")
        print("=" * 60)

        for i, (key, full_name) in enumerate(candidates, 1):
            print(f"{i}. {full_name} ({key})")

        while True:
            try:
                choice = input(f"Choose printer (1-{len(candidates)}) or 'q' to skip: ").strip()

                if choice.lower() == 'q':
                    return None

                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(candidates):
                    chosen = candidates[choice_idx][1]

                    # Cache the per-file choice
                    self.user_choices[filename] = chosen
                    self._save_choices_cache()

                    # Save as global preference rule for all similar files
                    pref_key = self._get_preference_key(candidates)
                    self.global_preferences[pref_key] = chosen
                    self._save_global_preferences()

                    print(f"✓ Applied globally: When you see {pref_key}, will use {chosen}")

                    return chosen
                else:
                    print(f"Invalid choice. Please enter a number between 1 and {len(candidates)}")
            except ValueError:
                print(f"Invalid input. Please enter a number or 'q'")

    def _get_printer_name_interactive(self, filename: str, detected_printer: str) -> str:
        """
        Get printer name, prompting user if file has multiple possible printers.
        Uses global preferences for printer conflicts when available.
        Returns the selected printer name.
        """
        # Check if we have a cached choice for this file
        if filename in self.user_choices:
            return self.user_choices[filename]

        # Find all possible printers
        candidates = self._find_printer_candidates(filename)

        if len(candidates) > 1:
            # Check if we have a global preference rule for this combo
            global_pref = self._check_global_preference(candidates)
            if global_pref:
                return global_pref

            # If no global preference and interactive mode, ask user
            if self.interactive:
                chosen = self._prompt_for_printer(filename, candidates)
                return chosen if chosen else detected_printer
            else:
                self.log(f"  ℹ Multi-printer file: {filename} (use --interactive to choose)")

        return detected_printer

    def _apply_printer_remapping(self, printer_name: str) -> str:
        """
        Apply printer remappings defined in config.
        If a mapping exists for this printer, return the mapped printer name.
        Otherwise, return the original printer name.

        Example: P700 profiles from P900 site can be remapped to P900.
        """
        if printer_name in self.PRINTER_REMAPPINGS:
            mapped_printer = self.PRINTER_REMAPPINGS[printer_name]
            self.log(f"  Remapping printer: {printer_name} -> {mapped_printer}")
            return mapped_printer
        return printer_name

    def extract_printer_and_paper_info(self, filename: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extract printer name, paper brand, and paper type from filename.
        Uses generalized pattern matching system defined in config.yaml.

        Returns:
            Tuple of (printer_name, paper_brand, paper_type)
        """
        # Use the pattern matcher to parse the filename
        result = self.pattern_matcher.match(filename)

        if result:
            printer_name, brand, paper_type = result
            # Apply printer remappings
            printer_name = self._apply_printer_remapping(printer_name)
            return printer_name, brand, paper_type

        return None, None, None

    def generate_new_filename(self, printer: str, brand: str, paper_type: str,
                             extension: str, existing_names: Dict[str, int]) -> str:
        """
        Generate standardized filename.

        Format: Printer Name - Paper Brand - Paper Type [N].ext
        Adds [N] if there are duplicates.
        """
        base_name = f"{printer} - {brand} - {paper_type}"

        # Check if we need a number
        if base_name in existing_names:
            existing_names[base_name] += 1
            return f"{base_name} [{existing_names[base_name]}].{extension}"
        else:
            existing_names[base_name] = 1
            return f"{base_name}.{extension}"

    def organize_profiles(self) -> bool:
        """
        Main function to organize ICC profiles and EMX files.

        Returns:
            True if successful, False otherwise
        """
        self.log("=" * 60)
        self.log("Starting ICC Profile Organization")
        self.log(f"Mode: {'DRY RUN' if self.dry_run else 'EXECUTE'}")
        self.log(f"Source directory: {self.profiles_dir}")
        self.log(f"Output directory: {self.output_dir}")
        self.log("=" * 60)

        # Find all ICC, ICM, and EMY2 files
        profile_files = self._find_profile_files()

        if not profile_files:
            self.log("No profile files found.", level='WARNING')
            return False

        self.log(f"\nFound {len(profile_files)} profile files:")
        for ftype, files in profile_files.items():
            self.log(f"  {ftype}: {len(files)} files")

        # Process each profile type
        all_files = []
        for file_list in profile_files.values():
            all_files.extend(file_list)

        # Track existing names to handle duplicates
        existing_names = defaultdict(int)

        for file_path in all_files:
            printer, brand, paper_type = self.extract_printer_and_paper_info(file_path.name)

            if not printer or not brand:
                self.log(f"  ⚠ Could not parse: {file_path.name}", level='WARNING')
                continue

            # Use interactive mode if enabled to choose printer for multi-printer files
            printer = self._get_printer_name_interactive(file_path.name, printer)

            # Determine extension
            ext = file_path.suffix.lstrip('.')

            # Generate new filename
            new_filename = self.generate_new_filename(printer, brand, paper_type, ext, existing_names)

            # Create new path: organized-profiles/Printer/Brand/filename
            new_path = self.output_dir / printer / brand / new_filename

            self.operations.append((file_path, new_path))

            # Only print if detailed mode is enabled
            if self.detailed:
                self.log(f"  {file_path.name} -> {new_path.relative_to(self.output_dir.parent)}")

        # Show summary organized by printer/brand
        if not self.detailed:
            self._print_organization_summary()

        # Execute operations if not dry run
        if not self.dry_run:
            self._execute_operations()
        else:
            self.log("\n[DRY RUN] Use --execute flag to apply changes")

        return True

    def _print_organization_summary(self):
        """Print a clean summary of how profiles will be organized."""
        self.log("\nProfile Organization Summary:")
        self.log("=" * 60)

        # Group operations by destination printer and brand
        summary = defaultdict(lambda: defaultdict(list))

        for old_path, new_path in self.operations:
            parts = new_path.parts
            # Extract printer and brand from path
            if len(parts) >= 2:
                printer = parts[-3]  # profiles/Printer/Brand/file
                brand = parts[-2]
                filename = parts[-1]
                summary[printer][brand].append(filename)

        # Print organized summary
        for printer in sorted(summary.keys()):
            print(f"\n📁 {printer}/")
            for brand in sorted(summary[printer].keys()):
                file_count = len(summary[printer][brand])
                print(f"   └─ {brand}/ ({file_count} files)")
                # Show first 2-3 files as examples
                for filename in sorted(summary[printer][brand])[:3]:
                    print(f"      • {filename}")
                if file_count > 3:
                    print(f"      • ... and {file_count - 3} more")

        total_files = len(self.operations)
        self.log(f"\nTotal profiles to organize: {total_files}")

    def organize_pdfs(self) -> bool:
        """
        Find, deduplicate, and organize PDF files.

        Returns:
            True if successful, False otherwise
        """
        self.log("\n" + "=" * 60)
        self.log("Starting PDF Organization")
        self.log("=" * 60)

        # Find all PDFs
        pdf_files = list(self.profiles_dir.rglob('*.pdf'))

        if not pdf_files:
            self.log("No PDF files found.")
            return True

        self.log(f"Found {len(pdf_files)} PDF files")

        # Calculate hashes and find duplicates
        self._find_pdf_duplicates(pdf_files)

        # Process PDFs
        for file_path in pdf_files:
            # Check if this is a duplicate (not the first occurrence)
            file_hash = self._hash_file(file_path)

            if file_hash in self.pdf_duplicates and self.pdf_duplicates[file_hash][0] != file_path:
                # This is a duplicate
                self.log(f"  DUPLICATE: {file_path.relative_to(self.profiles_dir)}")
                self.files_deleted.append(str(file_path))

                if not self.dry_run:
                    file_path.unlink()
                    self.log(f"    → Deleted")
            else:
                # This is a unique file, organize it
                # Try to extract printer from filename or parent folder
                printer = self._extract_printer_from_context(file_path)

                if printer:
                    new_path = self.output_dir / 'PDFs' / printer / file_path.name
                    self.operations.append((file_path, new_path))
                    if self.detailed:
                        self.log(f"  {file_path.relative_to(self.profiles_dir)} -> PDFs/{printer}/{file_path.name}")

        # Show PDF organization summary
        if not self.detailed and len(self.operations) > 0:
            self._print_pdf_organization_summary()

        # Execute operations if not dry run
        if not self.dry_run:
            self._execute_operations()
        else:
            self.log("\n[DRY RUN] Use --execute flag to apply changes")

        return True

    def _print_pdf_organization_summary(self):
        """Print a clean summary of how PDFs will be organized."""
        self.log("\nPDF Organization Summary:")
        self.log("=" * 60)

        # Group PDF operations by destination printer
        pdf_summary = defaultdict(list)

        for old_path, new_path in self.operations:
            parts = new_path.parts
            # Check if this is a PDF operation (PDFs in path)
            if 'PDFs' in parts:
                # Extract printer from PDFs/Printer/filename
                pdf_idx = parts.index('PDFs')
                if pdf_idx + 1 < len(parts) - 1:
                    printer = parts[pdf_idx + 1]
                    filename = parts[-1]
                    pdf_summary[printer].append(filename)

        if pdf_summary:
            for printer in sorted(pdf_summary.keys()):
                file_count = len(pdf_summary[printer])
                print(f"📄 PDFs/{printer}/ ({file_count} files)")
            print(f"\nTotal PDFs to organize: {sum(len(v) for v in pdf_summary.values())}")
            if self.files_deleted:
                print(f"Duplicate PDFs removed: {len(self.files_deleted)}")

    def _find_profile_files(self) -> Dict[str, List[Path]]:
        """Find all ICC, ICM, and EMY2 files in the directory."""
        icc_files = list(self.profiles_dir.rglob('*.icc'))
        icm_files = list(self.profiles_dir.rglob('*.icm'))
        emy2_files = list(self.profiles_dir.rglob('*.emy2'))

        # Filter out macOS resource fork files
        icc_files = [f for f in icc_files if '._' not in f.name]
        icm_files = [f for f in icm_files if '._' not in f.name]
        emy2_files = [f for f in emy2_files if '._' not in f.name]

        return {
            'ICC': icc_files,
            'ICM': icm_files,
            'EMY2': emy2_files,
        }

    def _find_pdf_duplicates(self, pdf_files: List[Path]):
        """Find duplicate PDFs based on file hash."""
        self.log("Checking for duplicate PDFs...")

        for pdf_file in pdf_files:
            file_hash = self._hash_file(pdf_file)
            self.pdf_duplicates[file_hash].append(pdf_file)

        duplicates_found = sum(1 for v in self.pdf_duplicates.values() if len(v) > 1)
        self.log(f"Found {duplicates_found} duplicate sets")

    def _hash_file(self, file_path: Path, chunk_size: int = 8192) -> str:
        """Calculate SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(chunk_size), b''):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def _extract_printer_from_pdf_filename(self, filename: str) -> Optional[str]:
        """
        Extract printer name from PDF filename.
        Uses the same pattern matcher as ICC profiles to ensure consistency.

        Returns the canonical printer name or None if not found.
        """
        # Use pattern matcher to extract printer (will return tuple of printer, brand, paper_type)
        result = self.pattern_matcher.match(filename)

        if result:
            printer_name, _, _ = result
            # Apply remapping if needed
            printer_name = self._apply_printer_remapping(printer_name)
            return printer_name

        return None

    def _extract_printer_from_context(self, file_path: Path) -> Optional[str]:
        """Extract printer name from file path context (filename first, then parent dirs)."""
        # First, try to extract from filename
        printer_from_filename = self._extract_printer_from_pdf_filename(file_path.name)
        if printer_from_filename:
            return printer_from_filename

        # Check parent directory name and all parents
        for parent in [file_path.parent] + list(file_path.parents):
            parent_name = parent.name

            # Look for exact and case-insensitive matches
            for key, full_name in self.PRINTER_NAMES.items():
                if key.lower() in parent_name.lower():
                    full_name = self._apply_printer_remapping(full_name)
                    return full_name

            # Special handling for patterns like "IPF 6450" vs "iPF6450"
            if 'iPF6450' in parent_name or 'ipf6450' in parent_name or 'IPF 6450' in parent_name or 'ipf 6450' in parent_name:
                return 'Canon iPF6450'
            if 'PRO-100' in parent_name or 'Pro-100' in parent_name or 'pro-100' in parent_name:
                return 'Canon Pixma PRO-100'

        return 'Uncategorized'

    def _execute_operations(self):
        """Execute all file copy operations."""
        self.log("\nExecuting file operations...")

        for old_path, new_path in self.operations:
            try:
                # Create parent directories
                new_path.parent.mkdir(parents=True, exist_ok=True)

                # Copy file (preserves metadata like timestamps)
                shutil.copy2(str(old_path), str(new_path))
                self.files_renamed.append((str(old_path), str(new_path)))
                self.log(f"  ✓ Copied: {old_path.name}")
            except Exception as e:
                self.log(f"  ✗ Error copying {old_path.name}: {e}", level='ERROR')

    def _get_system_profile_paths(self) -> Optional[dict]:
        """Get the system ICC profile paths for the current OS."""
        return SYSTEM_ICC_PATH

    def _check_windows_elevated(self) -> bool:
        """
        Check if running with elevated privileges on Windows.
        Returns True if elevated or not on Windows, False if on Windows without elevation.
        """
        if CURRENT_OS != 'Windows':
            return True

        try:
            import ctypes
            return ctypes.windll.shell.IsUserAnAdmin()
        except Exception:
            # If we can't determine, try to check write access directly
            return os.access(str(SYSTEM_ICC_PATHS['Windows']), os.W_OK)

    def prompt_for_system_profile_export(self) -> bool:
        """
        Prompt user if they want to copy profiles to system ICC directory.
        On Windows, checks for elevated privileges first.
        On macOS, asks user to choose between system and user directory.

        Returns:
            True if user wants to copy, False otherwise
        """
        paths = self._get_system_profile_paths()
        if not paths:
            return False

        # Windows: Check for elevated privileges
        if CURRENT_OS == 'Windows':
            if not self._check_windows_elevated():
                print("\n" + "=" * 60)
                print("Elevated Privileges Required")
                print("=" * 60)
                print("ERROR: Cannot write to Windows system ICC profile directory")
                print(f"Path: {SYSTEM_ICC_PATHS['Windows']}")
                print("\nThis directory requires Administrator privileges.")
                print("\nTo fix this, please:")
                print("  1. Open Command Prompt or PowerShell as Administrator")
                print("  2. Run the program again with the --system-profiles flag")
                print("=" * 60)
                return False

            system_path = SYSTEM_ICC_PATHS['Windows']
            print("\n" + "=" * 60)
            print("System ICC Profile Directory Found")
            print("=" * 60)
            print(f"Path: {system_path}")
            print("\nNote: Profiles will be copied to a flat structure")
            print("      (no subdirectories will be created in Windows system folder)")

            print("\nWould you like to copy the organized profiles to the system")
            print("ICC profile directory?")

            while True:
                response = input("\nCopy to system profiles? (yes/no): ").strip().lower()
                if response in ['yes', 'y']:
                    self.selected_system_profile_path = system_path
                    return True
                elif response in ['no', 'n']:
                    return False
                else:
                    print("Please enter 'yes' or 'no'")

        # macOS: Offer choice between system and user directory
        else:  # Darwin
            system_path = paths['system']
            user_path = paths['user']

            print("\n" + "=" * 60)
            print("ICC Profile Directory Options")
            print("=" * 60)
            print(f"\n1. System Directory (requires admin)")
            print(f"   Path: {system_path}")
            print(f"   Profiles available to all users")

            print(f"\n2. User Directory (no admin needed)")
            print(f"   Path: {user_path}")
            print(f"   Profiles available only to you")

            print(f"\nProfiles will be organized with folder structure")

            while True:
                response = input("\nChoose directory (1/2) or 'skip': ").strip().lower()
                if response in ['1', 'system']:
                    system_path.parent.mkdir(parents=True, exist_ok=True)
                    if not os.access(str(system_path.parent), os.W_OK):
                        print(f"\nError: No write permission to {system_path.parent}")
                        print("Try running with: sudo python3 organize_profiles.py ...")
                        continue

                    self.selected_system_profile_path = system_path
                    return True
                elif response in ['2', 'user']:
                    # Ensure user directory exists
                    user_path.mkdir(parents=True, exist_ok=True)
                    self.selected_system_profile_path = user_path
                    return True
                elif response in ['skip', 's', 'n', 'no']:
                    return False
                else:
                    print("Please enter '1', '2', or 'skip'")

    def copy_to_system_profiles(self) -> bool:
        """
        Copy organized profiles to system ICC profile directory.
        Uses the path selected during prompt_for_system_profile_export().
        Handles OS-specific requirements:
        - Windows: Flat structure (no subdirectories)
        - macOS: Preserves organized folder structure

        Returns:
            True if successful, False otherwise
        """
        if not self.selected_system_profile_path:
            self.log(f"Error: No system profile path selected", level='ERROR')
            return False

        system_path = self.selected_system_profile_path

        if not system_path.exists():
            self.log(f"Error: System profile path does not exist: {system_path}", level='ERROR')
            return False

        self.log("\n" + "=" * 60)
        self.log(f"Copying profiles to: {system_path}")
        self.log("=" * 60)

        # Check if we have write permissions
        if not os.access(str(system_path.parent), os.W_OK):
            self.log(f"Error: No write permission to {system_path}", level='ERROR')
            if CURRENT_OS == 'Darwin' and '/Library/ColorSync' in str(system_path):
                self.log("Note: Run with 'sudo' to write to system directory")
            return False

        copied_count = 0
        failed_count = 0

        if CURRENT_OS == 'Windows':
            # Windows: Flat structure - copy all profiles directly to the color folder
            self.log("Using flat structure for Windows system profiles...")

            for file_path in self.output_dir.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in ['.icc', '.icm']:
                    try:
                        # Copy directly to system profile folder (flat structure)
                        dest_path = system_path / file_path.name
                        shutil.copy2(str(file_path), str(dest_path))
                        self.log(f"  ✓ Copied: {file_path.name}")
                        copied_count += 1
                    except Exception as e:
                        self.log(f"  ✗ Error copying {file_path.name}: {e}", level='ERROR')
                        failed_count += 1

        else:  # macOS and others
            # Preserve folder structure
            self.log("Using organized folder structure for system profiles...")

            for file_path in self.output_dir.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in ['.icc', '.icm']:
                    try:
                        # Preserve relative path from output_dir
                        rel_path = file_path.relative_to(self.output_dir)
                        dest_path = system_path / rel_path

                        # Create parent directories
                        dest_path.parent.mkdir(parents=True, exist_ok=True)

                        shutil.copy2(str(file_path), str(dest_path))
                        self.log(f"  ✓ Copied: {rel_path}")
                        copied_count += 1
                    except Exception as e:
                        self.log(f"  ✗ Error copying {file_path.name}: {e}", level='ERROR')
                        failed_count += 1

        self.log(f"\nSuccessfully copied: {copied_count} profiles")
        if failed_count > 0:
            self.log(f"Failed to copy: {failed_count} profiles", level='WARNING')

        return failed_count == 0

    def update_profile_descriptions(self) -> bool:
        """
        Update ICC profile descriptions to match filenames.

        Returns:
            True if successful, False otherwise
        """
        self.log("\n" + "=" * 60)
        self.log("Updating ICC Profile Descriptions")
        self.log("=" * 60)

        if not self.output_dir.exists():
            self.log("Output directory does not exist yet. Skipping description update.", level='WARNING')
            return False

        updater = ICCProfileUpdater(verbose=False)
        processed, successful = updater.process_directory(self.output_dir, verbose=True)

        self.log(f"  Updated {successful} / {processed} profiles")

        return successful == processed

    def print_summary(self):
        """Print summary of operations."""
        self.log("\n" + "=" * 60)
        self.log("SUMMARY")
        self.log("=" * 60)
        self.log(f"Files processed: {len(self.operations)}")
        self.log(f"Files copied: {len(self.files_renamed)}")
        self.log(f"Duplicate PDFs removed: {len(self.files_deleted)}")

        if self.files_renamed:
            self.log("\nCopied files:")
            for old, new in self.files_renamed[:5]:  # Show first 5
                self.log(f"  {old} -> {new}")
            if len(self.files_renamed) > 5:
                self.log(f"  ... and {len(self.files_renamed) - 5} more")

        if self.files_deleted:
            self.log("\nDeleted files (duplicates):")
            for file in self.files_deleted[:5]:  # Show first 5
                self.log(f"  {file}")
            if len(self.files_deleted) > 5:
                self.log(f"  ... and {len(self.files_deleted) - 5} more")

        self.log("=" * 60)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Organize ICC profiles, EMX files, and PDFs'
    )
    parser.add_argument(
        'profiles_dir',
        nargs='?',
        default='./profiles',
        help='Path to source profiles directory (default: ./profiles)'
    )
    parser.add_argument(
        '--output-dir',
        default=None,
        help='Output directory for organized profiles (default: ./organized-profiles)'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Execute operations (default is dry-run mode)'
    )
    parser.add_argument(
        '--profiles-only',
        action='store_true',
        help='Only organize profiles, skip PDFs'
    )
    parser.add_argument(
        '--pdfs-only',
        action='store_true',
        help='Only organize PDFs, skip profiles'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress output'
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Interactively choose printer for files with multiple printer options'
    )
    parser.add_argument(
        '--detailed',
        action='store_true',
        help='Show detailed file-by-file transformation list (default is summary)'
    )
    parser.add_argument(
        '--skip-desc-update',
        action='store_true',
        help='Skip updating ICC profile descriptions to match filenames'
    )
    parser.add_argument(
        '--system-profiles',
        action='store_true',
        help='Copy organized profiles to system ICC profile directory (prompts if system directory found)'
    )
    parser.add_argument(
        '--no-system-profiles-prompt',
        action='store_true',
        help='Do not prompt to copy to system ICC profile directory'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.profiles_only and args.pdfs_only:
        print("Error: Cannot use both --profiles-only and --pdfs-only")
        sys.exit(1)

    # Initialize organizer
    organizer = ProfileOrganizer(
        args.profiles_dir,
        output_dir=args.output_dir,
        dry_run=not args.execute,
        verbose=not args.quiet,
        interactive=args.interactive,
        detailed=args.detailed,
        update_descriptions=not args.skip_desc_update
    )

    # Run organization
    try:
        if not args.pdfs_only:
            organizer.organize_profiles()

        if not args.profiles_only:
            organizer.organize_pdfs()

        # Update profile descriptions if enabled and in execute mode
        if organizer.update_descriptions and not organizer.dry_run:
            organizer.update_profile_descriptions()

        organizer.print_summary()

        # Handle system profile export
        should_export_to_system = False
        if not organizer.dry_run:
            if args.system_profiles:
                # User explicitly requested system profiles via flag
                should_export_to_system = True
            elif not args.no_system_profiles_prompt:
                # Prompt user if system directory is accessible
                should_export_to_system = organizer.prompt_for_system_profile_export()

            if should_export_to_system:
                organizer.copy_to_system_profiles()

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
