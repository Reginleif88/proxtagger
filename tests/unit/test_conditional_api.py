"""
Unit tests for the conditional tags API enrichment layer
(modules/conditional_tags/api.py)

Tests retry logic, error classification, VM enrichment functions,
and individual Proxmox API wrappers with mocked HTTP calls.
"""

import pytest
import requests
from unittest.mock import Mock, patch, MagicMock
from modules.conditional_tags.api import (
    ProxmoxAPIError,
    is_retryable_error,
    retry_on_failure,
    get_vm_config_extended,
    get_ha_status,
    get_replication_status,
    get_vm_snapshots,
    get_vm_backup_status,
    enrich_vm_data,
    enrich_vm_data_selective,
    get_available_vm_properties,
)


MOCK_CONFIG = {
    "PROXMOX_HOST": "test.local",
    "PROXMOX_PORT": "8006",
    "PROXMOX_USER": "root@pam",
    "PROXMOX_TOKEN_NAME": "tok",
    "PROXMOX_TOKEN_VALUE": "val",
    "VERIFY_SSL": False,
}


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------
class TestIsRetryableError:

    def test_proxmox_api_error_retryable(self):
        err = ProxmoxAPIError("timeout", status_code=503, retryable=True)
        assert is_retryable_error(err) is True

    def test_proxmox_api_error_not_retryable(self):
        err = ProxmoxAPIError("bad request", status_code=400, retryable=False)
        assert is_retryable_error(err) is False

    def test_connection_error_is_retryable(self):
        err = requests.exceptions.ConnectionError("refused")
        assert is_retryable_error(err) is True

    def test_timeout_is_retryable(self):
        err = requests.exceptions.Timeout("timed out")
        assert is_retryable_error(err) is True

    def test_read_timeout_is_retryable(self):
        err = requests.exceptions.ReadTimeout("read timed out")
        assert is_retryable_error(err) is True

    def test_5xx_http_error_is_retryable(self):
        resp = Mock()
        resp.status_code = 502
        err = requests.exceptions.HTTPError(response=resp)
        assert is_retryable_error(err) is True

    def test_4xx_http_error_is_not_retryable(self):
        resp = Mock()
        resp.status_code = 404
        err = requests.exceptions.HTTPError(response=resp)
        assert is_retryable_error(err) is False

    def test_generic_exception_is_not_retryable(self):
        assert is_retryable_error(ValueError("bad")) is False


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------
class TestRetryOnFailure:

    def test_succeeds_on_first_attempt(self):
        call_count = 0

        @retry_on_failure(max_attempts=3, delay=0.01)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        assert succeed() == "ok"
        assert call_count == 1

    def test_retries_on_retryable_error(self):
        call_count = 0

        @retry_on_failure(max_attempts=3, delay=0.01)
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise requests.exceptions.ConnectionError("transient")
            return "recovered"

        assert fail_then_succeed() == "recovered"
        assert call_count == 3

    def test_does_not_retry_non_retryable_error(self):
        call_count = 0

        @retry_on_failure(max_attempts=3, delay=0.01)
        def fail_hard():
            nonlocal call_count
            call_count += 1
            raise ValueError("permanent")

        with pytest.raises(ValueError, match="permanent"):
            fail_hard()
        assert call_count == 1

    def test_raises_after_max_attempts(self):
        @retry_on_failure(max_attempts=2, delay=0.01)
        def always_fail():
            raise requests.exceptions.ConnectionError("down")

        with pytest.raises(ProxmoxAPIError, match="failed after 2 attempts"):
            always_fail()


# ---------------------------------------------------------------------------
# Individual API functions
# ---------------------------------------------------------------------------
class TestGetVmConfigExtended:

    @patch('modules.conditional_tags.api.load_config', return_value=MOCK_CONFIG)
    @patch('modules.conditional_tags.api._get_headers', return_value={"Authorization": "test"})
    @patch('modules.conditional_tags.api._get_base_url', return_value="https://test:8006/api2/json")
    @patch('modules.conditional_tags.api.requests.get')
    def test_returns_config_data(self, mock_get, mock_url, mock_headers, mock_config):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = {"data": {"cores": 4, "memory": 8192}}
        mock_get.return_value = mock_resp

        result = get_vm_config_extended("node1", 100, "qemu")
        assert result == {"cores": 4, "memory": 8192}

    @patch('modules.conditional_tags.api.load_config', return_value=MOCK_CONFIG)
    @patch('modules.conditional_tags.api._get_headers', return_value={"Authorization": "test"})
    @patch('modules.conditional_tags.api._get_base_url', return_value="https://test:8006/api2/json")
    @patch('modules.conditional_tags.api.requests.get')
    def test_raises_on_http_error(self, mock_get, mock_url, mock_headers, mock_config):
        resp = Mock()
        resp.status_code = 500
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        mock_get.return_value = resp

        with pytest.raises(ProxmoxAPIError):
            get_vm_config_extended("node1", 100)


class TestGetHaStatus:

    @patch('modules.conditional_tags.api.load_config', return_value=MOCK_CONFIG)
    @patch('modules.conditional_tags.api._get_headers', return_value={"Authorization": "test"})
    @patch('modules.conditional_tags.api._get_base_url', return_value="https://test:8006/api2/json")
    @patch('modules.conditional_tags.api.requests.get')
    def test_finds_ha_resource(self, mock_get, mock_url, mock_headers, mock_config):
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = {"data": [
            {"sid": "vm:100", "state": "started", "group": "ha-group1"},
            {"sid": "vm:200", "state": "started"},
        ]}
        mock_get.return_value = mock_resp

        result = get_ha_status(100)
        assert result is not None
        assert result['state'] == 'started'
        assert result['group'] == 'ha-group1'

    @patch('modules.conditional_tags.api.load_config', return_value=MOCK_CONFIG)
    @patch('modules.conditional_tags.api._get_headers', return_value={"Authorization": "test"})
    @patch('modules.conditional_tags.api._get_base_url', return_value="https://test:8006/api2/json")
    @patch('modules.conditional_tags.api.requests.get')
    def test_returns_none_when_not_in_ha(self, mock_get, mock_url, mock_headers, mock_config):
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = {"data": []}
        mock_get.return_value = mock_resp

        assert get_ha_status(999) is None


# ---------------------------------------------------------------------------
# Enrichment functions
# ---------------------------------------------------------------------------
class TestEnrichVmData:

    @patch('modules.conditional_tags.api.get_vm_backup_status')
    @patch('modules.conditional_tags.api.get_vm_snapshots')
    @patch('modules.conditional_tags.api.get_replication_status')
    @patch('modules.conditional_tags.api.get_ha_status')
    @patch('modules.conditional_tags.api.get_vm_config_extended')
    def test_enriches_all_fields(self, mock_config, mock_ha, mock_repl,
                                  mock_snap, mock_backup):
        mock_config.return_value = {"cores": 4, "memory": 8192}
        mock_ha.return_value = {"state": "started", "group": "g1"}
        mock_repl.return_value = [{"guest": 100, "target": "node2"}]
        mock_snap.return_value = [{"name": "snap1"}, {"name": "current"}]
        mock_backup.return_value = {"starttime": "2024-01-15"}

        vm = {"vmid": 100, "name": "test", "node": "n1", "type": "qemu"}
        result = enrich_vm_data(vm)

        assert result['config'] == {"cores": 4, "memory": 8192}
        assert result['ha']['enabled'] is True
        assert result['ha']['group'] == "g1"
        assert result['replication']['enabled'] is True
        assert result['snapshots']['count'] == 2
        assert result['snapshots']['names'] == ['snap1']
        assert result['backup']['has_backup'] is True

    @patch('modules.conditional_tags.api.get_vm_backup_status')
    @patch('modules.conditional_tags.api.get_vm_snapshots')
    @patch('modules.conditional_tags.api.get_replication_status')
    @patch('modules.conditional_tags.api.get_ha_status')
    @patch('modules.conditional_tags.api.get_vm_config_extended')
    def test_gracefully_handles_api_failures(self, mock_config, mock_ha,
                                              mock_repl, mock_snap, mock_backup):
        mock_config.side_effect = ProxmoxAPIError("config fail")
        mock_ha.side_effect = ProxmoxAPIError("ha fail")
        mock_repl.side_effect = ProxmoxAPIError("repl fail")
        mock_snap.side_effect = ProxmoxAPIError("snap fail")
        mock_backup.side_effect = ProxmoxAPIError("backup fail")

        vm = {"vmid": 100, "name": "test", "node": "n1", "type": "qemu"}
        result = enrich_vm_data(vm)

        assert result['config'] == {}
        assert result['ha'] == {'enabled': False, 'state': None, 'group': None}
        assert result['replication'] == {'enabled': False, 'targets': []}
        assert result['snapshots'] == {'count': 0, 'names': []}
        assert result['backup'] == {'has_backup': False, 'last_backup': None}
        assert len(result['_api_errors']) == 5

    @patch('modules.conditional_tags.api.get_vm_backup_status')
    @patch('modules.conditional_tags.api.get_vm_snapshots')
    @patch('modules.conditional_tags.api.get_replication_status')
    @patch('modules.conditional_tags.api.get_ha_status')
    @patch('modules.conditional_tags.api.get_vm_config_extended')
    def test_preserves_original_vm_data(self, mock_config, mock_ha,
                                         mock_repl, mock_snap, mock_backup):
        mock_config.return_value = {}
        mock_ha.return_value = None
        mock_repl.return_value = []
        mock_snap.return_value = []
        mock_backup.return_value = None

        vm = {"vmid": 100, "name": "test", "node": "n1", "type": "qemu", "status": "running"}
        result = enrich_vm_data(vm)

        assert result['vmid'] == 100
        assert result['name'] == 'test'
        assert result['status'] == 'running'

    @patch('modules.conditional_tags.api.get_vm_backup_status')
    @patch('modules.conditional_tags.api.get_vm_snapshots')
    @patch('modules.conditional_tags.api.get_replication_status')
    @patch('modules.conditional_tags.api.get_ha_status')
    @patch('modules.conditional_tags.api.get_vm_config_extended')
    def test_does_not_mutate_original(self, mock_config, mock_ha,
                                       mock_repl, mock_snap, mock_backup):
        mock_config.return_value = {}
        mock_ha.return_value = None
        mock_repl.return_value = []
        mock_snap.return_value = []
        mock_backup.return_value = None

        vm = {"vmid": 100, "name": "test", "node": "n1", "type": "qemu"}
        enrich_vm_data(vm)

        assert 'config' not in vm
        assert 'ha' not in vm


class TestEnrichVmDataSelective:

    @patch('modules.conditional_tags.api.get_vm_config_extended')
    def test_only_fetches_requested_fields(self, mock_config):
        mock_config.return_value = {"cores": 2}

        vm = {"vmid": 100, "name": "test", "node": "n1", "type": "qemu"}
        result = enrich_vm_data_selective(vm, {"config."})

        assert result['config'] == {"cores": 2}
        assert 'ha' not in result
        assert 'replication' not in result
        assert 'snapshots' not in result
        assert 'backup' not in result
        mock_config.assert_called_once()

    @patch('modules.conditional_tags.api.get_ha_status')
    def test_fetches_ha_when_requested(self, mock_ha):
        mock_ha.return_value = {"state": "started", "group": "g1"}

        vm = {"vmid": 100, "name": "test", "node": "n1", "type": "qemu"}
        result = enrich_vm_data_selective(vm, {"ha."})

        assert result['ha']['enabled'] is True
        assert 'config' not in result

    @patch('modules.conditional_tags.api.get_vm_config_extended')
    @patch('modules.conditional_tags.api.get_ha_status')
    def test_fetches_multiple_field_groups(self, mock_ha, mock_config):
        mock_config.return_value = {"cores": 4}
        mock_ha.return_value = None

        vm = {"vmid": 100, "name": "test", "node": "n1", "type": "qemu"}
        result = enrich_vm_data_selective(vm, {"config.", "ha."})

        assert 'config' in result
        assert 'ha' in result
        assert result['ha']['enabled'] is False

    @patch('modules.conditional_tags.api.get_vm_config_extended')
    def test_handles_api_failure_gracefully(self, mock_config):
        mock_config.side_effect = ProxmoxAPIError("fail")

        vm = {"vmid": 100, "name": "test", "node": "n1", "type": "qemu"}
        result = enrich_vm_data_selective(vm, {"config."})

        assert result['config'] == {}
        assert len(result['_api_errors']) == 1

    def test_skips_all_when_no_fields_requested(self):
        vm = {"vmid": 100, "name": "test", "node": "n1", "type": "qemu"}
        result = enrich_vm_data_selective(vm, set())

        assert result == vm


# ---------------------------------------------------------------------------
# VM properties catalog
# ---------------------------------------------------------------------------
class TestGetAvailableVmProperties:

    def test_returns_all_property_categories(self):
        props = get_available_vm_properties()

        assert 'vmid' in props
        assert 'name' in props
        assert 'status' in props
        assert 'config.cores' in props
        assert 'ha.enabled' in props
        assert 'replication.enabled' in props
        assert 'snapshots.count' in props
        assert 'backup.has_backup' in props

    def test_properties_have_required_metadata(self):
        props = get_available_vm_properties()

        for name, meta in props.items():
            assert 'type' in meta, f"Property {name} missing 'type'"
            assert 'description' in meta, f"Property {name} missing 'description'"


# ---------------------------------------------------------------------------
# ProxmoxAPIError
# ---------------------------------------------------------------------------
class TestProxmoxAPIError:

    def test_stores_status_code(self):
        err = ProxmoxAPIError("not found", status_code=404, retryable=False)
        assert err.status_code == 404
        assert err.retryable is False

    def test_default_attributes(self):
        err = ProxmoxAPIError("generic error")
        assert err.status_code is None
        assert err.retryable is False
        assert str(err) == "generic error"
