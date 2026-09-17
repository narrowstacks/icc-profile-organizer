"""Boundary-aware lookup of printer aliases inside filenames.

Vendors glue printer tokens onto other text ("EpP900", "OEMSCP7000",
"P7570-P9570", "CANpro-2_4_6_21_41_61"), so aliases are matched as substrings.
Two rules keep that from misfiring once the alias table is large:

* the **longest** matching alias wins ("PRO-1000" beats "PRO-100"), and
* a numeric edge of an alias must not touch another digit, so "P900" never
  matches inside "P9000" and "Pro-10" never matches inside "Pro-100".
"""

from typing import Dict, List, Optional, Tuple


class PrinterKeyIndex:
    """Finds the best printer alias in a string or a list of delimited parts."""

    def __init__(self, printer_names: Dict[str, str]):
        self.printer_names = printer_names
        # Longest first so the first hit is the most specific alias.
        self._keys = sorted(printer_names, key=len, reverse=True)

    def canonical(self, key: str) -> str:
        """Canonical printer name for an alias."""
        return self.printer_names.get(key, key)

    @staticmethod
    def _bounded(text: str, key: str, start: int) -> bool:
        end = start + len(key)
        if key[-1].isdigit() and end < len(text) and text[end].isdigit():
            return False
        if key[0].isdigit() and start > 0 and text[start - 1].isdigit():
            return False
        return True

    def find(self, text: str) -> Optional[Tuple[str, int, int]]:
        """Return (alias, start, end) of the best alias in ``text``.

        Longest alias wins; among equally long aliases the leftmost occurrence.
        """
        lower = text.lower()
        best: Optional[Tuple[str, int, int]] = None
        for key in self._keys:
            if best is not None and len(key) < len(best[0]):
                break
            k = key.lower()
            pos = lower.find(k)
            while pos != -1:
                if self._bounded(lower, k, pos):
                    if best is None or pos < best[1]:
                        best = (key, pos, pos + len(key))
                    break
                pos = lower.find(k, pos + 1)
        return best

    def find_in_parts(self, parts: List[str], delimiter: str) -> Optional[Tuple[str, int, int]]:
        """Return (alias, first_part, last_part) for the best alias in ``parts``.

        Single-part aliases are matched inside one part (extra text around the
        alias is allowed, e.g. "EpP900"). Aliases that contain the delimiter
        span several parts; the outer parts may carry extra text
        ("ILFORD_CANpro-2" -> "CANpro-2"). The longest alias wins; among
        equally long aliases the one appearing earliest in ``parts``.
        """
        best: Optional[Tuple[str, int, int]] = None
        for key in self._keys:
            if best is not None and len(key) < len(best[0]):
                break
            k = key.lower()
            if delimiter in key:
                hit = self._find_spanning(parts, k.split(delimiter))
            else:
                hit = self._find_in_single_part(parts, k)
            if hit is not None and (best is None or hit[0] < best[1]):
                best = (key, hit[0], hit[1])
        return best

    def _find_in_single_part(self, parts: List[str], k: str) -> Optional[Tuple[int, int]]:
        for i, part in enumerate(parts):
            p = part.lower()
            pos = p.find(k)
            while pos != -1:
                if self._bounded(p, k, pos):
                    return i, i
                pos = p.find(k, pos + 1)
        return None

    @staticmethod
    def _find_spanning(parts: List[str], key_parts: List[str]) -> Optional[Tuple[int, int]]:
        n = len(key_parts)
        for i in range(len(parts) - n + 1):
            window = [p.lower() for p in parts[i:i + n]]
            if (window[0].endswith(key_parts[0]) and window[-1].startswith(key_parts[-1])
                    and window[1:-1] == key_parts[1:-1]):
                return i, i + n - 1
        return None
