"""Execution of planned file copy operations."""

import shutil
from pathlib import Path
from typing import List, Tuple


def execute_copy_operations(operations: List[Tuple[Path, Path]],
                            verbose: bool = False) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Copy each (source, destination) pair, creating parent directories.

    Uses ``shutil.copy2`` to preserve metadata. Returns ``(copied, failed)``
    where each is a list of ``(old_path, new_path)`` string tuples.
    """
    copied: List[Tuple[str, str]] = []
    failed: List[Tuple[str, str]] = []

    for old_path, new_path in operations:
        try:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(old_path), str(new_path))
            copied.append((str(old_path), str(new_path)))
            if verbose:
                print(f"  ✓ Copied: {old_path.name}")
        except Exception as e:
            failed.append((str(old_path), str(new_path)))
            if verbose:
                print(f"  ✗ Error copying {old_path.name}: {e}")

    return copied, failed
