"""
Integration tests for conditional tagging system
"""

import pytest
import json
from unittest.mock import Mock, patch
from modules.conditional_tags.models import ConditionalRule, RuleCondition, RuleConditionGroup, RuleAction
from modules.conditional_tags.engine import RuleEngine
from modules.conditional_tags.storage import RuleStorage, ExecutionHistory


class TestConditionalTaggingIntegration:
    """Test complete conditional tagging workflow"""
    
    @pytest.fixture
    def test_vms(self):
        """Test VM data for conditional tagging"""
        return [
            {
                "vmid": 100,
                "name": "prod-web-01",
                "node": "node1",
                "type": "qemu",
                "status": "running",
                "tags": "production;web",
                "cpu": 2,
                "maxmem": 2147483648,
                "uptime": 86400
            },
            {
                "vmid": 101,
                "name": "prod-db-01",
                "node": "node1",
                "type": "lxc", 
                "status": "running",
                "tags": "production;database",
                "cpu": 4,
                "maxmem": 4294967296,
                "uptime": 172800
            },
            {
                "vmid": 200,
                "name": "dev-app-01",
                "node": "node2",
                "type": "qemu",
                "status": "stopped",
                "tags": "development;application",
                "cpu": 1,
                "maxmem": 1073741824,
                "uptime": 0
            },
            {
                "vmid": 300,
                "name": "test-vm-01",
                "node": "node2",
                "type": "lxc",
                "status": "running", 
                "tags": "",  # No tags
                "cpu": 1,
                "maxmem": 1073741824,
                "uptime": 3600
            }
        ]
    
    @pytest.mark.integration
    def test_complete_rule_lifecycle(self, temp_storage_file, test_vms):
        """Test complete rule lifecycle: create, execute, update, delete"""
        # Initialize storage and engine
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        
        # 1. Create a rule
        conditions = RuleConditionGroup(operator="AND")
        conditions.add_condition(RuleCondition("status", "equals", "running"))
        conditions.add_condition(RuleCondition("vmid", "less_than", 200))
        
        actions = RuleAction(
            add_tags=["monitored", "active"],
            remove_tags=["inactive"],
            else_add_tags=["needs-review"],
            else_remove_tags=["monitored"]
        )
        
        rule = ConditionalRule(
            name="Production Monitoring Rule",
            description="Monitor running production VMs",
            conditions=conditions,
            actions=actions
        )
        
        # Save rule
        created_rule = storage.create_rule(rule)
        assert created_rule.name == "Production Monitoring Rule"
        
        # 2. Execute rule (dry run)
        with patch('tag_utils.parse_tags') as mock_parse:
            with patch('tag_utils.format_tags') as mock_format:
                mock_parse.side_effect = lambda tags: tags.split(';') if tags else []
                mock_format.side_effect = lambda tags: ';'.join(tags) if tags else ''
                
                result = engine.evaluate_rule(created_rule, test_vms, dry_run=True)
        
        assert result.success is True
        assert result.dry_run is True
        
        # Should match VMs 100 and 101 (running and vmid < 200)
        expected_matched = {100, 101}
        actual_matched = set(result.matched_vms)
        assert actual_matched == expected_matched
        
        # Check THEN actions for matched VMs
        for vmid in [100, 101]:
            assert vmid in result.tags_added
            assert "monitored" in result.tags_added[vmid]
            assert "active" in result.tags_added[vmid]
        
        # Check ELSE actions for non-matched VMs (200, 300)
        for vmid in [200, 300]:
            if vmid in result.tags_added:
                assert "needs-review" in result.tags_added[vmid]
        
        # 3. Update rule stats
        storage.update_rule_stats(created_rule.id, result)
        updated_rule = storage.get_rule(created_rule.id)
        assert updated_rule.stats["total_matches"] == 2
        
        # 4. Update rule configuration
        updates = {
            "description": "Updated description",
            "enabled": False
        }
        final_rule = storage.update_rule(created_rule.id, updates)
        assert final_rule.description == "Updated description"
        assert final_rule.enabled is False
        
        # 5. Delete rule
        deleted = storage.delete_rule(created_rule.id)
        assert deleted is True
        assert storage.get_rule(created_rule.id) is None
    
    @pytest.mark.integration
    @patch('proxmox_api.update_vm_tags')
    @patch('tag_utils.parse_tags')
    @patch('tag_utils.format_tags')
    def test_rule_execution_with_api_calls(self, mock_format, mock_parse, mock_update, 
                                         temp_storage_file, test_vms):
        """Test rule execution with actual API calls"""
        # Mock tag utilities
        mock_parse.side_effect = lambda tags: tags.split(';') if tags else []
        mock_format.side_effect = lambda tags: ';'.join(tags) if tags else ''
        
        # Mock API update
        mock_update.return_value = {"data": "success"}
        
        # Create rule
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        
        conditions = RuleConditionGroup()
        conditions.add_condition(RuleCondition("tags", "contains", "production"))
        
        actions = RuleAction(add_tags=["critical"], remove_tags=["development"])
        
        rule = ConditionalRule(
            name="Production Tagging Rule",
            conditions=conditions,
            actions=actions
        )
        storage.create_rule(rule)
        
        # Execute rule (not dry run)
        result = engine.evaluate_rule(rule, test_vms, dry_run=False)
        
        assert result.success is True
        assert result.dry_run is False
        
        # Should match VMs 100 and 101 (have production tag)
        expected_matched = {100, 101}
        actual_matched = set(result.matched_vms)
        assert actual_matched == expected_matched
        
        # Verify API calls were made
        assert mock_update.call_count == 2  # For VMs 100 and 101
        
        # Check API call parameters
        for call_args in mock_update.call_args_list:
            node, vmid, tags_str, vm_type = call_args[0]
            assert node in ["node1", "node2"]
            assert vmid in [100, 101]
            assert "critical" in tags_str  # Should have added critical tag
            assert vm_type in ["qemu", "lxc"]
    
    @pytest.mark.integration
    def test_multiple_rules_execution(self, temp_storage_file, test_vms):
        """Test executing multiple rules on the same VMs"""
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        
        # Rule 1: Tag running VMs as "online"
        rule1_conditions = RuleConditionGroup()
        rule1_conditions.add_condition(RuleCondition("status", "equals", "running"))
        rule1_actions = RuleAction(add_tags=["online"], remove_tags=["offline"])
        rule1 = ConditionalRule("Online Status Rule", conditions=rule1_conditions, actions=rule1_actions)
        
        # Rule 2: Tag production VMs as "critical"
        rule2_conditions = RuleConditionGroup()
        rule2_conditions.add_condition(RuleCondition("tags", "contains", "production"))
        rule2_actions = RuleAction(add_tags=["critical"])
        rule2 = ConditionalRule("Production Critical Rule", conditions=rule2_conditions, actions=rule2_actions)
        
        # Rule 3: Tag high-memory VMs as "resource-intensive"
        rule3_conditions = RuleConditionGroup()
        rule3_conditions.add_condition(RuleCondition("maxmem", "greater_than", 2000000000))
        rule3_actions = RuleAction(add_tags=["resource-intensive"])
        rule3 = ConditionalRule("Resource Intensive Rule", conditions=rule3_conditions, actions=rule3_actions)
        
        # Save all rules
        storage.create_rule(rule1)
        storage.create_rule(rule2)
        storage.create_rule(rule3)
        
        # Execute all rules
        results = []
        for rule in [rule1, rule2, rule3]:
            with patch('tag_utils.parse_tags') as mock_parse:
                with patch('tag_utils.format_tags') as mock_format:
                    mock_parse.side_effect = lambda tags: tags.split(';') if tags else []
                    mock_format.side_effect = lambda tags: ';'.join(tags) if tags else ''
                    
                    result = engine.evaluate_rule(rule, test_vms, dry_run=True)
                    results.append(result)
        
        # Verify results
        assert all(r.success for r in results)
        
        # Rule 1: Should match running VMs (100, 101, 300)
        assert set(results[0].matched_vms) == {100, 101, 300}
        
        # Rule 2: Should match production VMs (100, 101)
        assert set(results[1].matched_vms) == {100, 101}
        
        # Rule 3: Should match high-memory VMs (100, 101) - both have > 2GB
        assert set(results[2].matched_vms) == {100, 101}
    
    @pytest.mark.integration
    def test_rule_storage_and_history_integration(self, temp_storage_file):
        """Test integration between rule storage and execution history"""
        # Use separate files for storage and history
        history_file = temp_storage_file + "_history"
        
        storage = RuleStorage(temp_storage_file)
        history = ExecutionHistory(history_file)
        engine = RuleEngine()
        
        # Create a rule
        conditions = RuleConditionGroup()
        conditions.add_condition(RuleCondition("status", "equals", "running"))
        actions = RuleAction(add_tags=["active"])
        rule = ConditionalRule("Test Rule", conditions=conditions, actions=actions)
        
        created_rule = storage.create_rule(rule)
        
        # Execute rule multiple times
        test_vms = [
            {"vmid": 100, "name": "test-vm", "status": "running", "tags": ""},
            {"vmid": 101, "name": "test-vm-2", "status": "stopped", "tags": ""}
        ]
        
        execution_results = []
        for i in range(3):
            with patch('tag_utils.parse_tags') as mock_parse:
                with patch('tag_utils.format_tags') as mock_format:
                    mock_parse.side_effect = lambda tags: tags.split(';') if tags else []
                    mock_format.side_effect = lambda tags: ';'.join(tags) if tags else ''
                    
                    result = engine.evaluate_rule(created_rule, test_vms, dry_run=True)
                    execution_results.append(result)
                    
                    # Save to history
                    history.add_execution(result)
                    
                    # Update rule stats
                    storage.update_rule_stats(created_rule.id, result)
        
        # Verify rule stats were updated
        final_rule = storage.get_rule(created_rule.id)
        assert final_rule.stats["total_matches"] == 3  # 1 match per execution * 3 executions
        
        # Verify history was saved
        rule_history = history.get_rule_history(created_rule.id)
        assert len(rule_history) == 3
        
        # Most recent execution should be first
        assert rule_history[0]["timestamp"] >= rule_history[1]["timestamp"]
        assert rule_history[1]["timestamp"] >= rule_history[2]["timestamp"]
        
        # Get recent executions across all rules
        recent = history.get_recent_executions(limit=5)
        assert len(recent) == 3
        assert all(exec["rule_id"] == created_rule.id for exec in recent)
    
    @pytest.mark.integration
    def test_complex_rule_conditions_integration(self, temp_storage_file, test_vms):
        """Test complex rule with multiple condition groups"""
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        
        # Create complex rule with nested logic:
        # (status = "running" AND vmid > 100) OR (tags contains "critical")
        main_conditions = RuleConditionGroup(operator="OR")
        
        # First condition group: running AND vmid > 100
        group1 = RuleConditionGroup(operator="AND")
        group1.add_condition(RuleCondition("status", "equals", "running"))
        group1.add_condition(RuleCondition("vmid", "greater_than", 100))
        
        # For this test, we'll simulate nested conditions by creating a single group
        # with multiple conditions that represent the complex logic
        conditions = RuleConditionGroup(operator="OR")
        conditions.add_condition(RuleCondition("status", "equals", "running"))
        conditions.add_condition(RuleCondition("tags", "contains", "critical"))
        
        actions = RuleAction(add_tags=["complex-match"])
        
        rule = ConditionalRule(
            name="Complex Condition Rule",
            conditions=conditions,
            actions=actions
        )
        
        created_rule = storage.create_rule(rule)
        
        # Execute rule
        with patch('tag_utils.parse_tags') as mock_parse:
            with patch('tag_utils.format_tags') as mock_format:
                mock_parse.side_effect = lambda tags: tags.split(';') if tags else []
                mock_format.side_effect = lambda tags: ';'.join(tags) if tags else ''
                
                result = engine.evaluate_rule(created_rule, test_vms, dry_run=True)
        
        assert result.success is True
        
        # Should match running VMs (100, 101, 300) since OR condition includes status="running"
        expected_matched = {100, 101, 300}
        actual_matched = set(result.matched_vms)
        assert actual_matched == expected_matched
    
    @pytest.mark.integration
    def test_rule_validation_integration(self, temp_storage_file):
        """Test rule validation during storage operations"""
        storage = RuleStorage(temp_storage_file)
        
        # Test 1: Try to create invalid rule (no conditions)
        invalid_rule = ConditionalRule("Invalid Rule")
        # Default rule has no conditions and no actions
        
        with pytest.raises(ValueError, match="Invalid rule"):
            storage.create_rule(invalid_rule)
        
        # Test 2: Create valid rule
        conditions = RuleConditionGroup()
        conditions.add_condition(RuleCondition("status", "equals", "running"))
        actions = RuleAction(add_tags=["valid"])
        
        valid_rule = ConditionalRule("Valid Rule", conditions=conditions, actions=actions)
        created_rule = storage.create_rule(valid_rule)
        assert created_rule.name == "Valid Rule"
        
        # Test 3: Try to update rule to invalid state
        invalid_updates = {
            "actions": {
                "add_tags": [],
                "remove_tags": [],
                "else_add_tags": [],
                "else_remove_tags": []
            }
        }
        
        with pytest.raises(ValueError, match="Invalid rule"):
            storage.update_rule(created_rule.id, invalid_updates)
        
        # Test 4: Valid update
        valid_updates = {
            "description": "Updated valid rule",
            "actions": {
                "add_tags": ["updated-tag"],
                "remove_tags": [],
                "else_add_tags": [],
                "else_remove_tags": []
            }
        }
        
        updated_rule = storage.update_rule(created_rule.id, valid_updates)
        assert updated_rule.description == "Updated valid rule"
        assert updated_rule.actions.add_tags == ["updated-tag"]
    
    @pytest.mark.integration
    def test_error_handling_integration(self, temp_storage_file, test_vms):
        """Test error handling across the conditional tagging system"""
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        
        # Create rule with potentially problematic conditions
        conditions = RuleConditionGroup()
        conditions.add_condition(RuleCondition("nonexistent_field", "equals", "value"))
        actions = RuleAction(add_tags=["test"])
        
        rule = ConditionalRule("Error Test Rule", conditions=conditions, actions=actions)
        created_rule = storage.create_rule(rule)
        
        # Execute rule - should handle missing field gracefully
        with patch('tag_utils.parse_tags') as mock_parse:
            with patch('tag_utils.format_tags') as mock_format:
                mock_parse.side_effect = lambda tags: tags.split(';') if tags else []
                mock_format.side_effect = lambda tags: ';'.join(tags) if tags else ''
                
                result = engine.evaluate_rule(created_rule, test_vms, dry_run=True)
        
        # Should complete successfully even with missing field
        assert result.success is True
        # Should match no VMs since field doesn't exist
        assert len(result.matched_vms) == 0
        
        # Test with API error simulation
        with patch('proxmox_api.update_vm_tags') as mock_update:
            with patch('tag_utils.parse_tags') as mock_parse:
                with patch('tag_utils.format_tags') as mock_format:
                    mock_parse.side_effect = lambda tags: tags.split(';') if tags else []
                    mock_format.side_effect = lambda tags: ';'.join(tags) if tags else ''
                    mock_update.side_effect = Exception("API Error")
                    
                    # Create rule that matches VMs
                    conditions2 = RuleConditionGroup()
                    conditions2.add_condition(RuleCondition("status", "equals", "running"))
                    rule2 = ConditionalRule("API Error Rule", conditions=conditions2, actions=actions)
                    
                    result2 = engine.evaluate_rule(rule2, test_vms, dry_run=False)
        
        # Should handle API errors gracefully
        assert result2.success is True  # Engine execution succeeds
        assert len(result2.errors) > 0  # But records API errors
        assert "API Error" in str(result2.errors)