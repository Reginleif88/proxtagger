"""
Data models and validation for conditional tagging rules
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from enum import Enum

class OperatorType(Enum):
    """Supported comparison operators"""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUALS = "greater_equals"
    LESS_EQUALS = "less_equals"
    REGEX = "regex"
    IN = "in"
    NOT_IN = "not_in"

class LogicalOperator(Enum):
    """Logical operators for combining conditions"""
    AND = "AND"
    OR = "OR"

class RuleCondition:
    """Represents a single condition in a rule"""
    
    def __init__(self, field: str, operator: str, value: Any):
        self.field = field
        self.operator = OperatorType(operator)
        self.value = value
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "operator": self.operator.value,
            "value": self.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RuleCondition':
        return cls(
            field=data["field"],
            operator=data["operator"],
            value=data["value"]
        )

class RuleConditionGroup:
    """Group of conditions with a logical operator"""
    
    def __init__(self, operator: str = "AND", conditions: Optional[List[Dict]] = None):
        self.operator = LogicalOperator(operator)
        self.conditions = []
        if conditions:
            for cond in conditions:
                if isinstance(cond, dict):
                    self.conditions.append(RuleCondition.from_dict(cond))
                else:
                    self.conditions.append(cond)
    
    def add_condition(self, condition: RuleCondition):
        self.conditions.append(condition)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "operator": self.operator.value,
            "rules": [cond.to_dict() for cond in self.conditions]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RuleConditionGroup':
        return cls(
            operator=data.get("operator", "AND"),
            conditions=data.get("rules", [])
        )

class RuleAction:
    """Actions to perform when rule conditions are met or not met"""
    
    def __init__(self, add_tags: Optional[List[str]] = None, 
                 remove_tags: Optional[List[str]] = None,
                 else_add_tags: Optional[List[str]] = None,
                 else_remove_tags: Optional[List[str]] = None):
        # THEN actions (when conditions match)
        self.add_tags = add_tags or []
        self.remove_tags = remove_tags or []
        # ELSE actions (when conditions don't match)
        self.else_add_tags = else_add_tags or []
        self.else_remove_tags = else_remove_tags or []
    
    def to_dict(self) -> Dict[str, List[str]]:
        return {
            "add_tags": self.add_tags,
            "remove_tags": self.remove_tags,
            "else_add_tags": self.else_add_tags,
            "else_remove_tags": self.else_remove_tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, List[str]]) -> 'RuleAction':
        return cls(
            add_tags=data.get("add_tags", []),
            remove_tags=data.get("remove_tags", []),
            else_add_tags=data.get("else_add_tags", []),
            else_remove_tags=data.get("else_remove_tags", [])
        )

class RuleSchedule:
    """Schedule configuration for automated rule execution"""
    
    def __init__(self, enabled: bool = False, cron: str = ""):
        self.enabled = enabled
        self.cron = cron
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "cron": self.cron
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RuleSchedule':
        return cls(
            enabled=data.get("enabled", False),
            cron=data.get("cron", "")
        )

class ConditionalRule:
    """Complete conditional tagging rule"""
    
    def __init__(self, name: str, description: str = "", enabled: bool = True,
                 conditions: Optional[RuleConditionGroup] = None,
                 actions: Optional[RuleAction] = None,
                 schedule: Optional[RuleSchedule] = None,
                 rule_id: Optional[str] = None):
        self.id = rule_id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.enabled = enabled
        self.conditions = conditions or RuleConditionGroup()
        self.actions = actions or RuleAction()
        self.schedule = schedule or RuleSchedule()
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.last_run = None
        self.stats = {
            "total_matches": 0,
            "tags_added": 0,
            "tags_removed": 0,
            "last_execution_time": 0
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "conditions": self.conditions.to_dict(),
            "actions": self.actions.to_dict(),
            "schedule": self.schedule.to_dict(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "stats": self.stats
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConditionalRule':
        rule = cls(
            name=data["name"],
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
            rule_id=data.get("id")
        )
        
        # Set conditions
        if "conditions" in data:
            rule.conditions = RuleConditionGroup.from_dict(data["conditions"])
        
        # Set actions
        if "actions" in data:
            rule.actions = RuleAction.from_dict(data["actions"])
        
        # Set schedule
        if "schedule" in data:
            rule.schedule = RuleSchedule.from_dict(data["schedule"])
        
        # Set timestamps
        if "created_at" in data:
            rule.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            rule.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("last_run"):
            rule.last_run = datetime.fromisoformat(data["last_run"])
        
        # Set stats
        if "stats" in data:
            rule.stats = data["stats"]
        
        return rule
    
    def validate(self) -> List[str]:
        """Validate the rule and return list of errors"""
        errors = []
        
        if not self.name:
            errors.append("Rule name is required")
        
        if not self.conditions.conditions:
            errors.append("At least one condition is required")
        
        if (not self.actions.add_tags and not self.actions.remove_tags and 
            not self.actions.else_add_tags and not self.actions.else_remove_tags):
            errors.append("At least one action (THEN or ELSE add/remove tags) is required")
        
        # Validate cron expression if schedule is enabled
        if self.schedule.enabled:
            if not self.schedule.cron:
                errors.append("Cron expression is required when schedule is enabled")
            else:
                # Validate cron syntax
                try:
                    from apscheduler.triggers.cron import CronTrigger
                    CronTrigger.from_crontab(self.schedule.cron)
                except Exception as e:
                    errors.append(f"Invalid cron expression: {e}")
        
        return errors

class ExecutionResult:
    """Result of rule execution"""
    
    def __init__(self, rule_id: str, rule_name: str = "", success: bool = True):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.success = success
        self.timestamp = datetime.now(timezone.utc)
        self.matched_vms = []
        self.tags_added = {}
        self.tags_removed = {}
        self.tags_already_present = {}
        self.errors = []
        self.execution_time = 0
        self.dry_run = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
            "matched_vms": self.matched_vms,
            "tags_added": self.tags_added,
            "tags_removed": self.tags_removed,
            "tags_already_present": self.tags_already_present,
            "errors": self.errors,
            "execution_time": self.execution_time,
            "dry_run": self.dry_run
        }