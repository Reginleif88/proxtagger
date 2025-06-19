"""
Setup validation tests to ensure test environment is configured correctly
"""

import pytest
import sys
import os
from pathlib import Path


class TestSetupValidation:
    """Validate test environment setup"""
    
    @pytest.mark.unit
    def test_python_version(self):
        """Test Python version compatibility"""
        assert sys.version_info >= (3, 7), f"Python 3.7+ required, got {sys.version_info}"
    
    @pytest.mark.unit 
    def test_project_structure(self):
        """Test that required project files exist"""
        project_root = Path(__file__).parent.parent
        
        required_files = [
            "app.py",
            "tag_utils.py", 
            "proxmox_api.py",
            "backup_utils.py",
            "config.py",
            "requirements.txt",
            "pytest.ini"
        ]
        
        for file_name in required_files:
            file_path = project_root / file_name
            assert file_path.exists(), f"Required file missing: {file_name}"
    
    @pytest.mark.unit
    def test_modules_importable(self):
        """Test that all main modules can be imported"""
        try:
            import tag_utils
            import proxmox_api
            import backup_utils
            import config
            from modules.conditional_tags import models, engine, storage
        except ImportError as e:
            pytest.fail(f"Module import failed: {e}")
    
    @pytest.mark.unit
    def test_test_dependencies_available(self):
        """Test that testing dependencies are available"""
        try:
            import pytest
            import unittest.mock
        except ImportError as e:
            pytest.fail(f"Test dependency missing: {e}")
    
    @pytest.mark.unit
    def test_fixtures_accessible(self):
        """Test that test fixtures are accessible"""
        # These fixtures should be available from conftest.py
        pass  # Actual fixture usage will be tested by pytest discovery
    
    @pytest.mark.unit
    def test_temp_file_creation(self, temp_storage_file):
        """Test that temporary files can be created for testing"""
        assert temp_storage_file is not None
        
        # Write to temp file
        with open(temp_storage_file, 'w') as f:
            f.write('{"test": "data"}')
        
        # Read from temp file
        with open(temp_storage_file, 'r') as f:
            content = f.read()
            assert content == '{"test": "data"}'
    
    @pytest.mark.unit
    def test_mock_functionality(self, mock_config):
        """Test that mocking works correctly"""
        assert mock_config is not None
        assert "PROXMOX_HOST" in mock_config
        assert mock_config["PROXMOX_HOST"] == "test.proxmox.local"
    
    @pytest.mark.unit
    def test_sample_data_fixtures(self, sample_vms):
        """Test that sample data fixtures are properly formatted"""
        assert isinstance(sample_vms, list)
        assert len(sample_vms) > 0
        
        for vm in sample_vms:
            assert "vmid" in vm
            assert "name" in vm
            assert "node" in vm
            assert "type" in vm
            assert vm["type"] in ["qemu", "lxc"]
    
    @pytest.mark.integration
    def test_integration_test_capability(self):
        """Test that integration tests can run"""
        # This test verifies that integration test markers work
        # and that the test environment supports integration testing
        assert True  # If this runs, integration tests are working