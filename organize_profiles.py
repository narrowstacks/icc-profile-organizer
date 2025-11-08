#!/usr/bin/env python3
"""
ICC Profile, EMX/EMY2, and PDF Organizer
Renames and organizes color profiles and documentation by Printer and Paper Brand.
"""

import sys
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

try:
    from rich.console import Console
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from lib import (
    ICCProfileUpdater,
    ConfigManager,
    UserPreferences,
    find_profile_files,
    find_pdf_duplicates,
    hash_file,
    get_duplicate_paths,
    is_duplicate_file,
    find_printer_candidates,
    apply_printer_remapping,
    get_printer_name_interactive,
    generate_new_filename,
    execute_copy_operations,
    delete_duplicate_files,
    prompt_for_system_profile_export,
    copy_profiles_to_system,
    print_profile_organization_summary,
    print_pdf_organization_summary,
    print_final_summary,
)


class ProfileOrganizer:
    """Organizes ICC profiles, EMX files, and PDFs."""

    def __init__(self, profiles_dir: str, output_dir: str = None, dry_run: bool = True,
                 verbose: bool = False, interactive: bool = False, detailed: bool = False,
                 update_descriptions: bool = True):
        """
        Initialize the organizer.

        Args:
            profiles_dir: Path to source /profiles directory
            output_dir: Path to output directory (default: ./organized-profiles)
            dry_run: If True, don't actually move files, just preview
            verbose: If True, print detailed information (deprecated, use detailed)
            interactive: If True, prompt user for multi-printer profiles
            detailed: If True, show each file transformation; if False, show summary only
            update_descriptions: If True, update ICC profile descriptions to match filenames
        """
        self.profiles_dir = Path(profiles_dir).resolve()

        # Set output directory (default to organized-profiles sibling)
        if output_dir is None:
            self.output_dir = self.profiles_dir.parent / 'organized-profiles'
        else:
            self.output_dir = Path(output_dir).resolve()

        self.dry_run = dry_run
        self.verbose = verbose or detailed  # Keep verbose for logging, use detailed for UI
        self.interactive = interactive
        self.detailed = detailed
        self.update_descriptions = update_descriptions

        # Setup rich console for colored output
        self.console = Console() if HAS_RICH else None

        # Setup logging
        self.setup_logging()

        # Load configuration
        self.config_manager = ConfigManager(verbose=False)
        self.config_manager.load()

        # User preferences manager
        self.preferences = UserPreferences(self.profiles_dir, verbose=False)

        # Storage for file operations
        self.operations = []  # List of (old_path, new_path) tuples
        self.pdf_duplicates = {}  # Hash -> list of paths
        self.files_renamed = []
        self.files_deleted = []
        self.selected_system_profile_path = None

        if not self.profiles_dir.exists():
            self.log(f"Error: {self.profiles_dir} does not exist", level='ERROR')
            sys.exit(1)

    def setup_logging(self):
        """Setup logging configuration."""
        # Format for log file (with timestamp)
        file_format = '%(asctime)s - %(levelname)s - %(message)s'
        # Format for console (message only, no timestamp or level)
        console_format = '%(message)s'
        
        # Create handlers
        file_handler = logging.FileHandler('profile_organizer.log')
        file_handler.setFormatter(logging.Formatter(file_format))
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(console_format))
        
        # Configure root logger
        logging.basicConfig(
            level=logging.INFO,
            handlers=[file_handler, console_handler]
        )
        self.logger = logging.getLogger(__name__)

    def log(self, message: str, level: str = 'INFO'):
        """Log a message."""
        # Always log errors and warnings, only log info/debug when verbose
        if level.upper() in ('ERROR', 'WARNING') or self.verbose:
            getattr(self.logger, level.lower())(message)

    def organize_profiles(self) -> bool:
        """
        Main function to organize ICC profiles and EMX files.

        Returns:
            True if successful, False otherwise
        """
        self.log("=" * 60)
        if HAS_RICH and self.console:
            self.console.print("[bold cyan]Starting ICC Profile Organization[/bold cyan]")
        else:
            self.log("Starting ICC Profile Organization")
        mode_text = 'DRY RUN' if self.dry_run else 'EXECUTE'
        if HAS_RICH and self.console:
            if self.dry_run:
                self.console.print(f"Mode: [yellow]{mode_text}[/yellow]")
            else:
                self.console.print(f"Mode: [green]{mode_text}[/green]")
        else:
            self.log(f"Mode: {mode_text}")
        self.log(f"Source directory: {self.profiles_dir}")
        self.log(f"Output directory: {self.output_dir}")
        self.log("=" * 60)

        # Find all ICC, ICM, and EMY2 files
        profile_files = find_profile_files(self.profiles_dir)

        if not profile_files or not any(profile_files.values()):
            self.log("No profile files found.", level='WARNING')
            return False

        self.log(f"\nFound {sum(len(f) for f in profile_files.values())} profile files:")
        for ftype, files in profile_files.items():
            if files:
                self.log(f"  {ftype}: {len(files)} files")

        # Process each profile type
        all_files = []
        for file_list in profile_files.values():
            all_files.extend(file_list)

        # Track existing names to handle duplicates
        existing_names = {}

        for file_path in all_files:
            # Extract printer, brand, paper type from filename
            result = self.config_manager.match_filename(file_path.name)
            if not result:
                self.log(f"  ⚠ Could not parse: {file_path.name}", level='WARNING')
                continue

            printer, brand, paper_type = result

            if not printer or not brand:
                self.log(f"  ⚠ Could not parse: {file_path.name}", level='WARNING')
                continue

            # Use interactive mode if enabled to choose printer for multi-printer files
            candidates = find_printer_candidates(file_path.name, self.config_manager.PRINTER_NAMES)
            if len(candidates) > 1:
                printer = get_printer_name_interactive(
                    file_path.name, printer, candidates,
                    self.preferences.global_preferences,
                    self.interactive, self.preferences
                )

            # Apply printer remappings
            printer = apply_printer_remapping(printer, self.config_manager.PRINTER_REMAPPINGS)

            # Determine extension
            ext = file_path.suffix.lstrip('.')

            # Generate new filename
            new_filename = generate_new_filename(printer, brand, paper_type, ext, existing_names)

            # Create new path: organized-profiles/Printer/Brand/filename
            new_path = self.output_dir / printer / brand / new_filename

            self.operations.append((file_path, new_path))

            # Only print if detailed mode is enabled
            if self.detailed:
                self.log(f"  {file_path.name} -> {new_path.relative_to(self.output_dir.parent)}")

        # Show summary organized by printer/brand
        if not self.detailed:
            print_profile_organization_summary(self.operations, verbose=True)

        # Execute operations if not dry run
        if not self.dry_run:
            self.files_renamed, _ = execute_copy_operations(self.operations, verbose=self.verbose)

        return True

    def organize_pdfs(self) -> bool:
        """
        Find, deduplicate, and organize PDF files.

        Returns:
            True if successful, False otherwise
        """
        self.log("\n" + "=" * 60)
        if HAS_RICH and self.console:
            self.console.print("[bold cyan]Starting PDF Organization[/bold cyan]")
        else:
            self.log("Starting PDF Organization")
        self.log("=" * 60)

        # Find all PDFs
        pdf_files = list(self.profiles_dir.rglob('*.pdf'))

        if not pdf_files:
            self.log("No PDF files found.")
            return True

        self.log(f"Found {len(pdf_files)} PDF files")

        # Calculate hashes and find duplicates
        self.pdf_duplicates = find_pdf_duplicates(pdf_files)

        duplicates_found = sum(1 for v in self.pdf_duplicates.values() if len(v) > 1)
        self.log(f"Found {duplicates_found} duplicate sets")

        # Track existing names to handle duplicates
        existing_names = {}

        # Process PDFs
        for file_path in pdf_files:
            # Check if this is a duplicate (not the first occurrence)
            file_hash = hash_file(file_path)

            if is_duplicate_file(file_hash, self.pdf_duplicates, file_path):
                # This is a duplicate
                self.log(f"  DUPLICATE: {file_path.relative_to(self.profiles_dir)}")
                self.files_deleted.append(str(file_path))

                if not self.dry_run:
                    file_path.unlink()
                    self.log(f"    → Deleted")
            else:
                # This is a unique file, organize it
                # Try to extract printer from filename or parent folder
                printer = self._extract_printer_from_context(file_path)

                if printer:
                    ext = file_path.suffix.lstrip('.')
                    new_filename = generate_new_filename(printer, 'PDFs', file_path.stem, ext, existing_names)
                    new_path = self.output_dir / 'PDFs' / printer / new_filename
                    self.operations.append((file_path, new_path))
                    if self.detailed:
                        self.log(f"  {file_path.relative_to(self.profiles_dir)} -> PDFs/{printer}/{new_filename}")

        # Show PDF organization summary
        pdf_ops = [op for op in self.operations if 'PDFs' in str(op[1])]
        if not self.detailed and pdf_ops:
            print_pdf_organization_summary(pdf_ops, len(self.files_deleted), verbose=True)

        # Execute operations if not dry run
        if not self.dry_run:
            renamed, _ = execute_copy_operations(self.operations, verbose=self.verbose)
            self.files_renamed.extend(renamed)

        return True

    def _extract_printer_from_context(self, file_path: Path) -> Optional[str]:
        """Extract printer name from file path context (filename first, then parent dirs)."""
        # First, try to extract from filename
        result = self.config_manager.match_filename(file_path.name)
        if result:
            printer_name, _, _ = result
            return apply_printer_remapping(printer_name, self.config_manager.PRINTER_REMAPPINGS)

        # Check parent directory name and all parents
        for parent in [file_path.parent] + list(file_path.parents):
            parent_name = parent.name

            # Look for exact and case-insensitive matches
            for key, full_name in self.config_manager.PRINTER_NAMES.items():
                if key.lower() in parent_name.lower():
                    return apply_printer_remapping(full_name, self.config_manager.PRINTER_REMAPPINGS)

            # Special handling for patterns like "IPF 6450" vs "iPF6450"
            if 'iPF6450' in parent_name or 'ipf6450' in parent_name or 'IPF 6450' in parent_name or 'ipf 6450' in parent_name:
                return 'Canon iPF6450'
            if 'PRO-100' in parent_name or 'Pro-100' in parent_name or 'pro-100' in parent_name:
                return 'Canon Pixma PRO-100'

        return 'Uncategorized'

    def update_profile_descriptions(self) -> bool:
        """
        Update ICC profile descriptions to match filenames.

        Returns:
            True if successful, False otherwise
        """
        self.log("\n" + "=" * 60)
        if HAS_RICH and self.console:
            self.console.print("[bold cyan]Updating ICC Profile Descriptions[/bold cyan]")
        else:
            self.log("Updating ICC Profile Descriptions")
        self.log("=" * 60)

        if not self.output_dir.exists():
            self.log("Output directory does not exist yet. Skipping description update.", level='WARNING')
            return False

        updater = ICCProfileUpdater(verbose=False)
        processed, successful = updater.process_directory(self.output_dir, verbose=True)

        self.log(f"  Updated {successful} / {processed} profiles")

        return successful == processed

    def prompt_for_system_profile_export(self) -> bool:
        """
        Prompt user if they want to copy profiles to system ICC directory.

        Returns:
            True if user wants to copy, False otherwise
        """
        selected_path = prompt_for_system_profile_export()
        if selected_path:
            self.selected_system_profile_path = selected_path
            return True
        return False

    def copy_to_system_profiles(self) -> bool:
        """
        Copy organized profiles to system ICC profile directory.

        Returns:
            True if successful, False otherwise
        """
        if not self.selected_system_profile_path:
            self.log(f"Error: No system profile path selected", level='ERROR')
            return False

        copied_count, failed_count = copy_profiles_to_system(
            self.output_dir,
            self.selected_system_profile_path,
            verbose=self.verbose
        )

        return failed_count == 0

    def print_summary(self):
        """Print summary of operations."""
        print_final_summary(
            len(self.operations),
            len(self.files_renamed),
            len(self.files_deleted),
            self.files_renamed,
            self.files_deleted,
            verbose=self.verbose
        )
        
        # Show dry run message at the end if in dry run mode
        if self.dry_run:
            if HAS_RICH and self.console:
                self.console.print("\n[yellow bold][DRY RUN] Use --execute flag to apply changes[/yellow bold]")
            else:
                print("\n[DRY RUN] Use --execute flag to apply changes")
            self.logger.info("[DRY RUN] Use --execute flag to apply changes")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Organize ICC profiles, EMX files, and PDFs'
    )
    parser.add_argument(
        'profiles_dir',
        nargs='?',
        default='./profiles',
        help='Path to source profiles directory (default: ./profiles)'
    )
    parser.add_argument(
        '--output-dir',
        default=None,
        help='Output directory for organized profiles (default: ./organized-profiles)'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Execute operations (default is dry-run mode)'
    )
    parser.add_argument(
        '--profiles-only',
        action='store_true',
        help='Only organize profiles, skip PDFs'
    )
    parser.add_argument(
        '--pdfs-only',
        action='store_true',
        help='Only organize PDFs, skip profiles'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress output'
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Interactively choose printer for files with multiple printer options'
    )
    parser.add_argument(
        '--detailed',
        action='store_true',
        help='Show detailed file-by-file transformation list (default is summary)'
    )
    parser.add_argument(
        '--skip-desc-update',
        action='store_true',
        help='Skip updating ICC profile descriptions to match filenames'
    )
    parser.add_argument(
        '--system-profiles',
        action='store_true',
        help='Copy organized profiles to system ICC profile directory (prompts if system directory found)'
    )
    parser.add_argument(
        '--no-system-profiles-prompt',
        action='store_true',
        help='Do not prompt to copy to system ICC profile directory'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.profiles_only and args.pdfs_only:
        if HAS_RICH:
            console = Console()
            console.print("[bold red]Error: Cannot use both --profiles-only and --pdfs-only[/bold red]")
        else:
            print("Error: Cannot use both --profiles-only and --pdfs-only")
        sys.exit(1)

    # Initialize organizer
    organizer = ProfileOrganizer(
        args.profiles_dir,
        output_dir=args.output_dir,
        dry_run=not args.execute,
        verbose=not args.quiet,
        interactive=args.interactive,
        detailed=args.detailed,
        update_descriptions=not args.skip_desc_update
    )

    # Run organization
    try:
        if not args.pdfs_only:
            organizer.organize_profiles()

        if not args.profiles_only:
            organizer.organize_pdfs()

        # Update profile descriptions if enabled and in execute mode
        if organizer.update_descriptions and not organizer.dry_run:
            organizer.update_profile_descriptions()

        organizer.print_summary()

        # Handle system profile export
        should_export_to_system = False
        if not organizer.dry_run:
            if args.system_profiles:
                # User explicitly requested system profiles via flag
                should_export_to_system = True
            elif not args.no_system_profiles_prompt:
                # Prompt user if system directory is accessible
                should_export_to_system = organizer.prompt_for_system_profile_export()

            if should_export_to_system:
                organizer.copy_to_system_profiles()

    except KeyboardInterrupt:
        if HAS_RICH:
            console = Console()
            console.print("\n\n[yellow]Operation cancelled by user[/yellow]")
        else:
            print("\n\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        if HAS_RICH:
            console = Console()
            console.print(f"[bold red]Error: {e}[/bold red]")
        else:
            print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
