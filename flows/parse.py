"""
Pure parsing logic — no Prefect dependencies, fully testable in isolation.
"""
import re
import mwparserfromhell

_SKIP_PREFIXES = {"File", "Image", "Category", "Template", "Wikipedia", "w", "Help"}


def _names_from_field(value_str: str) -> list[str]:
    """Extract character names from a wikitext infobox field value."""
    parsed = mwparserfromhell.parse(str(value_str))

    # Wikilinks give the canonical page name — prefer these over plain text
    wikilinks = parsed.filter_wikilinks()
    if wikilinks:
        names = []
        for link in wikilinks:
            target = str(link.title).strip()
            namespace = target.split(":")[0] if ":" in target else ""
            if namespace in _SKIP_PREFIXES:
                continue
            # "Harry Potter (character)" → "Harry Potter"
            name = re.sub(r"\s*\([^)]*\)\s*$", "", target).strip()
            if name:
                names.append(name)
        return names

    # Fallback: strip markup and split by common delimiters
    plain = parsed.strip_code().strip()
    if not plain:
        return []
    parts = re.split(r"[,;\n]+|\*\s*", plain)
    return [
        re.sub(r"\s*\([^)]*\)\s*$", "", p).strip()
        for p in parts
        if p.strip() and len(p.strip()) > 1
    ]


def parse_character(wikitext: str, field_mappings: dict[str, str]) -> dict[str, list[str]]:
    """
    Given a character's raw wikitext and a field→relationship mapping,
    return {relationship_type: [target_character_names]}.
    """
    parsed = mwparserfromhell.parse(wikitext)
    relations: dict[str, list[str]] = {}

    for template in parsed.filter_templates():
        for field_name, rel_type in field_mappings.items():
            if template.has(field_name):
                names = _names_from_field(template.get(field_name).value)
                if names:
                    relations.setdefault(rel_type, []).extend(names)

    # Deduplicate, preserve order
    return {rel: list(dict.fromkeys(targets)) for rel, targets in relations.items()}
