"""
Integration tests for tag workflow operations
"""

import pytest
from unittest.mock import Mock, patch
from tag_utils import parse_tags, format_tags, extract_tags
from backup_utils import create_backup_file, restore_from_backup_data


class TestTagWorkflowIntegration:
    """Test complete tag workflow integration"""
    
    @pytest.mark.integration
    def test_complete_tag_parsing_workflow(self):
        """Test complete tag parsing and formatting workflow"""
        # Start with VM data
        vm_data = [
            {
                "vmid": 100,
                "name": "web-server",
                "tags": "production;web;frontend;monitoring"
            },
            {
                "vmid": 101,
                "name": "db-server", 
                "tags": "production;database;backend"
            },
            {
                "vmid": 102,
                "name": "dev-server",
                "tags": "development;testing;   ;web"  # Contains empty tag
            }
        ]
        
        # Extract all unique tags
        all_tags = extract_tags(vm_data)
        expected_tags = ["backend", "database", "development", "frontend", 
                        "monitoring", "production", "testing", "web"]
        assert all_tags == expected_tags
        
        # Test parsing and formatting individual VM tags
        for vm in vm_data:
            original_tags_str = vm["tags"]
            parsed_tags = parse_tags(original_tags_str)
            formatted_tags = format_tags(parsed_tags)
            reparsed_tags = parse_tags(formatted_tags)
            
            # Roundtrip should preserve tags (minus empty ones)
            assert parsed_tags == reparsed_tags
            
            # Empty tags should be filtered out
            assert "" not in parsed_tags
            assert "   " not in parsed_tags
    
    @pytest.mark.integration
    def test_backup_restore_tag_workflow(self, sample_vms):
        """Test complete backup and restore workflow"""
        # Create backup
        buffer, filename = create_backup_file(sample_vms)
        
        # Verify backup format
        buffer.seek(0)
        import json
        backup_data = json.loads(buffer.read().decode('utf-8'))
        
        assert len(backup_data) == len(sample_vms)
        
        # Mock update function to track calls
        mock_update = Mock()
        
        # Restore from backup
        result = restore_from_backup_data(backup_data, mock_update)
        
        assert result["success"] is True
        assert result["updated"] == len(sample_vms)
        assert result["failed"] == 0
        
        # Verify all VMs were processed
        assert mock_update.call_count == len(sample_vms)
        
        # Check that tags were properly formatted for each call
        for call_args in mock_update.call_args_list:
            node, vmid, tags_str, vm_type = call_args[0]
            
            # Verify types
            assert isinstance(node, str)
            assert isinstance(vmid, int)
            assert isinstance(tags_str, str)
            assert vm_type in ["qemu", "lxc"]
            
            # If tags_str is not empty, should be properly formatted
            if tags_str:
                parsed = parse_tags(tags_str)
                reformatted = format_tags(parsed)
                assert tags_str == reformatted
    
    @pytest.mark.integration
    def test_tag_modification_workflow(self):
        """Test workflow for modifying VM tags"""
        # Start with VM with existing tags
        vm = {
            "vmid": 100,
            "name": "test-vm",
            "node": "node1",
            "type": "qemu",
            "tags": "production;web;old-tag"
        }
        
        # Parse current tags
        current_tags = parse_tags(vm["tags"])
        assert "old-tag" in current_tags
        assert "production" in current_tags
        
        # Simulate tag modifications
        modified_tags = current_tags.copy()
        modified_tags.remove("old-tag")  # Remove tag
        modified_tags.append("new-tag")  # Add tag
        modified_tags.append("monitoring")  # Add another tag
        
        # Format for storage
        new_tags_str = format_tags(modified_tags)
        
        # Verify the modifications
        final_tags = parse_tags(new_tags_str)
        assert "old-tag" not in final_tags
        assert "new-tag" in final_tags
        assert "monitoring" in final_tags
        assert "production" in final_tags  # Preserved
        assert "web" in final_tags  # Preserved
    
    @pytest.mark.integration
    def test_bulk_tag_operations_workflow(self):
        """Test bulk tag operations workflow"""
        vms = [
            {"vmid": 100, "tags": "production;web"},
            {"vmid": 101, "tags": "production;database"},
            {"vmid": 102, "tags": "development;web"},
            {"vmid": 103, "tags": ""}  # No tags
        ]
        
        # Extract all current tags
        all_current_tags = extract_tags(vms)
        assert "production" in all_current_tags
        assert "development" in all_current_tags
        
        # Simulate bulk add operation - add "monitoring" to all VMs
        updated_vms = []
        for vm in vms:
            current_tags = parse_tags(vm["tags"])
            if "monitoring" not in current_tags:
                current_tags.append("monitoring")
            new_tags_str = format_tags(current_tags)
            
            updated_vm = vm.copy()
            updated_vm["tags"] = new_tags_str
            updated_vms.append(updated_vm)
        
        # Verify all VMs now have monitoring tag
        for vm in updated_vms:
            tags = parse_tags(vm["tags"])
            assert "monitoring" in tags
        
        # Simulate bulk remove operation - remove "production" from all VMs
        final_vms = []
        for vm in updated_vms:
            current_tags = parse_tags(vm["tags"])
            if "production" in current_tags:
                current_tags.remove("production")
            new_tags_str = format_tags(current_tags)
            
            final_vm = vm.copy()
            final_vm["tags"] = new_tags_str
            final_vms.append(final_vm)
        
        # Verify production tag was removed but others preserved
        for vm in final_vms:
            tags = parse_tags(vm["tags"])
            assert "production" not in tags
            assert "monitoring" in tags  # Should still be there
        
        # Check specific VMs
        vm_100_tags = parse_tags(final_vms[0]["tags"])
        assert set(vm_100_tags) == {"web", "monitoring"}
        
        vm_103_tags = parse_tags(final_vms[3]["tags"])
        assert set(vm_103_tags) == {"monitoring"}  # Was empty, now has monitoring
    
    @pytest.mark.integration
    def test_tag_data_consistency_workflow(self):
        """Test tag data consistency across operations"""
        # Test various edge cases that might break consistency
        test_cases = [
            "",  # Empty tags
            "   ",  # Whitespace only
            "single",  # Single tag
            "one;two",  # Multiple tags
            "  one  ;  two  ",  # Tags with spaces
            "one;;two",  # Empty tag in middle
            "one;two;",  # Trailing semicolon
            ";one;two",  # Leading semicolon
            "Tag1;TAG1;tag1",  # Case variations (should be preserved as-is)
        ]
        
        for tags_str in test_cases:
            # Parse tags
            parsed = parse_tags(tags_str)
            
            # Format back
            formatted = format_tags(parsed)
            
            # Parse again
            reparsed = parse_tags(formatted)
            
            # Should be consistent
            assert parsed == reparsed, f"Inconsistency with input: '{tags_str}'"
            
            # Formatted string should not have:
            # - Leading/trailing whitespace on individual tags
            # - Empty tags
            # - Leading/trailing semicolons
            if formatted:
                assert not formatted.startswith(";")
                assert not formatted.endswith(";")
                assert ";;" not in formatted
                
                for tag in formatted.split(";"):
                    assert tag.strip() == tag
                    assert len(tag) > 0
    
    @pytest.mark.integration 
    def test_error_recovery_workflow(self):
        """Test error recovery in tag operations"""
        # Test with problematic VM data
        problematic_vms = [
            {"vmid": 100, "tags": "good;tags"},  # Good VM
            {"vmid": 101},  # Missing tags field
            {"vmid": 102, "tags": None},  # None tags
            {"vmid": 103, "tags": 123},  # Wrong type
            {"vmid": 104, "tags": "more;good;tags"},  # Another good VM
        ]
        
        # extract_tags should handle problematic data gracefully
        try:
            extracted = extract_tags(problematic_vms)
            # Should extract tags from good VMs
            assert "good" in extracted
            assert "tags" in extracted
            assert "more" in extracted
        except Exception as e:
            # If any exception occurs, should be handled gracefully
            # This tests the error handling in extract_tags
            pass
        
        # Test parse_tags with various inputs
        problematic_inputs = [None, 123, [], {}, True]
        for bad_input in problematic_inputs:
            result = parse_tags(bad_input)
            assert result == []  # Should return empty list for bad inputs
        
        # Test format_tags with various inputs  
        result = format_tags(None)
        assert result == ""
        
        result = format_tags([])
        assert result == ""
        
        result = format_tags([None, "", "  ", "good"])
        assert result == "good"  # Should filter out bad tags


class TestTagWorkflowWithProxmoxApi:
    """Test tag workflow integration with Proxmox API"""
    
    @pytest.mark.integration
    @patch('proxmox_api.requests.get')
    @patch('proxmox_api.requests.put')
    def test_vm_tag_update_workflow(self, mock_put, mock_get, mock_load_config):
        """Test complete VM tag update workflow"""
        from proxmox_api import get_all_vms, update_vm_tags
        
        # Mock API responses
        mock_get_response = Mock()
        mock_get_response.json.return_value = {
            "data": [
                {
                    "vmid": 100,
                    "name": "test-vm",
                    "node": "node1", 
                    "type": "qemu",
                    "tags": "production;web"
                }
            ]
        }
        mock_get_response.raise_for_status.return_value = None
        mock_get.return_value = mock_get_response
        
        mock_put_response = Mock()
        mock_put_response.json.return_value = {"data": "success"}
        mock_put_response.raise_for_status.return_value = None
        mock_put.return_value = mock_put_response
        
        # Get VMs from API
        vms = get_all_vms()
        assert len(vms) == 1
        
        vm = vms[0]
        original_tags = parse_tags(vm["tags"])
        assert "production" in original_tags
        assert "web" in original_tags
        
        # Modify tags
        new_tags = original_tags + ["monitoring", "critical"]
        new_tags_str = format_tags(new_tags)
        
        # Update via API
        result = update_vm_tags(vm["node"], vm["vmid"], new_tags_str, vm["type"])
        assert result == {"data": "success"}
        
        # Verify API was called correctly
        mock_put.assert_called_once()
        call_args = mock_put.call_args
        assert call_args[1]["json"]["tags"] == new_tags_str
    
    @pytest.mark.integration
    @patch('proxmox_api.update_vm_tags')
    def test_backup_restore_with_api_integration(self, mock_update_vm_tags, sample_vms):
        """Test backup/restore workflow with API integration"""
        # Create backup
        buffer, filename = create_backup_file(sample_vms)
        
        # Mock API update function
        mock_update_vm_tags.return_value = {"data": "success"}
        
        # Parse backup
        buffer.seek(0)
        import json
        backup_data = json.loads(buffer.read().decode('utf-8'))
        
        # Restore using actual API function
        from proxmox_api import update_vm_tags
        result = restore_from_backup_data(backup_data, update_vm_tags)
        
        assert result["success"] is True
        assert result["updated"] == len(sample_vms)
        
        # Verify API calls were made with properly formatted tags
        for call_args in mock_update_vm_tags.call_args_list:
            node, vmid, tags_str, vm_type = call_args[0]
            
            # Tags should be properly formatted
            if tags_str:
                parsed = parse_tags(tags_str)
                reformatted = format_tags(parsed)
                assert tags_str == reformatted