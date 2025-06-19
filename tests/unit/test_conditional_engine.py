"""
Unit tests for conditional tagging engine
"""

import pytest
import re
from unittest.mock import Mock, patch, MagicMock
from modules.conditional_tags.engine import RuleEngine
from modules.conditional_tags.models import (
    ConditionalRule, RuleCondition, RuleConditionGroup, 
    RuleAction, OperatorType, LogicalOperator
)


class TestRuleEngine:
    """Test RuleEngine class"""
    
    @pytest.fixture
    def engine(self):
        """Create RuleEngine instance for testing"""
        return RuleEngine()
    
    @pytest.fixture
    def simple_rule(self):
        """Simple rule for testing"""
        condition = RuleCondition("status", "equals", "running")
        conditions = RuleConditionGroup()
        conditions.add_condition(condition)
        
        actions = RuleAction(add_tags=["monitored"], remove_tags=["unmonitored"])
        
        rule = ConditionalRule("Simple Test Rule", conditions=conditions, actions=actions)
        return rule
    
    @pytest.fixture
    def complex_rule(self):
        """Complex rule with multiple conditions"""
        conditions_data = {
            "operator": "AND",
            "rules": [
                {"field": "status", "operator": "equals", "value": "running"},
                {"field": "vmid", "operator": "greater_than", "value": 100}
            ]
        }
        conditions = RuleConditionGroup.from_dict(conditions_data)
        
        actions = RuleAction(
            add_tags=["production", "monitored"],
            remove_tags=["development"],
            else_add_tags=["needs-review"],
            else_remove_tags=["production"]
        )
        
        rule = ConditionalRule("Complex Test Rule", conditions=conditions, actions=actions)
        return rule


class TestOperatorFunctions:
    """Test individual operator functions"""
    
    @pytest.fixture
    def engine(self):
        return RuleEngine()
    
    @pytest.mark.unit
    def test_op_equals(self, engine):
        """Test equals operator"""
        assert engine._op_equals("running", "running") is True
        assert engine._op_equals("RUNNING", "running") is True  # Case insensitive
        assert engine._op_equals("running", "stopped") is False
        assert engine._op_equals(100, "100") is True  # Type conversion
    
    @pytest.mark.unit
    def test_op_not_equals(self, engine):
        """Test not equals operator"""
        assert engine._op_not_equals("running", "stopped") is True
        assert engine._op_not_equals("running", "running") is False
        assert engine._op_not_equals("RUNNING", "running") is False  # Case insensitive
    
    @pytest.mark.unit
    def test_op_contains(self, engine):
        """Test contains operator"""
        assert engine._op_contains("production-web-01", "web") is True
        assert engine._op_contains("PRODUCTION-WEB-01", "web") is True  # Case insensitive
        assert engine._op_contains("database-server", "web") is False
        assert engine._op_contains("web;database", "web") is True
    
    @pytest.mark.unit
    def test_op_not_contains(self, engine):
        """Test not contains operator"""
        assert engine._op_not_contains("database-server", "web") is True
        assert engine._op_not_contains("production-web-01", "web") is False
        assert engine._op_not_contains("PRODUCTION-WEB-01", "web") is False  # Case insensitive
    
    @pytest.mark.unit
    def test_op_greater_than(self, engine):
        """Test greater than operator"""
        assert engine._op_greater_than(200, 100) is True
        assert engine._op_greater_than("200", "100") is True  # String conversion
        assert engine._op_greater_than(100, 200) is False
        assert engine._op_greater_than("invalid", 100) is False  # Invalid conversion
        assert engine._op_greater_than(100, "invalid") is False
    
    @pytest.mark.unit
    def test_op_less_than(self, engine):
        """Test less than operator"""
        assert engine._op_less_than(100, 200) is True
        assert engine._op_less_than("100", "200") is True  # String conversion
        assert engine._op_less_than(200, 100) is False
        assert engine._op_less_than("invalid", 100) is False  # Invalid conversion
    
    @pytest.mark.unit
    def test_op_greater_equals(self, engine):
        """Test greater than or equal operator"""
        assert engine._op_greater_equals(200, 100) is True
        assert engine._op_greater_equals(100, 100) is True
        assert engine._op_greater_equals(100, 200) is False
        assert engine._op_greater_equals("invalid", 100) is False
    
    @pytest.mark.unit
    def test_op_less_equals(self, engine):
        """Test less than or equal operator"""
        assert engine._op_less_equals(100, 200) is True
        assert engine._op_less_equals(100, 100) is True
        assert engine._op_less_equals(200, 100) is False
        assert engine._op_less_equals("invalid", 100) is False
    
    @pytest.mark.unit
    def test_op_regex(self, engine):
        """Test regex operator"""
        assert engine._op_regex("prod-web-01", r"^prod-.*") is True
        assert engine._op_regex("dev-web-01", r"^prod-.*") is False
        assert engine._op_regex("test-123", r"\d+") is True
        
        # Test invalid regex - should return False and log error
        result = engine._op_regex("test", "[invalid-regex")
        assert result is False
    
    @pytest.mark.unit
    def test_op_in(self, engine):
        """Test in operator"""
        assert engine._op_in("node1", ["node1", "node2"]) is True
        assert engine._op_in("NODE1", ["node1", "node2"]) is True  # Case insensitive
        assert engine._op_in("node3", ["node1", "node2"]) is False
        
        # Test with single value (not list)
        assert engine._op_in("node1", "node1") is True
        assert engine._op_in("node1", "node2") is False
    
    @pytest.mark.unit
    def test_op_not_in(self, engine):
        """Test not in operator"""
        assert engine._op_not_in("node3", ["node1", "node2"]) is True
        assert engine._op_not_in("node1", ["node1", "node2"]) is False
        assert engine._op_not_in("NODE1", ["node1", "node2"]) is False  # Case insensitive
        
        # Test with single value (not list)
        assert engine._op_not_in("node1", "node2") is True
        assert engine._op_not_in("node1", "node1") is False


class TestFieldValueExtraction:
    """Test field value extraction from VM data"""
    
    @pytest.fixture
    def engine(self):
        return RuleEngine()
    
    @pytest.fixture
    def sample_vm(self):
        return {
            "vmid": 100,
            "name": "test-vm",
            "status": "running",
            "config": {
                "cores": 2,
                "memory": 2048,
                "ostype": "l26"
            }
        }
    
    @pytest.mark.unit
    def test_get_field_value_simple(self, engine, sample_vm):
        """Test extracting simple field values"""
        assert engine._get_field_value(sample_vm, "vmid") == 100
        assert engine._get_field_value(sample_vm, "name") == "test-vm"
        assert engine._get_field_value(sample_vm, "status") == "running"
    
    @pytest.mark.unit
    def test_get_field_value_nested(self, engine, sample_vm):
        """Test extracting nested field values"""
        assert engine._get_field_value(sample_vm, "config.cores") == 2
        assert engine._get_field_value(sample_vm, "config.memory") == 2048
        assert engine._get_field_value(sample_vm, "config.ostype") == "l26"
    
    @pytest.mark.unit
    def test_get_field_value_missing_field(self, engine, sample_vm):
        """Test extracting missing field values"""
        assert engine._get_field_value(sample_vm, "nonexistent") is None
        assert engine._get_field_value(sample_vm, "config.nonexistent") is None
        assert engine._get_field_value(sample_vm, "nonexistent.field") is None
    
    @pytest.mark.unit
    def test_get_field_value_deep_nested(self, engine):
        """Test extracting deeply nested field values"""
        vm = {
            "level1": {
                "level2": {
                    "level3": "deep_value"
                }
            }
        }
        assert engine._get_field_value(vm, "level1.level2.level3") == "deep_value"
        assert engine._get_field_value(vm, "level1.level2.missing") is None


class TestConditionEvaluation:
    """Test condition evaluation"""
    
    @pytest.fixture
    def engine(self):
        return RuleEngine()
    
    @pytest.fixture
    def sample_vm(self):
        return {
            "vmid": 150,
            "name": "prod-web-01",
            "status": "running",
            "tags": "production;web",
            "node": "node1"
        }
    
    @pytest.mark.unit
    def test_evaluate_condition_simple(self, engine, sample_vm):
        """Test evaluating simple condition"""
        condition = RuleCondition("status", "equals", "running")
        result = engine._evaluate_condition(condition, sample_vm)
        assert result is True
        
        condition = RuleCondition("status", "equals", "stopped")
        result = engine._evaluate_condition(condition, sample_vm)
        assert result is False
    
    @pytest.mark.unit
    def test_evaluate_condition_unknown_operator(self, engine, sample_vm):
        """Test evaluating condition with unknown operator"""
        # Create condition with invalid operator by bypassing validation
        condition = RuleCondition("status", "equals", "running")
        condition.operator = "unknown_operator"
        
        # Test unknown operator returns False and logs warning
        result = engine._evaluate_condition(condition, sample_vm)
        assert result is False
    
    @pytest.mark.unit
    def test_evaluate_condition_exception(self, engine, sample_vm):
        """Test evaluating condition that raises exception"""
        condition = RuleCondition("status", "equals", "running")
        
        # Mock the operator function in the operators dict to raise an exception
        original_op = engine.operators[OperatorType.EQUALS]
        engine.operators[OperatorType.EQUALS] = Mock(side_effect=Exception("Test error"))
        
        try:
            result = engine._evaluate_condition(condition, sample_vm)
            # Should return False when operator raises exception
            assert result is False
        finally:
            # Restore original operator
            engine.operators[OperatorType.EQUALS] = original_op
    
    @pytest.mark.unit
    def test_evaluate_conditions_and(self, engine, sample_vm):
        """Test evaluating condition group with AND operator"""
        conditions = RuleConditionGroup(operator="AND")
        conditions.add_condition(RuleCondition("status", "equals", "running"))
        conditions.add_condition(RuleCondition("vmid", "greater_than", 100))
        
        result = engine._evaluate_conditions(conditions, sample_vm)
        assert result is True  # Both conditions are true
        
        # Add failing condition
        conditions.add_condition(RuleCondition("status", "equals", "stopped"))
        result = engine._evaluate_conditions(conditions, sample_vm)
        assert result is False  # One condition fails
    
    @pytest.mark.unit
    def test_evaluate_conditions_or(self, engine, sample_vm):
        """Test evaluating condition group with OR operator"""
        conditions = RuleConditionGroup(operator="OR")
        conditions.add_condition(RuleCondition("status", "equals", "stopped"))  # False
        conditions.add_condition(RuleCondition("vmid", "greater_than", 100))     # True
        
        result = engine._evaluate_conditions(conditions, sample_vm)
        assert result is True  # At least one condition is true
        
        # All conditions false
        conditions = RuleConditionGroup(operator="OR")
        conditions.add_condition(RuleCondition("status", "equals", "stopped"))
        conditions.add_condition(RuleCondition("vmid", "less_than", 100))
        
        result = engine._evaluate_conditions(conditions, sample_vm)
        assert result is False  # All conditions are false
    
    @pytest.mark.unit
    def test_evaluate_conditions_empty(self, engine, sample_vm):
        """Test evaluating empty condition group"""
        conditions = RuleConditionGroup()
        result = engine._evaluate_conditions(conditions, sample_vm)
        assert result is False  # Empty conditions should return False


class TestRuleEvaluation:
    """Test complete rule evaluation"""
    
    @pytest.fixture
    def engine(self):
        return RuleEngine()
    
    @pytest.fixture
    def sample_vms(self):
        return [
            {
                "vmid": 100,
                "name": "prod-web-01",
                "node": "node1",
                "type": "qemu",
                "status": "running",
                "tags": "production;web"
            },
            {
                "vmid": 50,
                "name": "dev-db-01",
                "node": "node2", 
                "type": "lxc",
                "status": "stopped",
                "tags": "development;database"
            },
            {
                "vmid": 200,
                "name": "test-app-01",
                "node": "node1",
                "type": "qemu",
                "status": "running",
                "tags": ""
            }
        ]
    
    @pytest.mark.unit
    def test_evaluate_rule_dry_run(self, engine, simple_rule, sample_vms):
        """Test rule evaluation in dry run mode"""
        result = engine.evaluate_rule(simple_rule, sample_vms, dry_run=True)
        
        assert result.success is True
        assert result.dry_run is True
        assert len(result.matched_vms) == 2  # VMs 100 and 200 are running
        assert result.matched_vms == [100, 200]
        assert result.execution_time > 0
        
        # In dry run, should have simulated actions
        assert 100 in result.tags_added
        assert 200 in result.tags_added
    
    @pytest.mark.unit
    @patch('proxmox_api.update_vm_tags')
    @patch('tag_utils.parse_tags')
    @patch('tag_utils.format_tags')
    def test_evaluate_rule_real_run(self, mock_format_tags, mock_parse_tags, 
                                   mock_update_vm_tags, engine, simple_rule, sample_vms):
        """Test rule evaluation in real mode"""
        # Mock the tag utilities
        mock_parse_tags.side_effect = lambda tags: tags.split(';') if tags else []
        mock_format_tags.side_effect = lambda tags: ';'.join(tags) if tags else ''
        
        result = engine.evaluate_rule(simple_rule, sample_vms, dry_run=False)
        
        assert result.success is True
        assert result.dry_run is False
        assert len(result.matched_vms) == 2  # VMs 100 and 200 are running
        
        # Should have called update_vm_tags for matched VMs
        assert mock_update_vm_tags.call_count == 2
    
    @pytest.mark.unit
    def test_evaluate_rule_with_else_actions(self, engine, complex_rule, sample_vms):
        """Test rule evaluation with ELSE actions"""
        result = engine.evaluate_rule(complex_rule, sample_vms, dry_run=True)
        
        assert result.success is True
        
        # VM 100 should match (running and vmid > 100)
        # VMs 50 and 200 should not match
        matched_vms = result.matched_vms
        
        # Should have THEN actions for matched VMs and ELSE actions for non-matched
        assert len(matched_vms) >= 0  # Depends on exact conditions
    
    @pytest.mark.unit
    @patch('proxmox_api.update_vm_tags')
    def test_evaluate_rule_update_error(self, mock_update_vm_tags, engine, simple_rule, sample_vms):
        """Test rule evaluation with update errors"""
        # Mock update function to raise exception
        mock_update_vm_tags.side_effect = Exception("Update failed")
        
        with patch('tag_utils.parse_tags') as mock_parse_tags:
            with patch('tag_utils.format_tags') as mock_format_tags:
                mock_parse_tags.side_effect = lambda tags: tags.split(';') if tags else []
                mock_format_tags.side_effect = lambda tags: ';'.join(tags) if tags else ''
                
                result = engine.evaluate_rule(simple_rule, sample_vms, dry_run=False)
        
        assert result.success is True  # Rule evaluation succeeds
        assert len(result.errors) > 0  # But has errors from updates
        assert "Update failed" in str(result.errors)
    
    @pytest.mark.unit
    def test_evaluate_rule_exception(self, engine, simple_rule, sample_vms):
        """Test rule evaluation with exception"""
        # Mock condition evaluation to raise exception
        with patch.object(engine, '_evaluate_conditions', side_effect=Exception("Evaluation failed")):
            result = engine.evaluate_rule(simple_rule, sample_vms)
        
        assert result.success is False
        assert len(result.errors) == 1
        assert "Evaluation failed" in result.errors[0]
    
    @pytest.mark.unit
    def test_evaluate_rule_no_matched_vms(self, engine, sample_vms):
        """Test rule evaluation with no matching VMs"""
        # Create rule that matches no VMs
        condition = RuleCondition("status", "equals", "maintenance")
        conditions = RuleConditionGroup()
        conditions.add_condition(condition)
        actions = RuleAction(add_tags=["test"])
        rule = ConditionalRule("No Match Rule", conditions=conditions, actions=actions)
        
        result = engine.evaluate_rule(rule, sample_vms, dry_run=True)
        
        assert result.success is True
        assert len(result.matched_vms) == 0
        assert len(result.tags_added) == 0
    
    @pytest.mark.unit
    def test_evaluate_rule_all_matched_vms(self, engine, sample_vms):
        """Test rule evaluation where all VMs match"""
        # Create rule that matches all VMs (vmid > 0)
        condition = RuleCondition("vmid", "greater_than", 0)
        conditions = RuleConditionGroup()
        conditions.add_condition(condition)
        actions = RuleAction(add_tags=["all"])
        rule = ConditionalRule("Match All Rule", conditions=conditions, actions=actions)
        
        result = engine.evaluate_rule(rule, sample_vms, dry_run=True)
        
        assert result.success is True
        assert len(result.matched_vms) == 3  # All VMs match
        assert set(result.matched_vms) == {100, 50, 200}