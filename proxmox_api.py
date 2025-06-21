import requests
from config import load_config

# Constants
API_VERSION = "api2/json"
VALID_VM_TYPES = {"qemu", "lxc"}

def _get_base_url() -> str:
    """Construct the base URL for the Proxmox API."""
    cfg = load_config()
    return f"https://{cfg['PROXMOX_HOST']}:{cfg['PROXMOX_PORT']}/{API_VERSION}"

def _get_headers() -> dict:
    """Construct the headers for the Proxmox API requests."""
    cfg = load_config()
    return {
        "Authorization": f"PVEAPIToken={cfg['PROXMOX_USER']}!{cfg['PROXMOX_TOKEN_NAME']}={cfg['PROXMOX_TOKEN_VALUE']}"
    }

def get_all_vms() -> list:
    """Fetch all VMs and containers from the Proxmox API."""
    url = f"{_get_base_url()}/cluster/resources"
    headers = _get_headers()
    verify_ssl = load_config().get("VERIFY_SSL", True)

    response = requests.get(url, headers=headers, verify=verify_ssl, timeout=5)
    response.raise_for_status()

    all_resources = response.json().get("data", [])
    vms = [r for r in all_resources if r["type"] in VALID_VM_TYPES]
    return vms

def get_vm_config(node: str, vmid: int, vm_type: str = "qemu") -> dict:
    """Fetch the configuration of a specific VM."""
    if vm_type not in VALID_VM_TYPES:
        raise ValueError("Invalid VM type")
    
    url = f"{_get_base_url()}/nodes/{node}/{vm_type}/{vmid}/config"
    headers = _get_headers()
    verify_ssl = load_config().get("VERIFY_SSL", True)

    response = requests.get(url, headers=headers, verify=verify_ssl)
    response.raise_for_status()
    return response.json().get("data", {})

def update_vm_tags(node: str, vmid: int, tags: str, vm_type: str = "qemu") -> dict:
    """Update the tags for a specific VM."""
    if vm_type not in VALID_VM_TYPES:
        raise ValueError("Invalid VM type")

    url = f"{_get_base_url()}/nodes/{node}/{vm_type}/{vmid}/config"
    headers = _get_headers()
    verify_ssl = load_config().get("VERIFY_SSL", True)
    # If tags is empty or whitespace, ensure we send an empty string, not whitespace
    cleaned_tags = tags.strip() if tags else ""
    data = {"tags": cleaned_tags}

    response = requests.put(url, headers=headers, json=data, verify=verify_ssl, timeout=5)
    response.raise_for_status()
    return response.json()
