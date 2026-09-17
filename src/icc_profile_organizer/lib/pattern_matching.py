"""Unified pattern matching engine for filename parsing.

``PatternMatcher`` evaluates :class:`FilenamePattern` definitions in priority
order and returns ``(printer, brand, paper_type)`` for a filename. Pattern
dataclasses live in :mod:`pattern_types`; printer alias lookup in
:mod:`printer_keys`. Patterns are built from configuration by
:mod:`icc_profile_organizer.lib.config_manager`.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .pattern_types import (  # noqa: F401  (re-exported for callers)
    FieldDefinition,
    FilenamePattern,
    PaperTypeProcessing,
    PatternVariant,
)
from .printer_keys import PrinterKeyIndex


def format_paper_type(paper_type: str, remove_brand: Optional[str] = None) -> str:
    """Format a paper type by separating CamelCase and optionally removing a brand.

    Example: "PhotoLuster260" -> "Photo Luster 260"
             "HahnemuehlePhotoLuster260" -> "Photo Luster 260" (remove_brand="Hahnemuehle")
             "Bamboo_Paper_110gsm" -> "Bamboo Paper 110" (weights are bare numbers)
    """
    cleaned = paper_type

    # Remove brand name if specified (case-insensitive)
    if remove_brand:
        cleaned = re.sub(re.escape(remove_brand), '', cleaned, flags=re.IGNORECASE)

    # Replace underscores and plus signs with spaces
    cleaned = cleaned.replace('_', ' ').replace('+', ' ')

    # Separate CamelCase by inserting spaces before capital letters that
    # follow a letter or digit ("PhotoLuster" -> "Photo Luster", but
    # "Double-Sided" and "Semi-Gloss" keep their hyphen)
    cleaned = re.sub(r'(?<=[A-Za-z0-9])([A-Z][a-z]+)', r' \1', cleaned)

    # Insert space before number sequences that come after letters
    cleaned = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', cleaned)

    # Weights are written as bare numbers: "280gsm" / "280 gsm" -> "280"
    cleaned = re.sub(r'(\d)\s*gsm\b', r'\1', cleaned, flags=re.IGNORECASE)

    # Clean up multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Title case: capitalize first letter of each word
    if cleaned:
        cleaned = ' '.join(
            word[0].upper() + word[1:] if word else word
            for word in cleaned.split()
        )

    return cleaned


def split_paper_code(raw: str, code_map: Dict[str, str],
                     delimiter: str) -> Optional[Tuple[str, str]]:
    """Resolve an abbreviated paper code at the start of ``raw`` via ``code_map``.

    The longest key that prefixes ``raw`` (case-insensitive) wins, provided the
    key ends at a boundary: end of string, the delimiter, a digit, or any other
    non-letter (so "GPGFG17_PPPS" resolves via "GPGFG" and "OLM67(HWFAP)" via
    "OLM67", but "GPSCS_EMP" does not via "GPSC"). Keys may themselves contain
    the delimiter ("GTWE_Warm").

    Returns (mapped name, unmatched remainder), or None if no key matches.
    """
    raw_lower = raw.lower()
    for key in sorted(code_map, key=len, reverse=True):
        key_lower = key.lower()
        if not raw_lower.startswith(key_lower):
            continue
        rest = raw[len(key):]
        if rest == '' or rest.startswith(delimiter) or not rest[0].isalpha():
            return code_map[key], rest
    return None


def lookup_paper_code(raw: str, code_map: Dict[str, str], delimiter: str) -> Optional[str]:
    """Resolve an abbreviated paper code via ``code_map`` (see split_paper_code)."""
    hit = split_paper_code(raw, code_map, delimiter)
    return hit[0] if hit else None


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
        self.printers = PrinterKeyIndex(printer_names)
        self.brand_name_mappings = brand_name_mappings
        self.format_paper_type = format_paper_type_fn
        # Every spelling a brand may appear under in a filename, longest first.
        aliases = set(brand_name_mappings) | set(brand_name_mappings.values())
        self._brand_aliases = sorted(aliases, key=len, reverse=True)

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

    # ------------------------------------------------------------------
    # Pattern evaluation
    # ------------------------------------------------------------------
    def _strip_prefix(self, filename: str, pattern: FilenamePattern) -> Optional[str]:
        """Return the filename with the pattern prefix removed, or None if absent."""
        if pattern.prefix_regex:
            m = re.match(pattern.prefix_regex, filename, flags=re.IGNORECASE)
            return filename[m.end():] if m else None
        if pattern.prefix is None:
            return filename
        fold = (lambda s: s.lower()) if pattern.prefix_case_insensitive else (lambda s: s)
        candidates = pattern.variants or [PatternVariant(pattern.prefix, len(pattern.prefix))]
        for variant in candidates:
            if fold(filename).startswith(fold(variant.prefix)):
                return filename[variant.prefix_length:]
        return None

    def _try_pattern(self, filename: str, pattern: FilenamePattern) -> Optional[Tuple[str, str, str]]:
        """Try to match filename against a specific pattern."""
        for alias in pattern.delimiter_aliases:
            filename = filename.replace(alias, pattern.delimiter)
        remaining = self._strip_prefix(filename, pattern)
        if remaining is None:
            return None

        parts = remaining.split(pattern.delimiter)
        # Scratch state shared by relative positions (after_printer / after_brand).
        state: Dict[str, List[str]] = {}

        extracted = {}
        for field_def in pattern.structure:
            value = self._extract_field(parts, field_def, filename, pattern, state)
            if value is not None:
                extracted[field_def.field] = value

        # Get paper brand first
        if pattern.brand_value is not None:
            brand = pattern.brand_value
        elif 'brand' in extracted:
            brand = extracted['brand']
        elif pattern.brand_fallback is not None:
            brand = pattern.brand_fallback
        else:
            brand = 'Unknown'

        # Validate required fields. Printer is optional if brand_value is set
        # explicitly (e.g., for EMY2 documentation files).
        if 'printer' not in extracted:
            if pattern.brand_value is None and brand == 'Unknown':
                return None
            extracted['printer'] = 'Unknown'

        brand = self._normalize_brand(brand)
        paper_type = self._process_paper_type(extracted.get('paper_type', 'Unknown'), pattern)
        if paper_type is None:
            return None
        return extracted['printer'], brand, paper_type

    def _process_paper_type(self, raw: str, pattern: FilenamePattern) -> Optional[str]:
        """Strip noise, resolve codes and format the raw paper-type string.

        Returns None when the pattern requires a code_map hit and none matched.
        """
        ptp = pattern.paper_type_processing
        for regex in ptp.strip_regex:
            raw = re.sub(regex, '', raw, flags=re.IGNORECASE)
        raw = raw.strip(pattern.delimiter + ' ')

        # Resolve abbreviated paper codes (already human-readable; skip formatting)
        if ptp.code_map:
            hit = split_paper_code(raw, ptp.code_map, pattern.delimiter)
            if hit is not None:
                mapped, rest = hit
                rest = self.format_paper_type(rest) if ptp.code_map_keep_rest else ''
                return f'{mapped} {rest}'.strip()
            if ptp.require_code_map:
                return None

        if ptp.format:
            return self.format_paper_type(raw, remove_brand=ptp.remove_brand)
        return raw

    # ------------------------------------------------------------------
    # Field extraction
    # ------------------------------------------------------------------
    def _extract_field(self, parts: List[str], field_def: FieldDefinition, filename: str,
                       pattern: FilenamePattern, state: Dict[str, List[str]]) -> Optional[str]:
        """Extract a field value based on field definition."""
        delim = pattern.delimiter

        if field_def.match_type == 'key_search':
            hit = self.printers.find_in_parts(parts, delim)
            return self.printers.canonical(hit[0]) if hit else None

        if field_def.match_type == 'substring':
            hit = self.printers.find(filename)
            return self.printers.canonical(hit[0]) if hit else None

        if field_def.match_type == 'brand_search':
            split = self._split_at_printer(parts, delim)
            after = split[1] if split else parts
            brand = self._find_brand(after, delim)
            if brand is None:
                state['after_brand'] = after
                return None
            state['after_brand'] = after[brand[1]:]
            return brand[0]

        if isinstance(field_def.position, bool):
            # Guard: bool is a subclass of int; treat as no match
            return None

        if isinstance(field_def.position, int):
            if not 0 <= field_def.position < len(parts):
                return None
            part = parts[field_def.position]
            if field_def.field == 'printer':
                hit = self.printers.find(part)
                # No match found, return the raw part (may match later)
                return self.printers.canonical(hit[0]) if hit else part
            return part

        if field_def.position in ('before_printer', 'after_printer'):
            split = self._split_at_printer(parts, delim)
            if split is None:
                return None
            chosen = split[0] if field_def.position == 'before_printer' else split[1]
            return delim.join(chosen) if chosen else None

        if field_def.position == 'after_brand':
            after = state.get('after_brand')
            if after is None:
                split = self._split_at_printer(parts, delim)
                after = split[1] if split else None
            return delim.join(after) if after else None

        if isinstance(field_def.position, str) and field_def.position.endswith('+'):
            # Range: "1+" or "2+"
            try:
                start_idx = int(field_def.position[:-1])
            except ValueError:
                return None
            return delim.join(parts[start_idx:]) if start_idx < len(parts) else None

        if field_def.position == 'remaining':
            # Everything except the printer key
            hit = self.printers.find(filename)
            if hit is None:
                return None
            return (filename[:hit[1]] + filename[hit[2]:]).strip()

        return None

    def _split_at_printer(self, parts: List[str],
                          delimiter: str) -> Optional[Tuple[List[str], List[str]]]:
        """Split ``parts`` into (before, after) around the best printer alias."""
        hit = self.printers.find_in_parts(parts, delimiter)
        if hit is None:
            return None
        return parts[:hit[1]], parts[hit[2] + 1:]

    def _find_brand(self, parts: List[str], delimiter: str) -> Optional[Tuple[str, int]]:
        """Match a known brand alias at the start of ``parts``.

        Returns (canonical_brand, parts_consumed); aliases may span several
        parts ("Canson Infinity"). Longest alias wins.
        """
        lowered = [p.lower() for p in parts]
        for alias in self._brand_aliases:
            alias_parts = alias.lower().split(delimiter)
            n = len(alias_parts)
            if lowered[:n] == alias_parts:
                return self._normalize_brand(alias), n
        return None

    def _normalize_brand(self, brand: str) -> str:
        """Normalize brand name using mappings (case-insensitive)."""
        if brand in self.brand_name_mappings:
            return self.brand_name_mappings[brand]
        for alias, canonical in self.brand_name_mappings.items():
            if alias.lower() == brand.lower():
                return canonical
        return brand
