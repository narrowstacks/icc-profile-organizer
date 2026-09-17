"""Dataclasses describing a filename pattern.

A :class:`FilenamePattern` says how to pull printer, paper brand and paper
type out of a vendor filename. Patterns are declared in ``config.yaml`` and
parsed by :mod:`icc_profile_organizer.lib.config_manager`; the matching
engine lives in :mod:`icc_profile_organizer.lib.pattern_matching`.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FieldDefinition:
    """Defines a field in a filename pattern.

    ``position`` is an index, a range ("1+"), or one of the relative anchors
    "before_printer" / "after_printer" / "after_brand" / "remaining".
    ``match_type`` is "key_search" or "substring" for printers and
    "brand_search" for brands (see PatternMatcher).
    """

    field: str  # "printer", "paper_type", "brand", etc.
    position: Optional[Any] = None
    match_type: Optional[str] = None


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
    # Abbreviation -> full paper name (e.g. "GPGFS" -> "Gold Fibre Silk").
    # Matched by longest prefix of the raw paper-type string; see lookup_paper_code().
    code_map: Dict[str, str] = field(default_factory=dict)
    # Regexes (case-insensitive) deleted from the raw paper string before
    # code_map lookup and formatting, e.g. driver media codes or version tags.
    strip_regex: List[str] = field(default_factory=list)
    # Keep (and format) whatever follows a resolved code, so "UPSatin 4.0"
    # becomes "UltraPro Satin 4.0" instead of just "UltraPro Satin".
    code_map_keep_rest: bool = False
    # The pattern only matches when the paper code resolves via code_map.
    # Lets a prefix-less vendor pattern fire only on that vendor's codes.
    require_code_map: bool = False


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
    # Characters treated as the delimiter before splitting (e.g. ["_"] lets a
    # space-delimited pattern also accept "EPSON SC-P900_MOAB ...").
    delimiter_aliases: List[str] = field(default_factory=list)
    # Brand used when a "brand_search" field finds no known brand.
    brand_fallback: Optional[str] = None
    # Alternative to prefix: a regex (case-insensitive) anchored at the start
    # whose match is removed, e.g. '^(\d+\.)?APJ_' for "40.APJ_…".
    prefix_regex: Optional[str] = None

    def __lt__(self, other):
        """Enable sorting by priority (higher priority first)."""
        return self.priority > other.priority
