import logging
import json
import os
from datetime import datetime, timezone
from io import BytesIO

BACKUP_FORMAT_VERSION = 2


def create_backup_file(vms, color_map=None):
    """Generate a JSON file with all VM/CT tags and cluster tag colors.

    Emits a v2 wrapper:
        {
            "version": 2,
            "exported_at": "<ISO-8601 UTC>",
            "vms": [...same shape as v1 list entries...],
            "tag_colors": {tag: {"bg": "rrggbb", "fg": "rrggbb"|null}, ...}
        }

    The ``vms`` list-of-dicts shape inside ``vms`` is unchanged from v1, so
    diffing two backups touches only the wrapper and the optional
    ``tag_colors`` block.

    Args:
        vms (list): List of VMs to backup
        color_map (dict | None): {tag: {"bg", "fg"}} from cluster tag-style.
            Empty dict (``{}``) is preserved as-is — meaning "no overrides".

    Returns:
        tuple: (BytesIO buffer, filename)
    """
    vm_entries = []
    for vm in vms:
        tags = []
        if vm.get("tags"):
            tags = [tag.strip() for tag in vm.get("tags", "").split(";") if tag.strip()]
        vm_entries.append({
            "id": vm.get("vmid"),
            "name": vm.get("name"),
            "node": vm.get("node"),
            "type": vm.get("type"),
            "tags": tags,
        })

    backup_data = {
        "version": BACKUP_FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "vms": vm_entries,
        "tag_colors": color_map or {},
    }

    json_data = json.dumps(backup_data, indent=2)
    buffer = BytesIO(json_data.encode('utf-8'))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"proxmox_tags_backup_{timestamp}.json"

    return buffer, filename

def restore_from_backup_data(backup_data, update_vm_tags_func, restore_tag_colors_func=None):
    """Restore tags (and optionally tag colors) from backup data.

    Accepts both formats:
      - v1: a bare list of VM dicts (legacy backups).
      - v2: a dict with ``version``, ``vms``, ``tag_colors``.

    Args:
        backup_data: Parsed JSON. Either a list (v1) or a dict (v2).
        update_vm_tags_func: callable(node, vmid, tags_str, vm_type) for tag restore.
        restore_tag_colors_func: optional callable(color_map_dict) -> None for
            cluster color restore. When omitted, tag colors in the backup are
            ignored (tags still restore). The callable should raise on
            permission errors with a ``permission_denied`` semantic that the
            caller catches; here we just record the error string.

    Returns:
        dict: Results with at minimum:
            ``success``, ``updated``, ``failed``, ``failures``,
            ``format_version`` (1 or 2),
            ``colors_restored`` (int | None — None when backup carried no
                colors or no callback was provided),
            ``colors_error``    (str | None — set on color-restore failure).
    """
    # Detect format and normalize.
    if isinstance(backup_data, list):
        format_version = 1
        vm_list = backup_data
        tag_colors = {}
    elif isinstance(backup_data, dict):
        format_version = int(backup_data.get("version") or 2)
        vm_list = backup_data.get("vms")
        tag_colors = backup_data.get("tag_colors") or {}
        if not isinstance(vm_list, list):
            return {"success": False, "error": "Invalid backup format: 'vms' is not a list"}
        if not isinstance(tag_colors, dict):
            tag_colors = {}
    else:
        return {"success": False, "error": "Invalid backup format"}

    # Results tracking
    results = {
        "success": True,
        "format_version": format_version,
        "updated": 0,
        "failed": 0,
        "failures": [],
        "colors_restored": None,
        "colors_error": None,
    }

    # Process each VM in the backup
    for vm_data in vm_list:
        vmid = vm_data.get("id")
        node = vm_data.get("node")
        vm_type = vm_data.get("type")
        tags = vm_data.get("tags", [])
        
        if not vmid or not node or not vm_type or not isinstance(tags, list):
            continue
        
        # Join tags into semicolon-separated string
        # Only join tags that have content (avoid whitespace tags)
        filtered_tags = [tag for tag in tags if tag.strip()]
        tags_str = ";".join(filtered_tags)
        
        try:
            # Update the VM tags
            update_vm_tags_func(node, vmid, tags_str, vm_type)
            results["updated"] += 1
        except Exception as e:
            error_str = str(e)
            
            # Check if this is a "Configuration file does not exist" error (VM/container no longer exists)
            if "Configuration file" in error_str and "does not exist" in error_str:
                # Log with lower severity since this is expected when VMs are deleted
                logging.info(f"Skipping VM {vmid} as it no longer exists: {error_str}")
                
                # Don't count this as a failure since it's an expected scenario
                # Just continue processing the next VM
                continue
            
            # For other types of errors, track as failure
            results["failed"] += 1
            results["failures"].append({
                "vmid": vmid,
                "name": vm_data.get("name", f"VM {vmid}"),
                "error": error_str
            })
            logging.error(f"Error restoring tags for VM {vmid}: {e}")
    
    # If any operations failed, set success to false
    if results["failed"] > 0:
        results["success"] = False

    # Restore tag colors when the backup carries them and a callback was given.
    # Color-restore errors are non-fatal: tag restore stays successful, and the
    # caller surfaces ``colors_error`` to the user as a separate warning.
    if restore_tag_colors_func is not None and tag_colors:
        try:
            restore_tag_colors_func(tag_colors)
            results["colors_restored"] = len(tag_colors)
        except PermissionError:
            results["colors_restored"] = 0
            results["colors_error"] = "permission_denied"
        except Exception as e:
            results["colors_restored"] = 0
            results["colors_error"] = str(e)
            logging.error("Error restoring tag colors: %s", e)

    return results
