"""
Unit tests for backup_utils module
"""

import pytest
import json
from io import BytesIO
from unittest.mock import Mock, patch
from datetime import datetime
from backup_utils import create_backup_file, restore_from_backup_data


class TestCreateBackupFile:
    """Test the create_backup_file function"""
    
    @pytest.mark.unit
    def test_create_backup_file_basic(self, sample_vms):
        """Test basic backup file creation"""
        buffer, filename = create_backup_file(sample_vms)
        
        # Check that we got a BytesIO buffer and filename
        assert isinstance(buffer, BytesIO)
        assert filename.startswith("proxmox_tags_backup_")
        assert filename.endswith(".json")
        
        # Parse the JSON content
        buffer.seek(0)
        content = buffer.read().decode('utf-8')
        backup_data = json.loads(content)
        
        # Verify structure
        assert isinstance(backup_data, list)
        assert len(backup_data) == 4  # Same as sample_vms
        
        # Check first VM data
        vm_data = backup_data[0]
        assert vm_data["id"] == 100
        assert vm_data["name"] == "test-vm-1"
        assert vm_data["node"] == "node1"
        assert vm_data["type"] == "qemu"
        assert vm_data["tags"] == ["production", "web", "frontend"]
    
    @pytest.mark.unit
    def test_create_backup_file_empty_vms(self):
        """Test backup creation with empty VM list"""
        buffer, filename = create_backup_file([])
        
        buffer.seek(0)
        content = buffer.read().decode('utf-8')
        backup_data = json.loads(content)
        
        assert backup_data == []
    
    @pytest.mark.unit
    def test_create_backup_file_vm_no_tags(self):
        """Test backup creation with VM that has no tags"""
        vms = [
            {
                "vmid": 100,
                "name": "test-vm",
                "node": "node1",
                "type": "qemu",
                "tags": ""
            }
        ]
        
        buffer, filename = create_backup_file(vms)
        
        buffer.seek(0)
        content = buffer.read().decode('utf-8')
        backup_data = json.loads(content)
        
        assert len(backup_data) == 1
        assert backup_data[0]["tags"] == []
    
    @pytest.mark.unit
    def test_create_backup_file_tag_cleaning(self):
        """Test that tags are properly cleaned in backup"""
        vms = [
            {
                "vmid": 100,
                "name": "test-vm",
                "node": "node1", 
                "type": "qemu",
                "tags": "web;  ;production;;"  # Has empty and whitespace tags
            }
        ]
        
        buffer, filename = create_backup_file(vms)
        
        buffer.seek(0)
        content = buffer.read().decode('utf-8')
        backup_data = json.loads(content)
        
        # Empty and whitespace-only tags should be filtered out
        assert backup_data[0]["tags"] == ["web", "production"]
    
    @pytest.mark.unit
    def test_create_backup_file_missing_fields(self):
        """Test backup creation with VMs missing some fields"""
        vms = [
            {
                "vmid": 100,
                "name": "test-vm",
                "node": "node1",
                "type": "qemu"
                # Missing tags field
            },
            {
                "vmid": 101,
                # Missing name field
                "node": "node2",
                "type": "lxc",
                "tags": "web"
            }
        ]
        
        buffer, filename = create_backup_file(vms)
        
        buffer.seek(0)
        content = buffer.read().decode('utf-8')
        backup_data = json.loads(content)
        
        assert len(backup_data) == 2
        assert backup_data[0]["tags"] == []  # Missing tags field
        assert backup_data[1]["name"] is None  # Missing name field
    
    @pytest.mark.unit
    def test_create_backup_filename_format(self):
        """Test that backup filename has correct format"""
        with patch('backup_utils.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "20240115_120000"
            
            buffer, filename = create_backup_file([])
            
            expected_filename = "proxmox_tags_backup_20240115_120000.json"
            assert filename == expected_filename


class TestRestoreFromBackupData:
    """Test the restore_from_backup_data function"""
    
    @pytest.fixture
    def mock_update_function(self):
        """Mock function for updating VM tags"""
        return Mock()
    
    @pytest.fixture
    def valid_backup_data(self):
        """Valid backup data for testing"""
        return [
            {
                "id": 100,
                "name": "test-vm-1",
                "node": "node1",
                "type": "qemu",
                "tags": ["production", "web"]
            },
            {
                "id": 101,
                "name": "test-vm-2", 
                "node": "node2",
                "type": "lxc",
                "tags": ["development", "database"]
            }
        ]
    
    @pytest.mark.unit
    def test_restore_from_backup_data_success(self, valid_backup_data, mock_update_function):
        """Test successful restore from backup data"""
        result = restore_from_backup_data(valid_backup_data, mock_update_function)
        
        assert result["success"] is True
        assert result["updated"] == 2
        assert result["failed"] == 0
        assert result["failures"] == []
        
        # Verify update function was called correctly
        assert mock_update_function.call_count == 2
        
        # Check first call
        call_args = mock_update_function.call_args_list[0]
        assert call_args[0] == ("node1", 100, "production;web", "qemu")
        
        # Check second call
        call_args = mock_update_function.call_args_list[1]
        assert call_args[0] == ("node2", 101, "development;database", "lxc")
    
    @pytest.mark.unit
    def test_restore_from_backup_data_empty_tags(self, mock_update_function):
        """Test restore with empty tags"""
        backup_data = [
            {
                "id": 100,
                "name": "test-vm",
                "node": "node1",
                "type": "qemu",
                "tags": []
            }
        ]
        
        result = restore_from_backup_data(backup_data, mock_update_function)
        
        assert result["success"] is True
        assert result["updated"] == 1
        
        # Should call update function with empty string
        mock_update_function.assert_called_once_with("node1", 100, "", "qemu")
    
    @pytest.mark.unit
    def test_restore_from_backup_data_invalid_format(self, mock_update_function):
        """Test restore with invalid backup format"""
        # Test with non-list data
        result = restore_from_backup_data("invalid", mock_update_function)
        
        assert result["success"] is False
        assert "Invalid backup format" in result["error"]
        assert mock_update_function.call_count == 0
    
    @pytest.mark.unit
    def test_restore_from_backup_data_missing_fields(self, mock_update_function):
        """Test restore with missing required fields"""
        backup_data = [
            {
                "id": 100,
                "name": "test-vm",
                # Missing node and type
                "tags": ["web"]
            },
            {
                # Missing id
                "name": "test-vm-2",
                "node": "node1",
                "type": "qemu",
                "tags": ["database"]
            }
        ]
        
        result = restore_from_backup_data(backup_data, mock_update_function)
        
        # Should skip VMs with missing fields
        assert result["updated"] == 0
        assert result["failed"] == 0
        assert mock_update_function.call_count == 0
    
    @pytest.mark.unit
    def test_restore_from_backup_data_update_failures(self, valid_backup_data, mock_update_function):
        """Test restore with some update failures"""
        # First call succeeds, second fails
        mock_update_function.side_effect = [None, Exception("Update failed")]
        
        result = restore_from_backup_data(valid_backup_data, mock_update_function)
        
        assert result["success"] is False
        assert result["updated"] == 1
        assert result["failed"] == 1
        assert len(result["failures"]) == 1
        assert result["failures"][0]["vmid"] == 101
        assert "Update failed" in result["failures"][0]["error"]
    
    @pytest.mark.unit
    def test_restore_from_backup_data_vm_not_exists(self, mock_update_function):
        """Test restore when VM no longer exists"""
        backup_data = [
            {
                "id": 100,
                "name": "deleted-vm",
                "node": "node1",
                "type": "qemu", 
                "tags": ["web"]
            },
            {
                "id": 101,
                "name": "existing-vm",
                "node": "node1",
                "type": "qemu",
                "tags": ["database"]
            }
        ]
        
        # First call fails with "Configuration file does not exist" (VM deleted)
        # Second call succeeds
        mock_update_function.side_effect = [
            Exception("Configuration file does not exist"),
            None
        ]
        
        with patch('logging.info') as mock_log_info:
            result = restore_from_backup_data(backup_data, mock_update_function)
        
        # Should continue processing and not count VM deletion as failure
        assert result["success"] is True
        assert result["updated"] == 1
        assert result["failed"] == 0
        assert len(result["failures"]) == 0
        
        # Should log the skipped VM
        mock_log_info.assert_called_once()
        assert "Skipping VM 100" in mock_log_info.call_args[0][0]
    
    @pytest.mark.unit
    def test_restore_from_backup_data_tag_filtering(self, mock_update_function):
        """Test that empty tags are filtered during restore"""
        backup_data = [
            {
                "id": 100,
                "name": "test-vm",
                "node": "node1",
                "type": "qemu",
                "tags": ["web", "", "  ", "production", ""]  # Mixed empty tags
            }
        ]
        
        result = restore_from_backup_data(backup_data, mock_update_function)
        
        assert result["success"] is True
        
        # Should filter out empty and whitespace-only tags
        mock_update_function.assert_called_once_with("node1", 100, "web;production", "qemu")
    
    @pytest.mark.unit
    def test_restore_from_backup_data_non_list_tags(self, mock_update_function):
        """Test restore with non-list tags field"""
        backup_data = [
            {
                "id": 100,
                "name": "test-vm",
                "node": "node1",
                "type": "qemu",
                "tags": "not-a-list"  # Should be list
            }
        ]
        
        result = restore_from_backup_data(backup_data, mock_update_function)
        
        # Should skip VM with invalid tags field
        assert result["updated"] == 0
        assert result["failed"] == 0
        assert mock_update_function.call_count == 0


class TestBackupUtilsIntegration:
    """Integration tests for backup utilities working together"""
    
    @pytest.mark.unit
    def test_backup_restore_roundtrip(self, sample_vms):
        """Test creating backup and restoring it"""
        # Create backup
        buffer, filename = create_backup_file(sample_vms)
        
        # Parse backup data
        buffer.seek(0)
        content = buffer.read().decode('utf-8')
        backup_data = json.loads(content)
        
        # Mock update function
        mock_update = Mock()
        
        # Restore from backup
        result = restore_from_backup_data(backup_data, mock_update)
        
        assert result["success"] is True
        assert result["updated"] == 4  # All VMs from sample_vms
        
        # Verify all VMs were processed
        assert mock_update.call_count == 4
        
        # Check that VM with no tags gets empty string
        vm_102_call = None
        for call in mock_update.call_args_list:
            if call[0][1] == 102:  # VMID 102 has no tags in sample_vms
                vm_102_call = call
                break
        
        assert vm_102_call is not None
        assert vm_102_call[0][2] == ""  # Empty tags string
    
    @pytest.mark.unit
    def test_backup_data_consistency(self, sample_vms):
        """Test that backup data maintains consistency"""
        buffer, filename = create_backup_file(sample_vms)
        
        buffer.seek(0)
        content = buffer.read().decode('utf-8')
        backup_data = json.loads(content)
        
        # Check that all required fields are present and properly typed
        for vm_backup in backup_data:
            assert "id" in vm_backup
            assert "name" in vm_backup
            assert "node" in vm_backup
            assert "type" in vm_backup
            assert "tags" in vm_backup
            
            assert isinstance(vm_backup["id"], int)
            assert isinstance(vm_backup["tags"], list)
            assert vm_backup["type"] in ["qemu", "lxc"]
            
            # All tags should be strings
            for tag in vm_backup["tags"]:
                assert isinstance(tag, str)
                assert tag.strip() == tag  # No leading/trailing whitespace
                assert tag != ""  # No empty tags