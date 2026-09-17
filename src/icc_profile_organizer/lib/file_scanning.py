"""Discovery of profile files in a directory tree."""

from pathlib import Path
from typing import Dict, List, Union

# File type label -> glob. EMY2 (Epson) and AM1X/AM1 (Canon imagePROGRAF
# PRO / iPF) are the vendors' media-preset files that ship next to the ICC
# profile; they are organized and renamed like profiles but never get their
# description rewritten or installed into ColorSync.
_PROFILE_GLOBS = {
    'ICC': '*.icc',
    'ICM': '*.icm',
    'EMY2': '*.emy2',
    'AM1X': '*.am1x',
    'AM1': '*.am1',
}


def find_profile_files(profiles_dir: Union[str, Path]) -> Dict[str, List[Path]]:
    """Find all ICC, ICM, EMY2 and AM1X/AM1 files under ``profiles_dir`` recursively.

    Returns a dict keyed by file type ('ICC', 'ICM', 'EMY2', 'AM1X', 'AM1'),
    each mapping to a list of Paths. macOS resource-fork files ("._name")
    are excluded.
    """
    base = Path(profiles_dir)
    return {
        label: [f for f in base.rglob(pattern) if '._' not in f.name]
        for label, pattern in _PROFILE_GLOBS.items()
    }
