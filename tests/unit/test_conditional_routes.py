"""
Unit tests for conditional tags Flask routes (modules/conditional_tags/routes.py)

Tests rule CRUD, execute/dry-run, import/export, history, and VM properties
endpoints with mocked storage, scheduler, and Proxmox API.
"""

import pytest
import json
from io import BytesIO
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from modules.conditional_tags.models import (
    ConditionalRule, RuleConditionGroup, RuleCondition,
    RuleAction, RuleSchedule, ExecutionResult,
)

import app as app_module


@pytest.fixture
def client():
    app_module.app.config['TESTING'] = True
    with app_module.app.test_client() as client:
        yield client


@pytest.fixture
def mock_rule():
    conditions = RuleConditionGroup()
    conditions.add_condition(RuleCondition("status", "equals", "running"))
    return ConditionalRule(
        name="Test Rule",
        description="A test rule",
        enabled=True,
        conditions=conditions,
        actions=RuleAction(add_tags=["monitored"]),
        schedule=RuleSchedule(enabled=False),
    )


@pytest.fixture
def mock_execution_result():
    result = ExecutionResult(rule_id="test-id", rule_name="Test Rule", success=True)
    result.matched_vms = [100, 101]
    result.tags_added = {"100": ["monitored"]}
    return result


# ---------------------------------------------------------------------------
# GET /conditional-tags/api/rules
# ---------------------------------------------------------------------------
class TestGetRules:

    @patch('modules.conditional_tags.routes.get_scheduler')
    @patch('modules.conditional_tags.routes.storage')
    def test_returns_all_rules(self, mock_storage, mock_scheduler, client, mock_rule):
        mock_storage.get_all_rules.return_value = [mock_rule]
        mock_sched = Mock()
        mock_sched.get_next_run_time.return_value = None
        mock_scheduler.return_value = mock_sched

        response = client.get('/conditional-tags/api/rules')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert len(data) == 1
        assert data[0]['name'] == 'Test Rule'

    @patch('modules.conditional_tags.routes.get_scheduler')
    @patch('modules.conditional_tags.routes.storage')
    def test_returns_empty_list(self, mock_storage, mock_scheduler, client):
        mock_storage.get_all_rules.return_value = []
        mock_scheduler.return_value = Mock()

        response = client.get('/conditional-tags/api/rules')
        assert response.status_code == 200
        assert json.loads(response.data) == []

    @patch('modules.conditional_tags.routes.storage')
    def test_returns_500_on_storage_error(self, mock_storage, client):
        mock_storage.get_all_rules.side_effect = Exception("Disk error")

        response = client.get('/conditional-tags/api/rules')
        assert response.status_code == 500


# ---------------------------------------------------------------------------
# POST /conditional-tags/api/rules
# ---------------------------------------------------------------------------
class TestCreateRule:

    @patch('modules.conditional_tags.routes.get_scheduler')
    @patch('modules.conditional_tags.routes.storage')
    def test_creates_valid_rule(self, mock_storage, mock_scheduler, client):
        mock_storage.create_rule.side_effect = lambda r: r
        mock_scheduler.return_value = Mock()

        response = client.post('/conditional-tags/api/rules',
                               data=json.dumps({
                                   'name': 'New Rule',
                                   'description': 'Test',
                                   'enabled': True,
                                   'conditions': {
                                       'operator': 'AND',
                                       'rules': [{'field': 'status', 'operator': 'equals', 'value': 'running'}],
                                   },
                                   'actions': {'add_tags': ['tagged']},
                               }),
                               content_type='application/json')

        assert response.status_code == 201
        body = json.loads(response.data)
        assert body['name'] == 'New Rule'
        mock_storage.create_rule.assert_called_once()

        created = mock_storage.create_rule.call_args[0][0]
        assert created.name == 'New Rule'
        assert created.enabled is True
        assert len(created.conditions.conditions) == 1
        assert created.conditions.conditions[0].field == 'status'
        assert created.actions.add_tags == ['tagged']

    @patch('modules.conditional_tags.routes.storage')
    def test_returns_400_on_missing_name(self, mock_storage, client):
        response = client.post('/conditional-tags/api/rules',
                               data=json.dumps({'description': 'no name'}),
                               content_type='application/json')
        assert response.status_code == 400

    @patch('modules.conditional_tags.routes.get_scheduler')
    @patch('modules.conditional_tags.routes.storage')
    def test_schedules_rule_after_creation(self, mock_storage, mock_scheduler, client):
        mock_storage.create_rule.side_effect = lambda r: r
        mock_sched = Mock()
        mock_scheduler.return_value = mock_sched

        client.post('/conditional-tags/api/rules',
                    data=json.dumps({
                        'name': 'Scheduled Rule',
                        'conditions': {
                            'operator': 'AND',
                            'rules': [{'field': 'status', 'operator': 'equals', 'value': 'running'}],
                        },
                        'actions': {'add_tags': ['test']},
                        'schedule': {'enabled': True, 'cron': '0 2 * * *'},
                    }),
                    content_type='application/json')

        mock_sched.add_schedule.assert_called_once()


# ---------------------------------------------------------------------------
# PUT /conditional-tags/api/rules/<rule_id>
# ---------------------------------------------------------------------------
class TestUpdateRule:

    @patch('modules.conditional_tags.routes.get_scheduler')
    @patch('modules.conditional_tags.routes.storage')
    def test_updates_existing_rule(self, mock_storage, mock_scheduler, client, mock_rule):
        mock_storage.update_rule.return_value = mock_rule
        mock_scheduler.return_value = Mock()

        response = client.put('/conditional-tags/api/rules/some-id',
                              data=json.dumps({'name': 'Updated'}),
                              content_type='application/json')

        assert response.status_code == 200
        mock_storage.update_rule.assert_called_once_with('some-id', {'name': 'Updated'})

    @patch('modules.conditional_tags.routes.storage')
    def test_returns_404_for_missing_rule(self, mock_storage, client):
        mock_storage.update_rule.return_value = None

        response = client.put('/conditional-tags/api/rules/nonexistent',
                              data=json.dumps({'name': 'X'}),
                              content_type='application/json')
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /conditional-tags/api/rules/<rule_id>
# ---------------------------------------------------------------------------
class TestDeleteRule:

    @patch('modules.conditional_tags.routes.get_scheduler')
    @patch('modules.conditional_tags.routes.storage')
    def test_deletes_existing_rule(self, mock_storage, mock_scheduler, client):
        mock_storage.delete_rule.return_value = True
        mock_scheduler.return_value = Mock()

        response = client.delete('/conditional-tags/api/rules/rule-123')
        assert response.status_code == 200
        body = json.loads(response.data)
        assert body['success'] is True

    @patch('modules.conditional_tags.routes.get_scheduler')
    @patch('modules.conditional_tags.routes.storage')
    def test_returns_404_for_missing_rule(self, mock_storage, mock_scheduler, client):
        mock_storage.delete_rule.return_value = False
        mock_scheduler.return_value = Mock()

        response = client.delete('/conditional-tags/api/rules/gone')
        assert response.status_code == 404

    @patch('modules.conditional_tags.routes.get_scheduler')
    @patch('modules.conditional_tags.routes.storage')
    def test_removes_schedule_before_deleting(self, mock_storage, mock_scheduler, client):
        mock_storage.delete_rule.return_value = True
        mock_sched = Mock()
        mock_scheduler.return_value = mock_sched

        client.delete('/conditional-tags/api/rules/rule-123')
        mock_sched.remove_schedule.assert_called_once_with('rule-123')


# ---------------------------------------------------------------------------
# POST /conditional-tags/api/rules/<rule_id>/execute
# ---------------------------------------------------------------------------
class TestExecuteRule:

    @patch('modules.conditional_tags.routes.history')
    @patch('modules.conditional_tags.routes.engine')
    @patch('modules.conditional_tags.routes.get_all_vms')
    @patch('modules.conditional_tags.routes.storage')
    def test_executes_rule_and_records_result(self, mock_storage, mock_vms,
                                              mock_engine, mock_history,
                                              client, mock_rule, mock_execution_result,
                                              sample_vms):
        mock_storage.get_rule.return_value = mock_rule
        mock_vms.return_value = sample_vms
        mock_engine.evaluate_rule.return_value = mock_execution_result

        response = client.post(f'/conditional-tags/api/rules/{mock_rule.id}/execute')
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body['rule_id'] == 'test-id'
        assert body['matched_vms'] == [100, 101]

        args, kwargs = mock_engine.evaluate_rule.call_args
        assert args[0] is mock_rule
        assert len(args[1]) == len(sample_vms)
        assert kwargs['dry_run'] is False

        mock_storage.update_rule_stats.assert_called_once_with(mock_rule.id, mock_execution_result)
        mock_history.add_execution.assert_called_once_with(mock_execution_result)

    @patch('modules.conditional_tags.routes.storage')
    def test_returns_404_for_missing_rule(self, mock_storage, client):
        mock_storage.get_rule.return_value = None

        response = client.post('/conditional-tags/api/rules/missing/execute')
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /conditional-tags/api/rules/<rule_id>/dry-run
# ---------------------------------------------------------------------------
class TestDryRunRule:

    @patch('modules.conditional_tags.routes.history')
    @patch('modules.conditional_tags.routes.engine')
    @patch('modules.conditional_tags.routes.get_all_vms')
    @patch('modules.conditional_tags.routes.storage')
    def test_dry_run_does_not_persist(self, mock_storage, mock_vms,
                                      mock_engine, mock_history, client,
                                      mock_rule, mock_execution_result,
                                      sample_vms):
        mock_storage.get_rule.return_value = mock_rule
        mock_vms.return_value = sample_vms
        mock_execution_result.dry_run = True
        mock_engine.evaluate_rule.return_value = mock_execution_result

        response = client.post(f'/conditional-tags/api/rules/{mock_rule.id}/dry-run')
        assert response.status_code == 200

        _, kwargs = mock_engine.evaluate_rule.call_args
        assert kwargs['dry_run'] is True

        mock_storage.update_rule_stats.assert_not_called()
        mock_history.add_execution.assert_not_called()

    @patch('modules.conditional_tags.routes.storage')
    def test_returns_404_for_missing_rule(self, mock_storage, client):
        mock_storage.get_rule.return_value = None

        response = client.post('/conditional-tags/api/rules/nope/dry-run')
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /conditional-tags/api/vm-properties
# ---------------------------------------------------------------------------
class TestVmProperties:

    def test_returns_property_definitions(self, client):
        response = client.get('/conditional-tags/api/vm-properties')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'vmid' in data
        assert 'status' in data
        assert 'config.cores' in data
        assert 'ha.enabled' in data


# ---------------------------------------------------------------------------
# GET /conditional-tags/api/rules/<rule_id>/history
# ---------------------------------------------------------------------------
class TestRuleHistory:

    @patch('modules.conditional_tags.routes.history')
    def test_returns_rule_history(self, mock_history, client):
        mock_history.get_rule_history.return_value = [
            {'rule_id': 'r1', 'success': True, 'timestamp': '2024-01-15T12:00:00'},
        ]

        response = client.get('/conditional-tags/api/rules/r1/history')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert len(data) == 1

    @patch('modules.conditional_tags.routes.history')
    def test_respects_limit_parameter(self, mock_history, client):
        mock_history.get_rule_history.return_value = []

        client.get('/conditional-tags/api/rules/r1/history?limit=5')
        mock_history.get_rule_history.assert_called_once_with('r1', 5)


# ---------------------------------------------------------------------------
# GET /conditional-tags/api/history
# ---------------------------------------------------------------------------
class TestRecentExecutions:

    @patch('modules.conditional_tags.routes.storage')
    @patch('modules.conditional_tags.routes.history')
    def test_returns_recent_executions(self, mock_history, mock_storage, client):
        mock_history.get_recent_executions.return_value = [
            {'rule_id': 'r1', 'rule_name': 'Rule 1', 'success': True},
        ]
        mock_storage.get_all_rules.return_value = []

        response = client.get('/conditional-tags/api/history')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert len(data) == 1

    @patch('modules.conditional_tags.routes.storage')
    @patch('modules.conditional_tags.routes.history')
    def test_filters_by_rule_id(self, mock_history, mock_storage, client):
        mock_history.get_recent_executions.return_value = [
            {'rule_id': 'r1', 'rule_name': 'Rule 1'},
            {'rule_id': 'r2', 'rule_name': 'Rule 2'},
        ]
        mock_storage.get_all_rules.return_value = []

        response = client.get('/conditional-tags/api/history?rule=r1')
        data = json.loads(response.data)
        assert len(data) == 1
        assert data[0]['rule_id'] == 'r1'

    @patch('modules.conditional_tags.routes.storage')
    @patch('modules.conditional_tags.routes.history')
    def test_fills_missing_rule_names(self, mock_history, mock_storage, client, mock_rule):
        mock_history.get_recent_executions.return_value = [
            {'rule_id': mock_rule.id, 'rule_name': None},
        ]
        mock_storage.get_all_rules.return_value = [mock_rule]

        response = client.get('/conditional-tags/api/history')
        data = json.loads(response.data)
        assert data[0]['rule_name'] == 'Test Rule'


# ---------------------------------------------------------------------------
# GET /conditional-tags/export-rules
# ---------------------------------------------------------------------------
class TestExportRules:

    @patch('modules.conditional_tags.routes.storage')
    def test_exports_rules_as_json_file(self, mock_storage, client, mock_rule):
        mock_storage.get_all_rules.return_value = [mock_rule]

        response = client.get('/conditional-tags/export-rules')
        assert response.status_code == 200
        assert 'application/json' in response.content_type
        assert 'attachment' in response.headers.get('Content-Disposition', '')

        data = json.loads(response.data)
        assert 'export_info' in data
        assert 'rules' in data
        assert data['export_info']['rule_count'] == 1

    @patch('modules.conditional_tags.routes.storage')
    def test_exports_empty_when_no_rules(self, mock_storage, client):
        mock_storage.get_all_rules.return_value = []

        response = client.get('/conditional-tags/export-rules')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['export_info']['rule_count'] == 0
        assert data['rules'] == []


# ---------------------------------------------------------------------------
# POST /conditional-tags/api/import-rules
# ---------------------------------------------------------------------------
class TestImportRules:

    @patch('modules.conditional_tags.routes.get_scheduler')
    @patch('modules.conditional_tags.routes.storage')
    def test_imports_valid_rules(self, mock_storage, mock_scheduler, client, mock_rule):
        mock_storage.get_all_rules.return_value = []
        mock_storage.create_rule.side_effect = lambda r: r
        mock_scheduler.return_value = Mock()

        export_data = {
            'export_info': {'version': '1.0', 'rule_count': 1},
            'rules': [mock_rule.to_dict()],
        }
        buf = BytesIO(json.dumps(export_data).encode())

        response = client.post('/conditional-tags/api/import-rules',
                               data={'file': (buf, 'rules.json')},
                               content_type='multipart/form-data')

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body['success'] is True
        assert body['details']['imported'] == 1

    @patch('modules.conditional_tags.routes.storage')
    def test_skips_duplicate_rule_names(self, mock_storage, client, mock_rule):
        mock_storage.get_all_rules.return_value = [mock_rule]

        export_data = {
            'export_info': {'version': '1.0'},
            'rules': [mock_rule.to_dict()],
        }
        buf = BytesIO(json.dumps(export_data).encode())

        response = client.post('/conditional-tags/api/import-rules',
                               data={'file': (buf, 'rules.json')},
                               content_type='multipart/form-data')

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body['details']['skipped'] == 1
        assert body['details']['imported'] == 0

    def test_rejects_missing_file(self, client):
        response = client.post('/conditional-tags/api/import-rules',
                               data={},
                               content_type='multipart/form-data')
        assert response.status_code == 400

    def test_rejects_non_json_file(self, client):
        buf = BytesIO(b'hello')

        response = client.post('/conditional-tags/api/import-rules',
                               data={'file': (buf, 'rules.csv')},
                               content_type='multipart/form-data')
        assert response.status_code == 400

    def test_rejects_invalid_structure(self, client):
        buf = BytesIO(json.dumps({"not": "rules"}).encode())

        response = client.post('/conditional-tags/api/import-rules',
                               data={'file': (buf, 'bad.json')},
                               content_type='multipart/form-data')
        assert response.status_code == 400
        body = json.loads(response.data)
        assert 'Invalid file format' in body['error']


# ---------------------------------------------------------------------------
# GET /conditional-tags/api/scheduler/verify
# ---------------------------------------------------------------------------
class TestSchedulerVerify:

    @patch('modules.conditional_tags.routes.get_scheduler')
    def test_returns_scheduler_status(self, mock_scheduler, client):
        mock_sched = Mock()
        mock_sched.verify_schedules.return_value = {
            'scheduler_running': True,
            'registered_jobs': 2,
            'active_jobs': 2,
            'mismatches': [],
            'job_details': [],
        }
        mock_sched.get_schedule_info.return_value = {}
        mock_scheduler.return_value = mock_sched

        response = client.get('/conditional-tags/api/scheduler/verify')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['scheduler_running'] is True
        assert data['registered_jobs'] == 2
