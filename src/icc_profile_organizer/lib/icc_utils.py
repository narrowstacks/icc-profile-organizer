"""Reading and updating ICC profile descriptions.

``ICCProfileUpdater`` rewrites the ``desc`` tag of an ICC profile in place so
the embedded description matches the organized filename.
"""

import struct
from pathlib import Path
from typing import Optional, Tuple


class ICCProfileUpdater:
    """Handle reading and updating ICC profile descriptions."""

    # ASCII signature inside ICC files (at offset 36)
    ICC_SIGNATURE = b'acsp'

    # Tag signature for description
    DESC_TAG = b'desc'

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def log(self, message: str):
        if self.verbose:
            print(message)

    def read_icc_profile(self, file_path: Path) -> Optional[bytes]:
        """Read an ICC profile file."""
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            self.log(f"Error reading {file_path}: {e}")
            return None

    def write_icc_profile(self, file_path: Path, data: bytes) -> bool:
        """Write an ICC profile file."""
        try:
            with open(file_path, 'wb') as f:
                f.write(data)
            return True
        except Exception as e:
            self.log(f"Error writing {file_path}: {e}")
            return False

    def validate_header(self, data: bytes) -> bool:
        """Validate an ICC profile header."""
        if len(data) < 128:
            return False
        try:
            signature = data[36:40]
            return signature == self.ICC_SIGNATURE
        except Exception:
            return False

    def find_tag(self, data: bytes, tag_sig: bytes) -> Optional[Tuple[int, int]]:
        """Find a tag in an ICC profile, returning (offset, size) or None."""
        # Parse tag table at offset 128
        if len(data) < 132:
            return None

        try:
            tag_count = struct.unpack('>I', data[128:132])[0]

            # Each tag entry is 12 bytes: signature (4) + offset (4) + size (4)
            for i in range(tag_count):
                entry_offset = 132 + (i * 12)

                if entry_offset + 12 > len(data):
                    break

                entry_sig = data[entry_offset:entry_offset + 4]
                tag_offset = struct.unpack('>I', data[entry_offset + 4:entry_offset + 8])[0]
                tag_size = struct.unpack('>I', data[entry_offset + 8:entry_offset + 12])[0]

                if entry_sig == tag_sig:
                    return (tag_offset, tag_size)

            return None
        except Exception:
            return None

    def update_description_tag(self, data: bytes, new_description: str) -> Optional[bytes]:
        """Update the description tag in an ICC profile.

        The desc tag structure:
        - Bytes 0-3:  Tag signature ('desc')
        - Bytes 4-7:  Reserved (0)
        - Bytes 8-11: ASCII description length (including null terminator)
        - Bytes 12+:  ASCII description
        """
        try:
            tag_info = self.find_tag(data, self.DESC_TAG)
            if not tag_info:
                return None

            old_offset, old_size = tag_info

            # Limit description to ASCII, max 255 chars
            desc_ascii = new_description.encode('ascii', errors='replace')[:255]

            desc_data = self.DESC_TAG  # 4 bytes: 'desc'
            desc_data += b'\x00\x00\x00\x00'  # 4 bytes: reserved

            desc_length = len(desc_ascii) + 1  # +1 for null terminator
            desc_data += struct.pack('>I', desc_length)  # 4 bytes: length
            desc_data += desc_ascii
            desc_data += b'\x00'  # null terminator

            # Pad to multiple of 4 bytes (ICC requirement)
            padding = (4 - (len(desc_data) % 4)) % 4
            desc_data += b'\x00' * padding

            new_size = len(desc_data)

            if new_size <= old_size:
                # Pad the new data to match old size, then splice in place.
                if new_size < old_size:
                    desc_data += b'\x00' * (old_size - new_size)
                return data[:old_offset] + desc_data + data[old_offset + old_size:]

            # New description is too long to fit in-place; truncate to fit.
            max_desc_len = old_size - 12  # 12 bytes for header, rest for description
            if max_desc_len <= 0:
                return None

            desc_ascii = new_description.encode('ascii', errors='replace')[:max_desc_len - 1]

            desc_data = self.DESC_TAG
            desc_data += b'\x00\x00\x00\x00'
            desc_length = len(desc_ascii) + 1
            desc_data += struct.pack('>I', desc_length)
            desc_data += desc_ascii
            desc_data += b'\x00'

            padding = old_size - len(desc_data)
            if padding > 0:
                desc_data += b'\x00' * padding

            return data[:old_offset] + desc_data + data[old_offset + old_size:]

        except Exception:
            return None

    def process_profile(self, file_path: Path) -> bool:
        """Process a single ICC profile file. Returns True on success."""
        new_description = file_path.stem

        profile_data = self.read_icc_profile(file_path)
        if not profile_data:
            return False

        if not self.validate_header(profile_data):
            return False

        updated_data = self.update_description_tag(profile_data, new_description)
        if not updated_data:
            return False

        return self.write_icc_profile(file_path, updated_data)

    def process_directory(self, directory: Path, verbose: bool = True) -> Tuple[int, int]:
        """Process all ICC/ICM profiles in a directory recursively.

        Returns (processed, successful).
        """
        icc_files = list(directory.rglob('*.icc'))
        icm_files = list(directory.rglob('*.icm'))

        # Filter out macOS resource forks
        icc_files = [f for f in icc_files if '._' not in f.name]
        icm_files = [f for f in icm_files if '._' not in f.name]

        all_files = icc_files + icm_files

        if verbose:
            print(f"  Updating descriptions for {len(all_files)} profile files...")

        processed = 0
        successful = 0

        for file_path in sorted(all_files):
            processed += 1
            if self.process_profile(file_path):
                successful += 1

        return processed, successful
