"""Printer detection, remapping, and interactive multi-printer selection."""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def find_printer_candidates(filename: str, printer_names: Dict[str, str]) -> List[Tuple[str, str]]:
    """Find all distinct printers referenced in a filename.

    Returns a list of ``(printer_key, printer_name)`` tuples, deduplicated by
    canonical printer name (keeping the longest matching key per printer, so
    "pro100" and "pixmapro100" don't both appear).
    """
    name_lower = filename.lower()
    candidates_dict: Dict[str, Tuple[str, str]] = {}  # full_name -> (key, full_name)

    for key, full_name in printer_names.items():
        if key.lower() in name_lower:
            if full_name not in candidates_dict or len(key) > len(candidates_dict[full_name][0]):
                candidates_dict[full_name] = (key, full_name)

    return list(candidates_dict.values())


def apply_printer_remapping(printer_name: str, printer_remappings: Dict[str, str]) -> str:
    """Apply a configured printer remapping, if one exists for ``printer_name``."""
    if printer_name in printer_remappings:
        mapped = printer_remappings[printer_name]
        logger.info(f"Remapping printer: {printer_name} -> {mapped}")
        return mapped
    return printer_name


def _preference_key(candidates: List[Tuple[str, str]]) -> str:
    """Build a stable key for a set of printer candidates (e.g. "P7570-P9570")."""
    keys = sorted(key for key, _ in candidates)
    return "-".join(keys)


def _prompt_for_printer(filename: str, candidates: List[Tuple[str, str]],
                        preferences, preference_key: str) -> Optional[str]:
    """Prompt the user to choose a printer; persist the choice and a global rule.

    Returns the chosen printer name, or None if the user skips.
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

                # Persist the per-file choice and a global rule for the combo.
                preferences.save_choice(filename, chosen)
                preferences.set_preference(preference_key, chosen)

                print(f"✓ Applied globally: When you see {preference_key}, will use {chosen}")
                return chosen

            print(f"Invalid choice. Please enter a number between 1 and {len(candidates)}")
        except ValueError:
            print("Invalid input. Please enter a number or 'q'")


def get_printer_name_interactive(filename: str, detected_printer: str,
                                 candidates: List[Tuple[str, str]],
                                 global_preferences: Dict[str, str],
                                 interactive: bool, preferences) -> str:
    """Resolve the printer for a file that matches multiple printers.

    Resolution order:
      1. A cached per-file choice (``preferences.user_choices``).
      2. A global rule for this printer combo (``global_preferences``).
      3. If ``interactive``, prompt the user (and persist the answer).
      4. Otherwise fall back to ``detected_printer``.
    """
    if filename in preferences.user_choices:
        return preferences.user_choices[filename]

    if len(candidates) > 1:
        pref_key = _preference_key(candidates)
        if pref_key in global_preferences:
            return global_preferences[pref_key]

        if interactive:
            chosen = _prompt_for_printer(filename, candidates, preferences, pref_key)
            return chosen if chosen else detected_printer

        logger.info(f"Multi-printer file: {filename} (use --interactive to choose)")

    return detected_printer
