"""
Scheduler for automated rule execution
"""

import logging
import atexit
import threading
from datetime import datetime
from typing import Dict, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from .storage import RuleStorage, ExecutionHistory
from .engine import RuleEngine
from .models import ConditionalRule
from proxmox_api import get_all_vms

logger = logging.getLogger(__name__)

class RuleScheduler:
    """Manages scheduled execution of conditional rules"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.storage = RuleStorage()
        self.history = ExecutionHistory()
        self.engine = RuleEngine()
        self.jobs = {}  # Track job IDs for each rule
        
        # Start scheduler
        self.scheduler.start()
        
        # Register cleanup on shutdown
        atexit.register(self.shutdown)
        
        # Load and schedule all enabled rules
        self.reload_schedules()
    
    def shutdown(self):
        """Gracefully shutdown the scheduler"""
        logger.info("Shutting down rule scheduler")
        self.scheduler.shutdown(wait=False)
    
    def reload_schedules(self):
        """Reload all rule schedules from storage"""
        logger.info("Reloading rule schedules")
        
        # Remove all existing jobs
        for job_id in list(self.jobs.keys()):
            self.remove_schedule(job_id)
        
        # Schedule all enabled rules
        rules = self.storage.get_all_rules()
        for rule in rules:
            if rule.enabled and rule.schedule.enabled and rule.schedule.cron:
                self.add_schedule(rule)
    
    def add_schedule(self, rule: ConditionalRule):
        """Add a scheduled job for a rule"""
        if not rule.schedule.enabled or not rule.schedule.cron:
            return
        
        try:
            # Remove existing job if any
            if rule.id in self.jobs:
                self.remove_schedule(rule.id)
            
            # Create new job with cron validation
            try:
                trigger = CronTrigger.from_crontab(rule.schedule.cron)
            except Exception as e:
                logger.error(f"Invalid cron expression '{rule.schedule.cron}' for rule {rule.id}: {e}")
                return
            
            job = self.scheduler.add_job(
                func=self._execute_rule,
                trigger=trigger,
                args=[rule.id],
                id=f"rule_{rule.id}",
                name=f"Rule: {rule.name}",
                replace_existing=True
            )
            
            self.jobs[rule.id] = job.id
            logger.info(f"Scheduled rule '{rule.name}' with cron: {rule.schedule.cron}")
            
        except Exception as e:
            logger.error(f"Error scheduling rule '{rule.name}': {e}")
    
    def remove_schedule(self, rule_id: str):
        """Remove a scheduled job for a rule"""
        job_id = self.jobs.get(rule_id)
        if job_id:
            try:
                self.scheduler.remove_job(job_id)
                del self.jobs[rule_id]
                logger.info(f"Removed schedule for rule ID: {rule_id}")
            except Exception as e:
                logger.error(f"Error removing schedule: {e}")
    
    def update_schedule(self, rule: ConditionalRule):
        """Update schedule for a rule (remove and re-add)"""
        self.remove_schedule(rule.id)
        if rule.enabled and rule.schedule.enabled:
            self.add_schedule(rule)
    
    def _execute_rule(self, rule_id: str):
        """Execute a rule (called by scheduler)"""
        logger.info(f"Executing scheduled rule: {rule_id}")
        
        # Get the rule
        rule = self.storage.get_rule(rule_id)
        if not rule or not rule.enabled:
            logger.warning(f"Rule {rule_id} not found or disabled")
            return
        
        try:
            # Get enriched VM data
            from .api import enrich_vm_data
            vms = get_all_vms()
            enriched_vms = []
            
            # Enrich VM data for rules that need extended properties
            # Only enrich if rule uses extended properties to save API calls
            needs_enrichment = self._rule_needs_enrichment(rule)
            
            if needs_enrichment:
                for vm in vms:
                    enriched_vms.append(enrich_vm_data(vm))
            else:
                enriched_vms = vms
            
            # Execute the rule
            result = self.engine.evaluate_rule(rule, enriched_vms, dry_run=False)
            
            # Update statistics
            self.storage.update_rule_stats(rule_id, result)
            
            # Save execution history
            self.history.add_execution(result)
            
            if result.success:
                logger.info(f"Rule '{rule.name}' executed successfully: "
                          f"{len(result.matched_vms)} VMs matched")
            else:
                logger.error(f"Rule '{rule.name}' execution failed: {result.errors}")
                
        except Exception as e:
            logger.error(f"Error executing rule {rule_id}: {e}")
    
    def _rule_needs_enrichment(self, rule: ConditionalRule) -> bool:
        """Check if rule uses properties that require enrichment"""
        extended_fields = [
            'config.', 'ha.', 'replication.', 'snapshots.', 'backup.'
        ]
        
        for condition in rule.conditions.conditions:
            for field_prefix in extended_fields:
                if condition.field.startswith(field_prefix):
                    return True
        
        return False
    
    def get_next_run_time(self, rule_id: str) -> Optional[datetime]:
        """Get next scheduled run time for a rule"""
        job_id = self.jobs.get(rule_id)
        if job_id:
            job = self.scheduler.get_job(job_id)
            if job:
                return job.next_run_time
        return None
    
    def get_schedule_info(self) -> Dict[str, Dict]:
        """Get information about all scheduled rules"""
        info = {}
        
        for rule_id, job_id in self.jobs.items():
            job = self.scheduler.get_job(job_id)
            if job:
                rule = self.storage.get_rule(rule_id)
                info[rule_id] = {
                    'rule_name': rule.name if rule else 'Unknown',
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                    'cron': rule.schedule.cron if rule else None
                }
        
        return info

# Global scheduler instance
scheduler_instance = None
scheduler_lock = threading.Lock()

def get_scheduler() -> RuleScheduler:
    """Get or create the global scheduler instance"""
    global scheduler_instance
    if scheduler_instance is None:
        with scheduler_lock:
            # Double-check locking pattern
            if scheduler_instance is None:
                scheduler_instance = RuleScheduler()
    return scheduler_instance