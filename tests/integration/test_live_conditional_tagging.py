"""
Live integration tests for conditional tagging with real VM data

These tests verify that conditional tagging rules work correctly against
real Proxmox VMs. Tests are marked with @pytest.mark.live and require
PROXTAGGER_LIVE_TESTS=true to run.

Safety Features:
- Only operates on test VMs
- Backs up and restores VM states
- Uses dry-run mode by default
- Validates rule execution safely
"""

import pytest
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict

# Import conditional tagging modules
from modules.conditional_tags.models import ConditionalRule, RuleCondition, RuleConditionGroup, RuleAction
from modules.conditional_tags.engine import RuleEngine
from modules.conditional_tags.storage import RuleStorage, ExecutionHistory

# Import utilities
import tag_utils
import proxmox_api
from tests.live_config import (
    live_config, TagBackupManager, generate_test_tags,
    create_test_rule_data, safe_tag_update
)


class TestLiveConditionalTagging:
    """Live conditional tagging integration tests"""
    
    @pytest.mark.live
    def test_simple_rule_execution_live(self, live_proxmox_config, test_vms, temp_storage_file):
        """Test simple rule execution against live VMs"""
        if not test_vms:
            pytest.skip("No test VMs available")
        
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        backup_manager = TagBackupManager()
        
        # Backup all test VMs
        backup_manager.backup_multiple_vms(test_vms)
        
        try:
            # Create a simple rule: tag running VMs as "active"
            conditions = RuleConditionGroup(operator="AND")
            conditions.add_condition(RuleCondition("status", "equals", "running"))
            
            test_tags = generate_test_tags()[:2]
            actions = RuleAction(
                add_tags=test_tags,
                remove_tags=[],
                else_add_tags=["inactive-test"],
                else_remove_tags=[]
            )
            
            rule = ConditionalRule(
                name=f"Live Test Rule - {datetime.now().strftime('%H%M%S')}",
                description="Live test rule for running VMs",
                conditions=conditions,
                actions=actions
            )
            
            created_rule = storage.create_rule(rule)
            
            # Execute rule in dry-run mode first
            dry_result = engine.evaluate_rule(created_rule, test_vms, dry_run=True)
            
            assert dry_result.success
            assert dry_result.dry_run
            
            # Verify rule logic
            running_vms = [vm for vm in test_vms if vm.get("status") == "running"]
            stopped_vms = [vm for vm in test_vms if vm.get("status") != "running"]
            
            # Check matched VMs
            for vm in running_vms:
                assert vm["vmid"] in dry_result.matched_vms
            
            # Check THEN actions (running VMs should get test tags)
            for vm in running_vms:
                if vm["vmid"] in dry_result.tags_added:
                    for test_tag in test_tags:
                        assert test_tag in dry_result.tags_added[vm["vmid"]]
            
            # Check ELSE actions (stopped VMs should get inactive tag)
            for vm in stopped_vms:
                if vm["vmid"] in dry_result.tags_added:
                    assert "inactive-test" in dry_result.tags_added[vm["vmid"]]
            
            # If not in dry-run only mode, test actual execution
            if not live_config.dry_run_only and running_vms:
                live_result = engine.evaluate_rule(created_rule, test_vms, dry_run=False)
                
                assert live_result.success
                assert not live_result.dry_run
                
                # Wait for Proxmox to process updates
                time.sleep(2)
                
                # Verify actual tag updates
                for vm in running_vms[:1]:  # Test first running VM only for safety
                    updated_config = proxmox_api.get_vm_config(vm["node"], vm["vmid"])
                    updated_tags = tag_utils.parse_tags(updated_config.get("tags", ""))
                    
                    for test_tag in test_tags:
                        assert test_tag in updated_tags, f"Tag {test_tag} not found in VM {vm['vmid']}"
        
        finally:
            # Always restore original state
            if not live_config.dry_run_only:
                backup_manager.restore_all()
    
    @pytest.mark.live
    def test_complex_conditions_live(self, live_proxmox_config, test_vms, temp_storage_file):
        """Test complex conditional rules with live VM data"""
        if not test_vms:
            pytest.skip("No test VMs available")
        
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        
        # Create complex rule with multiple conditions
        # Rule: (status = running AND vmid > 100) OR (name contains "test")
        conditions = RuleConditionGroup(operator="OR")
        
        # First condition group: running AND vmid > 100
        group1 = RuleConditionGroup(operator="AND")
        group1.add_condition(RuleCondition("status", "equals", "running"))
        # Find a reasonable VMID threshold based on actual test VMs
        min_vmid = min(vm["vmid"] for vm in test_vms) if test_vms else 100
        threshold_vmid = min_vmid + 1
        group1.add_condition(RuleCondition("vmid", "greater_than", threshold_vmid))
        
        # Second condition: name contains "test"
        conditions.add_condition(RuleCondition("name", "contains", "test"))
        
        test_tags = generate_test_tags()[:1]
        actions = RuleAction(add_tags=test_tags)
        
        rule = ConditionalRule(
            name=f"Complex Live Rule - {datetime.now().strftime('%H%M%S')}",
            description="Complex rule testing multiple conditions",
            conditions=conditions,
            actions=actions
        )
        
        created_rule = storage.create_rule(rule)
        
        # Execute in dry-run mode
        result = engine.evaluate_rule(created_rule, test_vms, dry_run=True)
        
        assert result.success
        assert result.dry_run
        
        # Manually verify rule logic
        expected_matches = []
        for vm in test_vms:
            # Check first condition group: running AND vmid > threshold
            condition1_match = (vm.get("status") == "running" and vm.get("vmid", 0) > threshold_vmid)
            
            # Check second condition: name contains "test"
            condition2_match = "test" in vm.get("name", "").lower()
            
            # OR logic
            if condition1_match or condition2_match:
                expected_matches.append(vm["vmid"])
        
        # Verify engine results match our manual calculation
        assert set(result.matched_vms) == set(expected_matches)
    
    @pytest.mark.live
    def test_tag_based_conditions_live(self, live_proxmox_config, test_vms, temp_storage_file):
        """Test conditional rules based on existing tags"""
        if not test_vms:
            pytest.skip("No test VMs available")
        
        # Find VMs with existing tags
        vms_with_tags = [vm for vm in test_vms if vm.get("tags", "").strip()]
        
        if not vms_with_tags:
            pytest.skip("No test VMs with existing tags found")
        
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        backup_manager = TagBackupManager()
        
        # Get a common tag from test VMs or create one
        sample_vm = vms_with_tags[0]
        existing_tags = tag_utils.parse_tags(sample_vm.get("tags", ""))
        
        # Use first existing tag or create test condition
        if existing_tags:
            test_tag_condition = existing_tags[0]
        else:
            # Create a test tag temporarily
            test_tag_condition = generate_test_tags()[0]
            backup_manager.backup_vm_tags(sample_vm)
            
            try:
                current_tags = tag_utils.parse_tags(sample_vm.get("tags", ""))
                new_tags = current_tags + [test_tag_condition]
                new_tags_str = tag_utils.format_tags(new_tags)
                
                if not live_config.dry_run_only:
                    proxmox_api.update_vm_tags(
                        sample_vm["node"], sample_vm["vmid"], new_tags_str, sample_vm["type"]
                    )
                    time.sleep(1)
                    
                    # Update test_vms data
                    sample_vm["tags"] = new_tags_str
            except Exception:
                pytest.skip("Could not set up test tag condition")
        
        try:
            # Create rule based on tag condition
            conditions = RuleConditionGroup()
            conditions.add_condition(RuleCondition("tags", "contains", test_tag_condition))
            
            additional_test_tags = generate_test_tags()[1:3]  # Skip first tag
            actions = RuleAction(
                add_tags=additional_test_tags,
                else_add_tags=["no-condition-tag"]
            )
            
            rule = ConditionalRule(
                name=f"Tag-based Rule - {datetime.now().strftime('%H%M%S')}",
                description=f"Rule targeting VMs with '{test_tag_condition}' tag",
                conditions=conditions,
                actions=actions
            )
            
            created_rule = storage.create_rule(rule)
            
            # Execute rule
            result = engine.evaluate_rule(created_rule, test_vms, dry_run=True)
            
            assert result.success
            
            # Verify matches
            expected_matches = []
            for vm in test_vms:
                vm_tags = tag_utils.parse_tags(vm.get("tags", ""))
                if test_tag_condition in vm_tags:
                    expected_matches.append(vm["vmid"])
            
            assert set(result.matched_vms) == set(expected_matches)
            
            # Verify actions
            for vmid in expected_matches:
                if vmid in result.tags_added:
                    for tag in additional_test_tags:
                        assert tag in result.tags_added[vmid]
        
        finally:
            # Restore any changes made for test setup
            if not live_config.dry_run_only and backup_manager.backups:
                backup_manager.restore_all()
    
    @pytest.mark.live
    def test_rule_scheduling_simulation_live(self, live_proxmox_config, test_vms, temp_storage_file):
        """Test rule scheduling simulation with live VMs"""
        if not test_vms:
            pytest.skip("No test VMs available")
        
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        history = ExecutionHistory(temp_storage_file + "_history")
        
        # Create a simple scheduled rule
        conditions = RuleConditionGroup()
        conditions.add_condition(RuleCondition("type", "equals", "qemu"))  # Target QEMU VMs
        
        test_tags = generate_test_tags()[:1]
        actions = RuleAction(add_tags=test_tags)
        
        rule = ConditionalRule(
            name=f"Scheduled Rule - {datetime.now().strftime('%H%M%S')}",
            description="Simulated scheduled rule execution",
            conditions=conditions,
            actions=actions,
            schedule="0 */6 * * *",  # Every 6 hours
            enabled=True
        )
        
        created_rule = storage.create_rule(rule)
        
        # Simulate multiple scheduled executions
        execution_results = []
        
        for i in range(3):  # Simulate 3 executions
            result = engine.evaluate_rule(created_rule, test_vms, dry_run=True)
            execution_results.append(result)
            
            # Record execution in history
            history.add_execution(result)
            
            # Update rule stats
            storage.update_rule_stats(created_rule.id, result)
            
            # Small delay to ensure different timestamps
            time.sleep(0.1)
        
        # Verify all executions succeeded
        assert all(result.success for result in execution_results)
        
        # Verify consistent matching across executions
        first_matches = set(execution_results[0].matched_vms)
        for result in execution_results[1:]:
            assert set(result.matched_vms) == first_matches
        
        # Verify history was recorded
        rule_history = history.get_rule_history(created_rule.id)
        assert len(rule_history) == 3
        
        # Verify rule stats were updated
        updated_rule = storage.get_rule(created_rule.id)
        assert updated_rule.stats["total_executions"] == 3
        assert updated_rule.stats["total_matches"] == len(first_matches) * 3
    
    @pytest.mark.live
    def test_rule_performance_live(self, live_proxmox_config, test_vms, temp_storage_file):
        """Test rule execution performance with live VM data"""
        if not test_vms:
            pytest.skip("No test VMs available")
        
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        
        # Create multiple rules for performance testing
        rules = []
        
        # Rule 1: Simple status check
        rule1_conditions = RuleConditionGroup()
        rule1_conditions.add_condition(RuleCondition("status", "equals", "running"))
        rule1 = ConditionalRule(
            name="Performance Test Rule 1",
            conditions=rule1_conditions,
            actions=RuleAction(add_tags=[generate_test_tags()[0]])
        )
        rules.append(storage.create_rule(rule1))
        
        # Rule 2: VMID range check
        rule2_conditions = RuleConditionGroup()
        min_vmid = min(vm["vmid"] for vm in test_vms) if test_vms else 100
        max_vmid = max(vm["vmid"] for vm in test_vms) if test_vms else 200
        mid_vmid = (min_vmid + max_vmid) // 2
        rule2_conditions.add_condition(RuleCondition("vmid", "greater_than", mid_vmid))
        rule2 = ConditionalRule(
            name="Performance Test Rule 2",
            conditions=rule2_conditions,
            actions=RuleAction(add_tags=[generate_test_tags()[1]])
        )
        rules.append(storage.create_rule(rule2))
        
        # Rule 3: Name pattern check
        rule3_conditions = RuleConditionGroup()
        rule3_conditions.add_condition(RuleCondition("name", "contains", "test"))
        rule3 = ConditionalRule(
            name="Performance Test Rule 3",
            conditions=rule3_conditions,
            actions=RuleAction(add_tags=[generate_test_tags()[2]])
        )
        rules.append(storage.create_rule(rule3))
        
        # Measure execution time for each rule
        execution_times = []
        
        for rule in rules:
            start_time = time.time()
            result = engine.evaluate_rule(rule, test_vms, dry_run=True)
            end_time = time.time()
            
            execution_time = end_time - start_time
            execution_times.append(execution_time)
            
            # Verify successful execution
            assert result.success
            
            # Execution should be reasonably fast (under 5 seconds for small test sets)
            assert execution_time < 5.0, f"Rule execution took {execution_time:.2f}s, which is too slow"
        
        # Test batch execution performance
        start_time = time.time()
        batch_results = []
        for rule in rules:
            result = engine.evaluate_rule(rule, test_vms, dry_run=True)
            batch_results.append(result)
        end_time = time.time()
        
        batch_time = end_time - start_time
        assert all(result.success for result in batch_results)
        
        # Batch execution should not be significantly slower than sum of individual times
        individual_total = sum(execution_times)
        assert batch_time < individual_total * 1.5  # Allow 50% overhead for safety
    
    @pytest.mark.live
    def test_rule_validation_live(self, live_proxmox_config, test_vms, temp_storage_file):
        """Test rule validation with live VM data"""
        if not test_vms:
            pytest.skip("No test VMs available")
        
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        
        # Test 1: Valid rule with live-compatible conditions
        valid_conditions = RuleConditionGroup()
        
        # Use field that exists in test VMs
        sample_vm = test_vms[0]
        if "status" in sample_vm:
            valid_conditions.add_condition(RuleCondition("status", "equals", sample_vm["status"]))
        elif "type" in sample_vm:
            valid_conditions.add_condition(RuleCondition("type", "equals", sample_vm["type"]))
        else:
            pytest.skip("Test VMs don't have standard fields for validation testing")
        
        valid_actions = RuleAction(add_tags=generate_test_tags()[:1])
        valid_rule = ConditionalRule(
            name="Valid Live Rule",
            conditions=valid_conditions,
            actions=valid_actions
        )
        
        # Should create successfully
        created_rule = storage.create_rule(valid_rule)
        assert created_rule.name == "Valid Live Rule"
        
        # Should execute successfully
        result = engine.evaluate_rule(created_rule, test_vms, dry_run=True)
        assert result.success
        
        # Test 2: Rule with non-existent field
        invalid_conditions = RuleConditionGroup()
        invalid_conditions.add_condition(RuleCondition("nonexistent_field", "equals", "value"))
        invalid_actions = RuleAction(add_tags=["test-tag"])
        
        invalid_rule = ConditionalRule(
            name="Invalid Field Rule",
            conditions=invalid_conditions,
            actions=invalid_actions
        )
        
        created_invalid_rule = storage.create_rule(invalid_rule)
        
        # Should execute but match no VMs
        result = engine.evaluate_rule(created_invalid_rule, test_vms, dry_run=True)
        assert result.success  # Execution succeeds
        assert len(result.matched_vms) == 0  # But matches nothing
    
    @pytest.mark.live
    def test_rule_error_recovery_live(self, live_proxmox_config, test_vms, temp_storage_file):
        """Test rule engine error recovery with live data"""
        if not test_vms:
            pytest.skip("No test VMs available")
        
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        backup_manager = TagBackupManager()
        
        # Create a rule that will work
        working_conditions = RuleConditionGroup()
        working_conditions.add_condition(RuleCondition("status", "equals", "running"))
        working_actions = RuleAction(add_tags=generate_test_tags()[:1])
        
        working_rule = ConditionalRule(
            name="Working Rule",
            conditions=working_conditions,
            actions=working_actions
        )
        
        created_working_rule = storage.create_rule(working_rule)
        
        # Test normal execution
        result1 = engine.evaluate_rule(created_working_rule, test_vms, dry_run=True)
        assert result1.success
        
        # Test with potentially problematic VM data
        problematic_vms = test_vms.copy()
        
        # Add VM with missing required fields
        problematic_vms.append({
            "vmid": 99999,
            "name": "problematic-vm",
            # Missing other fields intentionally
        })
        
        # Should handle gracefully
        result2 = engine.evaluate_rule(created_working_rule, problematic_vms, dry_run=True)
        assert result2.success  # Should not crash
        
        # Original VMs should still be processed correctly
        running_original_vms = [vm for vm in test_vms if vm.get("status") == "running"]
        for vm in running_original_vms:
            assert vm["vmid"] in result2.matched_vms
        
        # Problematic VM should not match (due to missing status field)
        assert 99999 not in result2.matched_vms
    
    @pytest.mark.live
    def test_full_conditional_workflow_live(self, live_proxmox_config, test_vms, temp_storage_file):
        """Test complete conditional tagging workflow with live VMs"""
        if not test_vms:
            pytest.skip("No test VMs available")
        
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        history = ExecutionHistory(temp_storage_file + "_history")
        backup_manager = TagBackupManager()
        
        # Backup all test VMs
        backup_manager.backup_multiple_vms(test_vms)
        
        try:
            # Phase 1: Create and validate rule
            conditions = RuleConditionGroup(operator="OR")
            conditions.add_condition(RuleCondition("status", "equals", "running"))
            conditions.add_condition(RuleCondition("name", "contains", "test"))
            
            test_tags = generate_test_tags()[:2]
            actions = RuleAction(
                add_tags=test_tags,
                else_add_tags=["workflow-else-tag"]
            )
            
            rule = ConditionalRule(
                name=f"Full Workflow Rule - {datetime.now().strftime('%H%M%S')}",
                description="Complete workflow test rule",
                conditions=conditions,
                actions=actions,
                enabled=True
            )
            
            created_rule = storage.create_rule(rule)
            assert created_rule.enabled
            
            # Phase 2: Execute rule (dry-run)
            dry_result = engine.evaluate_rule(created_rule, test_vms, dry_run=True)
            assert dry_result.success
            assert dry_result.dry_run
            
            # Record dry-run execution
            history.add_execution(dry_result)
            storage.update_rule_stats(created_rule.id, dry_result)
            
            # Phase 3: If conditions allow, execute live
            if not live_config.dry_run_only and dry_result.matched_vms:
                # Execute on first matched VM only for safety
                single_vm = next(vm for vm in test_vms if vm["vmid"] in dry_result.matched_vms[:1])
                single_vm_list = [single_vm]
                
                live_result = engine.evaluate_rule(created_rule, single_vm_list, dry_run=False)
                assert live_result.success
                assert not live_result.dry_run
                
                # Record live execution
                history.add_execution(live_result)
                storage.update_rule_stats(created_rule.id, live_result)
                
                # Wait and verify
                time.sleep(2)
                updated_config = proxmox_api.get_vm_config(single_vm["node"], single_vm["vmid"])
                updated_tags = tag_utils.parse_tags(updated_config.get("tags", ""))
                
                # Should contain test tags
                for test_tag in test_tags:
                    assert test_tag in updated_tags
            
            # Phase 4: Verify history and stats
            rule_history = history.get_rule_history(created_rule.id)
            assert len(rule_history) >= 1  # At least dry-run execution
            
            updated_rule = storage.get_rule(created_rule.id)
            assert updated_rule.stats["total_executions"] >= 1
            
            # Phase 5: Update rule
            rule_updates = {
                "description": "Updated workflow test rule",
                "enabled": False
            }
            
            final_rule = storage.update_rule(created_rule.id, rule_updates)
            assert final_rule.description == "Updated workflow test rule"
            assert not final_rule.enabled
            
            # Phase 6: Clean up rule
            delete_success = storage.delete_rule(created_rule.id)
            assert delete_success
            assert storage.get_rule(created_rule.id) is None
        
        finally:
            # Always restore VM states
            if not live_config.dry_run_only:
                backup_manager.restore_all()


class TestLiveConditionalTaggingEdgeCases:
    """Test edge cases in conditional tagging with live data"""
    
    @pytest.mark.live
    def test_empty_rule_results_live(self, live_proxmox_config, test_vms, temp_storage_file):
        """Test rules that match no VMs"""
        if not test_vms:
            pytest.skip("No test VMs available")
        
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        
        # Create rule that should match nothing
        conditions = RuleConditionGroup()
        conditions.add_condition(RuleCondition("vmid", "equals", 999999))  # Non-existent VMID
        
        actions = RuleAction(add_tags=generate_test_tags()[:1])
        
        rule = ConditionalRule(
            name="No Match Rule",
            conditions=conditions,
            actions=actions
        )
        
        created_rule = storage.create_rule(rule)
        result = engine.evaluate_rule(created_rule, test_vms, dry_run=True)
        
        assert result.success
        assert len(result.matched_vms) == 0
        assert len(result.tags_added) == 0 or all(not tags for tags in result.tags_added.values())
    
    @pytest.mark.live
    def test_all_vms_match_rule_live(self, live_proxmox_config, test_vms, temp_storage_file):
        """Test rules that match all VMs"""
        if not test_vms:
            pytest.skip("No test VMs available")
        
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        
        # Create rule that should match all VMs (using vmid > 0)
        conditions = RuleConditionGroup()
        conditions.add_condition(RuleCondition("vmid", "greater_than", 0))
        
        actions = RuleAction(add_tags=generate_test_tags()[:1])
        
        rule = ConditionalRule(
            name="Match All Rule",
            conditions=conditions,
            actions=actions
        )
        
        created_rule = storage.create_rule(rule)
        result = engine.evaluate_rule(created_rule, test_vms, dry_run=True)
        
        assert result.success
        assert len(result.matched_vms) == len(test_vms)
        
        # All test VM IDs should be in matched list
        test_vm_ids = {vm["vmid"] for vm in test_vms}
        matched_vm_ids = set(result.matched_vms)
        assert matched_vm_ids == test_vm_ids
    
    @pytest.mark.live
    def test_rule_with_mixed_vm_types_live(self, live_proxmox_config, test_vms, temp_storage_file):
        """Test rules with mixed QEMU and LXC VMs"""
        if not test_vms:
            pytest.skip("No test VMs available")
        
        # Check if we have mixed VM types
        vm_types = {vm.get("type") for vm in test_vms}
        
        if len(vm_types) < 2:
            pytest.skip("Need mixed VM types (QEMU and LXC) for this test")
        
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        
        # Rule 1: Target only QEMU VMs
        qemu_conditions = RuleConditionGroup()
        qemu_conditions.add_condition(RuleCondition("type", "equals", "qemu"))
        
        qemu_rule = ConditionalRule(
            name="QEMU Only Rule",
            conditions=qemu_conditions,
            actions=RuleAction(add_tags=["qemu-test"])
        )
        
        created_qemu_rule = storage.create_rule(qemu_rule)
        qemu_result = engine.evaluate_rule(created_qemu_rule, test_vms, dry_run=True)
        
        assert qemu_result.success
        
        # Should only match QEMU VMs
        qemu_vms = [vm for vm in test_vms if vm.get("type") == "qemu"]
        qemu_vm_ids = {vm["vmid"] for vm in qemu_vms}
        matched_qemu_ids = set(qemu_result.matched_vms)
        assert matched_qemu_ids == qemu_vm_ids
        
        # Rule 2: Target only LXC containers
        lxc_conditions = RuleConditionGroup()
        lxc_conditions.add_condition(RuleCondition("type", "equals", "lxc"))
        
        lxc_rule = ConditionalRule(
            name="LXC Only Rule",
            conditions=lxc_conditions,
            actions=RuleAction(add_tags=["lxc-test"])
        )
        
        created_lxc_rule = storage.create_rule(lxc_rule)
        lxc_result = engine.evaluate_rule(created_lxc_rule, test_vms, dry_run=True)
        
        assert lxc_result.success
        
        # Should only match LXC VMs
        lxc_vms = [vm for vm in test_vms if vm.get("type") == "lxc"]
        lxc_vm_ids = {vm["vmid"] for vm in lxc_vms}
        matched_lxc_ids = set(lxc_result.matched_vms)
        assert matched_lxc_ids == lxc_vm_ids
        
        # Verify no overlap
        assert not (matched_qemu_ids & matched_lxc_ids)  # No intersection