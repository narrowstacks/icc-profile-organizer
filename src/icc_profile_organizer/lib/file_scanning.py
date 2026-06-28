"""Discovery of profile files in a directory tree."""

from pathlib import Path
from typing import Dict, List, Union


def find_profile_files(profiles_dir: Union[str, Path]) -> Dict[str, List[Path]]:
    """Find all ICC, ICM, and EMY2 files under ``profiles_dir`` recursively.

    Returns a dict keyed by file type ('ICC', 'ICM', 'EMY2'), each mapping to a
    list of Paths. macOS resource-fork files ("._name") are excluded.
    """
    base = Path(profiles_dir)

    icc_files = list(base.rglob('*.icc'))
    icm_files = list(base.rglob('*.icm'))
    emy2_files = list(base.rglob('*.emy2'))

    icc_files = [f for f in icc_files if '._' not in f.name]
    icm_files = [f for f in icm_files if '._' not in f.name]
    emy2_files = [f for f in emy2_files if '._' not in f.name]

    return {
        'ICC': icc_files,
        'ICM': icm_files,
        'EMY2': emy2_files,
    }
