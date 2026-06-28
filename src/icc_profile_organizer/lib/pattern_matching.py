"""Unified pattern matching engine for filename parsing.

Defines the dataclasses that describe a filename pattern (``FieldDefinition``,
``PatternVariant``, ``PaperTypeProcessing``, ``FilenamePattern``) and the
``PatternMatcher`` that evaluates them in priority order. Patterns are built
from configuration by :mod:`icc_profile_organizer.lib.config_manager`.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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


def format_paper_type(paper_type: str, remove_brand: Optional[str] = None) -> str:
    """Format a paper type by separating CamelCase and optionally removing a brand.

    Example: "PhotoLuster260" -> "Photo Luster 260"
             "HahnemuehlePhotoLuster260" -> "Photo Luster 260" (remove_brand="Hahnemuehle")
             "aqua310" -> "Aqua 310"
    """
    cleaned = paper_type

    # Remove brand name if specified (case-insensitive)
    if remove_brand:
        cleaned = re.sub(re.escape(remove_brand), '', cleaned, flags=re.IGNORECASE)

    # Replace underscores and plus signs with spaces
    cleaned = cleaned.replace('_', ' ').replace('+', ' ')

    # Separate CamelCase by inserting spaces before capital letters
    cleaned = re.sub(r'([A-Z][a-z]+)', r' \1', cleaned)

    # Insert space before number sequences that come after letters
    cleaned = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', cleaned)

    # Clean up multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Title case: capitalize first letter of each word
    if cleaned:
        cleaned = ' '.join(
            word[0].upper() + word[1:] if word else word
            for word in cleaned.split()
        )

    return cleaned


class PatternMatcher:
    """Unified pattern matching engine for filename parsing."""

    def __init__(self, patterns: List[FilenamePattern], printer_names: Dict[str, str],
                 brand_name_mappings: Dict[str, str], format_paper_type_fn=format_paper_type):
        """Initialize the pattern matcher.

        Args:
            patterns: List of FilenamePattern objects (sorted by priority on init)
            printer_names: Dict mapping printer keys to canonical names
            brand_name_mappings: Dict mapping brand variants to canonical names
            format_paper_type_fn: Function to format paper type strings
        """
        self.patterns = sorted(patterns)  # Sort by priority (higher first)
        self.printer_names = printer_names
        self.brand_name_mappings = brand_name_mappings
        self.format_paper_type = format_paper_type_fn

    def match(self, filename: str) -> Optional[Tuple[Optional[str], Optional[str], Optional[str]]]:
        """Try to match filename against patterns.

        Returns:
            Tuple of (printer_name, paper_brand, paper_type) or None if no match.
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

        # Get paper brand first
        if pattern.brand_value is not None:
            brand = pattern.brand_value
        elif 'brand' in extracted:
            brand = extracted['brand']
        else:
            brand = 'Unknown'

        # Validate required fields. Printer is optional if brand_value is set
        # explicitly (e.g., for EMY2 documentation files).
        if 'printer' not in extracted:
            if pattern.brand_value is None and brand == 'Unknown':
                return None
            extracted['printer'] = 'Unknown'

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
                for part in parts:
                    if part.lower() == printer_key.lower() or \
                       part == printer_key or \
                       printer_key.lower() in part.lower():
                        return self.printer_names.get(printer_key, printer_key)
            return None

        elif field_def.match_type == 'substring':
            # Find printer key via case-insensitive substring (longest wins)
            filename_lower = filename.lower()
            best_match = None
            best_key = None
            for printer_key in self.printer_names.keys():
                if printer_key.lower() in filename_lower:
                    if best_key is None or len(printer_key) > len(best_key):
                        best_key = printer_key
                        best_match = self.printer_names.get(printer_key, printer_key)
            return best_match

        elif isinstance(field_def.position, bool):
            # Guard: bool is a subclass of int; treat as no match
            return None

        elif isinstance(field_def.position, int):
            # Fixed position
            if 0 <= field_def.position < len(parts):
                part = parts[field_def.position]
                # If this is a printer field, try to look it up in printer names
                if field_def.field == 'printer':
                    if part in self.printer_names:
                        return self.printer_names[part]
                    for key, value in self.printer_names.items():
                        if part.lower() == key.lower():
                            return value
                        if key.lower() in part.lower() or part.lower() in key.lower():
                            return value
                    # No match found, return the raw part (may match later)
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
                return filename_lower.replace(best_key.lower(), '').strip()
            return None

        return None

    def _normalize_brand(self, brand: str) -> str:
        """Normalize brand name using mappings."""
        if brand in self.brand_name_mappings:
            return self.brand_name_mappings[brand]
        return brand
