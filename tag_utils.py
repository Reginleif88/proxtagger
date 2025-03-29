import logging

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
