"""
Storage operations for conditional rules
"""

import json
import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from .models import ConditionalRule, ExecutionResult

logger = logging.getLogger(__name__)

class RuleStorage:
    """Handles persistence of conditional rules"""
    
    def __init__(self, storage_file: str = "data/conditional_rules.json"):
        self.storage_file = storage_file
        self.rules = self._load_rules()
    
    def _load_rules(self) -> Dict[str, ConditionalRule]:
        """Load rules from storage file"""
        if not os.path.exists(self.storage_file):
            return {}
        
        try:
            with open(self.storage_file, 'r') as f:
                data = json.load(f)
                rules = {}
                for rule_data in data.get('rules', []):
                    rule = ConditionalRule.from_dict(rule_data)
                    rules[rule.id] = rule
                return rules
        except Exception as e:
            logger.error(f"Error loading rules: {e}")
            return {}
    
    def _save_rules(self):
        """Save rules to storage file"""
        try:
            data = {
                'rules': [rule.to_dict() for rule in self.rules.values()],
                'version': '1.0',
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving rules: {e}")
            raise
    
    def get_all_rules(self) -> List[ConditionalRule]:
        """Get all rules"""
        return list(self.rules.values())
    
    def get_rule(self, rule_id: str) -> Optional[ConditionalRule]:
        """Get a specific rule by ID"""
        return self.rules.get(rule_id)
    
    def create_rule(self, rule: ConditionalRule) -> ConditionalRule:
        """Create a new rule"""
        # Validate rule
        errors = rule.validate()
        if errors:
            raise ValueError(f"Invalid rule: {', '.join(errors)}")
        
        # Check for duplicate names
        for existing_rule in self.rules.values():
            if existing_rule.name == rule.name and existing_rule.id != rule.id:
                raise ValueError(f"Rule with name '{rule.name}' already exists")
        
        self.rules[rule.id] = rule
        self._save_rules()
        logger.info(f"Created rule: {rule.name}")
        return rule
    
    def update_rule(self, rule_id: str, updates: Dict[str, Any]) -> Optional[ConditionalRule]:
        """Update an existing rule"""
        rule = self.get_rule(rule_id)
        if not rule:
            return None
        
        # Update fields
        if 'name' in updates:
            rule.name = updates['name']
        if 'description' in updates:
            rule.description = updates['description']
        if 'enabled' in updates:
            rule.enabled = updates['enabled']
        if 'conditions' in updates:
            from .models import RuleConditionGroup
            rule.conditions = RuleConditionGroup.from_dict(updates['conditions'])
        if 'actions' in updates:
            from .models import RuleAction
            rule.actions = RuleAction.from_dict(updates['actions'])
        if 'schedule' in updates:
            from .models import RuleSchedule
            rule.schedule = RuleSchedule.from_dict(updates['schedule'])
        
        # Check for duplicate names (exclude current rule)
        if 'name' in updates:
            for existing_rule in self.rules.values():
                if existing_rule.name == rule.name and existing_rule.id != rule.id:
                    raise ValueError(f"Rule with name '{rule.name}' already exists")
        
        # Update timestamp
        rule.updated_at = datetime.now(timezone.utc)
        
        # Validate updated rule
        errors = rule.validate()
        if errors:
            raise ValueError(f"Invalid rule: {', '.join(errors)}")
        
        self._save_rules()
        logger.info(f"Updated rule: {rule.name}")
        return rule
    
    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule"""
        if rule_id in self.rules:
            rule_name = self.rules[rule_id].name
            del self.rules[rule_id]
            self._save_rules()
            logger.info(f"Deleted rule: {rule_name}")
            return True
        return False
    
    def update_rule_stats(self, rule_id: str, result: ExecutionResult):
        """Update rule statistics after execution"""
        rule = self.get_rule(rule_id)
        if not rule:
            return
        
        rule.last_run = result.timestamp
        rule.stats['total_matches'] += len(result.matched_vms)
        rule.stats['tags_added'] += sum(len(tags) for tags in result.tags_added.values())
        rule.stats['tags_removed'] += sum(len(tags) for tags in result.tags_removed.values())
        rule.stats['last_execution_time'] = result.execution_time
        
        self._save_rules()

class ExecutionHistory:
    """Handles storage of rule execution history"""
    
    def __init__(self, history_file: str = "data/rule_execution_history.json"):
        self.history_file = history_file
        self.max_history_per_rule = 100  # Keep last 100 executions per rule
    
    def add_execution(self, result: ExecutionResult):
        """Add an execution result to history"""
        history = self._load_history()
        
        # Add new execution
        rule_history = history.get(result.rule_id, [])
        rule_history.insert(0, result.to_dict())
        
        # Trim to max history
        rule_history = rule_history[:self.max_history_per_rule]
        history[result.rule_id] = rule_history
        
        self._save_history(history)
    
    def get_rule_history(self, rule_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get execution history for a specific rule"""
        history = self._load_history()
        rule_history = history.get(rule_id, [])
        return rule_history[:limit]
    
    def get_recent_executions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent executions across all rules"""
        history = self._load_history()
        
        # Collect all executions from all rules
        all_executions = []
        for rule_id, rule_history in history.items():
            for execution in rule_history:
                # Ensure execution has rule_id
                if 'rule_id' not in execution:
                    execution['rule_id'] = rule_id
                all_executions.append(execution)
        
        # Sort by timestamp (most recent first)
        all_executions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return all_executions[:limit]
    
    def _load_history(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load history from file"""
        if not os.path.exists(self.history_file):
            return {}
        
        try:
            with open(self.history_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading history: {e}")
            return {}
    
    def _save_history(self, history: Dict[str, List[Dict[str, Any]]]):
        """Save history to file"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving history: {e}")