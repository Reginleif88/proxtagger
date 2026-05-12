import logging
import re

# Proxmox tag-name pattern (PVE/JSONSchema.pm: PVE_TAG_RE).
TAG_NAME_RE = re.compile(r'^[a-z0-9_][a-z0-9_\-\+\.]*$')
HEX6_RE = re.compile(r'^[0-9a-fA-F]{6}$')


def parse_tags(tags_string: str) -> list:
    """
    Parse a semicolon-separated tags string into a list of tags.
    
    Args:
        tags_string (str): Semicolon-separated tags string
        
    Returns:
        list: List of individual tags (empty tags filtered out)
    """
    if not tags_string or not isinstance(tags_string, str):
        return []
    
    return [tag.strip() for tag in tags_string.split(";") if tag.strip()]

def format_tags(tags_list: list) -> str:
    """
    Format a list of tags into a semicolon-separated string.
    
    Args:
        tags_list (list): List of tag strings
        
    Returns:
        str: Semicolon-separated tags string
    """
    if not tags_list:
        return ""
    
    # Filter out empty/None tags and strip whitespace
    clean_tags = [str(tag).strip() for tag in tags_list if tag and str(tag).strip()]
    return ";".join(clean_tags)

def extract_tags(vm_list: list) -> list:
    """
    Collect and deduplicate tags across all VMs.
    
    Args:
        vm_list (list): List of VM dictionaries containing tag information
        
    Returns:
        list: Sorted list of unique tags
    """
    try:
        all_tags = set()
        for vm in vm_list:
            tags = vm.get("tags", "")
            if isinstance(tags, str) and tags.strip():
                all_tags.update(tag.strip() for tag in tags.split(";") if tag.strip())
        return sorted(all_tags)
    except Exception as e:
        logging.error(f"Error extracting tags: {str(e)}")
        return []


def parse_tag_style(tag_style: str) -> dict:
    """Parse a Proxmox tag-style string into its sub-options.

    Example input:  ``case-sensitive=1,ordering=alphabetical,color-map=a:ff0000;b:00ff00:ffffff``
    Example output: ``{'case-sensitive': '1', 'ordering': 'alphabetical',
                       'color-map': 'a:ff0000;b:00ff00:ffffff'}``
    """
    if not tag_style or not isinstance(tag_style, str):
        return {}
    parts = {}
    for chunk in tag_style.split(','):
        if '=' not in chunk:
            continue
        k, v = chunk.split('=', 1)
        k = k.strip()
        if k:
            parts[k] = v.strip()
    return parts


def format_tag_style(parts: dict) -> str:
    """Inverse of parse_tag_style. Stable alphabetical key order; drops empty values."""
    if not parts:
        return ""
    return ','.join(f'{k}={v}' for k, v in sorted(parts.items()) if v != '')


def parse_color_map(color_map: str) -> dict:
    """Parse a color-map string into ``{tag: {'bg': 'rrggbb', 'fg': 'rrggbb'|None}}``.

    Format: ``tag:bg[:fg];tag:bg[:fg];...`` with 6-digit hex (no leading ``#``).
    Invalid entries are silently dropped. Hex is lowercased on output.
    """
    if not color_map or not isinstance(color_map, str):
        return {}
    out = {}
    for entry in color_map.split(';'):
        entry = entry.strip()
        if not entry:
            continue
        bits = entry.split(':')
        if len(bits) < 2:
            continue
        name, bg = bits[0], bits[1]
        fg = bits[2] if len(bits) >= 3 and bits[2] else None
        if not TAG_NAME_RE.match(name) or not HEX6_RE.match(bg):
            continue
        if fg is not None and not HEX6_RE.match(fg):
            fg = None
        out[name] = {'bg': bg.lower(), 'fg': (fg.lower() if fg else None)}
    return out


def format_color_map(mapping: dict) -> str:
    """Inverse of parse_color_map. Drops invalid entries silently; sorts keys for stable output."""
    if not mapping:
        return ""
    parts = []
    for name in sorted(mapping.keys()):
        v = mapping.get(name) or {}
        if not isinstance(v, dict) or not TAG_NAME_RE.match(name):
            continue
        bg = (v.get('bg') or '').lstrip('#').lower()
        fg = (v.get('fg') or '').lstrip('#').lower() or None
        if not HEX6_RE.match(bg):
            continue
        if fg and HEX6_RE.match(fg):
            parts.append(f'{name}:{bg}:{fg}')
        else:
            parts.append(f'{name}:{bg}')
    return ';'.join(parts)
