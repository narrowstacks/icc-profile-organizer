"""JSON-backed persistence of the user's interactive printer choices.

Two files live next to the source profiles directory:

- ``.profile_choices.json``     - per-filename printer choices
- ``.profile_preferences.json`` - global rules keyed by a printer-combo key
  (e.g. ``"P7570-P9570"``), so the same conflict is resolved automatically next
  time.
"""

import json
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


class UserPreferences:
    """Loads and persists interactive printer-selection choices."""

    def __init__(self, profiles_dir: Path, verbose: bool = False):
        self.verbose = verbose
        profiles_dir = Path(profiles_dir)

        self.choices_path = profiles_dir.parent / '.profile_choices.json'
        self.preferences_path = profiles_dir.parent / '.profile_preferences.json'

        self.user_choices: Dict[str, str] = self._load(self.choices_path)
        self.global_preferences: Dict[str, str] = self._load(self.preferences_path)

    def log(self, message: str, level: str = 'INFO'):
        if self.verbose:
            print(message)
        getattr(logger, level.lower())(message)

    def _load(self, path: Path) -> Dict[str, str]:
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.log(f"Warning: Could not load {path.name}: {e}", level='WARNING')
        return {}

    def _save(self, path: Path, data: Dict[str, str]):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.log(f"Warning: Could not save {path.name}: {e}", level='WARNING')

    def save_choice(self, filename: str, printer_name: str):
        """Record (and persist) the chosen printer for a specific filename."""
        self.user_choices[filename] = printer_name
        self._save(self.choices_path, self.user_choices)

    def set_preference(self, preference_key: str, printer_name: str):
        """Record (and persist) a global rule for a printer-combo key."""
        self.global_preferences[preference_key] = printer_name
        self._save(self.preferences_path, self.global_preferences)
