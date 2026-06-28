"""Standardized output-filename construction."""

from typing import Dict


def generate_new_filename(printer: str, brand: str, paper_type: str,
                          extension: str, existing_names: Dict[str, int]) -> str:
    """Generate a standardized filename.

    Format: ``Printer Name - Paper Brand - Paper Type[ [N]].ext``

    ``existing_names`` tracks base names seen so far so that collisions get a
    ``[N]`` suffix. It is mutated in place by this function.
    """
    base_name = f"{printer} - {brand} - {paper_type}"

    if base_name in existing_names:
        existing_names[base_name] += 1
        return f"{base_name} [{existing_names[base_name]}].{extension}"

    existing_names[base_name] = 1
    return f"{base_name}.{extension}"
