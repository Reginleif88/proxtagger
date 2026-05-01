"""
Unit tests for Flask routes in app.py

Tests all HTTP endpoints with mocked Proxmox API calls to verify
request handling, validation, error paths, and security controls.
"""

import pytest
import json
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock

import app as app_module


@pytest.fixture
def client():
    app_module.app.config['TESTING'] = True
    with app_module.app.test_client() as client:
        yield client


@pytest.fixture
def csrf_client():
    app_module.app.config['TESTING'] = True
    with app_module.app.test_client() as client:
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-csrf-token'
        yield client


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------
class TestGetIndex:

    @patch('app.get_all_vms')
    @patch('app.load_config')
    def test_renders_vm_list_on_success(self, mock_config, mock_vms, client, sample_vms):
        mock_config.return_value = {
            "PROXMOX_HOST": "test.local", "PROXMOX_PORT": "8006",
            "PROXMOX_USER": "test@pve", "PROXMOX_TOKEN_NAME": "t",
            "PROXMOX_TOKEN_VALUE": "v", "VERIFY_SSL": False,
        }
        mock_vms.return_value = sample_vms

        response = client.get('/')
        assert response.status_code == 200
        assert b'test-vm-1' in response.data

    @patch('app.get_all_vms')
    @patch('app.load_config')
    def test_shows_config_form_on_connection_error(self, mock_config, mock_vms, client):
        mock_config.return_value = {"PROXMOX_HOST": "", "PROXMOX_PORT": "8006",
                                    "PROXMOX_USER": "", "PROXMOX_TOKEN_NAME": "",
                                    "PROXMOX_TOKEN_VALUE": "", "VERIFY_SSL": False}
        mock_vms.side_effect = Exception("Connection refused")

        response = client.get('/')
        assert response.status_code == 200
        assert b'Connection refused' in response.data

    @patch('app.get_all_vms')
    @patch('app.load_config')
    def test_shows_permission_warning_when_no_vms(self, mock_config, mock_vms, client):
        mock_config.return_value = {"PROXMOX_HOST": "test.local", "PROXMOX_PORT": "8006",
                                    "PROXMOX_USER": "test@pve", "PROXMOX_TOKEN_NAME": "t",
                                    "PROXMOX_TOKEN_VALUE": "v", "VERIFY_SSL": False}
        mock_vms.return_value = []

        response = client.get('/')
        assert response.status_code == 200
        assert b'permissions' in response.data.lower() or b'VM.Audit' in response.data


# ---------------------------------------------------------------------------
# POST /  (config form submission)
# ---------------------------------------------------------------------------
class TestPostIndex:

    def test_csrf_rejects_missing_token(self, csrf_client):
        response = csrf_client.post('/', data={
            'host': 'test.local', 'port': '8006', 'user': 'root@pam',
            'token_name': 'tok', 'token_value': 'val',
        })
        assert response.status_code == 403

    def test_csrf_rejects_wrong_token(self, csrf_client):
        response = csrf_client.post('/', data={
            '_csrf_token': 'attacker-forged-token',
            'host': 'test.local', 'port': '8006', 'user': 'root@pam',
            'token_name': 'tok', 'token_value': 'val',
        })
        assert response.status_code == 403

    @patch('app.save_config')
    @patch('app.get_all_vms')
    def test_saves_config_with_valid_csrf(self, mock_vms, mock_save, csrf_client, sample_vms):
        mock_vms.return_value = sample_vms

        response = csrf_client.post('/', data={
            '_csrf_token': 'test-csrf-token',
            'host': 'test.local', 'port': '8006', 'user': 'root@pam',
            'token_name': 'tok', 'token_value': 'val',
        }, follow_redirects=False)

        assert response.status_code == 302
        mock_save.assert_called_once()
        saved = mock_save.call_args[0][0]
        assert saved['PROXMOX_HOST'] == 'test.local'

    @patch('app.save_config')
    @patch('app.get_all_vms')
    def test_strips_https_prefix_from_host(self, mock_vms, mock_save, csrf_client, sample_vms):
        mock_vms.return_value = sample_vms

        csrf_client.post('/', data={
            '_csrf_token': 'test-csrf-token',
            'host': 'https://my-proxmox.example.com', 'port': '8006',
            'user': 'root@pam', 'token_name': 'tok', 'token_value': 'val',
        })

        saved = mock_save.call_args[0][0]
        assert saved['PROXMOX_HOST'] == 'my-proxmox.example.com'

    @patch('app.save_config')
    def test_rejects_missing_required_fields(self, mock_save, csrf_client):
        response = csrf_client.post('/', data={
            '_csrf_token': 'test-csrf-token',
            'host': 'test.local',
        }, follow_redirects=True)

        assert response.status_code == 200
        mock_save.assert_not_called()

    @patch('app.save_config')
    @patch('app.get_all_vms')
    def test_handles_connection_failure_after_save(self, mock_vms, mock_save, csrf_client):
        mock_vms.side_effect = Exception("Timeout")

        response = csrf_client.post('/', data={
            '_csrf_token': 'test-csrf-token',
            'host': 'bad.host', 'port': '8006', 'user': 'root@pam',
            'token_name': 'tok', 'token_value': 'val',
        }, follow_redirects=False)

        assert response.status_code == 302
        mock_save.assert_called_once()

    @patch('app.save_config')
    @patch('app.get_all_vms')
    def test_verify_ssl_checkbox(self, mock_vms, mock_save, csrf_client, sample_vms):
        mock_vms.return_value = sample_vms

        csrf_client.post('/', data={
            '_csrf_token': 'test-csrf-token',
            'host': 'test.local', 'port': '8006', 'user': 'root@pam',
            'token_name': 'tok', 'token_value': 'val',
            'verify_ssl': 'on',
        })
        assert mock_save.call_args[0][0]['VERIFY_SSL'] is True

        csrf_client.post('/', data={
            '_csrf_token': 'test-csrf-token',
            'host': 'test.local', 'port': '8006', 'user': 'root@pam',
            'token_name': 'tok', 'token_value': 'val',
        })
        assert mock_save.call_args[0][0]['VERIFY_SSL'] is False


# ---------------------------------------------------------------------------
# GET /api/vms
# ---------------------------------------------------------------------------
class TestApiVms:

    @patch('app.get_all_vms')
    def test_returns_vm_list_as_json(self, mock_vms, client, sample_vms):
        mock_vms.return_value = sample_vms

        response = client.get('/api/vms')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert len(data) == 4
        assert data[0]['vmid'] == 100

    @patch('app.get_all_vms')
    def test_returns_500_on_api_error(self, mock_vms, client):
        mock_vms.side_effect = Exception("API unreachable")

        response = client.get('/api/vms')
        assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/tags
# ---------------------------------------------------------------------------
class TestApiTags:

    @patch('app.get_all_vms')
    def test_returns_extracted_tags(self, mock_vms, client, sample_vms):
        mock_vms.return_value = sample_vms

        response = client.get('/api/tags')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert isinstance(data, list)
        assert 'production' in data
        assert 'web' in data

    @patch('app.get_all_vms')
    def test_returns_500_on_error(self, mock_vms, client):
        mock_vms.side_effect = Exception("Failed")

        response = client.get('/api/tags')
        assert response.status_code == 500


# ---------------------------------------------------------------------------
# PUT /api/vm/<vmid>/tags
# ---------------------------------------------------------------------------
class TestApiUpdateTags:

    @patch('app.update_vm_tags')
    def test_updates_tags_successfully(self, mock_update, client):
        mock_update.return_value = {"data": None}

        response = client.put('/api/vm/100/tags',
                              data=json.dumps({"tags": "web;prod", "node": "node1", "type": "qemu"}),
                              content_type='application/json')

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body['success'] is True
        assert body['tags'] == 'web;prod'
        mock_update.assert_called_once_with("node1", 100, "web;prod", "qemu")

    @patch('app.update_vm_tags')
    def test_handles_empty_tags(self, mock_update, client):
        mock_update.return_value = {"data": None}

        response = client.put('/api/vm/100/tags',
                              data=json.dumps({"tags": "", "node": "node1", "type": "qemu"}),
                              content_type='application/json')

        assert response.status_code == 200
        mock_update.assert_called_once_with("node1", 100, "", "qemu")

    @patch('app.update_vm_tags')
    def test_rejects_invalid_vm_type(self, mock_update, client):
        response = client.put('/api/vm/100/tags',
                              data=json.dumps({"tags": "web", "node": "node1", "type": "vmware"}),
                              content_type='application/json')
        assert response.status_code == 400

    @patch('app.update_vm_tags')
    def test_rejects_missing_node(self, mock_update, client):
        response = client.put('/api/vm/100/tags',
                              data=json.dumps({"tags": "web", "type": "qemu"}),
                              content_type='application/json')
        assert response.status_code == 400

    @patch('app.update_vm_tags')
    def test_returns_500_on_update_error(self, mock_update, client):
        mock_update.side_effect = Exception("Proxmox error")

        response = client.put('/api/vm/100/tags',
                              data=json.dumps({"tags": "web", "node": "node1", "type": "qemu"}),
                              content_type='application/json')
        assert response.status_code == 500


# ---------------------------------------------------------------------------
# POST /api/bulk-tag-update
# ---------------------------------------------------------------------------
class TestApiBulkTagUpdate:

    @patch('app.update_vm_tags')
    def test_bulk_add_tags(self, mock_update, client):
        mock_update.return_value = {"data": None}

        response = client.post('/api/bulk-tag-update',
                               data=json.dumps({
                                   "operation": "add",
                                   "tags": ["monitoring"],
                                   "vms": [
                                       {"id": 100, "node": "node1", "type": "qemu", "tags": "web"},
                                       {"id": 101, "node": "node1", "type": "lxc", "tags": ""},
                                   ],
                               }),
                               content_type='application/json')

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body['success'] is True
        assert body['updated'] == 2

        calls = {c[0][1]: c[0][2] for c in mock_update.call_args_list}
        assert 'monitoring' in calls[100]
        assert 'web' in calls[100]
        assert calls[101] == 'monitoring'

    @patch('app.update_vm_tags')
    def test_bulk_remove_tags(self, mock_update, client):
        mock_update.return_value = {"data": None}

        response = client.post('/api/bulk-tag-update',
                               data=json.dumps({
                                   "operation": "remove",
                                   "tags": ["web"],
                                   "vms": [
                                       {"id": 100, "node": "node1", "type": "qemu", "tags": "web;production"},
                                   ],
                               }),
                               content_type='application/json')

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body['success'] is True
        mock_update.assert_called_once()
        call_args = mock_update.call_args[0]
        assert 'web' not in call_args[2]
        assert 'production' in call_args[2]

    def test_rejects_invalid_operation(self, client):
        response = client.post('/api/bulk-tag-update',
                               data=json.dumps({
                                   "operation": "delete",
                                   "tags": ["web"],
                                   "vms": [{"id": 100, "node": "n1", "type": "qemu"}],
                               }),
                               content_type='application/json')
        assert response.status_code == 400

    def test_rejects_empty_tags_list(self, client):
        response = client.post('/api/bulk-tag-update',
                               data=json.dumps({
                                   "operation": "add",
                                   "tags": [],
                                   "vms": [{"id": 100, "node": "n1", "type": "qemu"}],
                               }),
                               content_type='application/json')
        assert response.status_code == 400

    def test_rejects_empty_vms_list(self, client):
        response = client.post('/api/bulk-tag-update',
                               data=json.dumps({
                                   "operation": "add",
                                   "tags": ["web"],
                                   "vms": [],
                               }),
                               content_type='application/json')
        assert response.status_code == 400

    @patch('app.update_vm_tags')
    @patch('app.get_all_vms')
    def test_looks_up_missing_vm_info_from_api(self, mock_get_vms, mock_update, client, sample_vms):
        mock_get_vms.return_value = sample_vms
        mock_update.return_value = {"data": None}

        response = client.post('/api/bulk-tag-update',
                               data=json.dumps({
                                   "operation": "add",
                                   "tags": ["new-tag"],
                                   "vms": [{"id": 100}],
                               }),
                               content_type='application/json')

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body['updated'] == 1
        mock_get_vms.assert_called_once()

        call_args = mock_update.call_args[0]
        assert call_args[0] == 'node1'
        assert call_args[1] == 100
        assert call_args[3] == 'qemu'
        assert 'new-tag' in call_args[2]

    @patch('app.update_vm_tags')
    def test_partial_failure_reporting(self, mock_update, client):
        mock_update.side_effect = [None, Exception("Proxmox timeout")]

        response = client.post('/api/bulk-tag-update',
                               data=json.dumps({
                                   "operation": "add",
                                   "tags": ["test"],
                                   "vms": [
                                       {"id": 100, "node": "n1", "type": "qemu", "tags": ""},
                                       {"id": 101, "node": "n1", "type": "qemu", "tags": ""},
                                   ],
                               }),
                               content_type='application/json')

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body['success'] is False
        assert body['updated'] == 1
        assert body['failed'] == 1
        assert len(body['failures']) == 1
        assert body['failures'][0]['vmid'] == 101

    @patch('app.update_vm_tags')
    def test_add_avoids_duplicate_tags(self, mock_update, client):
        mock_update.return_value = {"data": None}

        response = client.post('/api/bulk-tag-update',
                               data=json.dumps({
                                   "operation": "add",
                                   "tags": ["web"],
                                   "vms": [
                                       {"id": 100, "node": "n1", "type": "qemu", "tags": "web;production"},
                                   ],
                               }),
                               content_type='application/json')

        assert response.status_code == 200
        call_tags = mock_update.call_args[0][2]
        assert call_tags.count('web') == 1


# ---------------------------------------------------------------------------
# GET /backup-tags
# ---------------------------------------------------------------------------
class TestBackupTags:

    @patch('app.get_all_vms')
    def test_downloads_json_backup(self, mock_vms, client, sample_vms):
        mock_vms.return_value = sample_vms

        response = client.get('/backup-tags')
        assert response.status_code == 200
        assert 'application/json' in response.content_type

        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 4
        assert data[0]['id'] == 100

    @patch('app.get_all_vms')
    def test_sets_attachment_header(self, mock_vms, client, sample_vms):
        mock_vms.return_value = sample_vms

        response = client.get('/backup-tags')
        assert 'attachment' in response.headers.get('Content-Disposition', '')
        assert 'proxmox_tags_backup_' in response.headers.get('Content-Disposition', '')

    @patch('app.get_all_vms')
    def test_redirects_on_api_error(self, mock_vms, client):
        mock_vms.side_effect = Exception("API down")

        response = client.get('/backup-tags')
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# POST /api/restore-tags
# ---------------------------------------------------------------------------
class TestRestoreTags:

    @patch('app.update_vm_tags')
    def test_restores_from_valid_backup(self, mock_update, client):
        mock_update.return_value = None

        backup = [
            {"id": 100, "name": "vm1", "node": "n1", "type": "qemu", "tags": ["web", "prod"]},
            {"id": 101, "name": "vm2", "node": "n1", "type": "lxc", "tags": ["dev"]},
        ]
        data = BytesIO(json.dumps(backup).encode())

        response = client.post('/api/restore-tags',
                               data={'backup_file': (data, 'backup.json')},
                               content_type='multipart/form-data')

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body['success'] is True
        assert mock_update.call_count == 2

        calls = {c[0][1]: c[0] for c in mock_update.call_args_list}
        assert calls[100] == ('n1', 100, 'web;prod', 'qemu')
        assert calls[101] == ('n1', 101, 'dev', 'lxc')

    def test_rejects_missing_file(self, client):
        response = client.post('/api/restore-tags',
                               data={},
                               content_type='multipart/form-data')
        assert response.status_code == 400
        body = json.loads(response.data)
        assert body['success'] is False

    def test_rejects_empty_filename(self, client):
        response = client.post('/api/restore-tags',
                               data={'backup_file': (BytesIO(b'[]'), '')},
                               content_type='multipart/form-data')
        assert response.status_code == 400

    def test_returns_500_on_invalid_json(self, client):
        data = BytesIO(b'not json at all')

        response = client.post('/api/restore-tags',
                               data={'backup_file': (data, 'bad.json')},
                               content_type='multipart/form-data')
        assert response.status_code == 500

    @patch('app.update_vm_tags')
    def test_reports_all_failures(self, mock_update, client):
        mock_update.side_effect = Exception("Node offline")

        backup = [
            {"id": 100, "name": "vm1", "node": "n1", "type": "qemu", "tags": ["web"]},
        ]
        data = BytesIO(json.dumps(backup).encode())

        response = client.post('/api/restore-tags',
                               data={'backup_file': (data, 'backup.json')},
                               content_type='multipart/form-data')

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body['success'] is False

    @patch('app.update_vm_tags')
    def test_partial_restore_counts_as_success(self, mock_update, client):
        mock_update.side_effect = [None, Exception("Gone")]

        backup = [
            {"id": 100, "name": "vm1", "node": "n1", "type": "qemu", "tags": ["web"]},
            {"id": 101, "name": "vm2", "node": "n1", "type": "qemu", "tags": ["db"]},
        ]
        data = BytesIO(json.dumps(backup).encode())

        response = client.post('/api/restore-tags',
                               data={'backup_file': (data, 'backup.json')},
                               content_type='multipart/form-data')

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body['success'] is True
        assert 'partial_failures' in body


# ---------------------------------------------------------------------------
# GET /download-and-redirect
# ---------------------------------------------------------------------------
class TestDownloadAndRedirect:

    @patch('app.get_all_vms')
    def test_returns_html_with_download_script(self, mock_vms, client, sample_vms):
        mock_vms.return_value = sample_vms

        response = client.get('/download-and-redirect')
        assert response.status_code == 200
        assert b'backup-tags' in response.data
        assert b'setTimeout' in response.data

    @patch('app.get_all_vms')
    def test_redirects_when_no_vms(self, mock_vms, client):
        mock_vms.return_value = []

        response = client.get('/download-and-redirect')
        assert response.status_code == 302

    @patch('app.get_all_vms')
    def test_redirects_on_error(self, mock_vms, client):
        mock_vms.side_effect = Exception("Timeout")

        response = client.get('/download-and-redirect')
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# Security configuration
# ---------------------------------------------------------------------------
class TestSecurityConfig:

    def test_max_upload_size_set(self):
        assert app_module.app.config['MAX_CONTENT_LENGTH'] == 16 * 1024 * 1024

    def test_session_cookie_samesite(self):
        assert app_module.app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'

    def test_session_cookie_httponly(self):
        assert app_module.app.config['SESSION_COOKIE_HTTPONLY'] is True

    def test_debug_mode_disabled(self):
        assert app_module.app.debug is False

    def test_csrf_token_generator_registered(self):
        assert 'csrf_token' in app_module.app.jinja_env.globals

    def test_csrf_token_generates_hex_string(self):
        with app_module.app.test_request_context():
            from flask import session
            token = app_module.generate_csrf_token()
            assert isinstance(token, str)
            assert len(token) == 64
            int(token, 16)

    def test_csrf_token_stable_within_session(self):
        with app_module.app.test_request_context():
            from flask import session
            token1 = app_module.generate_csrf_token()
            token2 = app_module.generate_csrf_token()
            assert token1 == token2
