"""
Extended Proxmox API calls for conditional tagging
"""

import requests
import logging
import time
from functools import wraps
from typing import Dict, Any, List, Optional, Callable
from config import load_config
from proxmox_api import _get_base_url, _get_headers

logger = logging.getLogger(__name__)

# Configuration for API resilience
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 1.0  # seconds
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_TIMEOUT = 10  # seconds

class ProxmoxAPIError(Exception):
    """Custom exception for Proxmox API errors"""
    def __init__(self, message: str, status_code: int = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable

def is_retryable_error(e: Exception) -> bool:
    """Determine if an error is retryable"""
    if isinstance(e, ProxmoxAPIError):
        return e.retryable
    
    if isinstance(e, requests.exceptions.RequestException):
        # Network errors, timeouts, and 5xx errors are retryable
        if isinstance(e, (requests.exceptions.ConnectionError, 
                         requests.exceptions.Timeout,
                         requests.exceptions.ReadTimeout)):
            return True
        
        if hasattr(e, 'response') and e.response is not None:
            # 5xx server errors are retryable, 4xx client errors are not
            return 500 <= e.response.status_code < 600
    
    return False

def retry_on_failure(max_attempts: int = DEFAULT_RETRY_ATTEMPTS, 
                    delay: float = DEFAULT_RETRY_DELAY,
                    backoff_factor: float = DEFAULT_BACKOFF_FACTOR):
    """Decorator to retry API calls with exponential backoff"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if not is_retryable_error(e) or attempt == max_attempts - 1:
                        # Don't retry non-retryable errors or final attempt
                        break
                    
                    logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. Retrying in {current_delay}s...")
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
            
            # If we get here, all attempts failed
            if isinstance(last_exception, requests.exceptions.RequestException):
                status_code = getattr(last_exception.response, 'status_code', None) if hasattr(last_exception, 'response') else None
                raise ProxmoxAPIError(f"API call failed after {max_attempts} attempts: {last_exception}", 
                                    status_code=status_code, retryable=False)
            else:
                raise last_exception
        
        return wrapper
    return decorator

@retry_on_failure()
def get_vm_config_extended(node: str, vmid: int, vm_type: str = "qemu") -> Dict[str, Any]:
    """
    Get extended VM configuration including additional properties
    
    Args:
        node: Proxmox node name
        vmid: VM ID
        vm_type: "qemu" or "lxc"
        
    Returns:
        Extended VM configuration dictionary
    
    Raises:
        ProxmoxAPIError: If API call fails after retries
    """
    url = f"{_get_base_url()}/nodes/{node}/{vm_type}/{vmid}/config"
    headers = _get_headers()
    verify_ssl = load_config().get("VERIFY_SSL", True)
    
    try:
        response = requests.get(url, headers=headers, verify=verify_ssl, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json().get("data", {})
    except requests.exceptions.RequestException as e:
        status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
        retryable = is_retryable_error(e)
        raise ProxmoxAPIError(f"Failed to get VM config for {vmid}: {e}", 
                            status_code=status_code, retryable=retryable)
    except Exception as e:
        logger.error(f"Unexpected error getting VM config for {vmid}: {e}")
        raise ProxmoxAPIError(f"Unexpected error: {e}", retryable=False)

@retry_on_failure()
def get_ha_status(vmid: int) -> Optional[Dict[str, Any]]:
    """
    Get HA (High Availability) status for a VM
    
    Args:
        vmid: VM ID
        
    Returns:
        HA configuration if VM is in HA group, None otherwise
        
    Raises:
        ProxmoxAPIError: If API call fails after retries
    """
    url = f"{_get_base_url()}/cluster/ha/resources"
    headers = _get_headers()
    verify_ssl = load_config().get("VERIFY_SSL", True)
    
    try:
        response = requests.get(url, headers=headers, verify=verify_ssl, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        
        ha_resources = response.json().get("data", [])
        
        # Find HA config for this VM
        for resource in ha_resources:
            # HA resources are named like "vm:100" or "ct:101"
            if resource.get("sid", "").endswith(f":{vmid}"):
                return resource
        
        return None
    except requests.exceptions.RequestException as e:
        status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
        retryable = is_retryable_error(e)
        raise ProxmoxAPIError(f"Failed to get HA status: {e}", 
                            status_code=status_code, retryable=retryable)
    except Exception as e:
        logger.error(f"Unexpected error getting HA status: {e}")
        raise ProxmoxAPIError(f"Unexpected error: {e}", retryable=False)

@retry_on_failure()
def get_replication_status(node: str) -> List[Dict[str, Any]]:
    """
    Get replication status for all VMs on a node
    
    Args:
        node: Proxmox node name
        
    Returns:
        List of replication configurations
        
    Raises:
        ProxmoxAPIError: If API call fails after retries
    """
    url = f"{_get_base_url()}/nodes/{node}/replication"
    headers = _get_headers()
    verify_ssl = load_config().get("VERIFY_SSL", True)
    
    try:
        response = requests.get(url, headers=headers, verify=verify_ssl, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json().get("data", [])
    except requests.exceptions.RequestException as e:
        status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
        retryable = is_retryable_error(e)
        raise ProxmoxAPIError(f"Failed to get replication status: {e}", 
                            status_code=status_code, retryable=retryable)
    except Exception as e:
        logger.error(f"Unexpected error getting replication status: {e}")
        raise ProxmoxAPIError(f"Unexpected error: {e}", retryable=False)

@retry_on_failure()
def get_vm_snapshots(node: str, vmid: int, vm_type: str = "qemu") -> List[Dict[str, Any]]:
    """
    Get list of snapshots for a VM
    
    Args:
        node: Proxmox node name
        vmid: VM ID
        vm_type: "qemu" or "lxc"
        
    Returns:
        List of snapshots
        
    Raises:
        ProxmoxAPIError: If API call fails after retries
    """
    url = f"{_get_base_url()}/nodes/{node}/{vm_type}/{vmid}/snapshot"
    headers = _get_headers()
    verify_ssl = load_config().get("VERIFY_SSL", True)
    
    try:
        response = requests.get(url, headers=headers, verify=verify_ssl, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json().get("data", [])
    except requests.exceptions.RequestException as e:
        status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
        retryable = is_retryable_error(e)
        raise ProxmoxAPIError(f"Failed to get VM snapshots for {vmid}: {e}", 
                            status_code=status_code, retryable=retryable)
    except Exception as e:
        logger.error(f"Unexpected error getting VM snapshots for {vmid}: {e}")
        raise ProxmoxAPIError(f"Unexpected error: {e}", retryable=False)

@retry_on_failure()
def get_vm_backup_status(vmid: int) -> Optional[Dict[str, Any]]:
    """
    Get last backup status for a VM
    
    Args:
        vmid: VM ID
        
    Returns:
        Last backup information if available
        
    Raises:
        ProxmoxAPIError: If API call fails after retries
    """
    url = f"{_get_base_url()}/cluster/backup"
    headers = _get_headers()
    verify_ssl = load_config().get("VERIFY_SSL", True)
    
    try:
        response = requests.get(url, headers=headers, verify=verify_ssl, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        
        backups = response.json().get("data", [])
        
        # Find backups for this VM
        vm_backups = [b for b in backups if b.get("vmid") == vmid]
        
        # Return most recent backup
        if vm_backups:
            return sorted(vm_backups, key=lambda x: x.get("starttime", ""), reverse=True)[0]
        
        return None
    except requests.exceptions.RequestException as e:
        status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
        retryable = is_retryable_error(e)
        raise ProxmoxAPIError(f"Failed to get backup status: {e}", 
                            status_code=status_code, retryable=retryable)
    except Exception as e:
        logger.error(f"Unexpected error getting backup status: {e}")
        raise ProxmoxAPIError(f"Unexpected error: {e}", retryable=False)

def enrich_vm_data(vm: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich VM data with additional information for rule evaluation
    
    Args:
        vm: Basic VM data from cluster/resources
        
    Returns:
        Enriched VM data dictionary with graceful fallbacks on API errors
    """
    enriched = vm.copy()
    api_errors = []
    
    # Get extended configuration
    try:
        config = get_vm_config_extended(vm['node'], vm['vmid'], vm['type'])
        enriched['config'] = config
    except ProxmoxAPIError as e:
        logger.warning(f"Failed to get config for VM {vm['vmid']}: {e}")
        enriched['config'] = {}
        api_errors.append(f"config: {e}")
    
    # Add HA status
    try:
        ha_status = get_ha_status(vm['vmid'])
        enriched['ha'] = {
            'enabled': ha_status is not None,
            'state': ha_status.get('state') if ha_status else None,
            'group': ha_status.get('group') if ha_status else None
        }
    except ProxmoxAPIError as e:
        logger.warning(f"Failed to get HA status for VM {vm['vmid']}: {e}")
        enriched['ha'] = {'enabled': False, 'state': None, 'group': None}
        api_errors.append(f"HA: {e}")
    
    # Add replication info
    try:
        replication_configs = get_replication_status(vm['node'])
        vm_replication = [r for r in replication_configs if r.get('guest') == vm['vmid']]
        enriched['replication'] = {
            'enabled': len(vm_replication) > 0,
            'targets': [r.get('target') for r in vm_replication]
        }
    except ProxmoxAPIError as e:
        logger.warning(f"Failed to get replication status for VM {vm['vmid']}: {e}")
        enriched['replication'] = {'enabled': False, 'targets': []}
        api_errors.append(f"replication: {e}")
    
    # Add snapshot count
    try:
        snapshots = get_vm_snapshots(vm['node'], vm['vmid'], vm['type'])
        enriched['snapshots'] = {
            'count': len(snapshots),
            'names': [s.get('name') for s in snapshots if s.get('name') != 'current']
        }
    except ProxmoxAPIError as e:
        logger.warning(f"Failed to get snapshots for VM {vm['vmid']}: {e}")
        enriched['snapshots'] = {'count': 0, 'names': []}
        api_errors.append(f"snapshots: {e}")
    
    # Add backup status
    try:
        backup_info = get_vm_backup_status(vm['vmid'])
        enriched['backup'] = {
            'has_backup': backup_info is not None,
            'last_backup': backup_info.get('starttime') if backup_info else None
        }
    except ProxmoxAPIError as e:
        logger.warning(f"Failed to get backup status for VM {vm['vmid']}: {e}")
        enriched['backup'] = {'has_backup': False, 'last_backup': None}
        api_errors.append(f"backup: {e}")
    
    # Add API error information for debugging
    if api_errors:
        enriched['_api_errors'] = api_errors
        logger.info(f"VM {vm['vmid']} enrichment completed with {len(api_errors)} API errors")
    
    return enriched

def enrich_vm_data_selective(vm: Dict[str, Any], required_fields: set) -> Dict[str, Any]:
    """
    Selectively enrich VM data with only the required fields for better performance
    
    Args:
        vm: Basic VM data from cluster/resources
        required_fields: Set of field prefixes that are needed (e.g., {'config.', 'ha.'})
        
    Returns:
        Enriched VM data dictionary with only required fields and graceful fallbacks
    """
    enriched = vm.copy()
    api_errors = []
    
    # Only enrich the fields that are actually needed
    if any(field.startswith('config.') for field in required_fields):
        try:
            config = get_vm_config_extended(vm['node'], vm['vmid'], vm['type'])
            enriched['config'] = config
        except ProxmoxAPIError as e:
            logger.warning(f"Failed to get config for VM {vm['vmid']}: {e}")
            enriched['config'] = {}
            api_errors.append(f"config: {e}")
    
    if any(field.startswith('ha.') for field in required_fields):
        try:
            ha_status = get_ha_status(vm['vmid'])
            enriched['ha'] = {
                'enabled': ha_status is not None,
                'state': ha_status.get('state') if ha_status else None,
                'group': ha_status.get('group') if ha_status else None
            }
        except ProxmoxAPIError as e:
            logger.warning(f"Failed to get HA status for VM {vm['vmid']}: {e}")
            enriched['ha'] = {'enabled': False, 'state': None, 'group': None}
            api_errors.append(f"HA: {e}")
    
    if any(field.startswith('replication.') for field in required_fields):
        try:
            replication_configs = get_replication_status(vm['node'])
            vm_replication = [r for r in replication_configs if r.get('guest') == vm['vmid']]
            enriched['replication'] = {
                'enabled': len(vm_replication) > 0,
                'targets': [r.get('target') for r in vm_replication]
            }
        except ProxmoxAPIError as e:
            logger.warning(f"Failed to get replication status for VM {vm['vmid']}: {e}")
            enriched['replication'] = {'enabled': False, 'targets': []}
            api_errors.append(f"replication: {e}")
    
    if any(field.startswith('snapshots.') for field in required_fields):
        try:
            snapshots = get_vm_snapshots(vm['node'], vm['vmid'], vm['type'])
            enriched['snapshots'] = {
                'count': len(snapshots),
                'names': [s.get('name') for s in snapshots if s.get('name') != 'current']
            }
        except ProxmoxAPIError as e:
            logger.warning(f"Failed to get snapshots for VM {vm['vmid']}: {e}")
            enriched['snapshots'] = {'count': 0, 'names': []}
            api_errors.append(f"snapshots: {e}")
    
    if any(field.startswith('backup.') for field in required_fields):
        try:
            backup_info = get_vm_backup_status(vm['vmid'])
            enriched['backup'] = {
                'has_backup': backup_info is not None,
                'last_backup': backup_info.get('starttime') if backup_info else None
            }
        except ProxmoxAPIError as e:
            logger.warning(f"Failed to get backup status for VM {vm['vmid']}: {e}")
            enriched['backup'] = {'has_backup': False, 'last_backup': None}
            api_errors.append(f"backup: {e}")
    
    # Add API error information for debugging
    if api_errors:
        enriched['_api_errors'] = api_errors
        logger.info(f"VM {vm['vmid']} selective enrichment completed with {len(api_errors)} API errors")
    
    return enriched

def get_available_vm_properties() -> Dict[str, Dict[str, Any]]:
    """
    Get list of available VM properties for rule builder
    
    Returns:
        Dictionary of property paths with metadata
    """
    return {
        # Basic properties
        "vmid": {
            "type": "number",
            "description": "VM/Container ID",
            "example": 100
        },
        "name": {
            "type": "string",
            "description": "VM/Container name",
            "example": "webserver-01"
        },
        "node": {
            "type": "string", 
            "description": "Proxmox node",
            "example": "pve1"
        },
        "type": {
            "type": "string",
            "description": "Resource type",
            "values": ["qemu", "lxc"]
        },
        "status": {
            "type": "string",
            "description": "Current status",
            "values": ["running", "stopped", "paused"]
        },
        "tags": {
            "type": "string",
            "description": "Current tags (semicolon-separated)",
            "example": "production;web;linux"
        },
        "template": {
            "type": "number",
            "description": "Whether resource is a template",
            "values": [0, 1]
        },
        
        # Resource properties
        "cpu": {
            "type": "number",
            "description": "Current CPU usage (percentage)",
            "example": 25.5
        },
        "maxcpu": {
            "type": "number",
            "description": "Maximum CPU cores",
            "example": 4
        },
        "mem": {
            "type": "number",
            "description": "Current memory usage (bytes)",
            "example": 1073741824
        },
        "maxmem": {
            "type": "number",
            "description": "Maximum memory (bytes)",
            "example": 4294967296
        },
        "disk": {
            "type": "number",
            "description": "Current disk usage (bytes)",
            "example": 10737418240
        },
        "maxdisk": {
            "type": "number",
            "description": "Maximum disk size (bytes)",
            "example": 32212254720
        },
        
        # Config properties
        "config.ostype": {
            "type": "string",
            "description": "Operating system type",
            "example": "l26"
        },
        "config.cores": {
            "type": "number",
            "description": "Number of CPU cores",
            "example": 2
        },
        "config.memory": {
            "type": "number",
            "description": "Memory size (MB)",
            "example": 2048
        },
        "config.arch": {
            "type": "string",
            "description": "Architecture",
            "values": ["amd64", "i386", "arm64"]
        },
        "config.onboot": {
            "type": "number",
            "description": "Start on boot",
            "values": [0, 1]
        },
        "config.protection": {
            "type": "number", 
            "description": "Protected from deletion",
            "values": [0, 1]
        },
        "config.agent": {
            "type": "number",
            "description": "QEMU agent enabled",
            "values": [0, 1]
        },
        
        # HA properties
        "ha.enabled": {
            "type": "boolean",
            "description": "Whether VM is in HA group",
            "example": True
        },
        "ha.state": {
            "type": "string",
            "description": "HA state",
            "example": "started"
        },
        "ha.group": {
            "type": "string",
            "description": "HA group",
            "example": "ha_group"
        },
        
        # Replication properties
        "replication.enabled": {
            "type": "boolean",
            "description": "Whether replication is enabled",
            "example": True
        },
        "replication.targets": {
            "type": "array",
            "description": "Replication target nodes",
            "example": ["pve2", "pve3"]
        },
        
        # Snapshot properties
        "snapshots.count": {
            "type": "number",
            "description": "Number of snapshots",
            "example": 3
        },
        # Backup properties
        "backup.has_backup": {
            "type": "boolean",
            "description": "Whether VM has been backed up",
            "example": True
        }
    }