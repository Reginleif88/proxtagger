"""
Unit tests for proxmox_api module
"""

import pytest
import requests
from unittest.mock import Mock, patch
from proxmox_api import (
    get_all_vms, get_vm_config, update_vm_tags,
    _get_base_url, _get_headers, VALID_VM_TYPES
)

# Import live testing configuration
try:
    from tests.live_config import live_config
except ImportError:
    live_config = None


class TestHelperFunctions:
    """Test helper functions for API operations"""
    
    @pytest.mark.unit
    @patch('proxmox_api.load_config')
    def test_get_base_url(self, mock_load_config):
        """Test base URL construction"""
        mock_load_config.return_value = {
            "PROXMOX_HOST": "test.proxmox.local",
            "PROXMOX_PORT": "8006"
        }
        result = _get_base_url()
        expected = "https://test.proxmox.local:8006/api2/json"
        assert result == expected
    
    @pytest.mark.unit
    @patch('proxmox_api.load_config')
    def test_get_headers(self, mock_load_config):
        """Test headers construction"""
        mock_load_config.return_value = {
            "PROXMOX_USER": "test@pve",
            "PROXMOX_TOKEN_NAME": "test-token",
            "PROXMOX_TOKEN_VALUE": "test-token-value"
        }
        result = _get_headers()
        expected = {
            "Authorization": "PVEAPIToken=test@pve!test-token=test-token-value"
        }
        assert result == expected


class TestGetAllVms:
    """Test the get_all_vms function"""
    
    @pytest.mark.unit
    @patch('proxmox_api.load_config')
    def test_get_all_vms_success(self, mock_load_config_func, mock_requests_get):
        """Test successful VM retrieval"""
        # Setup mock config with all required keys
        mock_load_config_func.return_value = {
            "PROXMOX_HOST": "test.proxmox.local",
            "PROXMOX_PORT": "8006",
            "PROXMOX_USER": "test@pve",
            "PROXMOX_TOKEN_NAME": "test-token",
            "PROXMOX_TOKEN_VALUE": "test-token-value",
            "VERIFY_SSL": False
        }
        
        # Mock successful API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {"vmid": 100, "type": "qemu", "name": "test-vm-1"},
                {"vmid": 101, "type": "lxc", "name": "test-ct-1"},
                {"vmid": 102, "type": "storage", "name": "storage-1"}  # Should be filtered out
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response
        
        result = get_all_vms()
        
        # Should only return qemu and lxc VMs
        assert len(result) == 2
        assert result[0]["type"] == "qemu"
        assert result[1]["type"] == "lxc"
        
        # Verify API call was made correctly
        mock_requests_get.assert_called_once()
        args, kwargs = mock_requests_get.call_args
        assert "cluster/resources" in args[0]
        assert kwargs["verify"] is False  # Based on mock config
        assert kwargs["timeout"] == 5
    
    @pytest.mark.unit
    def test_get_all_vms_empty_response(self, mock_load_config, mock_requests_get):
        """Test handling of empty API response"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response
        
        result = get_all_vms()
        assert result == []
    
    @pytest.mark.unit
    def test_get_all_vms_no_data_key(self, mock_load_config, mock_requests_get):
        """Test handling of response without data key"""
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response
        
        result = get_all_vms()
        assert result == []
    
    @pytest.mark.unit
    def test_get_all_vms_http_error(self, mock_load_config, mock_requests_get):
        """Test handling of HTTP errors"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_requests_get.return_value = mock_response
        
        with pytest.raises(requests.HTTPError):
            get_all_vms()
    
    @pytest.mark.unit
    def test_get_all_vms_connection_error(self, mock_load_config, mock_requests_get):
        """Test handling of connection errors"""
        mock_requests_get.side_effect = requests.ConnectionError("Connection failed")
        
        with pytest.raises(requests.ConnectionError):
            get_all_vms()
    
    @pytest.mark.unit
    def test_get_all_vms_ssl_verification(self, mock_config, mock_requests_get):
        """Test SSL verification configuration"""
        # Test with SSL verification enabled
        mock_config["VERIFY_SSL"] = True
        
        with patch('config.load_config', return_value=mock_config):
            mock_response = Mock()
            mock_response.json.return_value = {"data": []}
            mock_response.raise_for_status.return_value = None
            mock_requests_get.return_value = mock_response
            
            get_all_vms()
            
            # Verify SSL verification was enabled
            args, kwargs = mock_requests_get.call_args
            assert kwargs["verify"] is True


class TestGetVmConfig:
    """Test the get_vm_config function"""
    
    @pytest.mark.unit
    def test_get_vm_config_success(self, mock_load_config, mock_requests_get, sample_vm_config):
        """Test successful VM config retrieval"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": sample_vm_config}
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response
        
        result = get_vm_config("node1", 100)
        
        assert result == sample_vm_config
        
        # Verify API call was made correctly
        mock_requests_get.assert_called_once()
        args, kwargs = mock_requests_get.call_args
        assert "nodes/node1/qemu/100/config" in args[0]
    
    @pytest.mark.unit
    def test_get_vm_config_empty_response(self, mock_load_config, mock_requests_get):
        """Test handling of empty config response"""
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response
        
        result = get_vm_config("node1", 100)
        assert result == {}
    
    @pytest.mark.unit
    def test_get_vm_config_http_error(self, mock_load_config, mock_requests_get):
        """Test handling of HTTP errors"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        mock_requests_get.return_value = mock_response
        
        with pytest.raises(requests.HTTPError):
            get_vm_config("node1", 100)


class TestUpdateVmTags:
    """Test the update_vm_tags function"""
    
    @pytest.mark.unit
    def test_update_vm_tags_success_qemu(self, mock_load_config, mock_requests_put):
        """Test successful tag update for QEMU VM"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": "success"}
        mock_response.raise_for_status.return_value = None
        mock_requests_put.return_value = mock_response
        
        result = update_vm_tags("node1", 100, "web;production", "qemu")
        
        assert result == {"data": "success"}
        
        # Verify API call was made correctly
        mock_requests_put.assert_called_once()
        args, kwargs = mock_requests_put.call_args
        assert "nodes/node1/qemu/100/config" in args[0]
        assert kwargs["json"] == {"tags": "web;production"}
        assert kwargs["timeout"] == 5
    
    @pytest.mark.unit
    def test_update_vm_tags_success_lxc(self, mock_load_config, mock_requests_put):
        """Test successful tag update for LXC container""" 
        mock_response = Mock()
        mock_response.json.return_value = {"data": "success"}
        mock_response.raise_for_status.return_value = None
        mock_requests_put.return_value = mock_response
        
        result = update_vm_tags("node1", 101, "database;development", "lxc")
        
        # Verify API call was made for LXC
        args, kwargs = mock_requests_put.call_args
        assert "nodes/node1/lxc/101/config" in args[0]
        assert kwargs["json"] == {"tags": "database;development"}
    
    @pytest.mark.unit
    def test_update_vm_tags_empty_tags(self, mock_load_config, mock_requests_put):
        """Test updating with empty tags"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": "success"}
        mock_response.raise_for_status.return_value = None
        mock_requests_put.return_value = mock_response
        
        update_vm_tags("node1", 100, "", "qemu")
        
        # Verify empty tags are sent as empty string
        args, kwargs = mock_requests_put.call_args
        assert kwargs["json"] == {"tags": ""}
    
    @pytest.mark.unit
    def test_update_vm_tags_whitespace_only(self, mock_load_config, mock_requests_put):
        """Test updating with whitespace-only tags"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": "success"}
        mock_response.raise_for_status.return_value = None
        mock_requests_put.return_value = mock_response
        
        update_vm_tags("node1", 100, "   ", "qemu")
        
        # Verify whitespace is cleaned to empty string
        args, kwargs = mock_requests_put.call_args
        assert kwargs["json"] == {"tags": ""}
    
    @pytest.mark.unit
    def test_update_vm_tags_none_tags(self, mock_load_config, mock_requests_put):
        """Test updating with None tags"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": "success"}
        mock_response.raise_for_status.return_value = None
        mock_requests_put.return_value = mock_response
        
        update_vm_tags("node1", 100, None, "qemu")
        
        # Verify None is converted to empty string
        args, kwargs = mock_requests_put.call_args
        assert kwargs["json"] == {"tags": ""}
    
    @pytest.mark.unit
    def test_update_vm_tags_invalid_vm_type(self, mock_load_config):
        """Test error handling for invalid VM type"""
        with pytest.raises(ValueError, match="Invalid VM type"):
            update_vm_tags("node1", 100, "web", "invalid")
    
    @pytest.mark.unit
    def test_update_vm_tags_http_error(self, mock_load_config, mock_requests_put):
        """Test handling of HTTP errors during update"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_requests_put.return_value = mock_response
        
        with pytest.raises(requests.HTTPError):
            update_vm_tags("node1", 100, "web", "qemu")
    
    @pytest.mark.unit
    def test_update_vm_tags_connection_error(self, mock_load_config, mock_requests_put):
        """Test handling of connection errors during update"""
        mock_requests_put.side_effect = requests.ConnectionError("Connection failed")
        
        with pytest.raises(requests.ConnectionError):
            update_vm_tags("node1", 100, "web", "qemu")


class TestValidVmTypes:
    """Test VM type validation"""
    
    @pytest.mark.unit
    def test_valid_vm_types_constant(self):
        """Test that VALID_VM_TYPES contains expected values"""
        assert VALID_VM_TYPES == {"qemu", "lxc"}
        assert "qemu" in VALID_VM_TYPES
        assert "lxc" in VALID_VM_TYPES
        assert "storage" not in VALID_VM_TYPES
        assert "node" not in VALID_VM_TYPES


class TestApiIntegration:
    """Integration tests for API functions working together"""
    
    @pytest.mark.unit
    def test_vm_filtering_consistency(self, mock_load_config, mock_requests_get):
        """Test that get_all_vms filters consistently with update_vm_tags validation"""
        # Mock API response with mixed VM types
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {"vmid": 100, "type": "qemu", "name": "test-vm"},
                {"vmid": 101, "type": "lxc", "name": "test-ct"},
                {"vmid": 102, "type": "storage", "name": "storage"},
                {"vmid": 103, "type": "node", "name": "node"}
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response
        
        vms = get_all_vms()
        
        # All returned VMs should have types that are valid for update_vm_tags
        for vm in vms:
            assert vm["type"] in VALID_VM_TYPES
            # This should not raise an error
            assert vm["type"] == "qemu" or vm["type"] == "lxc"
    
    @pytest.mark.unit
    def test_api_error_consistency(self, mock_load_config):
        """Test that all API functions handle errors consistently"""
        # Test that all functions propagate HTTP errors
        with patch('requests.get') as mock_get, patch('requests.put') as mock_put:
            # Set up error responses
            error_response = Mock()
            error_response.raise_for_status.side_effect = requests.HTTPError("500 Error")
            mock_get.return_value = error_response
            mock_put.return_value = error_response
            
            # All functions should raise HTTPError
            with pytest.raises(requests.HTTPError):
                get_all_vms()
            
            with pytest.raises(requests.HTTPError):
                get_vm_config("node1", 100)
            
            with pytest.raises(requests.HTTPError):
                update_vm_tags("node1", 100, "web", "qemu")


# Live testing classes
class TestProxmoxApiLive:
    """Live tests against real Proxmox instance"""
    
    @pytest.mark.live
    def test_proxmox_connection(self, live_proxmox_config):
        """Test connection to live Proxmox instance"""
        # This test validates basic connectivity
        try:
            vms = get_all_vms()
            assert isinstance(vms, list)
            # Connection successful if we get a list (even if empty)
        except Exception as e:
            pytest.fail(f"Could not connect to Proxmox: {e}")
    
    @pytest.mark.live
    def test_get_all_vms_live(self, live_proxmox_config):
        """Test get_all_vms against live Proxmox"""
        vms = get_all_vms()
        
        # Basic structure validation
        assert isinstance(vms, list)
        
        if vms:  # Only test if VMs exist
            vm = vms[0]
            
            # Required fields should be present
            required_fields = ["vmid", "name", "node", "type"]
            for field in required_fields:
                assert field in vm, f"VM missing required field: {field}"
            
            # VM type should be valid
            assert vm["type"] in VALID_VM_TYPES
            
            # VMID should be numeric
            assert isinstance(vm["vmid"], int)
            assert vm["vmid"] > 0
    
    @pytest.mark.live 
    def test_get_vm_config_live(self, live_proxmox_config, test_vms):
        """Test get_vm_config against live Proxmox"""
        if not test_vms:
            pytest.skip("No test VMs available")
        
        vm = test_vms[0]
        config = get_vm_config(vm["node"], vm["vmid"])
        
        # Config should be a dictionary
        assert isinstance(config, dict)
        
        # Should contain some expected fields
        expected_fields = ["name", "cores", "memory"]
        present_fields = [field for field in expected_fields if field in config]
        assert len(present_fields) > 0, "Config should contain at least some expected fields"
    
    @pytest.mark.live
    def test_update_vm_tags_live_dry_run(self, live_proxmox_config, safe_test_vm, tag_backup):
        """Test tag update with dry run validation"""
        if live_config and live_config.dry_run_only:
            pytest.skip("Running in dry-run only mode")
        
        vm = safe_test_vm
        
        # Backup original tags
        tag_backup.backup_vm_tags(vm)
        
        # Get current tags
        original_tags = vm.get("tags", "")
        
        # Create test tags
        from tests.live_config import generate_test_tags
        test_tags = generate_test_tags()[:2]  # Use first 2 test tags
        new_tags = ";".join(test_tags)
        
        try:
            # Update tags
            result = update_vm_tags(vm["node"], vm["vmid"], new_tags, vm["type"])
            
            # Should succeed
            assert "data" in result
            
            # Verify tags were applied by getting fresh config
            import time
            time.sleep(1)  # Give Proxmox time to process
            
            updated_config = get_vm_config(vm["node"], vm["vmid"])
            updated_tags = updated_config.get("tags", "")
            
            # Should contain our test tags
            for test_tag in test_tags:
                assert test_tag in updated_tags
            
        finally:
            # Always restore original tags
            try:
                update_vm_tags(vm["node"], vm["vmid"], original_tags, vm["type"])
            except Exception as e:
                print(f"Warning: Could not restore original tags: {e}")
    
    @pytest.mark.live 
    def test_ssl_verification_live(self, live_proxmox_config):
        """Test SSL verification with live connection"""
        # Test connection with current SSL settings
        try:
            vms = get_all_vms()
            assert isinstance(vms, list)
        except requests.exceptions.SSLError:
            # If SSL error occurs, verify VERIFY_SSL setting
            if live_proxmox_config.get("VERIFY_SSL", True):
                pytest.fail("SSL verification failed but VERIFY_SSL is True")
            else:
                pytest.skip("SSL verification disabled in configuration")
    
    @pytest.mark.live
    def test_vm_type_consistency_live(self, live_proxmox_config, test_vms):
        """Test that live VMs have consistent type information"""
        if not test_vms:
            pytest.skip("No test VMs available")
        
        for vm in test_vms:
            # VM type should be in valid types
            assert vm["type"] in VALID_VM_TYPES
            
            # Should be able to get config for this VM type
            config = get_vm_config(vm["node"], vm["vmid"])
            assert isinstance(config, dict)
            
            # Config should have name matching VM info
            if "name" in config and "name" in vm:
                assert config["name"] == vm["name"]
    
    @pytest.mark.live
    def test_tag_operations_safety_live(self, live_proxmox_config, safe_test_vm):
        """Test tag operations safety mechanisms"""
        vm = safe_test_vm
        
        # Verify VM is safe for testing
        if live_config:
            assert live_config.is_test_vm(vm), "VM should be marked as safe for testing"
        
        # Verify VM name contains safety indicators
        vm_name = vm["name"].lower()
        safety_indicators = ["test", "dev", "staging", "sandbox"]
        assert any(indicator in vm_name for indicator in safety_indicators)
        
        # Verify VM name doesn't contain production indicators
        production_indicators = ["prod", "production", "live", "master", "main"]
        assert not any(indicator in vm_name for indicator in production_indicators)