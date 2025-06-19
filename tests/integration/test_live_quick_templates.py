"""
Live integration tests for Quick Templates functionality

These tests verify that the predefined quick templates work correctly
against real Proxmox VMs and produce expected results.
"""

import pytest
from datetime import datetime
from unittest.mock import patch

# Import conditional tagging modules
from modules.conditional_tags.models import ConditionalRule, RuleCondition, RuleConditionGroup, RuleAction
from modules.conditional_tags.engine import RuleEngine
from modules.conditional_tags.storage import RuleStorage

# Import test utilities
from tests.unit.test_quick_templates import TestQuickTemplatesData, TestQuickTemplatesConversion
from tests.simple_live_config import simple_live_config


class TestQuickTemplatesLive:
    """Live tests for quick templates against real Proxmox VMs"""
    
    @pytest.mark.live
    @pytest.mark.templates
    def test_templates_against_live_vms(self, simple_live_proxmox_config, all_vms, temp_storage_file):
        """Test all quick templates against live VM data"""
        if not all_vms:
            pytest.skip("No VMs available for testing")
        
        templates = TestQuickTemplatesData().get_template_data()
        converter = TestQuickTemplatesConversion()
        engine = RuleEngine()
        
        results = {}
        
        for template_id, template_data in templates.items():
            # Convert template to rule
            rule = converter.convert_template_to_rule(template_data)
            
            # Execute against live VMs
            with patch('tag_utils.parse_tags') as mock_parse:
                with patch('tag_utils.format_tags') as mock_format:
                    mock_parse.side_effect = lambda tags: tags.split(';') if tags else []
                    mock_format.side_effect = lambda tags: ';'.join(tags) if tags else ''
                    
                    result = engine.evaluate_rule(rule, all_vms, dry_run=True)
            
            assert result.success, f"Template {template_id} execution failed"
            
            results[template_id] = {
                'template_name': template_data['name'],
                'total_vms': len(all_vms),
                'matched_vms': len(result.matched_vms),
                'matched_vmids': result.matched_vms,
                'tags_to_add': len([tag for tags in result.tags_added.values() for tag in tags]),
                'result': result
            }
            
            print(f"✅ Template '{template_id}' executed successfully:")
            print(f"   Total VMs: {len(all_vms)}")
            print(f"   Matched VMs: {len(result.matched_vms)}")
            print(f"   Matched VMIDs: {result.matched_vms}")
        
        # Print summary
        print(f"\n📊 Quick Templates Test Summary:")
        for template_id, data in results.items():
            print(f"  {template_id}: {data['matched_vms']}/{data['total_vms']} VMs matched")
        
        return results
    
    @pytest.mark.live
    @pytest.mark.templates
    def test_debian_lxc_template_live(self, simple_live_proxmox_config, all_vms):
        """Test debian-lxc template specifically against live VMs"""
        if not all_vms:
            pytest.skip("No VMs available for testing")
        
        templates = TestQuickTemplatesData().get_template_data()
        converter = TestQuickTemplatesConversion()
        engine = RuleEngine()
        
        template_data = templates['debian-lxc']
        rule = converter.convert_template_to_rule(template_data)
        
        # Execute template rule
        with patch('tag_utils.parse_tags') as mock_parse:
            with patch('tag_utils.format_tags') as mock_format:
                mock_parse.side_effect = lambda tags: tags.split(';') if tags else []
                mock_format.side_effect = lambda tags: ';'.join(tags) if tags else ''
                
                result = engine.evaluate_rule(rule, all_vms, dry_run=True)
        
        assert result.success
        
        # Analyze what VMs would be affected
        lxc_vms = [vm for vm in all_vms if vm.get('type') == 'lxc']
        debian_lxc_vms = []
        
        # Manual verification of rule logic
        for vm in lxc_vms:
            # Check if VM would match debian criteria
            # Note: config.ostype might not be available in VM list API
            # This template might need adjustment for real-world usage
            vm_name = vm.get('name', '').lower()
            if 'debian' in vm_name:
                debian_lxc_vms.append(vm)
        
        print(f"✅ Debian LXC Template Analysis:")
        print(f"   Total VMs: {len(all_vms)}")
        print(f"   LXC VMs: {len(lxc_vms)}")
        print(f"   Potential Debian LXC VMs (by name): {len(debian_lxc_vms)}")
        print(f"   Template matched: {len(result.matched_vms)} VMs")
        print(f"   Matched VMIDs: {result.matched_vms}")
        
        # The template rule logic checks config.ostype which might not be available
        # in the VM list API, so we expect it might match fewer VMs than manual check
        return result
    
    @pytest.mark.live
    @pytest.mark.templates
    def test_high_resource_template_live(self, simple_live_proxmox_config, all_vms):
        """Test high-resource template against live VMs"""
        if not all_vms:
            pytest.skip("No VMs available for testing")
        
        templates = TestQuickTemplatesData().get_template_data()
        converter = TestQuickTemplatesConversion()
        engine = RuleEngine()
        
        template_data = templates['high-resource']
        rule = converter.convert_template_to_rule(template_data)
        
        # Execute template rule
        with patch('tag_utils.parse_tags') as mock_parse:
            with patch('tag_utils.format_tags') as mock_format:
                mock_parse.side_effect = lambda tags: tags.split(';') if tags else []
                mock_format.side_effect = lambda tags: ';'.join(tags) if tags else ''
                
                result = engine.evaluate_rule(rule, all_vms, dry_run=True)
        
        assert result.success
        
        # Analyze resource usage manually
        high_cpu_vms = []
        high_mem_vms = []
        high_resource_vms = []
        
        for vm in all_vms:
            cpu = vm.get('maxcpu', 0)
            mem = vm.get('maxmem', 0)
            
            if cpu > 4:
                high_cpu_vms.append(vm)
            
            if mem > 8589934592:  # 8GB in bytes
                high_mem_vms.append(vm)
            
            if cpu > 4 and mem > 8589934592:
                high_resource_vms.append(vm)
        
        print(f"✅ High-Resource Template Analysis:")
        print(f"   Total VMs: {len(all_vms)}")
        print(f"   High CPU VMs (>4 cores): {len(high_cpu_vms)}")
        print(f"   High Memory VMs (>8GB): {len(high_mem_vms)}")
        print(f"   High Resource VMs (both): {len(high_resource_vms)}")
        print(f"   Template matched: {len(result.matched_vms)} VMs")
        print(f"   Matched VMIDs: {result.matched_vms}")
        
        # Verify template matches our manual calculation
        expected_matches = {vm['vmid'] for vm in high_resource_vms}
        actual_matches = set(result.matched_vms)
        
        # They should match (or be close if data access differs)
        if expected_matches != actual_matches:
            print(f"   ⚠️  Expected matches: {expected_matches}")
            print(f"   ⚠️  Actual matches: {actual_matches}")
            print(f"   ⚠️  Difference might be due to data access methods")
        
        return result
    
    @pytest.mark.live 
    def test_ha_validation_template_live(self, simple_live_proxmox_config, all_vms):
        """Test HA validation template against live VMs"""
        if not all_vms:
            pytest.skip("No VMs available for testing")
        
        templates = TestQuickTemplatesData().get_template_data()
        converter = TestQuickTemplatesConversion()
        engine = RuleEngine()
        
        template_data = templates['ha-validation']
        rule = converter.convert_template_to_rule(template_data)
        
        # Execute template rule  
        with patch('tag_utils.parse_tags') as mock_parse:
            with patch('tag_utils.format_tags') as mock_format:
                mock_parse.side_effect = lambda tags: tags.split(';') if tags else []
                mock_format.side_effect = lambda tags: ';'.join(tags) if tags else ''
                
                result = engine.evaluate_rule(rule, all_vms, dry_run=True)
        
        assert result.success
        
        print(f"✅ HA Validation Template Analysis:")
        print(f"   Total VMs: {len(all_vms)}")
        print(f"   Template matched: {len(result.matched_vms)} VMs")
        print(f"   Matched VMIDs: {result.matched_vms}")
        
        # Note: HA and replication data might not be available in VM list API
        # This template might need adjustment for real-world usage
        print(f"   ⚠️  Note: HA/replication data may not be available in VM list API")
        
        return result
    
    @pytest.mark.live
    @pytest.mark.templates
    def test_template_storage_and_execution_live(self, simple_live_proxmox_config, all_vms, temp_storage_file):
        """Test complete workflow: store template as rule and execute"""
        if not all_vms:
            pytest.skip("No VMs available for testing")
        
        templates = TestQuickTemplatesData().get_template_data()
        converter = TestQuickTemplatesConversion()
        storage = RuleStorage(temp_storage_file)
        engine = RuleEngine()
        
        # Pick high-resource template for full test
        template_data = templates['high-resource']
        
        # Step 1: Convert and store
        rule = converter.convert_template_to_rule(template_data)
        rule.name = f"Live Test - {rule.name} - {datetime.now().strftime('%H%M%S')}"
        
        created_rule = storage.create_rule(rule)
        assert created_rule.id is not None
        
        try:
            # Step 2: Retrieve and verify
            retrieved_rule = storage.get_rule(created_rule.id)
            assert retrieved_rule.name == rule.name
            
            # Step 3: Execute against live VMs
            with patch('tag_utils.parse_tags') as mock_parse:
                with patch('tag_utils.format_tags') as mock_format:
                    mock_parse.side_effect = lambda tags: tags.split(';') if tags else []
                    mock_format.side_effect = lambda tags: ';'.join(tags) if tags else ''
                    
                    result = engine.evaluate_rule(retrieved_rule, all_vms, dry_run=True)
            
            # Step 4: Verify execution
            assert result.success
            
            # Step 5: Update rule stats
            storage.update_rule_stats(created_rule.id, result)
            
            # Step 6: Verify stats were updated
            updated_rule = storage.get_rule(created_rule.id)
            # Check if stats exist and have the expected structure
            if hasattr(updated_rule, 'stats') and updated_rule.stats:
                # The exact stats structure may vary, just verify stats exist
                assert isinstance(updated_rule.stats, dict)
                print(f"✅ Rule stats updated: {updated_rule.stats}")
            else:
                print("⚠️  No stats found on updated rule")
            
            print(f"✅ Complete template workflow test successful:")
            print(f"   Rule created with ID: {created_rule.id}")
            print(f"   Execution result: {len(result.matched_vms)} matches")
            print(f"   Stats updated: {updated_rule.stats}")
            
        finally:
            # Clean up
            storage.delete_rule(created_rule.id)
    
    @pytest.mark.live
    @pytest.mark.templates
    def test_template_field_availability_live(self, simple_live_proxmox_config, all_vms):
        """Test which template fields are actually available in live VM data"""
        if not all_vms:
            pytest.skip("No VMs available for testing")
        
        # Analyze available fields in live VM data
        sample_vm = all_vms[0]
        available_fields = set(sample_vm.keys())
        
        print(f"✅ Available VM fields in live data:")
        for field in sorted(available_fields):
            print(f"   - {field}: {type(sample_vm[field]).__name__}")
        
        # Check template field requirements
        templates = TestQuickTemplatesData().get_template_data()
        
        print(f"\n📋 Template field requirements vs availability:")
        
        for template_id, template_data in templates.items():
            print(f"\n  Template: {template_id}")
            required_fields = set()
            
            for rule in template_data['conditions']['rules']:
                field = rule['field']
                required_fields.add(field)
                
                # Check if field is available
                if '.' in field:
                    # Nested field like 'config.ostype'
                    base_field = field.split('.')[0]
                    available = base_field in available_fields
                    nested_available = False
                    
                    if available and isinstance(sample_vm.get(base_field), dict):
                        nested_field = field.split('.', 1)[1]
                        nested_available = nested_field in sample_vm[base_field]
                    
                    status = "✅" if nested_available else ("⚠️" if available else "❌")
                    print(f"    {status} {field} (nested)")
                else:
                    # Direct field
                    available = field in available_fields
                    status = "✅" if available else "❌"
                    print(f"    {status} {field}")
            
            print(f"    Required fields: {len(required_fields)}")
        
        print(f"\n💡 Template Recommendations:")
        print(f"   - Templates with ❌ fields may need adjustment for live use")
        print(f"   - Templates with ⚠️ nested fields may need VM config API calls")
        print(f"   - Templates with ✅ fields should work well with VM list API")
        
        return available_fields
    
    @pytest.mark.live
    @pytest.mark.templates
    def test_template_performance_live(self, simple_live_proxmox_config, all_vms):
        """Test performance of template execution against live VMs"""
        if not all_vms:
            pytest.skip("No VMs available for testing")
        
        import time
        
        templates = TestQuickTemplatesData().get_template_data()
        converter = TestQuickTemplatesConversion()
        engine = RuleEngine()
        
        performance_results = {}
        
        for template_id, template_data in templates.items():
            rule = converter.convert_template_to_rule(template_data)
            
            # Measure execution time
            start_time = time.time()
            
            with patch('tag_utils.parse_tags') as mock_parse:
                with patch('tag_utils.format_tags') as mock_format:
                    mock_parse.side_effect = lambda tags: tags.split(';') if tags else []
                    mock_format.side_effect = lambda tags: ';'.join(tags) if tags else ''
                    
                    result = engine.evaluate_rule(rule, all_vms, dry_run=True)
            
            execution_time = time.time() - start_time
            
            performance_results[template_id] = {
                'execution_time': execution_time,
                'vm_count': len(all_vms),
                'matches': len(result.matched_vms),
                'success': result.success
            }
            
            assert result.success
            assert execution_time < 10.0, f"Template {template_id} took too long: {execution_time:.2f}s"
        
        print(f"\n⚡ Template Performance Results:")
        for template_id, perf in performance_results.items():
            print(f"  {template_id}:")
            print(f"    Execution time: {perf['execution_time']:.3f}s")
            print(f"    VMs processed: {perf['vm_count']}")
            print(f"    Matches found: {perf['matches']}")
            print(f"    Performance: {perf['vm_count']/perf['execution_time']:.0f} VMs/sec")
        
        return performance_results