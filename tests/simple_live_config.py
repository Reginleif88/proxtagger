"""
Simplified live integration test configuration for ProxTagger

This module provides basic configuration for running tests against
a real Proxmox environment without extensive safety mechanisms.
"""

import os
import pytest
from typing import Dict, List, Optional
import config
import proxmox_api


class SimpleLiveConfig:
    """Simple configuration for live Proxmox testing"""
    
    def __init__(self):
        self.enabled = os.getenv('PROXTAGGER_LIVE_TESTS', 'false').lower() == 'true'
        
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
    
    def get_all_vms(self) -> List[Dict]:
        """Get all VMs from Proxmox"""
        if not self.is_enabled():
            return []
        
        try:
            return proxmox_api.get_all_vms()
        except Exception as e:
            print(f"Warning: Could not fetch VMs: {e}")
            return []


# Global instance
simple_live_config = SimpleLiveConfig()


# Simple pytest fixtures
@pytest.fixture
def simple_live_test_config():
    """Fixture providing simple live test configuration"""
    return simple_live_config


@pytest.fixture
def simple_live_proxmox_config():
    """Fixture providing real Proxmox configuration"""
    if not simple_live_config.is_enabled():
        pytest.skip("Live testing is disabled")
    return simple_live_config.proxmox_config


@pytest.fixture
def all_vms():
    """Fixture providing all VMs from Proxmox"""
    if not simple_live_config.is_enabled():
        pytest.skip("Live testing is disabled")
    
    vms = simple_live_config.get_all_vms()
    if not vms:
        pytest.skip("No VMs found")
    
    return vms


@pytest.fixture
def first_vm():
    """Fixture providing first VM for simple testing"""
    if not simple_live_config.is_enabled():
        pytest.skip("Live testing is disabled")
    
    vms = simple_live_config.get_all_vms()
    if not vms:
        pytest.skip("No VMs found")
    
    return vms[0]


@pytest.fixture(autouse=True)
def skip_live_tests_if_disabled():
    """Auto-fixture to skip live tests when disabled"""
    def skip_if_disabled(request):
        if hasattr(request.node, 'get_closest_marker'):
            live_marker = request.node.get_closest_marker('live')
            if live_marker and not simple_live_config.is_enabled():
                pytest.skip("Live testing is disabled. Set PROXTAGGER_LIVE_TESTS=true to enable.")
    
    return skip_if_disabled


def validate_connection() -> bool:
    """Simple validation of Proxmox connection"""
    if not simple_live_config.is_enabled():
        return False
    
    try:
        vms = proxmox_api.get_all_vms()
        return isinstance(vms, list)
    except Exception:
        return False