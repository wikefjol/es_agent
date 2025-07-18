# tests/unit/tools/elasticsearch/test_client.py
"""Tests for Elasticsearch client configuration and management."""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from elasticsearch.exceptions import ConnectionError

from src.tools.elasticsearch.client import (
    ElasticsearchConfig,
    ElasticsearchClientManager,
    get_es_client,
    get_es_manager,
)


@pytest.mark.unit
class TestElasticsearchConfig:
    """Test Elasticsearch configuration."""

    def test_config_from_environment(self, monkeypatch):
        """Test configuration reads from environment variables."""
        # Set test environment variables
        monkeypatch.setenv("ES_HOST", "test-host.example.com")
        monkeypatch.setenv("ES_PORT", "9243")
        monkeypatch.setenv("ES_USER", "test_user")
        monkeypatch.setenv("ES_PASS", "test_password")
        monkeypatch.setenv("ES_USE_SSL", "true")
        monkeypatch.setenv("ES_VERIFY_CERTS", "false")
        monkeypatch.setenv("ES_TIMEOUT", "60")

        config = ElasticsearchConfig()

        assert config.host == "test-host.example.com"
        assert config.port == 9243
        assert config.user == "test_user"
        assert config.password == "test_password"
        assert config.use_ssl is True
        assert config.verify_certs is False
        assert config.timeout == 60

    def test_config_defaults(self, monkeypatch):
        """Test configuration uses defaults when env vars not set."""
        # Clear all ES environment variables
        for key in [
            "ES_HOST",
            "ES_PORT",
            "ES_USER",
            "ES_PASS",
            "ES_USE_SSL",
            "ES_VERIFY_CERTS",
            "ES_TIMEOUT",
        ]:
            monkeypatch.delenv(key, raising=False)

        config = ElasticsearchConfig()

        assert config.host == "localhost"
        assert config.port == 9200
        assert config.user == ""
        assert config.password == ""
        assert config.use_ssl is True
        assert config.verify_certs is True
        assert config.timeout == 30

    def test_connection_string_masks_password(self):
        """Test that connection string masks the password."""
        config = ElasticsearchConfig()
        config.user = "myuser"
        config.password = "secret123"
        config.host = "es.example.com"
        config.port = 9200
        config.use_ssl = True

        conn_string = config.connection_string

        assert "secret123" not in conn_string
        assert "***" in conn_string
        assert "https://myuser:***@es.example.com:9200" == conn_string


@pytest.mark.unit
class TestElasticsearchClientManager:
    """Test Elasticsearch client manager."""

    @pytest.fixture(autouse=True)
    def reset_manager(self):
        """Reset singleton before and after each test."""
        ElasticsearchClientManager.reset()
        yield
        ElasticsearchClientManager.reset()

    def test_singleton_pattern(self):
        """Test that manager follows singleton pattern."""
        manager1 = ElasticsearchClientManager()
        manager2 = ElasticsearchClientManager()

        assert manager1 is manager2

    @patch("src.tools.elasticsearch.client.Elasticsearch")
    def test_client_creation(self, mock_es_class, monkeypatch):
        """Test client is created with correct parameters."""
        # Set up environment
        monkeypatch.setenv("ES_HOST", "test.example.com")
        monkeypatch.setenv("ES_USER", "testuser")
        monkeypatch.setenv("ES_PASS", "testpass")
        monkeypatch.setenv("ES_PORT", "9200")

        # Mock the Elasticsearch instance
        mock_es_instance = Mock()
        mock_es_instance.info.return_value = {"version": {"number": "7.13.0"}}
        mock_es_class.return_value = mock_es_instance

        # Create manager and get client
        manager = ElasticsearchClientManager()
        client = manager.client

        # Verify Elasticsearch was instantiated with correct params
        mock_es_class.assert_called_once()
        call_kwargs = mock_es_class.call_args[1]

        # Check the hosts configuration
        assert len(call_kwargs["hosts"]) == 1
        host_config = call_kwargs["hosts"][0]
        assert host_config["host"] == "test.example.com"
        assert host_config["port"] == 9200
        assert call_kwargs["http_auth"] == ("testuser", "testpass")
        assert call_kwargs["timeout"] == 30
        assert call_kwargs["max_retries"] == 3
        assert call_kwargs["retry_on_timeout"] is True

    @patch("src.tools.elasticsearch.client.Elasticsearch")
    def test_client_lazy_initialization(self, mock_es_class):
        """Test client is only created when accessed."""
        manager = ElasticsearchClientManager()

        # Client should not be created yet
        assert manager._client is None
        mock_es_class.assert_not_called()

        # Mock the Elasticsearch instance
        mock_es_instance = Mock()
        mock_es_instance.info.return_value = {"version": {"number": "7.13.0"}}
        mock_es_class.return_value = mock_es_instance

        # Access client
        _ = manager.client

        # Now it should be created
        assert manager._client is not None
        mock_es_class.assert_called_once()

    @patch("src.tools.elasticsearch.client.Elasticsearch")
    def test_connection_test_on_creation(self, mock_es_class):
        """Test that connection is tested when client is created."""
        mock_es_instance = Mock()
        mock_es_instance.info.return_value = {
            "version": {"number": "7.13.0"},
            "cluster_name": "test-cluster",
        }
        mock_es_class.return_value = mock_es_instance

        manager = ElasticsearchClientManager()
        client = manager.client

        # Verify info was called to test connection
        mock_es_instance.info.assert_called_once()

    @patch("src.tools.elasticsearch.client.Elasticsearch")
    def test_connection_error_handling(self, mock_es_class):
        """Test handling of connection errors."""
        mock_es_instance = Mock()
        # Create a proper ES 7.x ConnectionError
        mock_es_instance.info.side_effect = ConnectionError(
            503,
            "Connection refused",
            {"error": {"type": "connection_error", "reason": "Connection refused"}},
        )
        mock_es_class.return_value = mock_es_instance

        manager = ElasticsearchClientManager()

        # Should raise the original ConnectionError
        with pytest.raises(ConnectionError) as exc_info:
            _ = manager.client

        # Verify it's an Elasticsearch ConnectionError
        assert isinstance(exc_info.value, ConnectionError)

    @patch("src.tools.elasticsearch.client.Elasticsearch")
    def test_health_check_success(self, mock_es_class):
        """Test successful health check."""
        mock_es_instance = Mock()
        mock_es_instance.info.return_value = {"version": {"number": "7.13.0"}}
        mock_es_instance.cluster.health.return_value = {
            "status": "green",
            "number_of_nodes": 3,
            "active_shards": 100,
        }
        mock_es_class.return_value = mock_es_instance

        manager = ElasticsearchClientManager()
        health = manager.health_check()

        assert health["status"] == "green"
        assert health["number_of_nodes"] == 3

    @patch("src.tools.elasticsearch.client.Elasticsearch")
    def test_health_check_error(self, mock_es_class):
        """Test health check error handling."""
        mock_es_instance = Mock()
        mock_es_instance.info.return_value = {"version": {"number": "7.13.0"}}
        mock_es_instance.cluster.health.side_effect = Exception("Health check failed")
        mock_es_class.return_value = mock_es_instance

        manager = ElasticsearchClientManager()
        health = manager.health_check()

        assert health["status"] == "red"
        assert "error" in health
        assert "Health check failed" in health["error"]

    @patch("src.tools.elasticsearch.client.Elasticsearch")
    def test_close_client(self, mock_es_class):
        """Test closing the client connection."""
        mock_es_instance = Mock()
        mock_es_instance.info.return_value = {"version": {"number": "7.13.0"}}
        mock_es_class.return_value = mock_es_instance

        manager = ElasticsearchClientManager()

        # Create client
        _ = manager.client
        assert manager._client is not None

        # Close it
        manager.close()

        # Verify close was called and client is None
        mock_es_instance.close.assert_called_once()
        assert manager._client is None

    def test_reset_clears_singleton(self):
        """Test that reset properly clears the singleton."""
        manager1 = ElasticsearchClientManager()
        ElasticsearchClientManager.reset()

        manager2 = ElasticsearchClientManager()

        # Should be different instances after reset
        assert manager1 is not manager2


@pytest.mark.unit
class TestHelperFunctions:
    """Test helper functions."""

    @pytest.fixture(autouse=True)
    def reset_manager(self):
        """Reset singleton before and after each test."""
        ElasticsearchClientManager.reset()
        yield
        ElasticsearchClientManager.reset()

    @patch("src.tools.elasticsearch.client.ElasticsearchClientManager")
    def test_get_es_client(self, mock_manager_class):
        """Test get_es_client returns client from manager."""
        mock_manager_instance = Mock()
        mock_client = Mock()
        type(mock_manager_instance).client = PropertyMock(return_value=mock_client)
        mock_manager_class.return_value = mock_manager_instance

        # Clear the lru_cache
        get_es_client.cache_clear()

        client = get_es_client()

        assert client is mock_client

    def test_get_es_manager(self):
        """Test get_es_manager returns manager instance."""
        manager = get_es_manager()

        assert isinstance(manager, ElasticsearchClientManager)
