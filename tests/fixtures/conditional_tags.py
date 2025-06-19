"""
Test fixtures for conditional tagging module
"""

import pytest
from datetime import datetime
from modules.conditional_tags.models import (
    ConditionalRule, RuleCondition, RuleConditionGroup, 
    RuleAction, RuleSchedule, OperatorType, LogicalOperator
)


@pytest.fixture
def sample_rule_condition():
    """Sample rule condition for testing"""
    return RuleCondition(
        field="status",
        operator="equals", 
        value="running"
    )


@pytest.fixture
def sample_rule_condition_group():
    """Sample rule condition group for testing"""
    conditions = [
        {
            "field": "status",
            "operator": "equals",
            "value": "running"
        },
        {
            "field": "tags", 
            "operator": "contains",
            "value": "production"
        }
    ]
    return RuleConditionGroup(operator="AND", conditions=conditions)


@pytest.fixture
def sample_rule_action():
    """Sample rule action for testing"""
    return RuleAction(
        add_tags=["monitored", "active"],
        remove_tags=["inactive"],
        else_add_tags=["needs-attention"],
        else_remove_tags=["monitored"]
    )


@pytest.fixture
def sample_rule_schedule():
    """Sample rule schedule for testing"""
    return RuleSchedule(
        enabled=True,
        cron="0 2 * * *"  # Daily at 2 AM
    )


@pytest.fixture
def sample_conditional_rule(sample_rule_condition_group, sample_rule_action, sample_rule_schedule):
    """Sample complete conditional rule for testing"""
    return ConditionalRule(
        name="Test Production Monitoring Rule",
        description="Add monitoring tags to running production VMs",
        enabled=True,
        conditions=sample_rule_condition_group,
        actions=sample_rule_action,
        schedule=sample_rule_schedule
    )


@pytest.fixture
def simple_rule():
    """Simple rule for basic testing"""
    conditions = RuleConditionGroup()
    conditions.add_condition(RuleCondition("status", "equals", "running"))
    actions = RuleAction(add_tags=["online"])
    return ConditionalRule(
        name="Simple Test Rule",
        description="Simple rule for testing",
        enabled=True,
        conditions=conditions,
        actions=actions
    )


@pytest.fixture  
def complex_rule():
    """Complex rule with multiple conditions and actions"""
    conditions = RuleConditionGroup(operator="OR")
    conditions.add_condition(RuleCondition("status", "equals", "running"))
    conditions.add_condition(RuleCondition("tags", "contains", "production"))
    
    actions = RuleAction(
        add_tags=["monitored"],
        remove_tags=["offline"],
        else_add_tags=["needs-attention"],
        else_remove_tags=["monitored"]
    )
    
    return ConditionalRule(
        name="Complex Test Rule",
        description="Complex rule with multiple conditions",
        enabled=True,
        conditions=conditions,
        actions=actions
    )


@pytest.fixture
def complex_rule_conditions():
    """Complex rule conditions for advanced testing"""
    return {
        "operator": "OR",
        "rules": [
            {
                "field": "vmid",
                "operator": "greater_than",
                "value": 100
            },
            {
                "field": "name",
                "operator": "regex",
                "value": "^prod-.*"
            },
            {
                "field": "node",
                "operator": "in",
                "value": ["node1", "node2"]
            }
        ]
    }


@pytest.fixture
def rule_execution_data():
    """Sample rule execution data for testing"""
    return {
        "rule_id": "test-rule-123",
        "rule_name": "Test Rule",
        "success": True,
        "timestamp": "2024-01-15T12:00:00",
        "matched_vms": [100, 101],
        "tags_added": {
            "100": ["monitored"],
            "101": ["active"]
        },
        "tags_removed": {
            "100": ["inactive"]
        },
        "tags_already_present": {
            "101": ["production"]
        },
        "errors": [],
        "execution_time": 1.5,
        "dry_run": False
    }


@pytest.fixture
def invalid_rule_data():
    """Invalid rule data for validation testing"""
    return [
        # Missing name
        {
            "description": "Rule without name",
            "enabled": True,
            "conditions": {
                "operator": "AND",
                "rules": []
            },
            "actions": {
                "add_tags": ["test"]
            }
        },
        # No conditions
        {
            "name": "Rule without conditions",
            "description": "Test rule",
            "enabled": True,
            "conditions": {
                "operator": "AND", 
                "rules": []
            },
            "actions": {
                "add_tags": ["test"]
            }
        },
        # No actions
        {
            "name": "Rule without actions",
            "description": "Test rule",
            "enabled": True,
            "conditions": {
                "operator": "AND",
                "rules": [
                    {
                        "field": "status",
                        "operator": "equals",
                        "value": "running"
                    }
                ]
            },
            "actions": {}
        },
        # Invalid cron when schedule enabled
        {
            "name": "Rule with invalid cron",
            "description": "Test rule",
            "enabled": True,
            "conditions": {
                "operator": "AND",
                "rules": [
                    {
                        "field": "status", 
                        "operator": "equals",
                        "value": "running"
                    }
                ]
            },
            "actions": {
                "add_tags": ["test"]
            },
            "schedule": {
                "enabled": True,
                "cron": "invalid-cron"
            }
        }
    ]


@pytest.fixture 
def vm_data_for_evaluation():
    """VM data specifically designed for rule evaluation testing"""
    return [
        {
            "vmid": 100,
            "name": "prod-web-01",
            "node": "node1",
            "type": "qemu",
            "status": "running",
            "tags": "production;web;frontend",
            "cpu": 2,
            "maxmem": 2147483648,
            "uptime": 86400,
            "config": {
                "ostype": "l26",
                "cores": 2,
                "memory": 2048
            }
        },
        {
            "vmid": 50,
            "name": "dev-db-01", 
            "node": "node2",
            "type": "lxc",
            "status": "stopped",
            "tags": "development;database",
            "cpu": 1,
            "maxmem": 1073741824,
            "uptime": 0,
            "config": {
                "ostype": "ubuntu",
                "cores": 1,
                "memory": 1024
            }
        },
        {
            "vmid": 200,
            "name": "test-api-01",
            "node": "node3",
            "type": "qemu", 
            "status": "running",
            "tags": "",
            "cpu": 4,
            "maxmem": 4294967296,
            "uptime": 172800,
            "config": {
                "ostype": "l26",
                "cores": 4,
                "memory": 4096
            }
        }
    ]