"""PDF duplicate detection via SHA-256 hashing."""

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Dict, List


def hash_file(file_path: Path, chunk_size: int = 8192) -> str:
    """Calculate the SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def find_pdf_duplicates(pdf_files: List[Path]) -> Dict[str, List[Path]]:
    """Group PDFs by content hash.

    Returns a dict mapping each hash to the list of paths with that hash.
    A hash with more than one path indicates duplicates.
    """
    duplicates: Dict[str, List[Path]] = defaultdict(list)
    for pdf_file in pdf_files:
        duplicates[hash_file(pdf_file)].append(pdf_file)
    return dict(duplicates)


def is_duplicate_file(file_hash: str, pdf_duplicates: Dict[str, List[Path]],
                      file_path: Path) -> bool:
    """Return True if ``file_path`` is a duplicate (not the first of its hash group)."""
    group = pdf_duplicates.get(file_hash)
    if not group or len(group) <= 1:
        return False
    return group[0] != file_path


def get_duplicate_paths(pdf_duplicates: Dict[str, List[Path]]) -> List[Path]:
    """Return the redundant paths (every path except the first in each group)."""
    redundant: List[Path] = []
    for group in pdf_duplicates.values():
        if len(group) > 1:
            redundant.extend(group[1:])
    return redundant


def delete_duplicate_files(paths: List[Path], dry_run: bool = False,
                           verbose: bool = False) -> List[str]:
    """Delete the given duplicate paths. Returns the list of deleted paths.

    When ``dry_run`` is True, no files are removed but the paths that *would*
    be deleted are still returned.
    """
    deleted: List[str] = []
    for path in paths:
        deleted.append(str(path))
        if verbose:
            print(f"  DUPLICATE: {path}")
        if not dry_run:
            try:
                Path(path).unlink()
                if verbose:
                    print(f"    → Deleted")
            except Exception as e:
                if verbose:
                    print(f"    ✗ Error deleting {path}: {e}")
    return deleted
