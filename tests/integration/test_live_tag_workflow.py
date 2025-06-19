"""
Live integration tests for complete tag management workflows

These tests run against a real Proxmox instance to verify end-to-end
tag management functionality. Tests are marked with @pytest.mark.live
and require PROXTAGGER_LIVE_TESTS=true to run.

Safety Features:
- Only operates on VMs with test- prefix
- Backs up and restores original tags
- Validates production VM exclusion
- Supports dry-run mode
"""

import pytest
import time
from typing import List, Dict, Set
from datetime import datetime

# Import modules under test
import tag_utils
import proxmox_api
import backup_utils

# Import live testing utilities
from tests.live_config import (
    live_config, TagBackupManager, generate_test_tags,
    safe_tag_update, validate_proxmox_connection
)


class TestLiveTagWorkflow:
    """Live end-to-end tag workflow tests"""
    
    @pytest.mark.live
    def test_complete_tag_lifecycle(self, live_proxmox_config, safe_test_vm, tag_backup):
        """Test complete tag lifecycle: parse, format, update, verify"""
        vm = safe_test_vm
        
        # Backup original state
        tag_backup.backup_vm_tags(vm)
        original_tags = vm.get("tags", "")
        
        try:
            # Step 1: Generate and format test tags
            test_tags_list = generate_test_tags()[:3]
            formatted_tags = tag_utils.format_tags(test_tags_list)
            
            # Step 2: Update VM with new tags
            result = safe_tag_update(
                vm["node"], vm["vmid"], formatted_tags, vm["type"], tag_backup
            )
            
            if not live_config.dry_run_only:
                assert "data" in result
                
                # Wait for Proxmox to process
                time.sleep(2)
                
                # Step 3: Fetch updated config and verify
                updated_config = proxmox_api.get_vm_config(vm["node"], vm["vmid"])
                retrieved_tags = updated_config.get("tags", "")
                
                # Step 4: Parse retrieved tags and verify
                parsed_tags = tag_utils.parse_tags(retrieved_tags)
                
                # All test tags should be present
                for test_tag in test_tags_list:
                    assert test_tag in parsed_tags, f"Tag {test_tag} not found in retrieved tags"
                
                # Step 5: Test tag extraction
                extracted_tags = tag_utils.extract_tags_from_vms([{
                    **vm,
                    "tags": retrieved_tags
                }])
                
                for test_tag in test_tags_list:
                    assert test_tag in extracted_tags
            
        finally:
            # Always restore original state
            if not live_config.dry_run_only:
                tag_backup.restore_vm_tags(vm["vmid"])
    
    @pytest.mark.live
    def test_tag_merge_operations_live(self, live_proxmox_config, safe_test_vm, tag_backup):
        """Test tag merging operations with live VM"""
        vm = safe_test_vm
        
        # Backup original state
        tag_backup.backup_vm_tags(vm)
        original_tags = vm.get("tags", "")
        original_tags_list = tag_utils.parse_tags(original_tags)
        
        try:
            # Step 1: Add some base tags
            base_test_tags = generate_test_tags()[:2]
            base_tags_str = tag_utils.format_tags(base_test_tags)
            
            result1 = safe_tag_update(
                vm["node"], vm["vmid"], base_tags_str, vm["type"], tag_backup
            )
            
            if not live_config.dry_run_only:
                assert "data" in result1
                time.sleep(1)
                
                # Step 2: Merge additional tags
                additional_tags = [generate_test_tags()[2]]  # Third test tag
                
                # Get current tags and merge
                current_config = proxmox_api.get_vm_config(vm["node"], vm["vmid"])
                current_tags = tag_utils.parse_tags(current_config.get("tags", ""))
                
                merged_tags = list(set(current_tags + additional_tags))
                merged_tags_str = tag_utils.format_tags(merged_tags)
                
                result2 = safe_tag_update(
                    vm["node"], vm["vmid"], merged_tags_str, vm["type"], tag_backup
                )
                
                assert "data" in result2
                time.sleep(1)
                
                # Step 3: Verify merged result
                final_config = proxmox_api.get_vm_config(vm["node"], vm["vmid"])
                final_tags = tag_utils.parse_tags(final_config.get("tags", ""))
                
                # Should contain all base tags plus additional
                for tag in base_test_tags + additional_tags:
                    assert tag in final_tags
                
                # Step 4: Test tag removal
                tags_to_keep = base_test_tags  # Remove additional tags
                keep_tags_str = tag_utils.format_tags(tags_to_keep)
                
                result3 = safe_tag_update(
                    vm["node"], vm["vmid"], keep_tags_str, vm["type"], tag_backup
                )
                
                assert "data" in result3
                time.sleep(1)
                
                # Verify removal
                final_config2 = proxmox_api.get_vm_config(vm["node"], vm["vmid"])
                final_tags2 = tag_utils.parse_tags(final_config2.get("tags", ""))
                
                for tag in base_test_tags:
                    assert tag in final_tags2
                for tag in additional_tags:
                    assert tag not in final_tags2
        
        finally:
            # Restore original state
            if not live_config.dry_run_only:
                tag_backup.restore_vm_tags(vm["vmid"])
    
    @pytest.mark.live
    def test_bulk_tag_operations_live(self, live_proxmox_config, test_vms, tag_backup):
        """Test bulk tag operations across multiple VMs"""
        if len(test_vms) < 2:
            pytest.skip("Need at least 2 test VMs for bulk operations")
        
        # Use first 2 test VMs
        target_vms = test_vms[:2]
        
        # Backup all VMs
        tag_backup.backup_multiple_vms(target_vms)
        
        try:
            # Step 1: Apply same tags to multiple VMs
            bulk_test_tags = generate_test_tags()[:2]
            bulk_tags_str = tag_utils.format_tags(bulk_test_tags)
            
            results = []
            for vm in target_vms:
                result = safe_tag_update(
                    vm["node"], vm["vmid"], bulk_tags_str, vm["type"], tag_backup
                )
                results.append(result)
            
            if not live_config.dry_run_only:
                # All updates should succeed
                for result in results:
                    assert "data" in result
                
                time.sleep(2)
                
                # Step 2: Verify all VMs have the tags
                for vm in target_vms:
                    config = proxmox_api.get_vm_config(vm["node"], vm["vmid"])
                    vm_tags = tag_utils.parse_tags(config.get("tags", ""))
                    
                    for test_tag in bulk_test_tags:
                        assert test_tag in vm_tags
                
                # Step 3: Test selective bulk updates
                # Add different tags to each VM
                for i, vm in enumerate(target_vms):
                    specific_tag = f"vm-specific-{i+1}-{datetime.now().strftime('%H%M%S')}"
                    current_config = proxmox_api.get_vm_config(vm["node"], vm["vmid"])
                    current_tags = tag_utils.parse_tags(current_config.get("tags", ""))
                    
                    updated_tags = current_tags + [specific_tag]
                    updated_tags_str = tag_utils.format_tags(updated_tags)
                    
                    result = safe_tag_update(
                        vm["node"], vm["vmid"], updated_tags_str, vm["type"], tag_backup
                    )
                    assert "data" in result
                
                time.sleep(1)
                
                # Verify specific tags
                for i, vm in enumerate(target_vms):
                    config = proxmox_api.get_vm_config(vm["node"], vm["vmid"])
                    vm_tags = tag_utils.parse_tags(config.get("tags", ""))
                    
                    expected_specific_tag = f"vm-specific-{i+1}"
                    matching_tags = [tag for tag in vm_tags if expected_specific_tag in tag]
                    assert len(matching_tags) > 0, f"VM {vm['vmid']} missing specific tag"
        
        finally:
            # Restore all VMs
            if not live_config.dry_run_only:
                tag_backup.restore_all()
    
    @pytest.mark.live
    def test_tag_backup_restore_workflow_live(self, live_proxmox_config, safe_test_vm):
        """Test tag backup and restore workflow"""
        vm = safe_test_vm
        
        # Create fresh backup manager for this test
        backup_manager = TagBackupManager()
        
        # Step 1: Backup original state
        backup_manager.backup_vm_tags(vm)
        original_tags = vm.get("tags", "")
        
        # Step 2: Modify tags
        test_tags = generate_test_tags()[:2]
        test_tags_str = tag_utils.format_tags(test_tags)
        
        try:
            if not live_config.dry_run_only:
                result = proxmox_api.update_vm_tags(
                    vm["node"], vm["vmid"], test_tags_str, vm["type"]
                )
                assert "data" in result
                time.sleep(1)
                
                # Verify tags were changed
                modified_config = proxmox_api.get_vm_config(vm["node"], vm["vmid"])
                modified_tags = modified_config.get("tags", "")
                assert modified_tags != original_tags
                
                # Step 3: Restore original tags
                restore_success = backup_manager.restore_vm_tags(vm["vmid"])
                assert restore_success
                time.sleep(1)
                
                # Step 4: Verify restoration
                restored_config = proxmox_api.get_vm_config(vm["node"], vm["vmid"])
                restored_tags = restored_config.get("tags", "")
                assert restored_tags == original_tags
                
                # Step 5: Test backup info
                backup_info = backup_manager.get_backup_info()
                assert backup_info["vm_count"] == 1
                assert vm["vmid"] in backup_info["vmids"]
                assert "timestamp" in backup_info
        
        finally:
            # Ensure restoration in case of failure
            backup_manager.restore_vm_tags(vm["vmid"])
    
    @pytest.mark.live
    def test_tag_validation_workflow_live(self, live_proxmox_config, safe_test_vm, tag_backup):
        """Test tag validation in live environment"""
        vm = safe_test_vm
        
        # Backup original state
        tag_backup.backup_vm_tags(vm)
        
        try:
            # Test 1: Valid tags
            valid_tags = ["test-valid", "automation", "safe-delete"]
            valid_tags_str = tag_utils.format_tags(valid_tags)
            
            # Should parse and format correctly
            parsed_valid = tag_utils.parse_tags(valid_tags_str)
            assert set(parsed_valid) == set(valid_tags)
            
            formatted_valid = tag_utils.format_tags(parsed_valid)
            assert isinstance(formatted_valid, str)
            
            # Test 2: Edge case tags
            edge_tags = ["", "  ", "tag-with-hyphen", "tag_with_underscore"]
            cleaned_tags = [tag.strip() for tag in edge_tags if tag.strip()]
            
            if cleaned_tags:
                edge_tags_str = tag_utils.format_tags(cleaned_tags)
                parsed_edge = tag_utils.parse_tags(edge_tags_str)
                
                # Should handle edge cases gracefully
                assert isinstance(parsed_edge, list)
                assert all(tag.strip() for tag in parsed_edge)  # No empty tags
            
            # Test 3: Live update with edge cases
            if not live_config.dry_run_only and cleaned_tags:
                result = safe_tag_update(
                    vm["node"], vm["vmid"], edge_tags_str, vm["type"], tag_backup
                )
                assert "data" in result
                time.sleep(1)
                
                # Verify edge case handling
                config = proxmox_api.get_vm_config(vm["node"], vm["vmid"])
                retrieved_tags = tag_utils.parse_tags(config.get("tags", ""))
                
                # Should not contain empty or whitespace-only tags
                assert all(tag.strip() for tag in retrieved_tags)
        
        finally:
            # Restore original state
            if not live_config.dry_run_only:
                tag_backup.restore_vm_tags(vm["vmid"])
    
    @pytest.mark.live
    def test_error_handling_workflow_live(self, live_proxmox_config, test_vms):
        """Test error handling in live tag workflows"""
        if not test_vms:
            pytest.skip("No test VMs available")
        
        vm = test_vms[0]
        
        # Test 1: Invalid VMID
        with pytest.raises(Exception):  # Should raise HTTP error or similar
            proxmox_api.get_vm_config(vm["node"], 99999)  # Non-existent VMID
        
        # Test 2: Invalid node
        with pytest.raises(Exception):
            proxmox_api.get_vm_config("nonexistent-node", vm["vmid"])
        
        # Test 3: Invalid VM type for update
        with pytest.raises(ValueError):
            proxmox_api.update_vm_tags(vm["node"], vm["vmid"], "test", "invalid_type")
        
        # Test 4: Connection handling (if config allows)
        original_host = live_config.proxmox_config.get("PROXMOX_HOST")
        if original_host:
            # Test graceful handling of network issues
            # This is mainly to verify error propagation is correct
            try:
                vms = proxmox_api.get_all_vms()
                assert isinstance(vms, list)  # Should work normally
            except Exception as e:
                # If it fails, error should be informative
                assert str(e)  # Error message should exist
    
    @pytest.mark.live
    def test_concurrent_tag_operations_live(self, live_proxmox_config, test_vms, tag_backup):
        """Test concurrent tag operations safety"""
        if len(test_vms) < 2:
            pytest.skip("Need at least 2 test VMs for concurrent operations")
        
        # Use first 2 VMs
        vm1, vm2 = test_vms[:2]
        
        # Backup both VMs
        tag_backup.backup_multiple_vms([vm1, vm2])
        
        try:
            # Simulate concurrent operations by rapid updates
            test_tags1 = generate_test_tags()[:2]
            test_tags2 = [generate_test_tags()[2]]  # Different tag
            
            tags_str1 = tag_utils.format_tags(test_tags1)
            tags_str2 = tag_utils.format_tags(test_tags2)
            
            if not live_config.dry_run_only:
                # Update both VMs rapidly
                result1 = safe_tag_update(
                    vm1["node"], vm1["vmid"], tags_str1, vm1["type"], tag_backup
                )
                result2 = safe_tag_update(
                    vm2["node"], vm2["vmid"], tags_str2, vm2["type"], tag_backup
                )
                
                # Both should succeed
                assert "data" in result1
                assert "data" in result2
                
                time.sleep(2)
                
                # Verify both VMs have correct tags
                config1 = proxmox_api.get_vm_config(vm1["node"], vm1["vmid"])
                config2 = proxmox_api.get_vm_config(vm2["node"], vm2["vmid"])
                
                tags1 = tag_utils.parse_tags(config1.get("tags", ""))
                tags2 = tag_utils.parse_tags(config2.get("tags", ""))
                
                # VM1 should have test_tags1
                for tag in test_tags1:
                    assert tag in tags1
                
                # VM2 should have test_tags2
                for tag in test_tags2:
                    assert tag in tags2
                
                # VMs should not have each other's exclusive tags
                for tag in test_tags2:
                    assert tag not in tags1
                for tag in test_tags1:
                    assert tag not in tags2
        
        finally:
            # Restore both VMs
            if not live_config.dry_run_only:
                tag_backup.restore_all()
    
    @pytest.mark.live
    def test_tag_persistence_live(self, live_proxmox_config, safe_test_vm, tag_backup):
        """Test that tag changes persist across API calls"""
        vm = safe_test_vm
        
        # Backup original state
        tag_backup.backup_vm_tags(vm)
        
        try:
            # Step 1: Set tags
            persistence_tags = generate_test_tags()[:2]
            tags_str = tag_utils.format_tags(persistence_tags)
            
            if not live_config.dry_run_only:
                result = safe_tag_update(
                    vm["node"], vm["vmid"], tags_str, vm["type"], tag_backup
                )
                assert "data" in result
                time.sleep(1)
                
                # Step 2: Verify immediate persistence
                config1 = proxmox_api.get_vm_config(vm["node"], vm["vmid"])
                tags1 = tag_utils.parse_tags(config1.get("tags", ""))
                
                for tag in persistence_tags:
                    assert tag in tags1
                
                # Step 3: Wait and verify persistence over time
                time.sleep(3)
                
                config2 = proxmox_api.get_vm_config(vm["node"], vm["vmid"])
                tags2 = tag_utils.parse_tags(config2.get("tags", ""))
                
                # Tags should still be there
                for tag in persistence_tags:
                    assert tag in tags2
                
                # Step 4: Verify through VM list API
                all_vms = proxmox_api.get_all_vms()
                target_vm = next((v for v in all_vms if v["vmid"] == vm["vmid"]), None)
                
                if target_vm:
                    list_tags = tag_utils.parse_tags(target_vm.get("tags", ""))
                    for tag in persistence_tags:
                        assert tag in list_tags
        
        finally:
            # Restore original state
            if not live_config.dry_run_only:
                tag_backup.restore_vm_tags(vm["vmid"])


class TestLiveTagUtilityFunctions:
    """Test tag utility functions with live data"""
    
    @pytest.mark.live
    def test_extract_tags_from_live_vms(self, live_proxmox_config, test_vms):
        """Test tag extraction from live VM data"""
        if not test_vms:
            pytest.skip("No test VMs available")
        
        # Extract tags from all test VMs
        all_tags = tag_utils.extract_tags_from_vms(test_vms)
        
        # Should return a set
        assert isinstance(all_tags, set)
        
        # If any VM has tags, they should be in the extracted set
        for vm in test_vms:
            vm_tags = tag_utils.parse_tags(vm.get("tags", ""))
            for tag in vm_tags:
                if tag.strip():  # Ignore empty tags
                    assert tag in all_tags
    
    @pytest.mark.live
    def test_tag_formatting_consistency_live(self, live_proxmox_config, test_vms):
        """Test that tag formatting is consistent with live Proxmox format"""
        if not test_vms:
            pytest.skip("No test VMs available")
        
        # Find a VM with existing tags
        vm_with_tags = next((vm for vm in test_vms if vm.get("tags")), None)
        
        if vm_with_tags:
            original_tags_str = vm_with_tags["tags"]
            
            # Parse and reformat
            parsed_tags = tag_utils.parse_tags(original_tags_str)
            reformatted_tags = tag_utils.format_tags(parsed_tags)
            
            # Parse the reformatted tags
            reparsed_tags = tag_utils.parse_tags(reformatted_tags)
            
            # Should maintain tag content (order may differ)
            assert set(parsed_tags) == set(reparsed_tags)
    
    @pytest.mark.live
    def test_tag_normalization_live(self, live_proxmox_config):
        """Test tag normalization with live-like data"""
        # Test various tag formats that might come from live systems
        test_cases = [
            "production;web;frontend",  # Standard format
            "production; web ; frontend",  # With spaces
            "production;;web;frontend",  # Double semicolons
            ";production;web;frontend;",  # Leading/trailing semicolons
            "PRODUCTION;Web;FrontEnd",  # Mixed case
        ]
        
        for tags_str in test_cases:
            parsed = tag_utils.parse_tags(tags_str)
            formatted = tag_utils.format_tags(parsed)
            
            # Should be valid format
            assert isinstance(formatted, str)
            
            # Should not have empty tags
            reparsed = tag_utils.parse_tags(formatted)
            assert all(tag.strip() for tag in reparsed)
            
            # Should contain expected tag content
            expected_tags = {"production", "web", "frontend"}
            # Case handling depends on implementation
            normalized_tags = {tag.lower() for tag in reparsed if tag.strip()}
            assert expected_tags.issubset(normalized_tags) or expected_tags == {tag for tag in reparsed if tag.strip()}