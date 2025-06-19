"""
Pytest configuration and shared fixtures
"""

import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch
from datetime import datetime

# Import live testing configuration and fixtures
try:
    from .live_config import (
        live_test_config, live_proxmox_config, test_vms, 
        safe_test_vm, tag_backup, skip_live_tests
    )
except ImportError:
    # Fallback if live_config is not available
    pass

# Import simple live testing configuration and fixtures
try:
    from .simple_live_config import (
        simple_live_test_config, simple_live_proxmox_config,
        all_vms, first_vm, skip_live_tests_if_disabled
    )
except ImportError:
    # Fallback if simple_live_config is not available
    pass

# Import conditional tags fixtures
try:
    from .fixtures.conditional_tags import (
        sample_rule_condition, sample_rule_condition_group, sample_rule_action,
        sample_rule_schedule, sample_conditional_rule, simple_rule, complex_rule,
        complex_rule_conditions, rule_execution_data, invalid_rule_data,
        vm_data_for_evaluation
    )
except ImportError:
    # Fallback if conditional_tags fixtures are not available
    pass


@pytest.fixture
def mock_config():
    """Mock configuration for testing"""
    return {
        "PROXMOX_HOST": "test.proxmox.local",
        "PROXMOX_PORT": "8006",
        "PROXMOX_USER": "test@pve",
        "PROXMOX_TOKEN_NAME": "test-token",
        "PROXMOX_TOKEN_VALUE": "test-token-value",
        "VERIFY_SSL": False
    }


@pytest.fixture
def sample_vms():
    """Sample VM data for testing"""
    return [
        {
            "vmid": 100,
            "name": "test-vm-1",
            "node": "node1",
            "type": "qemu",
            "status": "running",
            "tags": "production;web;frontend",
            "cpu": 2,
            "maxmem": 2147483648,
            "uptime": 86400
        },
        {
            "vmid": 101,
            "name": "test-vm-2", 
            "node": "node1",
            "type": "lxc",
            "status": "stopped",
            "tags": "development;database",
            "cpu": 1,
            "maxmem": 1073741824,
            "uptime": 0
        },
        {
            "vmid": 102,
            "name": "test-vm-3",
            "node": "node2", 
            "type": "qemu",
            "status": "running",
            "tags": "",  # No tags
            "cpu": 4,
            "maxmem": 4294967296,
            "uptime": 172800
        },
        {
            "vmid": 103,
            "name": "test-vm-4",
            "node": "node2",
            "type": "lxc", 
            "status": "running",
            "tags": "production;api;backend;monitoring",
            "cpu": 2,
            "maxmem": 2147483648,
            "uptime": 259200
        }
    ]


@pytest.fixture
def sample_vm_config():
    """Sample VM configuration for testing"""
    return {
        "cores": 2,
        "memory": 2048,
        "name": "test-vm-1",
        "ostype": "l26",
        "tags": "production;web;frontend"
    }


@pytest.fixture
def temp_storage_file():
    """Create a temporary file for storage testing"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    if os.path.exists(temp_file):
        os.unlink(temp_file)


@pytest.fixture
def mock_proxmox_response():
    """Mock successful Proxmox API response"""
    return {
        "data": [
            {
                "vmid": 100,
                "name": "test-vm-1",
                "node": "node1",
                "type": "qemu",
                "status": "running",
                "tags": "production;web"
            }
        ]
    }


@pytest.fixture
def mock_requests_get():
    """Mock requests.get for API testing"""
    with patch('requests.get') as mock_get:
        yield mock_get


@pytest.fixture
def mock_requests_put():
    """Mock requests.put for API testing"""
    with patch('requests.put') as mock_put:
        yield mock_put


@pytest.fixture
def mock_load_config(mock_config):
    """Mock config loading"""
    with patch('config.load_config', return_value=mock_config):
        yield mock_config


@pytest.fixture
def freeze_time():
    """Freeze time for consistent testing"""
    frozen_time = datetime(2024, 1, 15, 12, 0, 0)
    with patch('datetime.datetime') as mock_datetime:
        mock_datetime.utcnow.return_value = frozen_time
        mock_datetime.now.return_value = frozen_time
        yield frozen_time


@pytest.fixture
def mock_logger():
    """Mock logger to capture log messages"""
    with patch('logging.getLogger') as mock_get_logger:
        mock_logger_instance = Mock()
        mock_get_logger.return_value = mock_logger_instance
        yield mock_logger_instance


def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "live: Tests that require live Proxmox connection"
    )