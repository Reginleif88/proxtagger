"""Helpers for reading cluster-wide tag styling from Proxmox."""

import logging

from proxmox_api import get_cluster_options
from tag_utils import parse_tag_style, parse_color_map


def safe_get_color_map():
    """Return ``(color_map_dict, tag_style_extras_dict)`` or ``({}, {})`` on failure.

    Failure here is expected for tokens lacking ``Sys.Audit`` on ``/`` — the
    caller should treat an empty result as "use deterministic colors only".
    """
    try:
        opts = get_cluster_options()
    except Exception as e:
        logging.info("Could not fetch cluster tag-style (likely missing Sys.Audit): %s", e)
        return {}, {}

    tag_style = opts.get('tag-style', '') or ''
    parts = parse_tag_style(tag_style)
    color_map_str = parts.pop('color-map', '')
    return parse_color_map(color_map_str), parts
