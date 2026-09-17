"""Standardized output-filename construction."""

from typing import Dict


def generate_new_filename(printer: str, brand: str, paper_type: str,
                          extension: str, existing_names: Dict[str, int]) -> str:
    """Generate a standardized filename.

    Format: ``Printer Name - Paper Brand - Paper Type[ [N]].ext``

    ``existing_names`` tracks names seen so far so that collisions get a
    ``[N]`` suffix. It is mutated in place by this function. The key includes
    the extension: an ``.icc`` and its ``.emy2`` media preset share a stem
    on purpose and must not suffix each other.
    """
    base_name = f"{printer} - {brand} - {paper_type}"
    key = f"{base_name}.{extension.lower()}"

    if key in existing_names:
        existing_names[key] += 1
        return f"{base_name} [{existing_names[key]}].{extension}"

    existing_names[key] = 1
    return f"{base_name}.{extension}"
