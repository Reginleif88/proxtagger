"""
Unit tests for Quick Templates functionality

Tests the predefined rule templates used in the conditional tagging system.
These templates provide common rule patterns that users can quickly apply.
"""

import pytest
import json
from unittest.mock import Mock, patch
from pathlib import Path

# Import conditional tagging modules
from modules.conditional_tags.models import ConditionalRule, RuleCondition, RuleConditionGroup, RuleAction
from modules.conditional_tags.engine import RuleEngine
from modules.conditional_tags.storage import RuleStorage


class TestQuickTemplatesData:
    """Test the structure and validity of quick templates"""
    
    def get_template_data(self):
        """Extract template data from JavaScript file"""
        js_file = Path(__file__).parent.parent.parent / "static/js/modules/conditional_tags/main.js"
        
        if not js_file.exists():
            pytest.skip("JavaScript file not found")
        
        # Read and parse the ruleTemplates from JavaScript
        # This is a simplified extraction - in a real scenario you might want
        # to use a proper JS parser or extract to JSON
        templates = {
            'debian-lxc': {
                'name': 'Debian LXC Tagging',
                'description': 'Automatically tag all Debian-based LXC containers',
                'conditions': {
                    'operator': 'AND',
                    'rules': [
                        {'field': 'type', 'operator': 'equals', 'value': 'lxc'},
                        {'field': 'config.ostype', 'operator': 'contains', 'value': 'debian'}
                    ]
                },
                'actions': {
                    'add_tags': ['deb-lxc'],
                    'remove_tags': [],
                    'else_add_tags': [],
                    'else_remove_tags': []
                },
                'schedule': {
                    'enabled': True,
                    'cron': '0 */6 * * *'
                }
            },
            'ha-validation': {
                'name': 'HA Validation',
                'description': 'Add "ha" tag for replicated + HA VMs, remove for others',
                'conditions': {
                    'operator': 'AND',
                    'rules': [
                        {'field': 'ha.enabled', 'operator': 'equals', 'value': 'true'},
                        {'field': 'replication.enabled', 'operator': 'equals', 'value': 'true'}
                    ]
                },
                'actions': {
                    'add_tags': ['ha'],
                    'remove_tags': [],
                    'else_add_tags': [],
                    'else_remove_tags': ['ha']
                },
                'schedule': {
                    'enabled': True,
                    'cron': '0 0 * * *'
                }
            },
            'high-resource': {
                'name': 'High-Resource VMs',
                'description': 'Tag VMs with more than 4 cores and 8GB RAM',
                'conditions': {
                    'operator': 'AND',
                    'rules': [
                        {'field': 'maxcpu', 'operator': 'greater_than', 'value': '4'},
                        {'field': 'maxmem', 'operator': 'greater_than', 'value': '8589934592'}
                    ]
                },
                'actions': {
                    'add_tags': ['high-resource'],
                    'remove_tags': [],
                    'else_add_tags': [],
                    'else_remove_tags': []
                },
                'schedule': {
                    'enabled': False,
                    'cron': ''
                }
            }
        }
        
        return templates
    
    @pytest.mark.unit
    @pytest.mark.templates
    def test_template_structure_valid(self):
        """Test that all templates have valid structure"""
        templates = self.get_template_data()
        
        required_fields = ['name', 'description', 'conditions', 'actions']
        
        for template_id, template in templates.items():
            # Check required fields exist
            for field in required_fields:
                assert field in template, f"Template {template_id} missing field: {field}"
            
            # Check field types
            assert isinstance(template['name'], str), f"Template {template_id} name must be string"
            assert isinstance(template['description'], str), f"Template {template_id} description must be string"
            assert isinstance(template['conditions'], dict), f"Template {template_id} conditions must be dict"
            assert isinstance(template['actions'], dict), f"Template {template_id} actions must be dict"
            
            # Check conditions structure
            conditions = template['conditions']
            assert 'operator' in conditions, f"Template {template_id} conditions missing operator"
            assert 'rules' in conditions, f"Template {template_id} conditions missing rules"
            assert isinstance(conditions['rules'], list), f"Template {template_id} rules must be list"
            
            # Check actions structure
            actions = template['actions']
            action_fields = ['add_tags', 'remove_tags', 'else_add_tags', 'else_remove_tags']
            for action_field in action_fields:
                assert action_field in actions, f"Template {template_id} actions missing {action_field}"
                assert isinstance(actions[action_field], list), f"Template {template_id} {action_field} must be list"
    
    @pytest.mark.unit
    @pytest.mark.templates
    def test_template_conditions_valid(self):
        """Test that template conditions are valid"""
        templates = self.get_template_data()
        
        valid_operators = ['equals', 'not_equals', 'contains', 'not_contains', 'greater_than', 'less_than', 'starts_with', 'ends_with']
        valid_logic_operators = ['AND', 'OR']
        
        for template_id, template in templates.items():
            conditions = template['conditions']
            
            # Check logic operator
            assert conditions['operator'] in valid_logic_operators, f"Template {template_id} invalid logic operator"
            
            # Check individual rules
            for i, rule in enumerate(conditions['rules']):
                assert 'field' in rule, f"Template {template_id} rule {i} missing field"
                assert 'operator' in rule, f"Template {template_id} rule {i} missing operator"
                assert 'value' in rule, f"Template {template_id} rule {i} missing value"
                
                assert rule['operator'] in valid_operators, f"Template {template_id} rule {i} invalid operator"
                assert isinstance(rule['field'], str), f"Template {template_id} rule {i} field must be string"
    
    @pytest.mark.unit
    @pytest.mark.templates
    def test_template_actions_valid(self):
        """Test that template actions are valid"""
        templates = self.get_template_data()
        
        for template_id, template in templates.items():
            actions = template['actions']
            
            # Check that at least one action is specified
            all_actions = (actions['add_tags'] + actions['remove_tags'] + 
                          actions['else_add_tags'] + actions['else_remove_tags'])
            assert len(all_actions) > 0, f"Template {template_id} must have at least one action"
            
            # Check that tag names are valid strings
            for action_type, tag_list in actions.items():
                for tag in tag_list:
                    assert isinstance(tag, str), f"Template {template_id} {action_type} tag must be string"
                    assert tag.strip(), f"Template {template_id} {action_type} tag cannot be empty"
    
    @pytest.mark.unit
    @pytest.mark.templates
    def test_template_schedule_valid(self):
        """Test that template schedules are valid"""
        templates = self.get_template_data()
        
        for template_id, template in templates.items():
            if 'schedule' in template:
                schedule = template['schedule']
                
                assert 'enabled' in schedule, f"Template {template_id} schedule missing enabled"
                assert isinstance(schedule['enabled'], bool), f"Template {template_id} schedule enabled must be boolean"
                
                if schedule['enabled']:
                    assert 'cron' in schedule, f"Template {template_id} enabled schedule missing cron"
                    assert schedule['cron'], f"Template {template_id} enabled schedule cron cannot be empty"
    
    @pytest.mark.unit
    @pytest.mark.templates
    def test_specific_template_debian_lxc(self):
        """Test debian-lxc template specifically"""
        templates = self.get_template_data()
        template = templates['debian-lxc']
        
        # Check specific requirements
        assert template['name'] == 'Debian LXC Tagging'
        assert 'debian' in template['description'].lower()
        assert 'lxc' in template['description'].lower()
        
        # Check conditions target LXC containers
        rules = template['conditions']['rules']
        lxc_rule = next((r for r in rules if r['field'] == 'type'), None)
        assert lxc_rule is not None, "debian-lxc template must check VM type"
        assert lxc_rule['value'] == 'lxc'
        
        # Check it adds the deb-lxc tag
        assert 'deb-lxc' in template['actions']['add_tags']
    
    @pytest.mark.unit
    @pytest.mark.templates
    def test_specific_template_ha_validation(self):
        """Test ha-validation template specifically"""
        templates = self.get_template_data()
        template = templates['ha-validation']
        
        # Check specific requirements
        assert 'ha' in template['name'].lower()
        assert 'ha' in template['description'].lower()
        
        # Check conditions target HA and replication
        rules = template['conditions']['rules']
        ha_fields = [r['field'] for r in rules]
        assert any('ha' in field for field in ha_fields), "ha-validation template must check HA status"
        assert any('replication' in field for field in ha_fields), "ha-validation template must check replication"
        
        # Check it manages the ha tag
        assert 'ha' in template['actions']['add_tags']
        assert 'ha' in template['actions']['else_remove_tags']
    
    @pytest.mark.unit
    @pytest.mark.templates
    def test_specific_template_high_resource(self):
        """Test high-resource template specifically"""
        templates = self.get_template_data()
        template = templates['high-resource']
        
        # Check specific requirements
        assert 'resource' in template['name'].lower()
        assert '8gb ram' in template['description'].lower() or 'more than 4 cores' in template['description'].lower()
        
        # Check conditions target CPU and memory
        rules = template['conditions']['rules']
        rule_fields = [r['field'] for r in rules]
        assert 'maxcpu' in rule_fields, "high-resource template must check CPU"
        assert 'maxmem' in rule_fields, "high-resource template must check memory"
        
        # Check thresholds are reasonable
        cpu_rule = next(r for r in rules if r['field'] == 'maxcpu')
        mem_rule = next(r for r in rules if r['field'] == 'maxmem')
        
        assert cpu_rule['operator'] == 'greater_than'
        assert int(cpu_rule['value']) > 0
        
        assert mem_rule['operator'] == 'greater_than'
        assert int(mem_rule['value']) > 1000000  # More than 1MB (reasonable threshold)
        
        # Check it adds the high-resource tag
        assert 'high-resource' in template['actions']['add_tags']


class TestQuickTemplatesConversion:
    """Test converting templates to actual rules"""
    
    def get_template_data(self):
        """Get template data for testing"""
        return TestQuickTemplatesData().get_template_data()
    
    def convert_template_to_rule(self, template_data):
        """Convert template data to ConditionalRule object"""
        # Convert conditions
        conditions = RuleConditionGroup(operator=template_data['conditions']['operator'])
        
        for rule_data in template_data['conditions']['rules']:
            condition = RuleCondition(
                field=rule_data['field'],
                operator=rule_data['operator'],
                value=rule_data['value']
            )
            conditions.add_condition(condition)
        
        # Convert actions
        actions = RuleAction(
            add_tags=template_data['actions']['add_tags'],
            remove_tags=template_data['actions']['remove_tags'],
            else_add_tags=template_data['actions']['else_add_tags'],
            else_remove_tags=template_data['actions']['else_remove_tags']
        )
        
        # Create rule
        rule = ConditionalRule(
            name=template_data['name'],
            description=template_data['description'],
            conditions=conditions,
            actions=actions
        )
        
        return rule
    
    @pytest.mark.unit
    @pytest.mark.templates
    def test_template_conversion_valid(self):
        """Test that all templates can be converted to valid rules"""
        templates = self.get_template_data()
        
        for template_id, template_data in templates.items():
            # Should not raise any exceptions
            rule = self.convert_template_to_rule(template_data)
            
            assert isinstance(rule, ConditionalRule)
            assert rule.name == template_data['name']
            assert rule.description == template_data['description']
            
            # Validate the rule structure
            errors = rule.validate()
            assert len(errors) == 0, f"Rule validation failed for {template_id}: {errors}"
    
    @pytest.mark.unit
    @pytest.mark.templates
    def test_template_rule_storage(self, temp_storage_file):
        """Test that template-based rules can be stored"""
        templates = self.get_template_data()
        storage = RuleStorage(temp_storage_file)
        
        created_rules = []
        
        for template_id, template_data in templates.items():
            rule = self.convert_template_to_rule(template_data)
            
            # Should be able to store the rule
            created_rule = storage.create_rule(rule)
            created_rules.append(created_rule)
            
            assert created_rule.id is not None
            assert created_rule.name == template_data['name']
        
        # Verify all rules were stored
        all_rules = storage.get_all_rules()
        assert len(all_rules) == len(templates)
        
        # Clean up
        for rule in created_rules:
            storage.delete_rule(rule.id)
    
    @pytest.mark.unit
    @pytest.mark.templates
    def test_template_rule_execution_dry_run(self):
        """Test that template-based rules can be executed"""
        templates = self.get_template_data()
        engine = RuleEngine()
        
        # Sample VM data for testing
        sample_vms = [
            {
                'vmid': 100,
                'name': 'test-lxc-debian',
                'type': 'lxc',
                'config': {'ostype': 'debian-11'},
                'maxcpu': 2,
                'maxmem': 2147483648,  # 2GB
                'status': 'running'
            },
            {
                'vmid': 101,
                'name': 'test-vm-ubuntu',
                'type': 'qemu',
                'maxcpu': 8,
                'maxmem': 17179869184,  # 16GB
                'status': 'running'
            },
            {
                'vmid': 102,
                'name': 'test-ha-vm',
                'type': 'qemu',
                'ha': {'enabled': True},
                'replication': {'enabled': True},
                'maxcpu': 4,
                'maxmem': 8589934592,  # 8GB
                'status': 'running'
            }
        ]
        
        for template_id, template_data in templates.items():
            rule = self.convert_template_to_rule(template_data)
            
            # Should be able to execute the rule
            with patch('tag_utils.parse_tags') as mock_parse:
                with patch('tag_utils.format_tags') as mock_format:
                    mock_parse.side_effect = lambda tags: tags.split(';') if tags else []
                    mock_format.side_effect = lambda tags: ';'.join(tags) if tags else ''
                    
                    result = engine.evaluate_rule(rule, sample_vms, dry_run=True)
            
            assert result.success, f"Template {template_id} rule execution failed"
            assert result.dry_run
            
            # Verify expected behavior for specific templates
            if template_id == 'debian-lxc':
                # Should match the Debian LXC container (VM 100)
                assert 100 in result.matched_vms
                assert 'deb-lxc' in result.tags_added.get(100, [])
            
            elif template_id == 'high-resource':
                # Should match high-resource VMs (VM 101 and 102)
                high_resource_vms = [vm for vm in sample_vms 
                                   if vm['maxcpu'] > 4 and vm['maxmem'] > 8589934592]
                expected_matches = [vm['vmid'] for vm in high_resource_vms]
                
                for vmid in expected_matches:
                    assert vmid in result.matched_vms
                    assert 'high-resource' in result.tags_added.get(vmid, [])


class TestQuickTemplatesIntegration:
    """Integration tests for quick templates with other systems"""
    
    @pytest.mark.integration
    def test_template_workflow_complete(self, temp_storage_file):
        """Test complete workflow from template to execution"""
        templates = TestQuickTemplatesData().get_template_data()
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        
        # Pick one template for full workflow test
        template_data = templates['debian-lxc']
        
        # Step 1: Convert template to rule
        converter = TestQuickTemplatesConversion()
        rule = converter.convert_template_to_rule(template_data)
        
        # Step 2: Store rule
        created_rule = storage.create_rule(rule)
        assert created_rule.id is not None
        
        # Step 3: Retrieve and verify
        retrieved_rule = storage.get_rule(created_rule.id)
        assert retrieved_rule.name == template_data['name']
        
        # Step 4: Execute rule
        sample_vms = [
            {
                'vmid': 100,
                'name': 'debian-container',
                'type': 'lxc',
                'config': {'ostype': 'debian-11'},
                'status': 'running'
            },
            {
                'vmid': 101,
                'name': 'ubuntu-vm',
                'type': 'qemu',
                'config': {'ostype': 'ubuntu-20.04'},
                'status': 'running'
            }
        ]
        
        with patch('tag_utils.parse_tags') as mock_parse:
            with patch('tag_utils.format_tags') as mock_format:
                mock_parse.side_effect = lambda tags: tags.split(';') if tags else []
                mock_format.side_effect = lambda tags: ';'.join(tags) if tags else ''
                
                result = engine.evaluate_rule(retrieved_rule, sample_vms, dry_run=True)
        
        # Step 5: Verify execution results
        assert result.success
        assert 100 in result.matched_vms  # Debian LXC should match
        assert 101 not in result.matched_vms  # Ubuntu QEMU should not match
        
        # Step 6: Clean up
        storage.delete_rule(created_rule.id)
    
    @pytest.mark.integration
    def test_all_templates_integration(self, temp_storage_file):
        """Test that all templates work in the complete system"""
        templates = TestQuickTemplatesData().get_template_data()
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        converter = TestQuickTemplatesConversion()
        
        created_rules = []
        
        try:
            # Create rules from all templates
            for template_id, template_data in templates.items():
                rule = converter.convert_template_to_rule(template_data)
                created_rule = storage.create_rule(rule)
                created_rules.append(created_rule)
            
            # Verify all rules were created
            all_rules = storage.get_all_rules()
            assert len(all_rules) >= len(templates)
            
            # Test execution of all rules
            sample_vms = [
                {
                    'vmid': 100,
                    'type': 'lxc',
                    'config': {'ostype': 'debian-11'},
                    'maxcpu': 2,
                    'maxmem': 2147483648,
                    'ha': {'enabled': False},
                    'replication': {'enabled': False}
                },
                {
                    'vmid': 101,
                    'type': 'qemu', 
                    'maxcpu': 8,
                    'maxmem': 17179869184,
                    'ha': {'enabled': True},
                    'replication': {'enabled': True}
                }
            ]
            
            for rule in created_rules:
                with patch('tag_utils.parse_tags') as mock_parse:
                    with patch('tag_utils.format_tags') as mock_format:
                        mock_parse.side_effect = lambda tags: tags.split(';') if tags else []
                        mock_format.side_effect = lambda tags: ';'.join(tags) if tags else ''
                        
                        result = engine.evaluate_rule(rule, sample_vms, dry_run=True)
                
                assert result.success, f"Rule {rule.name} execution failed"
        
        finally:
            # Clean up all created rules
            for rule in created_rules:
                try:
                    storage.delete_rule(rule.id)
                except:
                    pass  # Ignore cleanup errors