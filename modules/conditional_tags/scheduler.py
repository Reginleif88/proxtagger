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
from .storage import ExecutionHistory, get_rule_storage
from .engine import RuleEngine
from .models import ConditionalRule
from proxmox_api import get_all_vms

logger = logging.getLogger(__name__)

class RuleScheduler:
    """Manages scheduled execution of conditional rules"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.storage = get_rule_storage()
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
        existing_count = len(self.jobs)
        logger.info(f"Removing {existing_count} existing scheduled jobs")
        for job_id in list(self.jobs.keys()):
            self.remove_schedule(job_id)
        
        # Schedule all enabled rules
        rules = self.storage.get_all_rules()
        logger.info(f"Found {len(rules)} total rules in storage")
        
        scheduled_count = 0
        for rule in rules:
            if rule.enabled and rule.schedule.enabled and rule.schedule.cron:
                logger.debug(f"Scheduling rule '{rule.name}' (ID: {rule.id}) with cron: {rule.schedule.cron}")
                self.add_schedule(rule)
                scheduled_count += 1
            else:
                reasons = []
                if not rule.enabled:
                    reasons.append("rule disabled")
                if not rule.schedule.enabled:
                    reasons.append("schedule disabled")
                if not rule.schedule.cron:
                    reasons.append("no cron expression")
                logger.debug(f"Skipping rule '{rule.name}' (ID: {rule.id}): {', '.join(reasons)}")
        
        logger.info(f"Scheduled {scheduled_count} rules out of {len(rules)} total rules")
        logger.info(f"Active APScheduler jobs: {len(self.scheduler.get_jobs())}")
    
    def add_schedule(self, rule: ConditionalRule):
        """Add a scheduled job for a rule"""
        logger.debug(f"Attempting to schedule rule '{rule.name}' (ID: {rule.id})")
        
        if not rule.schedule.enabled:
            logger.info(f"Rule '{rule.name}' (ID: {rule.id}) not scheduled - schedule is disabled")
            return
            
        if not rule.schedule.cron:
            logger.info(f"Rule '{rule.name}' (ID: {rule.id}) not scheduled - no cron expression provided")
            return
        
        try:
            # Remove existing job if any
            if rule.id in self.jobs:
                logger.debug(f"Removing existing schedule for rule '{rule.name}' (ID: {rule.id})")
                self.remove_schedule(rule.id)
            
            # Create new job with cron validation
            try:
                trigger = CronTrigger.from_crontab(rule.schedule.cron)
                logger.debug(f"Created CronTrigger for rule '{rule.name}' with expression: {rule.schedule.cron}")
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
            logger.info(f"Successfully scheduled rule '{rule.name}' (ID: {rule.id}) with cron: {rule.schedule.cron}")
            
            # Log next run time for verification
            if job.next_run_time:
                logger.info(f"Next execution for rule '{rule.name}' scheduled at: {job.next_run_time}")
            else:
                logger.warning(f"Rule '{rule.name}' scheduled but no next_run_time available")
            
            # Log current scheduler state
            logger.debug(f"Total scheduled jobs: {len(self.scheduler.get_jobs())}")
            logger.debug(f"Scheduler running: {self.scheduler.running}")
            
        except Exception as e:
            logger.error(f"Error scheduling rule '{rule.name}' (ID: {rule.id}): {e}", exc_info=True)
    
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
        logger.info(f"[SCHEDULER] Starting execution of rule: {rule_id}")
        
        # Get the rule
        rule = self.storage.get_rule(rule_id)
        if not rule or not rule.enabled:
            logger.warning(f"[SCHEDULER] Rule {rule_id} not found or disabled")
            return
        
        logger.info(f"[SCHEDULER] Executing rule '{rule.name}' with conditions: {rule.conditions}")
        logger.info(f"[SCHEDULER] Rule actions - add_tags: {rule.actions.add_tags}, remove_tags: {rule.actions.remove_tags}")
        
        try:
            # Get enriched VM data
            from .api import enrich_vm_data
            vms = get_all_vms()
            logger.info(f"[SCHEDULER] Retrieved {len(vms)} VMs from Proxmox")
            enriched_vms = []
            
            # Enrich VM data for rules that need extended properties
            # Only enrich if rule uses extended properties to save API calls
            needs_enrichment = self._rule_needs_enrichment(rule)
            logger.info(f"[SCHEDULER] Rule needs enrichment: {needs_enrichment}")
            
            if needs_enrichment:
                for vm in vms:
                    enriched_vms.append(enrich_vm_data(vm))
            else:
                enriched_vms = vms
            
            # Execute the rule
            logger.info(f"[SCHEDULER] Evaluating rule against {len(enriched_vms)} VMs")
            result = self.engine.evaluate_rule(rule, enriched_vms, dry_run=False)
            
            # Log detailed results
            logger.info(f"[SCHEDULER] Rule evaluation result - Success: {result.success}")
            logger.info(f"[SCHEDULER] Matched VMs: {result.matched_vms}")
            logger.info(f"[SCHEDULER] Tags added: {result.tags_added}")
            logger.info(f"[SCHEDULER] Tags removed: {result.tags_removed}")
            logger.info(f"[SCHEDULER] Tags already present: {result.tags_already_present}")
            if result.errors:
                logger.error(f"[SCHEDULER] Errors during execution: {result.errors}")
            
            # Update statistics
            self.storage.update_rule_stats(rule_id, result)
            
            # Save execution history
            self.history.add_execution(result)
            
            if result.success:
                logger.info(f"[SCHEDULER] Rule '{rule.name}' completed successfully: "
                          f"{len(result.matched_vms)} VMs matched, "
                          f"{sum(len(tags) for tags in result.tags_added.values())} tags added, "
                          f"{sum(len(tags) for tags in result.tags_removed.values())} tags removed")
            else:
                logger.error(f"[SCHEDULER] Rule '{rule.name}' execution failed: {result.errors}")
                
        except Exception as e:
            logger.error(f"[SCHEDULER] Error executing rule {rule_id}: {e}", exc_info=True)
    
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
    
    def verify_schedules(self) -> Dict[str, any]:
        """Verify that all scheduled rules are properly registered with APScheduler"""
        verification = {
            'scheduler_running': self.scheduler.running,
            'registered_jobs': len(self.jobs),
            'active_jobs': len(self.scheduler.get_jobs()),
            'mismatches': [],
            'job_details': []
        }
        
        # Check each registered job
        for rule_id, job_id in self.jobs.items():
            job = self.scheduler.get_job(job_id)
            if not job:
                verification['mismatches'].append({
                    'rule_id': rule_id,
                    'job_id': job_id,
                    'issue': 'Job registered but not found in scheduler'
                })
            else:
                verification['job_details'].append({
                    'rule_id': rule_id,
                    'job_id': job_id,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                    'pending': job.pending
                })
        
        # Log verification results
        logger.info(f"Schedule verification: {verification['registered_jobs']} registered, "
                   f"{verification['active_jobs']} active in scheduler")
        
        if verification['mismatches']:
            logger.warning(f"Found {len(verification['mismatches'])} scheduling mismatches")
        
        return verification

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