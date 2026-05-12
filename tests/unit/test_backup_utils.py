"""
Unit tests for backup_utils module
"""

import pytest
import json
from io import BytesIO
from unittest.mock import Mock, patch
from datetime import datetime
from backup_utils import create_backup_file, restore_from_backup_data, BACKUP_FORMAT_VERSION


class TestCreateBackupFile:
    """Test the create_backup_file function"""
    
    @pytest.mark.unit
    def test_create_backup_file_basic(self, sample_vms):
        """Test basic backup file creation (v2 wrapper)."""
        buffer, filename = create_backup_file(sample_vms)

        assert isinstance(buffer, BytesIO)
        assert filename.startswith("proxmox_tags_backup_")
        assert filename.endswith(".json")

        buffer.seek(0)
        backup_data = json.loads(buffer.read().decode('utf-8'))

        # v2 wrapper shape
        assert isinstance(backup_data, dict)
        assert backup_data["version"] == BACKUP_FORMAT_VERSION
        assert "exported_at" in backup_data
        assert isinstance(backup_data["vms"], list)
        assert backup_data["tag_colors"] == {}
        assert len(backup_data["vms"]) == 4

        vm_data = backup_data["vms"][0]
        assert vm_data["id"] == 100
        assert vm_data["name"] == "test-vm-1"
        assert vm_data["node"] == "node1"
        assert vm_data["type"] == "qemu"
        assert vm_data["tags"] == ["production", "web", "frontend"]

    @pytest.mark.unit
    def test_create_backup_file_empty_vms(self):
        """Test backup creation with empty VM list (still emits v2 wrapper)."""
        buffer, filename = create_backup_file([])
        buffer.seek(0)
        backup_data = json.loads(buffer.read().decode('utf-8'))
        assert backup_data["version"] == BACKUP_FORMAT_VERSION
        assert backup_data["vms"] == []
        assert backup_data["tag_colors"] == {}

    @pytest.mark.unit
    def test_create_backup_file_vm_no_tags(self):
        """Test backup creation with VM that has no tags"""
        vms = [{"vmid": 100, "name": "test-vm", "node": "node1", "type": "qemu", "tags": ""}]
        buffer, _ = create_backup_file(vms)
        buffer.seek(0)
        backup_data = json.loads(buffer.read().decode('utf-8'))

        assert len(backup_data["vms"]) == 1
        assert backup_data["vms"][0]["tags"] == []

    @pytest.mark.unit
    def test_create_backup_file_tag_cleaning(self):
        """Test that tags are properly cleaned in backup"""
        vms = [{"vmid": 100, "name": "t", "node": "n", "type": "qemu", "tags": "web;  ;production;;"}]
        buffer, _ = create_backup_file(vms)
        buffer.seek(0)
        backup_data = json.loads(buffer.read().decode('utf-8'))

        assert backup_data["vms"][0]["tags"] == ["web", "production"]

    @pytest.mark.unit
    def test_create_backup_file_missing_fields(self):
        """Test backup creation with VMs missing some fields"""
        vms = [
            {"vmid": 100, "name": "test-vm", "node": "node1", "type": "qemu"},
            {"vmid": 101, "node": "node2", "type": "lxc", "tags": "web"},
        ]
        buffer, _ = create_backup_file(vms)
        buffer.seek(0)
        backup_data = json.loads(buffer.read().decode('utf-8'))

        assert len(backup_data["vms"]) == 2
        assert backup_data["vms"][0]["tags"] == []
        assert backup_data["vms"][1]["name"] is None

    @pytest.mark.unit
    def test_create_backup_file_includes_color_map(self):
        """Test that a non-empty color map is embedded under tag_colors."""
        color_map = {
            "prod": {"bg": "ff0000", "fg": "ffffff"},
            "dev": {"bg": "00ff00", "fg": None},
        }
        buffer, _ = create_backup_file([], color_map=color_map)
        buffer.seek(0)
        data = json.loads(buffer.read().decode('utf-8'))
        assert data["tag_colors"] == color_map

    @pytest.mark.unit
    def test_create_backup_file_color_map_default_empty(self):
        """Omitting color_map yields tag_colors: {}."""
        buffer, _ = create_backup_file([])
        buffer.seek(0)
        data = json.loads(buffer.read().decode('utf-8'))
        assert data["tag_colors"] == {}
    
    @pytest.mark.unit
    def test_create_backup_filename_format(self):
        """Test that backup filename has correct format"""
        with patch('backup_utils.datetime') as mock_datetime:
            fixed = Mock()
            fixed.strftime.return_value = "20240115_120000"
            fixed.isoformat.return_value = "2024-01-15T12:00:00+00:00"
            mock_datetime.now.return_value = fixed

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
        """Test creating backup and restoring it (v2 round-trip)."""
        buffer, _ = create_backup_file(sample_vms)
        buffer.seek(0)
        backup_data = json.loads(buffer.read().decode('utf-8'))

        mock_update = Mock()
        result = restore_from_backup_data(backup_data, mock_update)

        assert result["success"] is True
        assert result["format_version"] == 2
        assert result["updated"] == 4
        assert mock_update.call_count == 4

        vm_102_call = next((c for c in mock_update.call_args_list if c[0][1] == 102), None)
        assert vm_102_call is not None
        assert vm_102_call[0][2] == ""

    @pytest.mark.unit
    def test_backup_data_consistency(self, sample_vms):
        """Test that backup data maintains consistency"""
        buffer, _ = create_backup_file(sample_vms)
        buffer.seek(0)
        backup_data = json.loads(buffer.read().decode('utf-8'))

        for vm_backup in backup_data["vms"]:
            assert "id" in vm_backup
            assert "name" in vm_backup
            assert "node" in vm_backup
            assert "type" in vm_backup
            assert "tags" in vm_backup
            assert isinstance(vm_backup["id"], int)
            assert isinstance(vm_backup["tags"], list)
            assert vm_backup["type"] in ["qemu", "lxc"]
            for tag in vm_backup["tags"]:
                assert isinstance(tag, str)
                assert tag.strip() == tag
                assert tag != ""


class TestRestoreV2:
    """Restore-side tests for the v2 wrapper format."""

    @pytest.fixture
    def mock_update(self):
        return Mock()

    @pytest.fixture
    def v2_backup(self):
        return {
            "version": 2,
            "exported_at": "2026-05-06T00:00:00+00:00",
            "vms": [
                {"id": 100, "name": "vm1", "node": "n1", "type": "qemu", "tags": ["a"]},
                {"id": 101, "name": "vm2", "node": "n1", "type": "lxc", "tags": ["b"]},
            ],
            "tag_colors": {
                "prod": {"bg": "ff0000", "fg": "ffffff"},
                "dev": {"bg": "00ff00", "fg": None},
            },
        }

    @pytest.mark.unit
    def test_v1_list_format_still_accepted(self, mock_update):
        """A bare list (legacy v1) still imports successfully."""
        v1 = [{"id": 100, "name": "vm", "node": "n1", "type": "qemu", "tags": ["a"]}]
        result = restore_from_backup_data(v1, mock_update)
        assert result["success"] is True
        assert result["format_version"] == 1
        assert result["updated"] == 1
        assert result["colors_restored"] is None
        assert result["colors_error"] is None

    @pytest.mark.unit
    def test_v2_format_imports_vms(self, v2_backup, mock_update):
        result = restore_from_backup_data(v2_backup, mock_update)
        assert result["success"] is True
        assert result["format_version"] == 2
        assert result["updated"] == 2

    @pytest.mark.unit
    def test_v2_no_callback_skips_colors(self, v2_backup, mock_update):
        result = restore_from_backup_data(v2_backup, mock_update, restore_tag_colors_func=None)
        # Tags restored, but colors are silently skipped because no callback.
        assert result["updated"] == 2
        assert result["colors_restored"] is None
        assert result["colors_error"] is None

    @pytest.mark.unit
    def test_v2_calls_color_callback_with_full_map(self, v2_backup, mock_update):
        color_cb = Mock()
        result = restore_from_backup_data(v2_backup, mock_update, color_cb)
        color_cb.assert_called_once_with(v2_backup["tag_colors"])
        assert result["colors_restored"] == 2
        assert result["colors_error"] is None

    @pytest.mark.unit
    def test_v2_color_callback_permission_denied_is_non_fatal(self, v2_backup, mock_update):
        color_cb = Mock(side_effect=PermissionError("Sys.Modify required"))
        result = restore_from_backup_data(v2_backup, mock_update, color_cb)
        # Tags still restored:
        assert result["updated"] == 2
        assert result["success"] is True
        # Colors marked as failed with structured code:
        assert result["colors_restored"] == 0
        assert result["colors_error"] == "permission_denied"

    @pytest.mark.unit
    def test_v2_color_callback_other_error_recorded_but_non_fatal(self, v2_backup, mock_update):
        color_cb = Mock(side_effect=RuntimeError("connection refused"))
        result = restore_from_backup_data(v2_backup, mock_update, color_cb)
        assert result["updated"] == 2
        assert result["success"] is True
        assert result["colors_restored"] == 0
        assert "connection refused" in result["colors_error"]

    @pytest.mark.unit
    def test_v2_empty_tag_colors_skips_callback(self, mock_update):
        backup = {"version": 2, "vms": [], "tag_colors": {}}
        color_cb = Mock()
        result = restore_from_backup_data(backup, mock_update, color_cb)
        color_cb.assert_not_called()
        assert result["colors_restored"] is None

    @pytest.mark.unit
    def test_invalid_dict_format_rejected(self, mock_update):
        # Dict without 'vms' as list
        result = restore_from_backup_data({"version": 2, "vms": "nope"}, mock_update)
        assert result["success"] is False
        assert "Invalid backup format" in result["error"]

    @pytest.mark.unit
    def test_unknown_top_level_type_rejected(self, mock_update):
        result = restore_from_backup_data("a string", mock_update)
        assert result["success"] is False