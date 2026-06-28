"""Two-tier configuration loading and pattern-matcher construction.

``ConfigManager`` loads the shipped ``defaults.yaml`` (packaged alongside this
module) and overlays an optional user ``config.yaml`` found in the current
working directory. It exposes the flattened name mappings used throughout the
organizer and builds a :class:`PatternMatcher` from the configured filename
patterns (falling back to a built-in default set when none are configured).
"""

import logging
from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PyYAML missing
    YAML_AVAILABLE = False

from .pattern_matching import (
    FieldDefinition,
    FilenamePattern,
    PaperTypeProcessing,
    PatternMatcher,
    PatternVariant,
    format_paper_type,
)

logger = logging.getLogger(__name__)

# Name of the shipped defaults file, packaged inside icc_profile_organizer/
_DEFAULTS_RESOURCE = "defaults.yaml"
# Name of the optional user override file, looked up in the working directory
_USER_CONFIG_FILENAME = "config.yaml"


class ConfigManager:
    """Loads configuration and constructs the filename PatternMatcher."""

    # Fallback values used if defaults.yaml cannot be read.
    DEFAULT_PAPER_BRANDS = ['Moab', 'Canson', 'Hahnemuehle']

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.config: Dict[str, Any] = {}
        self.PRINTER_NAMES: Dict[str, str] = {}
        self.PAPER_BRANDS: List[str] = []
        self.BRAND_NAME_MAPPINGS: Dict[str, str] = {}
        self.PRINTER_REMAPPINGS: Dict[str, str] = {}
        self.pattern_matcher: Optional[PatternMatcher] = None

    def log(self, message: str, level: str = 'INFO'):
        """Log a message (always to the logger; to stdout when verbose)."""
        if self.verbose:
            print(message)
        getattr(logger, level.lower())(message)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def load(self) -> Dict[str, Any]:
        """Load defaults.yaml and overlay an optional config.yaml override.

        Returns the merged configuration dict (also stored on ``self.config``).
        """
        defaults = self._load_packaged_defaults()
        override = self._load_user_override()

        # Two-tier merge: top-level keys in the user override replace those
        # from defaults (config.yaml is authoritative where present).
        merged = dict(defaults)
        merged.update(override)
        self.config = merged

        # Flatten the canonical -> [aliases] mappings into alias -> canonical.
        self.PRINTER_NAMES = self._flatten_mapping(merged.get('printer_names', {}))
        self.BRAND_NAME_MAPPINGS = self._flatten_mapping(merged.get('brand_name_mappings', {}))
        self.PAPER_BRANDS = merged.get('paper_brands', self.DEFAULT_PAPER_BRANDS)
        self.PRINTER_REMAPPINGS = merged.get('printer_remappings', {})

        # Build the pattern matcher from configured patterns, else defaults.
        patterns_raw = merged.get('filename_patterns', [])
        self._build_pattern_matcher(patterns_raw)

        return self.config

    def _load_packaged_defaults(self) -> Dict[str, Any]:
        """Load the defaults.yaml shipped inside the package."""
        if not YAML_AVAILABLE:
            self.log("PyYAML not available; using built-in fallback config.", level='WARNING')
            return {}
        try:
            resource = resources.files('icc_profile_organizer').joinpath(_DEFAULTS_RESOURCE)
            with resource.open('r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:  # pragma: no cover - defensive
            self.log(f"Warning: Could not load packaged defaults.yaml: {e}", level='WARNING')
            return {}

    def _load_user_override(self) -> Dict[str, Any]:
        """Load an optional config.yaml from the current working directory."""
        if not YAML_AVAILABLE:
            return {}
        config_path = Path.cwd() / _USER_CONFIG_FILENAME
        if not config_path.exists():
            return {}
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                override = yaml.safe_load(f) or {}
            self.log(f"Loaded user configuration override from {config_path}")
            return override
        except Exception as e:
            self.log(f"Warning: Could not load {config_path}: {e}", level='WARNING')
            return {}

    @staticmethod
    def _flatten_mapping(mapping: Dict[str, List[str]]) -> Dict[str, str]:
        """Convert {'Canonical': ['alias1', 'alias2']} to {'alias1': 'Canonical', ...}."""
        flat: Dict[str, str] = {}
        for canonical_name, aliases in mapping.items():
            if isinstance(aliases, list):
                for alias in aliases:
                    flat[alias] = canonical_name
            else:
                # Tolerate a scalar value instead of a list.
                flat[aliases] = canonical_name
        return flat

    # ------------------------------------------------------------------
    # Pattern matcher construction
    # ------------------------------------------------------------------
    def _build_pattern_matcher(self, patterns_raw: List[Dict[str, Any]]):
        """Build the PatternMatcher from raw YAML pattern dicts."""
        try:
            patterns = []
            for pattern_dict in patterns_raw:
                pattern = self._parse_pattern_dict(pattern_dict)
                if pattern:
                    patterns.append(pattern)

            if patterns:
                self.pattern_matcher = PatternMatcher(
                    patterns, self.PRINTER_NAMES, self.BRAND_NAME_MAPPINGS, format_paper_type
                )
                self.log(f"Loaded {len(patterns)} filename patterns")
            else:
                self.log("No patterns configured; using built-in defaults.", level='INFO')
                self._build_default_pattern_matcher()
        except Exception as e:
            self.log(f"Error building pattern matcher: {e}", level='WARNING')
            self._build_default_pattern_matcher()

    def _parse_pattern_dict(self, pattern_dict: Dict[str, Any]) -> Optional[FilenamePattern]:
        """Parse a YAML pattern dict into a FilenamePattern."""
        try:
            structure = [
                FieldDefinition(
                    field=field_dict.get('field'),
                    position=field_dict.get('position'),
                    match_type=field_dict.get('match_type'),
                )
                for field_dict in pattern_dict.get('structure', [])
            ]

            variants = [
                PatternVariant(
                    prefix=variant_dict.get('prefix'),
                    prefix_length=variant_dict.get('prefix_length'),
                )
                for variant_dict in pattern_dict.get('variants', [])
            ]

            ptp_raw = pattern_dict.get('paper_type_processing', {})
            paper_type_processing = PaperTypeProcessing(
                format=ptp_raw.get('format', False),
                remove_brand=ptp_raw.get('remove_brand'),
            )

            return FilenamePattern(
                name=pattern_dict.get('name'),
                priority=pattern_dict.get('priority', 50),
                description=pattern_dict.get('description', ''),
                prefix=pattern_dict.get('prefix'),
                prefix_case_insensitive=pattern_dict.get('prefix_case_insensitive', False),
                delimiter=pattern_dict.get('delimiter', ' '),
                structure=structure,
                brand_value=pattern_dict.get('brand_value'),
                paper_type_processing=paper_type_processing,
                variants=variants,
            )
        except Exception as e:
            self.log(f"Error parsing pattern {pattern_dict.get('name', 'unknown')}: {e}", level='WARNING')
            return None

    def _build_default_pattern_matcher(self):
        """Build a PatternMatcher with hardcoded fallback patterns."""
        patterns = [
            FilenamePattern(
                name='moab_profiles', priority=100, description='MOAB brand profiles',
                prefix='MOAB ', prefix_case_insensitive=True, delimiter=' ',
                structure=[
                    FieldDefinition('paper_type', position='before_printer'),
                    FieldDefinition('printer', match_type='key_search'),
                    FieldDefinition('code', position='after_printer'),
                ],
                brand_value='MOAB',
                paper_type_processing=PaperTypeProcessing(format=True),
            ),
            FilenamePattern(
                name='epson_sc_files', priority=90, description='EPSON SC-P### EMY2 files',
                prefix='EPSON SC-', prefix_case_insensitive=False, delimiter=' ',
                structure=[
                    FieldDefinition('printer', position=0),
                    FieldDefinition('brand', position=1),
                    FieldDefinition('paper_type', position='2+'),
                ],
                brand_value=None,
                paper_type_processing=PaperTypeProcessing(format=True),
            ),
            FilenamePattern(
                name='cifa_profiles', priority=80, description='Canson/CIFA profiles',
                prefix='cifa_', prefix_case_insensitive=True, delimiter='_',
                structure=[
                    FieldDefinition('printer', position=0),
                    FieldDefinition('paper_type', position='1+'),
                ],
                brand_value='Canson',
                paper_type_processing=PaperTypeProcessing(format=True),
            ),
            FilenamePattern(
                name='hfa_profiles', priority=85, description='Hahnemuehle HFA profiles',
                prefix='HFA', prefix_case_insensitive=False, delimiter='_',
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
            FilenamePattern(
                name='red_river_profiles', priority=75, description='Red River Papers ICC profiles',
                prefix='RR ', prefix_case_insensitive=False, delimiter=' ',
                structure=[
                    FieldDefinition('paper_type', position='before_printer'),
                    FieldDefinition('printer', match_type='key_search'),
                ],
                brand_value='Red River',
                paper_type_processing=PaperTypeProcessing(format=True, remove_brand='Ep'),
            ),
            FilenamePattern(
                name='red_river_emy2_files', priority=74,
                description='Red River Papers EMY2 documentation files',
                prefix='Red River Paper_RR ', prefix_case_insensitive=True, delimiter=' ',
                structure=[
                    FieldDefinition('paper_type', position='0+'),
                ],
                brand_value='Red River',
                paper_type_processing=PaperTypeProcessing(format=True),
            ),
            FilenamePattern(
                name='fallback_printer_detection', priority=10,
                description='Fallback printer detection',
                prefix=None, prefix_case_insensitive=True, delimiter=' ',
                structure=[
                    FieldDefinition('printer', match_type='substring'),
                    FieldDefinition('paper_type', position='remaining'),
                ],
                brand_value='Unknown',
                paper_type_processing=PaperTypeProcessing(format=True),
            ),
        ]

        self.pattern_matcher = PatternMatcher(
            patterns, self.PRINTER_NAMES, self.BRAND_NAME_MAPPINGS, format_paper_type
        )
        self.log("Using default pattern matcher")

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    def match_filename(self, filename: str) -> Optional[Tuple[Optional[str], Optional[str], Optional[str]]]:
        """Parse a filename into (printer, brand, paper_type).

        Returns the raw pattern-match result without applying printer
        remappings; callers apply :func:`apply_printer_remapping` separately.
        Returns None if the matcher has not been built or nothing matched.
        """
        if self.pattern_matcher is None:
            return None
        return self.pattern_matcher.match(filename)
