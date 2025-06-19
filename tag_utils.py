import logging

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
