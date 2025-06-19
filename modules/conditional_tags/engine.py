"""
Rule evaluation engine for conditional tagging
"""

import re
import time
import logging
from typing import Dict, List, Any, Tuple
from .models import (
    ConditionalRule, RuleCondition, OperatorType, 
    LogicalOperator, ExecutionResult
)

logger = logging.getLogger(__name__)

class RuleEngine:
    """Engine for evaluating conditional rules against VMs"""
    
    def __init__(self):
        self.operators = {
            OperatorType.EQUALS: self._op_equals,
            OperatorType.NOT_EQUALS: self._op_not_equals,
            OperatorType.CONTAINS: self._op_contains,
            OperatorType.NOT_CONTAINS: self._op_not_contains,
            OperatorType.GREATER_THAN: self._op_greater_than,
            OperatorType.LESS_THAN: self._op_less_than,
            OperatorType.GREATER_EQUALS: self._op_greater_equals,
            OperatorType.LESS_EQUALS: self._op_less_equals,
            OperatorType.REGEX: self._op_regex,
            OperatorType.IN: self._op_in,
            OperatorType.NOT_IN: self._op_not_in
        }
    
    def evaluate_rule(self, rule: ConditionalRule, vms: List[Dict[str, Any]], 
                     dry_run: bool = False) -> ExecutionResult:
        """
        Evaluate a rule against a list of VMs
        
        Args:
            rule: The conditional rule to evaluate
            vms: List of VM dictionaries from Proxmox API
            dry_run: If True, don't actually apply changes
            
        Returns:
            ExecutionResult with details of the execution
        """
        start_time = time.time()
        result = ExecutionResult(rule.id, rule.name)
        result.dry_run = dry_run
        
        try:
            # Separate VMs into matched and non-matched groups
            matched_vms = []
            non_matched_vms = []
            
            for vm in vms:
                if self._evaluate_conditions(rule.conditions, vm):
                    matched_vms.append(vm)
                else:
                    non_matched_vms.append(vm)
            
            result.matched_vms = [vm['vmid'] for vm in matched_vms]
            
            # Apply THEN actions to matched VMs
            if matched_vms:
                if dry_run:
                    self._simulate_then_actions(rule, matched_vms, result)
                else:
                    self._apply_then_actions(rule, matched_vms, result)
            
            # Apply ELSE actions to non-matched VMs (if any ELSE actions are defined)
            if non_matched_vms and (rule.actions.else_add_tags or rule.actions.else_remove_tags):
                if dry_run:
                    self._simulate_else_actions(rule, non_matched_vms, result)
                else:
                    self._apply_else_actions(rule, non_matched_vms, result)
            
            result.execution_time = time.time() - start_time
            logger.info(f"Rule '{rule.name}' evaluated: {len(matched_vms)} VMs matched, {len(non_matched_vms)} VMs non-matched")
            
        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            logger.error(f"Error evaluating rule '{rule.name}': {e}")
        
        return result
    
    def _evaluate_conditions(self, condition_group, vm: Dict[str, Any]) -> bool:
        """Evaluate a group of conditions against a VM"""
        if not condition_group.conditions:
            return False
        
        results = []
        for condition in condition_group.conditions:
            results.append(self._evaluate_condition(condition, vm))
        
        if condition_group.operator == LogicalOperator.AND:
            return all(results)
        else:  # OR
            return any(results)
    
    def _evaluate_condition(self, condition: RuleCondition, vm: Dict[str, Any]) -> bool:
        """Evaluate a single condition against a VM"""
        # Get the field value from the VM
        field_value = self._get_field_value(vm, condition.field)
        
        # Get the appropriate operator function
        op_func = self.operators.get(condition.operator)
        if not op_func:
            logger.warning(f"Unknown operator: {condition.operator}")
            return False
        
        # Evaluate the condition
        try:
            return op_func(field_value, condition.value)
        except Exception as e:
            logger.error(f"Error evaluating condition: {e}")
            return False
    
    def _get_field_value(self, vm: Dict[str, Any], field_path: str) -> Any:
        """
        Get a field value from VM data, supporting nested paths
        e.g., "config.ostype" -> vm['config']['ostype']
        """
        parts = field_path.split('.')
        value = vm
        
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        
        return value
    
    def _apply_then_actions(self, rule: ConditionalRule, vms: List[Dict[str, Any]], 
                           result: ExecutionResult):
        """Apply THEN actions to matched VMs"""
        from proxmox_api import update_vm_tags
        from tag_utils import parse_tags, format_tags
        
        for vm in vms:
            vmid = vm['vmid']
            node = vm['node']
            vm_type = vm['type']
            current_tags = parse_tags(vm.get('tags', ''))
            
            # Calculate new tags (normalize to lowercase)
            new_tags = set(tag.lower() for tag in current_tags)
            
            # Add tags
            if rule.actions.add_tags:
                for tag in rule.actions.add_tags:
                    tag_lower = tag.lower()
                    if tag_lower not in new_tags:
                        new_tags.add(tag_lower)
                        result.tags_added.setdefault(vmid, []).append(tag_lower)
                    else:
                        result.tags_already_present.setdefault(vmid, []).append(tag_lower)
            
            # Remove tags
            if rule.actions.remove_tags:
                for tag in rule.actions.remove_tags:
                    tag_lower = tag.lower()
                    if tag_lower in new_tags:
                        new_tags.remove(tag_lower)
                        result.tags_removed.setdefault(vmid, []).append(tag_lower)
            
            # Update VM if tags changed
            if new_tags != set(current_tags):
                try:
                    formatted_tags = format_tags(list(new_tags))
                    update_vm_tags(node, vmid, formatted_tags, vm_type)
                except Exception as e:
                    result.errors.append(f"Failed to update VM {vmid}: {e}")
    
    def _apply_else_actions(self, rule: ConditionalRule, vms: List[Dict[str, Any]], 
                           result: ExecutionResult):
        """Apply ELSE actions to non-matched VMs"""
        from proxmox_api import update_vm_tags
        from tag_utils import parse_tags, format_tags
        
        for vm in vms:
            vmid = vm['vmid']
            node = vm['node']
            vm_type = vm['type']
            current_tags = parse_tags(vm.get('tags', ''))
            
            # Calculate new tags (normalize to lowercase)
            new_tags = set(tag.lower() for tag in current_tags)
            
            # Add ELSE tags
            if rule.actions.else_add_tags:
                for tag in rule.actions.else_add_tags:
                    tag_lower = tag.lower()
                    if tag_lower not in new_tags:
                        new_tags.add(tag_lower)
                        result.tags_added.setdefault(vmid, []).append(tag_lower)
                    else:
                        result.tags_already_present.setdefault(vmid, []).append(tag_lower)
            
            # Remove ELSE tags
            if rule.actions.else_remove_tags:
                for tag in rule.actions.else_remove_tags:
                    tag_lower = tag.lower()
                    if tag_lower in new_tags:
                        new_tags.remove(tag_lower)
                        result.tags_removed.setdefault(vmid, []).append(tag_lower)
            
            # Update VM if tags changed
            if new_tags != set(current_tags):
                try:
                    formatted_tags = format_tags(list(new_tags))
                    update_vm_tags(node, vmid, formatted_tags, vm_type)
                except Exception as e:
                    result.errors.append(f"Failed to update VM {vmid}: {e}")
    
    def _simulate_then_actions(self, rule: ConditionalRule, vms: List[Dict[str, Any]], 
                              result: ExecutionResult):
        """Simulate THEN actions without applying them (dry run)"""
        from tag_utils import parse_tags
        
        for vm in vms:
            vmid = vm['vmid']
            current_tags = parse_tags(vm.get('tags', ''))
            
            # Calculate what would be added/removed
            new_tags = set(current_tags)
            
            # Simulate adding tags
            if rule.actions.add_tags:
                for tag in rule.actions.add_tags:
                    tag_lower = tag.lower()
                    if tag_lower not in new_tags:
                        new_tags.add(tag_lower)
                        result.tags_added.setdefault(vmid, []).append(tag_lower)
                    else:
                        result.tags_already_present.setdefault(vmid, []).append(tag_lower)
            
            # Simulate removing tags
            if rule.actions.remove_tags:
                for tag in rule.actions.remove_tags:
                    tag_lower = tag.lower()
                    if tag_lower in new_tags:
                        new_tags.remove(tag_lower)
                        result.tags_removed.setdefault(vmid, []).append(tag_lower)
    
    def _simulate_else_actions(self, rule: ConditionalRule, vms: List[Dict[str, Any]], 
                              result: ExecutionResult):
        """Simulate ELSE actions without applying them (dry run)"""
        from tag_utils import parse_tags
        
        for vm in vms:
            vmid = vm['vmid']
            current_tags = parse_tags(vm.get('tags', ''))
            
            # Calculate what would be added/removed
            new_tags = set(current_tags)
            
            # Simulate adding ELSE tags
            if rule.actions.else_add_tags:
                for tag in rule.actions.else_add_tags:
                    tag_lower = tag.lower()
                    if tag_lower not in new_tags:
                        new_tags.add(tag_lower)
                        result.tags_added.setdefault(vmid, []).append(tag_lower)
                    else:
                        result.tags_already_present.setdefault(vmid, []).append(tag_lower)
            
            # Simulate removing ELSE tags
            if rule.actions.else_remove_tags:
                for tag in rule.actions.else_remove_tags:
                    tag_lower = tag.lower()
                    if tag_lower in new_tags:
                        new_tags.remove(tag_lower)
                        result.tags_removed.setdefault(vmid, []).append(tag_lower)
    
    # Operator implementations
    def _op_equals(self, field_value: Any, compare_value: Any) -> bool:
        return str(field_value).lower() == str(compare_value).lower()
    
    def _op_not_equals(self, field_value: Any, compare_value: Any) -> bool:
        return str(field_value).lower() != str(compare_value).lower()
    
    def _op_contains(self, field_value: Any, compare_value: Any) -> bool:
        return str(compare_value).lower() in str(field_value).lower()
    
    def _op_not_contains(self, field_value: Any, compare_value: Any) -> bool:
        return str(compare_value).lower() not in str(field_value).lower()
    
    def _op_greater_than(self, field_value: Any, compare_value: Any) -> bool:
        try:
            return float(field_value) > float(compare_value)
        except (ValueError, TypeError):
            return False
    
    def _op_less_than(self, field_value: Any, compare_value: Any) -> bool:
        try:
            return float(field_value) < float(compare_value)
        except (ValueError, TypeError):
            return False
    
    def _op_greater_equals(self, field_value: Any, compare_value: Any) -> bool:
        try:
            return float(field_value) >= float(compare_value)
        except (ValueError, TypeError):
            return False
    
    def _op_less_equals(self, field_value: Any, compare_value: Any) -> bool:
        try:
            return float(field_value) <= float(compare_value)
        except (ValueError, TypeError):
            return False
    
    def _op_regex(self, field_value: Any, pattern: str) -> bool:
        try:
            return bool(re.search(pattern, str(field_value)))
        except re.error:
            logger.error(f"Invalid regex pattern: {pattern}")
            return False
    
    def _op_in(self, field_value: Any, compare_list: List[Any]) -> bool:
        if not isinstance(compare_list, list):
            compare_list = [compare_list]
        return str(field_value).lower() in [str(v).lower() for v in compare_list]
    
    def _op_not_in(self, field_value: Any, compare_list: List[Any]) -> bool:
        if not isinstance(compare_list, list):
            compare_list = [compare_list]
        return str(field_value).lower() not in [str(v).lower() for v in compare_list]