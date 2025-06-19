"""
Routes for conditional tagging feature
"""

from flask import render_template, request, jsonify, redirect, url_for, send_file
from . import conditional_tags_bp
from .storage import RuleStorage, ExecutionHistory
from .engine import RuleEngine
from .models import ConditionalRule, RuleConditionGroup, RuleAction, RuleSchedule
from .scheduler import get_scheduler
from .api import get_available_vm_properties, enrich_vm_data, enrich_vm_data_selective
from proxmox_api import get_all_vms
from config import load_config
import logging
import json
import io
from datetime import datetime

logger = logging.getLogger(__name__)

# Initialize components
storage = RuleStorage()
history = ExecutionHistory()
engine = RuleEngine()

@conditional_tags_bp.route('/')
def index():
    """Main conditional tags page"""
    # Use same logic as main app for connection check
    config = load_config()
    try:
        vms = get_all_vms()
        
        # Check for permission issues where we connect but get no VMs
        if len(vms) == 0:
            logger.warning("No VMs found - redirecting to main config")
            return redirect(url_for('index'))
            
        # Normal case: we have VMs and everything is OK    
        logger.info(f"Rendering conditional tags page with {len(vms)} VMs")
        return render_template('conditional_tags/index.html', config_ok=True)
        
    except Exception as e:
        logger.error("Error fetching VMs: %s", e)
        # Redirect to main app for configuration
        return redirect(url_for('index'))

@conditional_tags_bp.route('/api/rules', methods=['GET'])
def api_get_rules():
    """Get all conditional rules"""
    try:
        rules = storage.get_all_rules()
        scheduler = get_scheduler()
        
        # Add schedule info to each rule
        rules_data = []
        for rule in rules:
            rule_data = rule.to_dict()
            rule_data['next_run'] = None
            
            if rule.schedule.enabled:
                next_run = scheduler.get_next_run_time(rule.id)
                if next_run:
                    rule_data['next_run'] = next_run.isoformat()
            
            rules_data.append(rule_data)
        
        return jsonify(rules_data)
    except Exception as e:
        logger.error(f"Error getting rules: {e}")
        return jsonify({"error": str(e)}), 500

@conditional_tags_bp.route('/api/rules', methods=['POST'])
def api_create_rule():
    """Create a new conditional rule"""
    try:
        data = request.get_json()
        
        # Create rule object
        rule = ConditionalRule(
            name=data['name'],
            description=data.get('description', ''),
            enabled=data.get('enabled', True)
        )
        
        # Set conditions
        if 'conditions' in data:
            rule.conditions = RuleConditionGroup.from_dict(data['conditions'])
        
        # Set actions
        if 'actions' in data:
            rule.actions = RuleAction.from_dict(data['actions'])
        
        # Set schedule
        if 'schedule' in data:
            rule.schedule = RuleSchedule.from_dict(data['schedule'])
        
        # Save rule
        created_rule = storage.create_rule(rule)
        
        # Update scheduler
        scheduler = get_scheduler()
        scheduler.add_schedule(created_rule)
        
        return jsonify(created_rule.to_dict()), 201
    except Exception as e:
        logger.error(f"Error creating rule: {e}")
        return jsonify({"error": str(e)}), 400

@conditional_tags_bp.route('/api/rules/<rule_id>', methods=['PUT'])
def api_update_rule(rule_id):
    """Update an existing rule"""
    try:
        data = request.get_json()
        updated_rule = storage.update_rule(rule_id, data)
        
        if not updated_rule:
            return jsonify({"error": "Rule not found"}), 404
        
        # Update scheduler
        scheduler = get_scheduler()
        scheduler.update_schedule(updated_rule)
        
        return jsonify(updated_rule.to_dict())
    except Exception as e:
        logger.error(f"Error updating rule: {e}")
        return jsonify({"error": str(e)}), 400

@conditional_tags_bp.route('/api/rules/<rule_id>', methods=['DELETE'])
def api_delete_rule(rule_id):
    """Delete a rule"""
    try:
        # Remove from scheduler first
        scheduler = get_scheduler()
        scheduler.remove_schedule(rule_id)
        
        # Delete rule
        success = storage.delete_rule(rule_id)
        
        if not success:
            return jsonify({"error": "Rule not found"}), 404
        
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error deleting rule: {e}")
        return jsonify({"error": str(e)}), 500

@conditional_tags_bp.route('/api/rules/<rule_id>/execute', methods=['POST'])
def api_execute_rule(rule_id):
    """Execute a rule manually"""
    try:
        rule = storage.get_rule(rule_id)
        if not rule:
            return jsonify({"error": "Rule not found"}), 404
        
        # Get VMs and enrich if needed
        vms = get_all_vms()
        
        # Check if rule needs enrichment and collect required fields
        required_fields = set()
        for condition in rule.conditions.conditions:
            if condition.field.startswith(('config.', 'ha.', 'replication.', 'snapshots.', 'backup.')):
                # Extract prefix (e.g., 'ha.' from 'ha.enabled')
                prefix = condition.field.split('.')[0] + '.'
                required_fields.add(prefix)
        
        if required_fields:
            enriched_vms = [enrich_vm_data_selective(vm, required_fields) for vm in vms]
        else:
            enriched_vms = vms
        
        # Execute rule
        result = engine.evaluate_rule(rule, enriched_vms, dry_run=False)
        
        # Update statistics and history
        storage.update_rule_stats(rule_id, result)
        history.add_execution(result)
        
        return jsonify(result.to_dict())
    except Exception as e:
        logger.error(f"Error executing rule: {e}")
        return jsonify({"error": str(e)}), 500

@conditional_tags_bp.route('/api/rules/<rule_id>/dry-run', methods=['POST'])
def api_dry_run_rule(rule_id):
    """Test a rule without applying changes"""
    try:
        rule = storage.get_rule(rule_id)
        if not rule:
            return jsonify({"error": "Rule not found"}), 404
        
        # Get VMs and enrich if needed
        vms = get_all_vms()
        
        # Check if rule needs enrichment and collect required fields
        required_fields = set()
        for condition in rule.conditions.conditions:
            if condition.field.startswith(('config.', 'ha.', 'replication.', 'snapshots.', 'backup.')):
                # Extract prefix (e.g., 'ha.' from 'ha.enabled')
                prefix = condition.field.split('.')[0] + '.'
                required_fields.add(prefix)
        
        if required_fields:
            enriched_vms = [enrich_vm_data_selective(vm, required_fields) for vm in vms]
        else:
            enriched_vms = vms
        
        # Execute rule in dry-run mode
        result = engine.evaluate_rule(rule, enriched_vms, dry_run=True)
        
        return jsonify(result.to_dict())
    except Exception as e:
        logger.error(f"Error dry-running rule: {e}")
        return jsonify({"error": str(e)}), 500

@conditional_tags_bp.route('/api/vm-properties', methods=['GET'])
def api_get_vm_properties():
    """Get available VM properties for rule builder"""
    try:
        properties = get_available_vm_properties()
        logger.info(f"Returning {len(properties)} VM properties")
        return jsonify(properties)
    except Exception as e:
        logger.error(f"Error getting VM properties: {e}")
        return jsonify({"error": str(e)}), 500

@conditional_tags_bp.route('/api/rules/<rule_id>/history', methods=['GET'])
def api_get_rule_history(rule_id):
    """Get execution history for a rule"""
    try:
        limit = request.args.get('limit', 10, type=int)
        rule_history = history.get_rule_history(rule_id, limit)
        return jsonify(rule_history)
    except Exception as e:
        logger.error(f"Error getting rule history: {e}")
        return jsonify({"error": str(e)}), 500

@conditional_tags_bp.route('/api/history', methods=['GET'])
def api_get_recent_executions():
    """Get recent executions across all rules"""
    try:
        limit = request.args.get('limit', 10, type=int)
        rule_filter = request.args.get('rule')
        
        recent_executions = history.get_recent_executions(limit)
        
        # Filter by rule if specified
        if rule_filter:
            recent_executions = [
                execution for execution in recent_executions 
                if execution.get('rule_id') == rule_filter
            ]
        
        # Ensure all executions have rule names (for backward compatibility)
        rules = storage.get_all_rules()
        rule_names = {rule.id: rule.name for rule in rules}
        
        for execution in recent_executions:
            # Use stored rule_name if available, otherwise fall back to lookup
            if not execution.get('rule_name'):
                rule_id = execution.get('rule_id')
                execution['rule_name'] = rule_names.get(rule_id, f'Unknown Rule ({rule_id})')
        
        return jsonify(recent_executions)
    except Exception as e:
        logger.error(f"Error getting recent executions: {e}")
        return jsonify({"error": str(e)}), 500

@conditional_tags_bp.route('/export-rules')
def export_rules():
    """Export all conditional rules to a JSON file"""
    try:
        rules = storage.get_all_rules()
        
        # Convert rules to exportable format
        export_data = {
            "export_info": {
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0",
                "rule_count": len(rules)
            },
            "rules": [rule.to_dict() for rule in rules]
        }
        
        # Create JSON file in memory
        json_str = json.dumps(export_data, indent=2)
        buffer = io.BytesIO(json_str.encode('utf-8'))
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"conditional_rules_{timestamp}.json"
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/json'
        )
        
    except Exception as e:
        logger.error(f"Error exporting rules: {e}")
        return jsonify({"error": str(e)}), 500

@conditional_tags_bp.route('/api/import-rules', methods=['POST'])
def api_import_rules():
    """Import conditional rules from uploaded JSON file"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if not file.filename.lower().endswith('.json'):
            return jsonify({"error": "File must be a JSON file"}), 400
        
        # Parse the JSON file
        import_data = json.load(file)
        
        # Validate file structure
        if not isinstance(import_data, dict) or 'rules' not in import_data:
            return jsonify({"error": "Invalid file format. Expected conditional rules export file."}), 400
        
        rules_data = import_data['rules']
        if not isinstance(rules_data, list):
            return jsonify({"error": "Invalid rules data format"}), 400
        
        # Track import results
        results = {
            "success": True,
            "imported": 0,
            "failed": 0,
            "failures": [],
            "skipped": 0,
            "updated": 0
        }
        
        # Get existing rules once at the start
        existing_rules = storage.get_all_rules()
        existing_names = [r.name for r in existing_rules]
        
        # Process each rule
        for rule_data in rules_data:
            try:
                rule_name = rule_data.get('name')
                
                if rule_name in existing_names:
                    # Skip existing rules to avoid conflicts
                    results["skipped"] += 1
                    results["failures"].append(f"Rule '{rule_name}' already exists (skipped)")
                    continue
                
                # Create rule from imported data
                rule = ConditionalRule.from_dict(rule_data)
                
                # Validate the rule
                validation_errors = rule.validate()
                if validation_errors:
                    results["failed"] += 1
                    results["failures"].append(f"Rule '{rule.name}': {', '.join(validation_errors)}")
                    continue
                
                # Save the rule
                storage.save_rule(rule)
                
                # Schedule if enabled
                if rule.schedule.enabled:
                    scheduler = get_scheduler()
                    scheduler.add_or_update_schedule(rule)
                
                # Add to existing names to prevent duplicates within the import
                existing_names.append(rule_name)
                results["imported"] += 1
                
            except Exception as e:
                results["failed"] += 1
                rule_name = rule_data.get('name', 'Unknown')
                results["failures"].append(f"Rule '{rule_name}': {str(e)}")
        
        # Generate response message
        message_parts = []
        if results["imported"] > 0:
            message_parts.append(f"Successfully imported {results['imported']} rules")
        if results["skipped"] > 0:
            message_parts.append(f"{results['skipped']} rules skipped (already exist)")
        if results["failed"] > 0:
            message_parts.append(f"{results['failed']} rules failed to import")
        
        if not message_parts:
            message = "No rules were imported"
            success = False
        else:
            message = ". ".join(message_parts)
            success = results["imported"] > 0
        
        return jsonify({
            "success": success,
            "message": message,
            "details": results
        })
        
    except Exception as e:
        logger.error(f"Error importing rules: {e}")
        return jsonify({"error": f"Import failed: {str(e)}"}), 500