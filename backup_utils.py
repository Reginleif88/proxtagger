import logging
import json
import os
from datetime import datetime
from io import BytesIO

def create_backup_file(vms):
    """Generate a JSON file with all VM/CT tags for download.
    
    Args:
        vms (list): List of VMs to backup
        
    Returns:
        tuple: (BytesIO buffer, filename)
    """
    # Create a data structure for backup
    backup_data = []
    for vm in vms:
        # Get tags and ensure we don't include empty tags
        tags = []
        if vm.get("tags"):
            tags = [tag.strip() for tag in vm.get("tags", "").split(";") if tag.strip()]
            
        vm_data = {
            "id": vm.get("vmid"),
            "name": vm.get("name"),
            "node": vm.get("node"),
            "type": vm.get("type"),
            "tags": tags
        }
        backup_data.append(vm_data)
    
    # Create the JSON file
    json_data = json.dumps(backup_data, indent=2)
    buffer = BytesIO(json_data.encode('utf-8'))
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"proxmox_tags_backup_{timestamp}.json"
    
    return buffer, filename

def restore_from_backup_data(backup_data, update_vm_tags_func):
    """Restore tags from backup data.
    
    Args:
        backup_data (list): Parsed backup data
        update_vm_tags_func (function): Function to update VM tags
        
    Returns:
        dict: Results of the restore operation
    """
    # Validate the structure
    if not isinstance(backup_data, list):
        return {"success": False, "error": "Invalid backup format"}
    
    # Results tracking
    results = {
        "success": True,
        "updated": 0,
        "failed": 0,
        "failures": []
    }
    
    # Process each VM in the backup
    for vm_data in backup_data:
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
    
    return results
