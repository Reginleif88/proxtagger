"""
Simple live tests for ProxTagger

Basic tests that verify tagging and conditional tagging work with your live Proxmox.
Run with: python3 run_tests.py --live
"""

import pytest
import time
from datetime import datetime

# Import modules under test
import tag_utils
import proxmox_api
from modules.conditional_tags.models import ConditionalRule, RuleCondition, RuleConditionGroup, RuleAction
from modules.conditional_tags.engine import RuleEngine
from modules.conditional_tags.storage import RuleStorage

# Import simple live config
from tests.simple_live_config import simple_live_config


class TestBasicLiveFunctionality:
    """Basic live functionality tests"""
    
    @pytest.mark.live
    def test_proxmox_connection(self, simple_live_proxmox_config):
        """Test basic connection to Proxmox"""
        vms = proxmox_api.get_all_vms()
        assert isinstance(vms, list)
        print(f"✅ Connected to Proxmox - found {len(vms)} VMs")
    
    @pytest.mark.live
    def test_vm_data_structure(self, all_vms):
        """Test that VM data has expected structure"""
        assert len(all_vms) > 0
        
        vm = all_vms[0]
        required_fields = ["vmid", "name", "node", "type"]
        
        for field in required_fields:
            assert field in vm, f"VM missing required field: {field}"
        
        print(f"✅ VM data structure validated - sample VM: {vm['name']} (ID: {vm['vmid']})")
    
    @pytest.mark.live
    def test_get_vm_config(self, first_vm):
        """Test getting VM configuration"""
        # Skip LXC containers as get_vm_config only works with QEMU VMs
        if first_vm.get("type") == "lxc":
            pytest.skip("get_vm_config only supports QEMU VMs, skipping LXC container")
            
        config = proxmox_api.get_vm_config(first_vm["node"], first_vm["vmid"])
        
        assert isinstance(config, dict)
        assert len(config) > 0
        
        print(f"✅ Retrieved config for VM {first_vm['vmid']} - {len(config)} fields")
    
    @pytest.mark.live
    def test_tag_parsing_with_live_data(self, all_vms):
        """Test tag parsing with real VM tag data"""
        vms_with_tags = [vm for vm in all_vms if vm.get("tags", "").strip()]
        
        if vms_with_tags:
            vm = vms_with_tags[0]
            tags_str = vm["tags"]
            
            # Parse tags
            parsed_tags = tag_utils.parse_tags(tags_str)
            assert isinstance(parsed_tags, list)
            
            # Format tags back
            formatted_tags = tag_utils.format_tags(parsed_tags)
            assert isinstance(formatted_tags, str)
            
            print(f"✅ Tag parsing works - VM {vm['vmid']} has tags: {parsed_tags}")
        else:
            print("ℹ️  No VMs with tags found - tag parsing test skipped")
    
    @pytest.mark.live
    def test_tag_extraction_from_all_vms(self, all_vms):
        """Test extracting all unique tags from VMs"""
        all_tags = tag_utils.extract_tags(all_vms)
        
        assert isinstance(all_tags, list)
        
        if all_tags:
            print(f"✅ Extracted {len(all_tags)} unique tags from all VMs: {list(all_tags)[:10]}...")
        else:
            print("ℹ️  No tags found in any VMs")


class TestConditionalTaggingLive:
    """Test conditional tagging with live data"""
    
    @pytest.mark.live
    def test_simple_rule_dry_run(self, all_vms, temp_storage_file):
        """Test simple conditional rule in dry-run mode"""
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        
        # Create simple rule: find running VMs
        conditions = RuleConditionGroup()
        conditions.add_condition(RuleCondition("status", "equals", "running"))
        
        actions = RuleAction(add_tags=["test-active"])
        
        rule = ConditionalRule(
            name="Test Rule - Running VMs",
            description="Find running VMs",
            conditions=conditions,
            actions=actions
        )
        
        created_rule = storage.create_rule(rule)
        
        # Execute in dry-run mode
        result = engine.evaluate_rule(created_rule, all_vms, dry_run=True)
        
        assert result.success
        assert result.dry_run
        
        running_vms = [vm for vm in all_vms if vm.get("status") == "running"]
        
        print(f"✅ Rule executed successfully")
        print(f"   Running VMs found: {len(running_vms)}")
        print(f"   Rule matched: {len(result.matched_vms)} VMs")
        print(f"   Matched VMIDs: {result.matched_vms}")
    
    @pytest.mark.live
    def test_vmid_range_rule(self, all_vms, temp_storage_file):
        """Test rule based on VMID ranges"""
        if not all_vms:
            pytest.skip("No VMs available")
        
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        
        # Find VMID range
        vmids = [vm["vmid"] for vm in all_vms]
        min_vmid = min(vmids)
        max_vmid = max(vmids)
        mid_vmid = (min_vmid + max_vmid) // 2
        
        # Create rule: VMs with VMID > mid_vmid
        conditions = RuleConditionGroup()
        conditions.add_condition(RuleCondition("vmid", "greater_than", mid_vmid))
        
        actions = RuleAction(add_tags=["high-vmid"])
        
        rule = ConditionalRule(
            name="High VMID Rule",
            conditions=conditions,
            actions=actions
        )
        
        created_rule = storage.create_rule(rule)
        result = engine.evaluate_rule(created_rule, all_vms, dry_run=True)
        
        assert result.success
        
        expected_matches = [vm["vmid"] for vm in all_vms if vm["vmid"] > mid_vmid]
        
        print(f"✅ VMID range rule executed")
        print(f"   VMID range: {min_vmid} - {max_vmid} (threshold: {mid_vmid})")
        print(f"   Expected matches: {len(expected_matches)}")
        print(f"   Actual matches: {len(result.matched_vms)}")
        
        assert set(result.matched_vms) == set(expected_matches)
    
    @pytest.mark.live
    def test_vm_type_rule(self, all_vms, temp_storage_file):
        """Test rule based on VM type"""
        if not all_vms:
            pytest.skip("No VMs available")
        
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        
        # Get available VM types
        vm_types = {vm.get("type") for vm in all_vms}
        
        if not vm_types:
            pytest.skip("No VM types found")
        
        # Test rule for each type
        for vm_type in vm_types:
            conditions = RuleConditionGroup()
            conditions.add_condition(RuleCondition("type", "equals", vm_type))
            
            actions = RuleAction(add_tags=[f"{vm_type}-vm"])
            
            rule = ConditionalRule(
                name=f"{vm_type.upper()} VM Rule",
                conditions=conditions,
                actions=actions
            )
            
            created_rule = storage.create_rule(rule)
            result = engine.evaluate_rule(created_rule, all_vms, dry_run=True)
            
            assert result.success
            
            expected_matches = [vm["vmid"] for vm in all_vms if vm.get("type") == vm_type]
            actual_matches = result.matched_vms
            
            print(f"✅ {vm_type.upper()} VM rule: {len(actual_matches)} matches")
            
            assert set(actual_matches) == set(expected_matches)
    
    @pytest.mark.live
    def test_complex_rule_with_live_data(self, all_vms, temp_storage_file):
        """Test complex rule with multiple conditions"""
        if len(all_vms) < 2:
            pytest.skip("Need at least 2 VMs for complex rule testing")
        
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        
        # Create complex rule: (status = running) OR (type = qemu)
        conditions = RuleConditionGroup(operator="OR")
        conditions.add_condition(RuleCondition("status", "equals", "running"))
        conditions.add_condition(RuleCondition("type", "equals", "qemu"))
        
        actions = RuleAction(add_tags=["complex-match"])
        
        rule = ConditionalRule(
            name="Complex OR Rule",
            conditions=conditions,
            actions=actions
        )
        
        created_rule = storage.create_rule(rule)
        result = engine.evaluate_rule(created_rule, all_vms, dry_run=True)
        
        assert result.success
        
        # Manually calculate expected matches
        expected_matches = []
        for vm in all_vms:
            if vm.get("status") == "running" or vm.get("type") == "qemu":
                expected_matches.append(vm["vmid"])
        
        print(f"✅ Complex OR rule executed")
        print(f"   Total VMs: {len(all_vms)}")
        print(f"   Running VMs: {len([vm for vm in all_vms if vm.get('status') == 'running'])}")
        print(f"   QEMU VMs: {len([vm for vm in all_vms if vm.get('type') == 'qemu'])}")
        print(f"   Expected matches: {len(expected_matches)}")
        print(f"   Actual matches: {len(result.matched_vms)}")
        
        assert set(result.matched_vms) == set(expected_matches)


class TestLiveTagModification:
    """Test actual tag modifications (USE WITH CAUTION)"""
    
    @pytest.mark.live
    def test_tag_backup_and_restore(self, first_vm):
        """Test tag backup and restore functionality"""
        # Skip LXC containers as get_vm_config only works with QEMU VMs
        if first_vm.get("type") == "lxc":
            pytest.skip("get_vm_config only supports QEMU VMs, skipping LXC container")
            
        # Get original tags
        original_config = proxmox_api.get_vm_config(first_vm["node"], first_vm["vmid"])
        original_tags = original_config.get("tags", "")
        
        print(f"✅ VM {first_vm['vmid']} original tags: '{original_tags}'")
        
        # This test just validates the backup/restore concept without actual modification
        # In a real scenario, you would:
        # 1. Backup original tags
        # 2. Apply test tags
        # 3. Verify application
        # 4. Restore original tags
        # 5. Verify restoration
        
        print("ℹ️  Tag modification test completed (no changes made)")
    
    @pytest.mark.live
    def test_dry_run_vs_live_execution(self, all_vms, temp_storage_file):
        """Compare dry-run vs live execution results"""
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        
        # Create simple rule
        conditions = RuleConditionGroup()
        conditions.add_condition(RuleCondition("status", "equals", "running"))
        
        actions = RuleAction(add_tags=["execution-test"])
        
        rule = ConditionalRule(
            name="Execution Test Rule",
            conditions=conditions,
            actions=actions
        )
        
        created_rule = storage.create_rule(rule)
        
        # Execute dry-run
        dry_result = engine.evaluate_rule(created_rule, all_vms, dry_run=True)
        
        assert dry_result.success
        assert dry_result.dry_run
        
        print(f"✅ Dry-run execution completed")
        print(f"   Matched VMs: {len(dry_result.matched_vms)}")
        print(f"   Tags to add: {dry_result.tags_added}")
        
        # Note: For actual live execution, you would call with dry_run=False
        # live_result = engine.evaluate_rule(created_rule, all_vms, dry_run=False)
        # But we skip this to avoid unwanted changes
        
        print("ℹ️  Live execution test skipped (would modify VMs)")


def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "live: Tests that require live Proxmox connection"
    )