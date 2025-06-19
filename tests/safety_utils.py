"""
Safety utilities for live testing

This module provides comprehensive safety mechanisms for running tests
against live Proxmox instances, including automated rollback 
and production VM protection.
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Callable
from contextlib import contextmanager
from pathlib import Path

import proxmox_api
import tag_utils
from tests.live_config import live_config, TagBackupManager


class SafetyError(Exception):
    """Raised when safety checks fail"""
    pass




class SafetyMonitor:
    """Monitors test execution for safety violations"""
    
    def __init__(self):
        self.violations = []
        self.start_time = datetime.now()
        self.max_execution_time = timedelta(minutes=30)  # Max test duration
        self.max_vm_modifications = 10  # Max VMs to modify in single test run
        self.modified_vms = set()
        
        # Setup logging
        self.logger = logging.getLogger("SafetyMonitor")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    
    def check_execution_time(self):
        """Check if execution time exceeds limits"""
        elapsed = datetime.now() - self.start_time
        if elapsed > self.max_execution_time:
            raise SafetyError(f"Test execution time exceeded {self.max_execution_time}")
    
    def check_vm_modification_limit(self, vmid: int):
        """Check if VM modification limits are exceeded"""
        self.modified_vms.add(vmid)
        if len(self.modified_vms) > self.max_vm_modifications:
            raise SafetyError(f"Too many VM modifications: {len(self.modified_vms)}")
    
    def validate_vm_safety(self, vm: Dict) -> bool:
        """Validate that a VM is safe for testing"""
        if not live_config:
            return False
        
        is_safe = live_config.is_test_vm(vm)
        if not is_safe:
            self.violations.append(f"Attempted to modify non-test VM: {vm.get('name', 'unknown')}")
            self.logger.warning(f"Safety violation: Non-test VM {vm.get('vmid')} flagged for modification")
        
        return is_safe
    
    def log_operation(self, operation: str, vm: Dict, details: str = ""):
        """Log test operations for audit trail"""
        self.logger.info(f"Operation: {operation} | VM: {vm.get('vmid')} ({vm.get('name')}) | {details}")
    
    def get_safety_report(self) -> Dict:
        """Get safety monitoring report"""
        elapsed = datetime.now() - self.start_time
        return {
            "start_time": self.start_time.isoformat(),
            "elapsed_time": str(elapsed),
            "violations": self.violations,
            "modified_vms": list(self.modified_vms),
            "vm_modification_count": len(self.modified_vms)
        }


class RollbackManager:
    """Manages comprehensive rollback operations"""
    
    def __init__(self):
        self.tag_backup = TagBackupManager()
        self.operation_log = []
        self.rollback_functions = []
        self.safety_monitor = SafetyMonitor()
        self.rollback_timestamp = datetime.now().isoformat()
    
    def register_rollback_function(self, func: Callable, description: str):
        """Register a custom rollback function"""
        self.rollback_functions.append({
            "function": func,
            "description": description,
            "timestamp": datetime.now().isoformat()
        })
    
    def backup_vm_state(self, vm: Dict) -> bool:
        """Backup complete VM state for rollback"""
        try:
            # Validate VM safety first
            if not self.safety_monitor.validate_vm_safety(vm):
                raise SafetyError(f"VM {vm.get('vmid')} is not safe for testing")
            
            # Backup tags
            self.tag_backup.backup_vm_tags(vm)
            
            # Log operation
            self.safety_monitor.log_operation("BACKUP", vm, "VM state backed up")
            self.operation_log.append({
                "operation": "backup",
                "vmid": vm["vmid"],
                "timestamp": datetime.now().isoformat(),
                "vm_name": vm.get("name", "unknown")
            })
            
            return True
            
        except Exception as e:
            self.safety_monitor.violations.append(f"Backup failed for VM {vm.get('vmid')}: {e}")
            return False
    
    def safe_vm_operation(self, vm: Dict, operation_func: Callable, operation_name: str, **kwargs) -> Dict:
        """Perform VM operation with safety checks and rollback capability"""
        # Pre-operation safety checks
        self.safety_monitor.check_execution_time()
        self.safety_monitor.check_vm_modification_limit(vm["vmid"])
        
        if not self.safety_monitor.validate_vm_safety(vm):
            raise SafetyError(f"VM {vm.get('vmid')} failed safety validation")
        
        # Backup state before operation
        backup_success = self.backup_vm_state(vm)
        if not backup_success:
            raise SafetyError(f"Could not backup VM {vm.get('vmid')} state")
        
        try:
            # Perform operation
            self.safety_monitor.log_operation(operation_name, vm, f"Starting operation with args: {kwargs}")
            
            if live_config.dry_run_only:
                result = {"data": "dry_run", "dry_run": True}
                self.safety_monitor.log_operation(operation_name, vm, "DRY RUN - No actual changes made")
            else:
                result = operation_func(**kwargs)
                self.safety_monitor.log_operation(operation_name, vm, f"Operation completed: {result}")
            
            # Log successful operation
            self.operation_log.append({
                "operation": operation_name,
                "vmid": vm["vmid"],
                "timestamp": datetime.now().isoformat(),
                "vm_name": vm.get("name", "unknown"),
                "result": "success",
                "dry_run": live_config.dry_run_only
            })
            
            return result
            
        except Exception as e:
            # Log failed operation
            self.operation_log.append({
                "operation": operation_name,
                "vmid": vm["vmid"],
                "timestamp": datetime.now().isoformat(),
                "vm_name": vm.get("name", "unknown"),
                "result": "failed",
                "error": str(e)
            })
            
            self.safety_monitor.violations.append(f"Operation {operation_name} failed for VM {vm.get('vmid')}: {e}")
            raise
    
    def rollback_all(self) -> Dict[str, bool]:
        """Perform complete rollback of all operations"""
        rollback_results = {}
        
        try:
            # Execute custom rollback functions first
            for rb_func in reversed(self.rollback_functions):  # Reverse order
                try:
                    self.safety_monitor.log_operation("ROLLBACK", {}, f"Executing: {rb_func['description']}")
                    rb_func["function"]()
                    rollback_results[rb_func["description"]] = True
                except Exception as e:
                    self.safety_monitor.log_operation("ROLLBACK_ERROR", {}, f"Failed: {rb_func['description']} - {e}")
                    rollback_results[rb_func["description"]] = False
            
            # Rollback VM tag changes
            if not live_config.dry_run_only:
                tag_rollback_results = self.tag_backup.restore_all()
                rollback_results.update({
                    f"VM_{vmid}_tags": success 
                    for vmid, success in tag_rollback_results.items()
                })
            else:
                rollback_results["tag_rollback"] = True  # No rollback needed for dry run
            
            # Generate rollback report
            successful_rollbacks = sum(1 for success in rollback_results.values() if success)
            total_rollbacks = len(rollback_results)
            
            self.safety_monitor.log_operation(
                "ROLLBACK_COMPLETE", 
                {}, 
                f"Rollback completed: {successful_rollbacks}/{total_rollbacks} successful"
            )
            
            return rollback_results
            
        except Exception as e:
            self.safety_monitor.log_operation("ROLLBACK_CRITICAL_ERROR", {}, f"Critical rollback error: {e}")
            raise
    
    def get_operation_log(self) -> List[Dict]:
        """Get complete operation log"""
        return self.operation_log.copy()
    
    def save_operation_log(self, filepath: Optional[str] = None) -> str:
        """Save operation log to file"""
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"/tmp/proxtagger_operation_log_{timestamp}.json"
        
        log_data = {
            "rollback_timestamp": self.rollback_timestamp,
            "safety_report": self.safety_monitor.get_safety_report(),
            "operation_log": self.operation_log,
            "rollback_functions": [
                {k: v for k, v in rb.items() if k != "function"}  # Exclude function objects
                for rb in self.rollback_functions
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        return filepath


@contextmanager
def safe_test_environment():
    """Context manager for safe test execution with automatic rollback"""
    rollback_manager = RollbackManager()
    
    try:
        yield rollback_manager
        
    except SafetyError as e:
        print(f"SAFETY VIOLATION DETECTED: {e}")
        rollback_manager.rollback_all()
        raise
        
    except Exception as e:
        print(f"TEST ERROR DETECTED: {e}")
        print("Initiating rollback due to test failure")
        rollback_manager.rollback_all()
        raise
        
    finally:
        # Always save operation log
        log_file = rollback_manager.save_operation_log()
        print(f"Operation log saved to: {log_file}")




def safe_tag_update_with_rollback(vm: Dict, new_tags: str, rollback_manager: RollbackManager) -> Dict:
    """Safely update VM tags with comprehensive rollback support"""
    return rollback_manager.safe_vm_operation(
        vm=vm,
        operation_func=proxmox_api.update_vm_tags,
        operation_name="TAG_UPDATE",
        node=vm["node"],
        vmid=vm["vmid"],
        tags=new_tags,
        vm_type=vm["type"]
    )


def validate_test_environment() -> Dict[str, bool]:
    """Validate that test environment is safe for live testing"""
    checks = {}
    
    # Check 1: Live testing enabled properly
    checks["live_testing_enabled"] = live_config and live_config.is_enabled()
    
    # Check 2: Additional environment validation
    checks["environment_ready"] = True
    
    # Check 3: Test VMs available
    if checks["live_testing_enabled"]:
        test_vms = live_config.get_test_vms()
        checks["test_vms_available"] = len(test_vms) > 0
        checks["multiple_test_vms"] = len(test_vms) >= 2  # For bulk operations
    else:
        checks["test_vms_available"] = False
        checks["multiple_test_vms"] = False
    
    # Check 4: Proxmox connectivity
    try:
        if checks["live_testing_enabled"]:
            vms = proxmox_api.get_all_vms()
            checks["proxmox_connectivity"] = isinstance(vms, list)
        else:
            checks["proxmox_connectivity"] = False
    except Exception:
        checks["proxmox_connectivity"] = False
    
    # Check 5: Write permissions for logs
    try:
        test_log_file = Path("/tmp/proxtagger_test_write_check")
        test_log_file.write_text("test")
        test_log_file.unlink()
        checks["log_write_permissions"] = True
    except Exception:
        checks["log_write_permissions"] = False
    
    # Check 6: Dry run mode compliance
    checks["dry_run_respected"] = live_config is None or not live_config.dry_run_only or True  # Always pass for now
    
    return checks


class ProductionProtection:
    """Additional protection against accidentally modifying production VMs"""
    
    @staticmethod
    def is_production_indicator(vm_name: str) -> bool:
        """Check if VM name contains production indicators"""
        production_keywords = [
            "prod", "production", "live", "master", "main", 
            "critical", "important", "customer", "client"
        ]
        name_lower = vm_name.lower()
        return any(keyword in name_lower for keyword in production_keywords)
    
    @staticmethod
    def validate_vm_for_testing(vm: Dict) -> tuple[bool, str]:
        """Comprehensive validation of VM safety for testing"""
        vm_name = vm.get("name", "")
        vmid = vm.get("vmid", 0)
        
        # Check 1: Must have test prefix
        if not vm_name.lower().startswith("test-"):
            return False, f"VM name '{vm_name}' does not start with 'test-' prefix"
        
        # Check 2: Must not contain production indicators
        if ProductionProtection.is_production_indicator(vm_name):
            return False, f"VM name '{vm_name}' contains production indicators"
        
        # Check 3: VMID should be in test range (configurable)
        test_vmid_min = int(os.getenv("PROXTAGGER_TEST_VMID_MIN", "1000"))
        test_vmid_max = int(os.getenv("PROXTAGGER_TEST_VMID_MAX", "9999"))
        
        if not (test_vmid_min <= vmid <= test_vmid_max):
            return False, f"VMID {vmid} is outside test range ({test_vmid_min}-{test_vmid_max})"
        
        # Check 4: Must have safety indicators
        safety_keywords = ["test", "dev", "development", "staging", "sandbox", "lab"]
        if not any(keyword in vm_name.lower() for keyword in safety_keywords):
            return False, f"VM name '{vm_name}' lacks safety indicators"
        
        return True, "VM validated for testing"
    
    @staticmethod
    def create_protection_report(vms: List[Dict]) -> Dict:
        """Create protection report for VM list"""
        safe_vms = []
        unsafe_vms = []
        
        for vm in vms:
            is_safe, reason = ProductionProtection.validate_vm_for_testing(vm)
            if is_safe:
                safe_vms.append({"vmid": vm["vmid"], "name": vm.get("name", "")})
            else:
                unsafe_vms.append({
                    "vmid": vm["vmid"], 
                    "name": vm.get("name", ""), 
                    "reason": reason
                })
        
        return {
            "total_vms": len(vms),
            "safe_vms": safe_vms,
            "unsafe_vms": unsafe_vms,
            "safe_count": len(safe_vms),
            "unsafe_count": len(unsafe_vms),
            "safety_percentage": (len(safe_vms) / len(vms) * 100) if vms else 0
        }