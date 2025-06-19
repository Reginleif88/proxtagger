"""
Unit tests for conditional tagging storage
"""

import pytest
import json
import os
from unittest.mock import Mock, patch, mock_open
from datetime import datetime
from modules.conditional_tags.storage import RuleStorage, ExecutionHistory
from modules.conditional_tags.models import ConditionalRule, RuleCondition, RuleConditionGroup, RuleAction, ExecutionResult


class TestRuleStorage:
    """Test RuleStorage class"""
    
    @pytest.fixture
    def mock_rule_storage_data(self):
        """Mock rule storage data"""
        return {
            "rules": [
                {
                    "id": "test-rule-1",
                    "name": "Test Rule 1",
                    "description": "Test description",
                    "enabled": True,
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
                    "updated_at": "2024-01-15T12:00:00",
                    "last_run": None,
                    "stats": {
                        "total_matches": 0,
                        "tags_added": 0,
                        "tags_removed": 0,
                        "last_execution_time": 0
                    }
                }
            ],
            "version": "1.0",
            "updated_at": "2024-01-15T12:00:00"
        }
    
    @pytest.mark.unit
    def test_rule_storage_init_new_file(self, temp_storage_file):
        """Test RuleStorage initialization with new file"""
        storage = RuleStorage(temp_storage_file)
        
        assert storage.storage_file == temp_storage_file
        assert storage.rules == {}
    
    @pytest.mark.unit
    def test_rule_storage_init_existing_file(self, temp_storage_file, mock_rule_storage_data):
        """Test RuleStorage initialization with existing file"""
        # Write test data to file
        with open(temp_storage_file, 'w') as f:
            json.dump(mock_rule_storage_data, f)
        
        storage = RuleStorage(temp_storage_file)
        
        assert len(storage.rules) == 1
        assert "test-rule-1" in storage.rules
        assert storage.rules["test-rule-1"].name == "Test Rule 1"
    
    @pytest.mark.unit
    def test_rule_storage_init_corrupted_file(self, temp_storage_file):
        """Test RuleStorage initialization with corrupted file"""
        # Write invalid JSON to file
        with open(temp_storage_file, 'w') as f:
            f.write("invalid json")
        
        with patch('modules.conditional_tags.storage.logger') as mock_logger:
            storage = RuleStorage(temp_storage_file)
            
            assert storage.rules == {}
            mock_logger.error.assert_called_once()
    
    @pytest.mark.unit
    def test_get_all_rules(self, temp_storage_file, mock_rule_storage_data):
        """Test getting all rules"""
        with open(temp_storage_file, 'w') as f:
            json.dump(mock_rule_storage_data, f)
        
        storage = RuleStorage(temp_storage_file)
        rules = storage.get_all_rules()
        
        assert len(rules) == 1
        assert isinstance(rules[0], ConditionalRule)
        assert rules[0].name == "Test Rule 1"
    
    @pytest.mark.unit
    def test_get_rule_exists(self, temp_storage_file, mock_rule_storage_data):
        """Test getting existing rule"""
        with open(temp_storage_file, 'w') as f:
            json.dump(mock_rule_storage_data, f)
        
        storage = RuleStorage(temp_storage_file)
        rule = storage.get_rule("test-rule-1")
        
        assert rule is not None
        assert rule.name == "Test Rule 1"
    
    @pytest.mark.unit
    def test_get_rule_not_exists(self, temp_storage_file):
        """Test getting non-existent rule"""
        storage = RuleStorage(temp_storage_file)
        rule = storage.get_rule("non-existent")
        
        assert rule is None
    
    @pytest.mark.unit
    def test_create_rule_valid(self, temp_storage_file):
        """Test creating valid rule"""
        storage = RuleStorage(temp_storage_file)
        
        # Create valid rule
        condition = RuleCondition("status", "equals", "running")
        conditions = RuleConditionGroup()
        conditions.add_condition(condition)
        actions = RuleAction(add_tags=["test"])
        rule = ConditionalRule("New Rule", conditions=conditions, actions=actions)
        
        created_rule = storage.create_rule(rule)
        
        assert created_rule.name == "New Rule"
        assert rule.id in storage.rules
        
        # Verify file was saved
        assert os.path.exists(temp_storage_file)
        with open(temp_storage_file, 'r') as f:
            data = json.load(f)
            assert len(data["rules"]) == 1
    
    @pytest.mark.unit
    def test_create_rule_invalid(self, temp_storage_file):
        """Test creating invalid rule"""
        storage = RuleStorage(temp_storage_file)
        
        # Create invalid rule (no conditions)
        rule = ConditionalRule("Invalid Rule")
        
        with pytest.raises(ValueError, match="Invalid rule"):
            storage.create_rule(rule)
    
    @pytest.mark.unit
    def test_create_rule_duplicate_name(self, temp_storage_file):
        """Test creating rule with duplicate name"""
        storage = RuleStorage(temp_storage_file)
        
        # Create first rule
        condition = RuleCondition("status", "equals", "running")
        conditions = RuleConditionGroup()
        conditions.add_condition(condition)
        actions = RuleAction(add_tags=["test"])
        rule1 = ConditionalRule("Duplicate Name", conditions=conditions, actions=actions)
        storage.create_rule(rule1)
        
        # Try to create second rule with same name
        rule2 = ConditionalRule("Duplicate Name", conditions=conditions, actions=actions)
        
        with pytest.raises(ValueError, match="already exists"):
            storage.create_rule(rule2)
    
    @pytest.mark.unit
    def test_update_rule_exists(self, temp_storage_file, mock_rule_storage_data):
        """Test updating existing rule"""
        with open(temp_storage_file, 'w') as f:
            json.dump(mock_rule_storage_data, f)
        
        storage = RuleStorage(temp_storage_file)
        
        updates = {
            "name": "Updated Rule Name",
            "description": "Updated description",
            "enabled": False
        }
        
        updated_rule = storage.update_rule("test-rule-1", updates)
        
        assert updated_rule is not None
        assert updated_rule.name == "Updated Rule Name"
        assert updated_rule.description == "Updated description"
        assert updated_rule.enabled is False
        assert isinstance(updated_rule.updated_at, datetime)
    
    @pytest.mark.unit
    def test_update_rule_not_exists(self, temp_storage_file):
        """Test updating non-existent rule"""
        storage = RuleStorage(temp_storage_file)
        
        updated_rule = storage.update_rule("non-existent", {"name": "New Name"})
        
        assert updated_rule is None
    
    @pytest.mark.unit
    def test_update_rule_conditions(self, temp_storage_file, mock_rule_storage_data):
        """Test updating rule conditions"""
        with open(temp_storage_file, 'w') as f:
            json.dump(mock_rule_storage_data, f)
        
        storage = RuleStorage(temp_storage_file)
        
        new_conditions = {
            "operator": "OR",
            "rules": [
                {"field": "vmid", "operator": "greater_than", "value": 100}
            ]
        }
        
        updates = {"conditions": new_conditions}
        updated_rule = storage.update_rule("test-rule-1", updates)
        
        assert updated_rule.conditions.operator.value == "OR"
        assert len(updated_rule.conditions.conditions) == 1
        assert updated_rule.conditions.conditions[0].field == "vmid"
    
    @pytest.mark.unit
    def test_update_rule_invalid_after_update(self, temp_storage_file, mock_rule_storage_data):
        """Test updating rule that becomes invalid"""
        with open(temp_storage_file, 'w') as f:
            json.dump(mock_rule_storage_data, f)
        
        storage = RuleStorage(temp_storage_file)
        
        # Update to remove all actions (makes rule invalid)
        updates = {
            "actions": {
                "add_tags": [],
                "remove_tags": [],
                "else_add_tags": [],
                "else_remove_tags": []
            }
        }
        
        with pytest.raises(ValueError, match="Invalid rule"):
            storage.update_rule("test-rule-1", updates)
    
    @pytest.mark.unit
    def test_update_rule_duplicate_name(self, temp_storage_file):
        """Test updating rule to duplicate name"""
        storage = RuleStorage(temp_storage_file)
        
        # Create two rules
        condition = RuleCondition("status", "equals", "running")
        conditions = RuleConditionGroup()
        conditions.add_condition(condition)
        actions = RuleAction(add_tags=["test"])
        
        rule1 = ConditionalRule("Rule 1", conditions=conditions, actions=actions)
        rule2 = ConditionalRule("Rule 2", conditions=conditions, actions=actions)
        
        storage.create_rule(rule1)
        storage.create_rule(rule2)
        
        # Try to update rule2 to have same name as rule1
        with pytest.raises(ValueError, match="already exists"):
            storage.update_rule(rule2.id, {"name": "Rule 1"})
    
    @pytest.mark.unit
    def test_delete_rule_exists(self, temp_storage_file, mock_rule_storage_data):
        """Test deleting existing rule"""
        with open(temp_storage_file, 'w') as f:
            json.dump(mock_rule_storage_data, f)
        
        storage = RuleStorage(temp_storage_file)
        
        result = storage.delete_rule("test-rule-1")
        
        assert result is True
        assert "test-rule-1" not in storage.rules
        
        # Verify file was updated
        with open(temp_storage_file, 'r') as f:
            data = json.load(f)
            assert len(data["rules"]) == 0
    
    @pytest.mark.unit
    def test_delete_rule_not_exists(self, temp_storage_file):
        """Test deleting non-existent rule"""
        storage = RuleStorage(temp_storage_file)
        
        result = storage.delete_rule("non-existent")
        
        assert result is False
    
    @pytest.mark.unit
    def test_update_rule_stats(self, temp_storage_file, mock_rule_storage_data):
        """Test updating rule statistics"""
        with open(temp_storage_file, 'w') as f:
            json.dump(mock_rule_storage_data, f)
        
        storage = RuleStorage(temp_storage_file)
        
        # Create execution result
        result = ExecutionResult("test-rule-1", "Test Rule")
        result.matched_vms = [100, 101]
        result.tags_added = {"100": ["web"], "101": ["api"]}
        result.tags_removed = {"100": ["old"]}
        result.execution_time = 2.5
        
        storage.update_rule_stats("test-rule-1", result)
        
        rule = storage.get_rule("test-rule-1")
        assert rule.last_run == result.timestamp
        assert rule.stats["total_matches"] == 2
        assert rule.stats["tags_added"] == 2  # 2 added tags total
        assert rule.stats["tags_removed"] == 1
        assert rule.stats["last_execution_time"] == 2.5
    
    @pytest.mark.unit
    def test_update_rule_stats_not_exists(self, temp_storage_file):
        """Test updating stats for non-existent rule"""
        storage = RuleStorage(temp_storage_file)
        
        result = ExecutionResult("non-existent", "Test Rule")
        # Should not raise error
        storage.update_rule_stats("non-existent", result)
    
    @pytest.mark.unit
    def test_save_rules_error(self, temp_storage_file):
        """Test error handling during rule saving"""
        storage = RuleStorage(temp_storage_file)
        
        # Create rule
        condition = RuleCondition("status", "equals", "running")
        conditions = RuleConditionGroup()
        conditions.add_condition(condition)
        actions = RuleAction(add_tags=["test"])
        rule = ConditionalRule("Test Rule", conditions=conditions, actions=actions)
        storage.rules[rule.id] = rule
        
        # Mock open to raise exception
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            with pytest.raises(IOError):
                storage._save_rules()


class TestExecutionHistory:
    """Test ExecutionHistory class"""
    
    @pytest.fixture
    def mock_history_data(self):
        """Mock execution history data"""
        return {
            "rule-1": [
                {
                    "rule_id": "rule-1",
                    "rule_name": "Test Rule",
                    "success": True,
                    "timestamp": "2024-01-15T12:00:00",
                    "matched_vms": [100, 101],
                    "tags_added": {"100": ["web"]},
                    "tags_removed": {},
                    "tags_already_present": {},
                    "errors": [],
                    "execution_time": 1.5,
                    "dry_run": False
                }
            ]
        }
    
    @pytest.mark.unit
    def test_execution_history_init_new_file(self, temp_storage_file):
        """Test ExecutionHistory initialization with new file"""
        history = ExecutionHistory(temp_storage_file)
        
        assert history.history_file == temp_storage_file
        assert history.max_history_per_rule == 100
    
    @pytest.mark.unit
    def test_add_execution(self, temp_storage_file):
        """Test adding execution result to history"""
        history = ExecutionHistory(temp_storage_file)
        
        result = ExecutionResult("rule-123", "Test Rule")
        result.matched_vms = [100]
        result.tags_added = {"100": ["web"]}
        
        history.add_execution(result)
        
        # Verify file was created and data saved
        assert os.path.exists(temp_storage_file)
        with open(temp_storage_file, 'r') as f:
            data = json.load(f)
            assert "rule-123" in data
            assert len(data["rule-123"]) == 1
            assert data["rule-123"][0]["rule_name"] == "Test Rule"
    
    @pytest.mark.unit
    def test_add_execution_multiple(self, temp_storage_file):
        """Test adding multiple execution results"""
        history = ExecutionHistory(temp_storage_file)
        
        # Add multiple executions
        for i in range(5):
            result = ExecutionResult("rule-123", f"Test Rule {i}")
            history.add_execution(result)
        
        with open(temp_storage_file, 'r') as f:
            data = json.load(f)
            assert len(data["rule-123"]) == 5
            # Most recent should be first
            assert data["rule-123"][0]["rule_name"] == "Test Rule 4"
    
    @pytest.mark.unit
    def test_add_execution_trim_history(self, temp_storage_file):
        """Test trimming history to max limit"""
        history = ExecutionHistory(temp_storage_file)
        history.max_history_per_rule = 3  # Set low limit for testing
        
        # Add more executions than limit
        for i in range(5):
            result = ExecutionResult("rule-123", f"Test Rule {i}")
            history.add_execution(result)
        
        with open(temp_storage_file, 'r') as f:
            data = json.load(f)
            assert len(data["rule-123"]) == 3  # Trimmed to limit
            # Should keep most recent
            assert data["rule-123"][0]["rule_name"] == "Test Rule 4"
            assert data["rule-123"][2]["rule_name"] == "Test Rule 2"
    
    @pytest.mark.unit
    def test_get_rule_history(self, temp_storage_file, mock_history_data):
        """Test getting rule execution history"""
        with open(temp_storage_file, 'w') as f:
            json.dump(mock_history_data, f)
        
        history = ExecutionHistory(temp_storage_file)
        rule_history = history.get_rule_history("rule-1")
        
        assert len(rule_history) == 1
        assert rule_history[0]["rule_name"] == "Test Rule"
        assert rule_history[0]["success"] is True
    
    @pytest.mark.unit
    def test_get_rule_history_with_limit(self, temp_storage_file):
        """Test getting rule history with limit"""
        history = ExecutionHistory(temp_storage_file)
        
        # Add multiple executions
        for i in range(5):
            result = ExecutionResult("rule-123", f"Test Rule {i}")
            history.add_execution(result)
        
        rule_history = history.get_rule_history("rule-123", limit=3)
        
        assert len(rule_history) == 3
        # Should get most recent 3
        assert rule_history[0]["rule_name"] == "Test Rule 4"
        assert rule_history[2]["rule_name"] == "Test Rule 2"
    
    @pytest.mark.unit
    def test_get_rule_history_not_exists(self, temp_storage_file):
        """Test getting history for non-existent rule"""
        history = ExecutionHistory(temp_storage_file)
        rule_history = history.get_rule_history("non-existent")
        
        assert rule_history == []
    
    @pytest.mark.unit
    def test_get_recent_executions(self, temp_storage_file):
        """Test getting recent executions across all rules"""
        history = ExecutionHistory(temp_storage_file)
        
        # Add executions for multiple rules
        for rule_id in ["rule-1", "rule-2", "rule-3"]:
            for i in range(2):
                result = ExecutionResult(rule_id, f"Rule {rule_id} Execution {i}")
                history.add_execution(result)
        
        recent = history.get_recent_executions(limit=4)
        
        assert len(recent) == 4
        # Should be sorted by timestamp (most recent first)
        # All executions should have rule_id field
        for execution in recent:
            assert "rule_id" in execution
            assert execution["rule_id"] in ["rule-1", "rule-2", "rule-3"]
    
    @pytest.mark.unit
    def test_get_recent_executions_empty(self, temp_storage_file):
        """Test getting recent executions from empty history"""
        history = ExecutionHistory(temp_storage_file)
        recent = history.get_recent_executions()
        
        assert recent == []
    
    @pytest.mark.unit
    def test_load_history_corrupted_file(self, temp_storage_file):
        """Test loading corrupted history file"""
        # Write invalid JSON
        with open(temp_storage_file, 'w') as f:
            f.write("invalid json")
        
        with patch('modules.conditional_tags.storage.logger') as mock_logger:
            history = ExecutionHistory(temp_storage_file)
            data = history._load_history()
            
            assert data == {}
            mock_logger.error.assert_called_once()
    
    @pytest.mark.unit
    def test_save_history_error(self, temp_storage_file):
        """Test error handling during history saving"""
        history = ExecutionHistory(temp_storage_file)
        
        # Mock open to raise exception
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            with patch('modules.conditional_tags.storage.logger') as mock_logger:
                history._save_history({"test": []})
                
                mock_logger.error.assert_called_once()