"""
Live integration test configuration for ProxTagger

This module provides configuration and utilities for running tests against
a real Proxmox environment. Tests using live configuration are marked with
@pytest.mark.live and can be controlled via environment variables.

Safety Features:
- Tests are disabled by default
- Backup mechanisms for tag changes
- Test VM filtering to avoid production VMs
- Rollback capabilities for failed tests
"""

import os
import pytest
import json
from typing import Dict, List, Optional, Set
from datetime import datetime
from unittest.mock import patch
import config
import proxmox_api
import tag_utils


class LiveTestConfig:
    """Configuration for live Proxmox testing"""
    
    def __init__(self):
        self.enabled = os.getenv('PROXTAGGER_LIVE_TESTS', 'false').lower() == 'true'
        self.backup_tags = os.getenv('PROXTAGGER_BACKUP_TAGS', 'true').lower() == 'true'
        self.test_vm_prefix = os.getenv('PROXTAGGER_TEST_VM_PREFIX', 'test-')
        self.max_test_vms = int(os.getenv('PROXTAGGER_MAX_TEST_VMS', '10'))
        self.dry_run_only = os.getenv('PROXTAGGER_DRY_RUN_ONLY', 'false').lower() == 'true'
        
        # Load actual Proxmox configuration
        try:
            self.proxmox_config = config.load_config()
        except Exception as e:
            self.proxmox_config = None
            self.enabled = False
            print(f"Warning: Could not load Proxmox config: {e}")
    
    def is_enabled(self) -> bool:
        """Check if live testing is enabled"""
        return self.enabled and self.proxmox_config is not None
    
    def is_test_vm(self, vm: Dict) -> bool:
        """Check if a VM is suitable for testing"""
        if not vm.get('name'):
            return False
        
        name = vm['name'].lower()
        
        # Must start with test prefix
        if not name.startswith(self.test_vm_prefix):
            return False
        
        # Additional safety checks
        safety_indicators = ['test', 'dev', 'staging', 'sandbox']
        if not any(indicator in name for indicator in safety_indicators):
            return False
        
        # Avoid production indicators
        production_indicators = ['prod', 'production', 'live', 'master', 'main']
        if any(indicator in name for indicator in production_indicators):
            return False
        
        return True
    
    def get_test_vms(self) -> List[Dict]:
        """Get VMs suitable for testing"""
        if not self.is_enabled():
            return []
        
        try:
            all_vms = proxmox_api.get_all_vms()
            test_vms = [vm for vm in all_vms if self.is_test_vm(vm)]
            
            # Limit number of test VMs
            if len(test_vms) > self.max_test_vms:
                test_vms = test_vms[:self.max_test_vms]
            
            return test_vms
        except Exception as e:
            print(f"Warning: Could not fetch test VMs: {e}")
            return []


class TagBackupManager:
    """Manages tag backups for safe testing"""
    
    def __init__(self):
        self.backups: Dict[int, Dict] = {}
        self.backup_timestamp = datetime.now().isoformat()
    
    def backup_vm_tags(self, vm: Dict) -> None:
        """Backup current tags for a VM"""
        vmid = vm['vmid']
        self.backups[vmid] = {
            'vmid': vmid,
            'name': vm.get('name', ''),
            'node': vm.get('node', ''),
            'type': vm.get('type', ''),
            'original_tags': vm.get('tags', ''),
            'timestamp': self.backup_timestamp
        }
    
    def backup_multiple_vms(self, vms: List[Dict]) -> None:
        """Backup tags for multiple VMs"""
        for vm in vms:
            self.backup_vm_tags(vm)
    
    def restore_vm_tags(self, vmid: int) -> bool:
        """Restore original tags for a VM"""
        if vmid not in self.backups:
            return False
        
        backup = self.backups[vmid]
        try:
            result = proxmox_api.update_vm_tags(
                backup['node'],
                vmid,
                backup['original_tags'],
                backup['type']
            )
            return 'data' in result
        except Exception as e:
            print(f"Failed to restore tags for VM {vmid}: {e}")
            return False
    
    def restore_all(self) -> Dict[int, bool]:
        """Restore all backed up VMs"""
        results = {}
        for vmid in self.backups:
            results[vmid] = self.restore_vm_tags(vmid)
        return results
    
    def get_backup_info(self) -> Dict:
        """Get backup information"""
        return {
            'timestamp': self.backup_timestamp,
            'vm_count': len(self.backups),
            'vmids': list(self.backups.keys())
        }


# Global instances
live_config = LiveTestConfig()
tag_backup_manager = TagBackupManager()


# Pytest fixtures
@pytest.fixture
def live_test_config():
    """Fixture providing live test configuration"""
    return live_config


@pytest.fixture
def live_proxmox_config():
    """Fixture providing real Proxmox configuration"""
    if not live_config.is_enabled():
        pytest.skip("Live testing is disabled")
    return live_config.proxmox_config


@pytest.fixture
def test_vms():
    """Fixture providing real test VMs from Proxmox"""
    if not live_config.is_enabled():
        pytest.skip("Live testing is disabled")
    
    vms = live_config.get_test_vms()
    if not vms:
        pytest.skip("No test VMs found")
    
    return vms


@pytest.fixture
def safe_test_vm():
    """Fixture providing a single safe test VM"""
    if not live_config.is_enabled():
        pytest.skip("Live testing is disabled")
    
    vms = live_config.get_test_vms()
    if not vms:
        pytest.skip("No test VMs found")
    
    # Return the first test VM
    return vms[0]


@pytest.fixture
def tag_backup():
    """Fixture providing tag backup manager"""
    return TagBackupManager()


@pytest.fixture(autouse=True)
def skip_live_tests():
    """Auto-fixture to skip live tests when disabled"""
    def skip_if_live_disabled(request):
        if hasattr(request.node, 'get_closest_marker'):
            live_marker = request.node.get_closest_marker('live')
            if live_marker and not live_config.is_enabled():
                pytest.skip("Live testing is disabled. Set PROXTAGGER_LIVE_TESTS=true to enable.")
    
    return skip_if_live_disabled


# Utility functions
def requires_live_testing(func):
    """Decorator to mark tests that require live Proxmox connection"""
    return pytest.mark.live(func)


def safe_tag_update(node: str, vmid: int, tags: str, vm_type: str, backup_manager: TagBackupManager) -> Dict:
    """Safely update VM tags with backup"""
    if live_config.dry_run_only:
        return {"data": "dry_run", "dry_run": True}
    
    # Backup is handled by the test setup
    return proxmox_api.update_vm_tags(node, vmid, tags, vm_type)


def validate_proxmox_connection() -> bool:
    """Validate connection to Proxmox"""
    if not live_config.is_enabled():
        return False
    
    try:
        vms = proxmox_api.get_all_vms()
        return isinstance(vms, list)
    except Exception:
        return False


# Test markers
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "live: Tests that require live Proxmox connection"
    )


# Environment setup validation
def validate_live_test_environment():
    """Validate that live test environment is properly configured"""
    issues = []
    
    if not live_config.is_enabled():
        issues.append("Live testing is disabled")
    
    if not live_config.proxmox_config:
        issues.append("Proxmox configuration could not be loaded")
    
    if not validate_proxmox_connection():
        issues.append("Cannot connect to Proxmox")
    
    test_vms = live_config.get_test_vms()
    if not test_vms:
        issues.append("No test VMs found (VMs must start with 'test-' prefix)")
    
    return issues


# Test data generators
def generate_test_tags() -> List[str]:
    """Generate safe test tags"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return [
        f"test-{timestamp}",
        "automated-test",
        "unit-test",
        "safe-to-delete"
    ]


def create_test_rule_data() -> Dict:
    """Create safe test rule data"""
    return {
        "name": f"Test Rule {datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "description": "Automated test rule - safe to delete",
        "conditions": {
            "operator": "AND",
            "conditions": [
                {
                    "field": "name",
                    "operator": "contains",
                    "value": "test-"
                }
            ]
        },
        "actions": {
            "add_tags": generate_test_tags()[:2],
            "remove_tags": [],
            "else_add_tags": [],
            "else_remove_tags": []
        }
    }