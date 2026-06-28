"""Public API for the ICC Profile Organizer core library.

Re-exports the classes and functions used by the CLI entry points
(``organize_profiles`` and ``config_wizard``).
"""

from .config_manager import ConfigManager
from .file_operations import execute_copy_operations
from .file_scanning import find_profile_files
from .filename_utils import generate_new_filename
from .icc_utils import ICCProfileUpdater
from .pattern_matching import (
    FieldDefinition,
    FilenamePattern,
    PaperTypeProcessing,
    PatternMatcher,
    PatternVariant,
    format_paper_type,
)
from .pdf_utils import (
    delete_duplicate_files,
    find_pdf_duplicates,
    get_duplicate_paths,
    hash_file,
    is_duplicate_file,
)
from .printer_utils import (
    apply_printer_remapping,
    find_printer_candidates,
    get_printer_name_interactive,
)
from .reporting import (
    print_final_summary,
    print_pdf_organization_summary,
    print_profile_organization_summary,
)
from .system_profiles import copy_profiles_to_system, prompt_for_system_profile_export
from .user_preferences import UserPreferences

__all__ = [
    # classes
    "ConfigManager",
    "ICCProfileUpdater",
    "UserPreferences",
    "PatternMatcher",
    "FilenamePattern",
    "FieldDefinition",
    "PatternVariant",
    "PaperTypeProcessing",
    # pattern / filename helpers
    "format_paper_type",
    "generate_new_filename",
    # scanning / file ops
    "find_profile_files",
    "execute_copy_operations",
    # pdf
    "hash_file",
    "find_pdf_duplicates",
    "is_duplicate_file",
    "get_duplicate_paths",
    "delete_duplicate_files",
    # printer
    "find_printer_candidates",
    "apply_printer_remapping",
    "get_printer_name_interactive",
    # system profiles
    "prompt_for_system_profile_export",
    "copy_profiles_to_system",
    # reporting
    "print_profile_organization_summary",
    "print_pdf_organization_summary",
    "print_final_summary",
]
