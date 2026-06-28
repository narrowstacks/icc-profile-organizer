"""Summary output formatting for organization runs."""

from collections import defaultdict
from pathlib import Path
from typing import List, Tuple


def print_profile_organization_summary(operations: List[Tuple[Path, Path]],
                                       verbose: bool = True):
    """Print a grouped summary of how profiles will be organized."""
    if not verbose:
        return

    print("\nProfile Organization Summary:")
    print("=" * 60)

    # Group operations by destination printer and brand.
    summary = defaultdict(lambda: defaultdict(list))
    for _old_path, new_path in operations:
        parts = new_path.parts
        if len(parts) >= 3:
            printer = parts[-3]  # .../Printer/Brand/file
            brand = parts[-2]
            filename = parts[-1]
            summary[printer][brand].append(filename)

    for printer in sorted(summary.keys()):
        print(f"\n📁 {printer}/")
        for brand in sorted(summary[printer].keys()):
            file_count = len(summary[printer][brand])
            print(f"   └─ {brand}/ ({file_count} files)")
            for filename in sorted(summary[printer][brand])[:3]:
                print(f"      • {filename}")
            if file_count > 3:
                print(f"      • ... and {file_count - 3} more")

    print(f"\nTotal profiles to organize: {len(operations)}")


def print_pdf_organization_summary(pdf_operations: List[Tuple[Path, Path]],
                                   num_deleted: int, verbose: bool = True):
    """Print a grouped summary of how PDFs will be organized."""
    if not verbose:
        return

    print("\nPDF Organization Summary:")
    print("=" * 60)

    pdf_summary = defaultdict(list)
    for _old_path, new_path in pdf_operations:
        parts = new_path.parts
        if 'PDFs' in parts:
            pdf_idx = parts.index('PDFs')
            if pdf_idx + 1 < len(parts) - 1:
                printer = parts[pdf_idx + 1]
                pdf_summary[printer].append(parts[-1])

    if pdf_summary:
        for printer in sorted(pdf_summary.keys()):
            print(f"📄 PDFs/{printer}/ ({len(pdf_summary[printer])} files)")
        total = sum(len(v) for v in pdf_summary.values())
        print(f"\nTotal PDFs to organize: {total}")
        if num_deleted:
            print(f"Duplicate PDFs removed: {num_deleted}")


def print_final_summary(num_operations: int, num_renamed: int, num_deleted: int,
                        files_renamed: List[Tuple[str, str]],
                        files_deleted: List[str], verbose: bool = False):
    """Print the final run summary."""
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Files processed: {num_operations}")
    print(f"Files copied: {num_renamed}")
    print(f"Duplicate PDFs removed: {num_deleted}")

    if files_renamed:
        print("\nCopied files:")
        for old, new in files_renamed[:5]:
            print(f"  {old} -> {new}")
        if len(files_renamed) > 5:
            print(f"  ... and {len(files_renamed) - 5} more")

    if files_deleted:
        print("\nDeleted files (duplicates):")
        for file in files_deleted[:5]:
            print(f"  {file}")
        if len(files_deleted) > 5:
            print(f"  ... and {len(files_deleted) - 5} more")

    print("=" * 60)
