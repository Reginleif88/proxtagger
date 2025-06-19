"""
Unit tests for conditional tagging models
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import patch
from modules.conditional_tags.models import (
    OperatorType, LogicalOperator, RuleCondition, RuleConditionGroup,
    RuleAction, RuleSchedule, ConditionalRule, ExecutionResult
)


class TestOperatorType:
    """Test OperatorType enum"""
    
    @pytest.mark.unit
    def test_operator_type_values(self):
        """Test that all expected operator types exist"""
        expected_operators = {
            "equals", "not_equals", "contains", "not_contains",
            "greater_than", "less_than", "greater_equals", "less_equals",
            "regex", "in", "not_in"
        }
        
        actual_operators = {op.value for op in OperatorType}
        assert actual_operators == expected_operators


class TestLogicalOperator:
    """Test LogicalOperator enum"""
    
    @pytest.mark.unit
    def test_logical_operator_values(self):
        """Test logical operators"""
        assert LogicalOperator.AND.value == "AND"
        assert LogicalOperator.OR.value == "OR"


class TestRuleCondition:
    """Test RuleCondition class"""
    
    @pytest.mark.unit
    def test_rule_condition_creation(self):
        """Test creating a rule condition"""
        condition = RuleCondition("status", "equals", "running")
        
        assert condition.field == "status"
        assert condition.operator == OperatorType.EQUALS
        assert condition.value == "running"
    
    @pytest.mark.unit
    def test_rule_condition_to_dict(self):
        """Test converting condition to dictionary"""
        condition = RuleCondition("vmid", "greater_than", 100)
        result = condition.to_dict()
        
        expected = {
            "field": "vmid",
            "operator": "greater_than",
            "value": 100
        }
        assert result == expected
    
    @pytest.mark.unit
    def test_rule_condition_from_dict(self):
        """Test creating condition from dictionary"""
        data = {
            "field": "name",
            "operator": "contains",
            "value": "prod"
        }
        condition = RuleCondition.from_dict(data)
        
        assert condition.field == "name"
        assert condition.operator == OperatorType.CONTAINS
        assert condition.value == "prod"
    
    @pytest.mark.unit
    def test_rule_condition_invalid_operator(self):
        """Test creating condition with invalid operator"""
        with pytest.raises(ValueError):
            RuleCondition("status", "invalid_operator", "running")


class TestRuleConditionGroup:
    """Test RuleConditionGroup class"""
    
    @pytest.mark.unit
    def test_rule_condition_group_creation_empty(self):
        """Test creating empty condition group"""
        group = RuleConditionGroup()
        
        assert group.operator == LogicalOperator.AND
        assert group.conditions == []
    
    @pytest.mark.unit
    def test_rule_condition_group_creation_with_conditions(self):
        """Test creating condition group with conditions"""
        conditions = [
            {"field": "status", "operator": "equals", "value": "running"},
            {"field": "vmid", "operator": "greater_than", "value": 100}
        ]
        group = RuleConditionGroup(operator="OR", conditions=conditions)
        
        assert group.operator == LogicalOperator.OR
        assert len(group.conditions) == 2
        assert isinstance(group.conditions[0], RuleCondition)
        assert group.conditions[0].field == "status"
    
    @pytest.mark.unit
    def test_rule_condition_group_add_condition(self):
        """Test adding condition to group"""
        group = RuleConditionGroup()
        condition = RuleCondition("name", "contains", "test")
        
        group.add_condition(condition)
        
        assert len(group.conditions) == 1
        assert group.conditions[0] == condition
    
    @pytest.mark.unit
    def test_rule_condition_group_to_dict(self):
        """Test converting condition group to dictionary"""
        conditions = [
            {"field": "status", "operator": "equals", "value": "running"}
        ]
        group = RuleConditionGroup(operator="AND", conditions=conditions)
        result = group.to_dict()
        
        expected = {
            "operator": "AND",
            "rules": [
                {
                    "field": "status",
                    "operator": "equals",
                    "value": "running"
                }
            ]
        }
        assert result == expected
    
    @pytest.mark.unit
    def test_rule_condition_group_from_dict(self):
        """Test creating condition group from dictionary"""
        data = {
            "operator": "OR",
            "rules": [
                {"field": "vmid", "operator": "less_than", "value": 200},
                {"field": "node", "operator": "equals", "value": "node1"}
            ]
        }
        group = RuleConditionGroup.from_dict(data)
        
        assert group.operator == LogicalOperator.OR
        assert len(group.conditions) == 2
        assert group.conditions[0].field == "vmid"
        assert group.conditions[1].field == "node"


class TestRuleAction:
    """Test RuleAction class"""
    
    @pytest.mark.unit
    def test_rule_action_creation_empty(self):
        """Test creating empty rule action"""
        action = RuleAction()
        
        assert action.add_tags == []
        assert action.remove_tags == []
        assert action.else_add_tags == []
        assert action.else_remove_tags == []
    
    @pytest.mark.unit
    def test_rule_action_creation_with_tags(self):
        """Test creating rule action with tags"""
        action = RuleAction(
            add_tags=["production", "monitored"],
            remove_tags=["development"],
            else_add_tags=["needs-review"],
            else_remove_tags=["production"]
        )
        
        assert action.add_tags == ["production", "monitored"]
        assert action.remove_tags == ["development"]
        assert action.else_add_tags == ["needs-review"]
        assert action.else_remove_tags == ["production"]
    
    @pytest.mark.unit
    def test_rule_action_to_dict(self):
        """Test converting action to dictionary"""
        action = RuleAction(
            add_tags=["web"],
            remove_tags=["old"],
            else_add_tags=["review"],
            else_remove_tags=["web"]
        )
        result = action.to_dict()
        
        expected = {
            "add_tags": ["web"],
            "remove_tags": ["old"],
            "else_add_tags": ["review"],
            "else_remove_tags": ["web"]
        }
        assert result == expected
    
    @pytest.mark.unit
    def test_rule_action_from_dict(self):
        """Test creating action from dictionary"""
        data = {
            "add_tags": ["api", "backend"],
            "remove_tags": ["frontend"],
            "else_add_tags": ["untagged"],
            "else_remove_tags": ["api"]
        }
        action = RuleAction.from_dict(data)
        
        assert action.add_tags == ["api", "backend"]
        assert action.remove_tags == ["frontend"]
        assert action.else_add_tags == ["untagged"]
        assert action.else_remove_tags == ["api"]


class TestRuleSchedule:
    """Test RuleSchedule class"""
    
    @pytest.mark.unit
    def test_rule_schedule_creation_default(self):
        """Test creating default schedule"""
        schedule = RuleSchedule()
        
        assert schedule.enabled is False
        assert schedule.cron == ""
    
    @pytest.mark.unit
    def test_rule_schedule_creation_enabled(self):
        """Test creating enabled schedule"""
        schedule = RuleSchedule(enabled=True, cron="0 2 * * *")
        
        assert schedule.enabled is True
        assert schedule.cron == "0 2 * * *"
    
    @pytest.mark.unit
    def test_rule_schedule_to_dict(self):
        """Test converting schedule to dictionary"""
        schedule = RuleSchedule(enabled=True, cron="0 */6 * * *")
        result = schedule.to_dict()
        
        expected = {
            "enabled": True,
            "cron": "0 */6 * * *"
        }
        assert result == expected
    
    @pytest.mark.unit
    def test_rule_schedule_from_dict(self):
        """Test creating schedule from dictionary"""
        data = {
            "enabled": True,
            "cron": "30 1 * * *"
        }
        schedule = RuleSchedule.from_dict(data)
        
        assert schedule.enabled is True
        assert schedule.cron == "30 1 * * *"


class TestConditionalRule:
    """Test ConditionalRule class"""
    
    @pytest.mark.unit
    def test_conditional_rule_creation_minimal(self):
        """Test creating minimal conditional rule"""
        rule = ConditionalRule("Test Rule")
        
        assert rule.name == "Test Rule"
        assert rule.description == ""
        assert rule.enabled is True
        assert isinstance(rule.conditions, RuleConditionGroup)
        assert isinstance(rule.actions, RuleAction)
        assert isinstance(rule.schedule, RuleSchedule)
        assert isinstance(rule.id, str)
        assert len(rule.id) > 0
        assert isinstance(rule.created_at, datetime)
        assert isinstance(rule.updated_at, datetime)
        assert rule.last_run is None
        assert isinstance(rule.stats, dict)
    
    @pytest.mark.unit
    def test_conditional_rule_creation_full(self, sample_conditional_rule):
        """Test creating full conditional rule"""
        rule = sample_conditional_rule
        
        assert rule.name == "Test Production Monitoring Rule"
        assert "monitoring tags" in rule.description
        assert rule.enabled is True
        assert len(rule.conditions.conditions) == 2
        assert len(rule.actions.add_tags) == 2
        assert rule.schedule.enabled is True
    
    @pytest.mark.unit
    def test_conditional_rule_with_custom_id(self):
        """Test creating rule with custom ID"""
        custom_id = "custom-rule-123"
        rule = ConditionalRule("Test Rule", rule_id=custom_id)
        
        assert rule.id == custom_id
    
    @pytest.mark.unit
    def test_conditional_rule_to_dict(self, sample_conditional_rule):
        """Test converting rule to dictionary"""
        rule = sample_conditional_rule
        result = rule.to_dict()
        
        # Check required fields are present
        assert "id" in result
        assert "name" in result
        assert "description" in result
        assert "enabled" in result
        assert "conditions" in result
        assert "actions" in result
        assert "schedule" in result
        assert "created_at" in result
        assert "updated_at" in result
        assert "last_run" in result
        assert "stats" in result
        
        # Check values
        assert result["name"] == rule.name
        assert result["enabled"] == rule.enabled
        assert isinstance(result["conditions"], dict)
        assert isinstance(result["actions"], dict)
        assert isinstance(result["schedule"], dict)
    
    @pytest.mark.unit
    def test_conditional_rule_from_dict(self):
        """Test creating rule from dictionary"""
        data = {
            "id": "test-rule-123",
            "name": "Test Rule",
            "description": "Test description",
            "enabled": False,
            "conditions": {
                "operator": "AND",
                "rules": [
                    {"field": "status", "operator": "equals", "value": "running"}
                ]
            },
            "actions": {
                "add_tags": ["test"],
                "remove_tags": [],
                "else_add_tags": [],
                "else_remove_tags": []
            },
            "schedule": {
                "enabled": False,
                "cron": ""
            },
            "created_at": "2024-01-15T12:00:00",
            "updated_at": "2024-01-15T12:30:00",
            "last_run": "2024-01-15T13:00:00",
            "stats": {
                "total_matches": 5,
                "tags_added": 10,
                "tags_removed": 2,
                "last_execution_time": 1.5
            }
        }
        
        rule = ConditionalRule.from_dict(data)
        
        assert rule.id == "test-rule-123"
        assert rule.name == "Test Rule"
        assert rule.description == "Test description"
        assert rule.enabled is False
        assert len(rule.conditions.conditions) == 1
        assert rule.actions.add_tags == ["test"]
        assert rule.schedule.enabled is False
        assert rule.stats["total_matches"] == 5


class TestConditionalRuleValidation:
    """Test ConditionalRule validation"""
    
    @pytest.mark.unit
    def test_validate_valid_rule(self, sample_conditional_rule):
        """Test validation of valid rule"""
        errors = sample_conditional_rule.validate()
        assert errors == []
    
    @pytest.mark.unit
    def test_validate_missing_name(self):
        """Test validation with missing name"""
        rule = ConditionalRule("")
        errors = rule.validate()
        
        assert "Rule name is required" in errors
    
    @pytest.mark.unit
    def test_validate_no_conditions(self):
        """Test validation with no conditions"""
        rule = ConditionalRule("Test Rule")
        # Default conditions group is empty
        errors = rule.validate()
        
        assert "At least one condition is required" in errors
    
    @pytest.mark.unit
    def test_validate_no_actions(self):
        """Test validation with no actions"""
        rule = ConditionalRule("Test Rule")
        # Add condition but no actions
        condition = RuleCondition("status", "equals", "running")
        rule.conditions.add_condition(condition)
        
        errors = rule.validate()
        
        assert "At least one action (THEN or ELSE add/remove tags) is required" in errors
    
    @pytest.mark.unit
    def test_validate_schedule_enabled_no_cron(self):
        """Test validation with schedule enabled but no cron"""
        rule = ConditionalRule("Test Rule")
        condition = RuleCondition("status", "equals", "running")
        rule.conditions.add_condition(condition)
        rule.actions.add_tags = ["test"]
        rule.schedule.enabled = True
        rule.schedule.cron = ""
        
        errors = rule.validate()
        
        assert "Cron expression is required when schedule is enabled" in errors
    
    @pytest.mark.unit
    def test_validate_invalid_cron(self):
        """Test validation with invalid cron expression"""
        rule = ConditionalRule("Test Rule")
        condition = RuleCondition("status", "equals", "running")
        rule.conditions.add_condition(condition)
        rule.actions.add_tags = ["test"]
        rule.schedule.enabled = True
        rule.schedule.cron = "invalid-cron"
        
        errors = rule.validate()
        
        assert any("Invalid cron expression" in error for error in errors)
    
    @pytest.mark.unit
    def test_validate_valid_cron(self):
        """Test validation with valid cron expression"""
        rule = ConditionalRule("Test Rule")
        condition = RuleCondition("status", "equals", "running")
        rule.conditions.add_condition(condition)
        rule.actions.add_tags = ["test"]
        rule.schedule.enabled = True
        rule.schedule.cron = "0 2 * * *"  # Valid cron
        
        errors = rule.validate()
        
        # Should not have cron-related errors
        assert not any("cron" in error.lower() for error in errors)


class TestExecutionResult:
    """Test ExecutionResult class"""
    
    @pytest.mark.unit
    def test_execution_result_creation(self):
        """Test creating execution result"""
        result = ExecutionResult("rule-123", "Test Rule")
        
        assert result.rule_id == "rule-123"
        assert result.rule_name == "Test Rule"
        assert result.success is True
        assert isinstance(result.timestamp, datetime)
        assert result.matched_vms == []
        assert result.tags_added == {}
        assert result.tags_removed == {}
        assert result.tags_already_present == {}
        assert result.errors == []
        assert result.execution_time == 0
        assert result.dry_run is False
    
    @pytest.mark.unit
    def test_execution_result_creation_with_failure(self):
        """Test creating execution result with failure"""
        result = ExecutionResult("rule-123", success=False)
        
        assert result.success is False
    
    @pytest.mark.unit
    def test_execution_result_to_dict(self):
        """Test converting execution result to dictionary"""
        result = ExecutionResult("rule-123", "Test Rule")
        result.matched_vms = [100, 101]
        result.tags_added = {"100": ["web"], "101": ["api"]}
        result.tags_removed = {"100": ["old"]}
        result.execution_time = 2.5
        result.dry_run = True
        
        result_dict = result.to_dict()
        
        assert result_dict["rule_id"] == "rule-123"
        assert result_dict["rule_name"] == "Test Rule"
        assert result_dict["success"] is True
        assert result_dict["matched_vms"] == [100, 101]
        assert result_dict["tags_added"] == {"100": ["web"], "101": ["api"]}
        assert result_dict["tags_removed"] == {"100": ["old"]}
        assert result_dict["execution_time"] == 2.5
        assert result_dict["dry_run"] is True
        assert "timestamp" in result_dict