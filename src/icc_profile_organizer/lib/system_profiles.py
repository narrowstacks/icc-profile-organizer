"""OS-specific installation of organized profiles into system ICC directories.

macOS preserves the organized folder structure; Windows uses a flat layout
(its ColorSync directory does not read subfolders).
"""

import os
import platform
import shutil
from pathlib import Path
from typing import Optional, Tuple

# System ICC profile paths by OS
SYSTEM_ICC_PATHS = {
    'Darwin': {
        'system': Path('/Library/ColorSync/Profiles'),
        'user': Path.home() / 'Library' / 'ColorSync' / 'Profiles',
    },
    'Windows': Path('C:\\Windows\\System32\\spool\\drivers\\color'),
}

# Detect current OS
CURRENT_OS = platform.system()
SYSTEM_ICC_PATH = SYSTEM_ICC_PATHS.get(CURRENT_OS)


def _check_windows_elevated() -> bool:
    """Return True if elevated on Windows (or not on Windows at all)."""
    if CURRENT_OS != 'Windows':
        return True
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        # Fall back to a direct write-access probe.
        return os.access(str(SYSTEM_ICC_PATHS['Windows']), os.W_OK)


def prompt_for_system_profile_export() -> Optional[Path]:
    """Prompt the user to pick a system ICC profile destination.

    On Windows, verifies elevation and offers the single flat directory.
    On macOS, offers a choice between the system and user directories.

    Returns the selected destination Path, or None if the user declines or the
    platform is unsupported.
    """
    paths = SYSTEM_ICC_PATH
    if not paths:
        return None

    if CURRENT_OS == 'Windows':
        if not _check_windows_elevated():
            print("\n" + "=" * 60)
            print("Elevated Privileges Required")
            print("=" * 60)
            print("ERROR: Cannot write to Windows system ICC profile directory")
            print(f"Path: {SYSTEM_ICC_PATHS['Windows']}")
            print("\nThis directory requires Administrator privileges.")
            print("\nTo fix this, please:")
            print("  1. Open Command Prompt or PowerShell as Administrator")
            print("  2. Run the program again with the --system-profiles flag")
            print("=" * 60)
            return None

        system_path = SYSTEM_ICC_PATHS['Windows']
        print("\n" + "=" * 60)
        print("System ICC Profile Directory Found")
        print("=" * 60)
        print(f"Path: {system_path}")
        print("\nNote: Profiles will be copied to a flat structure")
        print("      (no subdirectories will be created in Windows system folder)")
        print("\nWould you like to copy the organized profiles to the system")
        print("ICC profile directory?")

        while True:
            response = input("\nCopy to system profiles? (yes/no): ").strip().lower()
            if response in ('yes', 'y'):
                return system_path
            if response in ('no', 'n'):
                return None
            print("Please enter 'yes' or 'no'")

    # macOS (Darwin) and others: offer system vs user directory.
    system_path = paths['system']
    user_path = paths['user']

    print("\n" + "=" * 60)
    print("ICC Profile Directory Options")
    print("=" * 60)
    print("\n1. System Directory (requires admin)")
    print(f"   Path: {system_path}")
    print("   Profiles available to all users")
    print("\n2. User Directory (no admin needed)")
    print(f"   Path: {user_path}")
    print("   Profiles available only to you")
    print("\nProfiles will be organized with folder structure")

    while True:
        response = input("\nChoose directory (1/2) or 'skip': ").strip().lower()
        if response in ('1', 'system'):
            system_path.parent.mkdir(parents=True, exist_ok=True)
            if not os.access(str(system_path.parent), os.W_OK):
                print(f"\nError: No write permission to {system_path.parent}")
                print("Try running with: sudo ...")
                continue
            return system_path
        if response in ('2', 'user'):
            user_path.mkdir(parents=True, exist_ok=True)
            return user_path
        if response in ('skip', 's', 'n', 'no'):
            return None
        print("Please enter '1', '2', or 'skip'")


def copy_profiles_to_system(output_dir: Path, system_path: Path,
                            verbose: bool = False) -> Tuple[int, int]:
    """Copy organized ``.icc``/``.icm`` profiles into ``system_path``.

    Windows uses a flat layout; other platforms preserve the folder structure
    relative to ``output_dir``. Returns ``(copied_count, failed_count)``.
    """
    output_dir = Path(output_dir)
    system_path = Path(system_path)

    if not system_path.exists():
        if verbose:
            print(f"Error: System profile path does not exist: {system_path}")
        return 0, 0

    if not os.access(str(system_path.parent), os.W_OK):
        if verbose:
            print(f"Error: No write permission to {system_path}")
            if CURRENT_OS == 'Darwin' and '/Library/ColorSync' in str(system_path):
                print("Note: Run with 'sudo' to write to system directory")
        return 0, 0

    copied_count = 0
    failed_count = 0

    flat = CURRENT_OS == 'Windows'

    for file_path in output_dir.rglob('*'):
        if not (file_path.is_file() and file_path.suffix.lower() in ('.icc', '.icm')):
            continue
        try:
            if flat:
                dest_path = system_path / file_path.name
            else:
                rel_path = file_path.relative_to(output_dir)
                dest_path = system_path / rel_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)

            shutil.copy2(str(file_path), str(dest_path))
            copied_count += 1
            if verbose:
                print(f"  ✓ Copied: {file_path.name}")
        except Exception as e:
            failed_count += 1
            if verbose:
                print(f"  ✗ Error copying {file_path.name}: {e}")

    if verbose:
        print(f"\nSuccessfully copied: {copied_count} profiles")
        if failed_count:
            print(f"Failed to copy: {failed_count} profiles")

    return copied_count, failed_count
