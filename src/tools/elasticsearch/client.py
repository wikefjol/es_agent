# src/tools/elasticsearch/client.py
"""Elasticsearch client configuration and connection management."""

import os
from typing import Optional
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, ConnectionTimeout
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


class ElasticsearchConfig:
    """Configuration for Elasticsearch connection."""

    def __init__(self):
        self.host = os.getenv("ES_HOST", "localhost")
        self.port = int(os.getenv("ES_PORT", "9200"))
        self.user = os.getenv("ES_USER", "")
        self.password = os.getenv("ES_PASS", "")
        self.use_ssl = os.getenv("ES_USE_SSL", "true").lower() == "true"
        self.verify_certs = os.getenv("ES_VERIFY_CERTS", "true").lower() == "true"
        self.timeout = int(os.getenv("ES_TIMEOUT", "30"))

    @property
    def connection_string(self) -> str:
        """Build connection string for logging (without password)."""
        # If host is already a full URL, just mask the password
        if self.host.startswith(("http://", "https://")):
            if self.user and self.password:
                # Replace password in URL
                return self.host.replace(
                    f"{self.user}:{self.password}@", f"{self.user}:***@"
                )
            return self.host
        else:
            # Build connection string from components
            protocol = "https" if self.use_ssl else "http"
            if self.user:
                return f"{protocol}://{self.user}:***@{self.host}:{self.port}"
            return f"{protocol}://{self.host}:{self.port}"


class ElasticsearchClientManager:
    """Manages Elasticsearch client instances with connection pooling."""

    _instance: Optional["ElasticsearchClientManager"] = None
    _client: Optional[Elasticsearch] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self.config = ElasticsearchConfig()
            self._initialized = True

    @classmethod
    def reset(cls):
        """Reset the singleton instance. Useful for testing."""
        if cls._instance and cls._client:
            try:
                cls._client.close()
            except:
                pass
        cls._instance = None
        cls._client = None

    @property
    def client(self) -> Elasticsearch:
        """Get or create Elasticsearch client with lazy initialization."""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _create_client(self) -> Elasticsearch:
        """Create and configure Elasticsearch client."""
        # Re-read config to pick up any environment changes
        self.config = ElasticsearchConfig()

        logger.info(
            f"Creating Elasticsearch client for {self.config.connection_string}"
        )

        # Check if ES_HOST is a full URL or just a hostname
        if self.config.host.startswith(("http://", "https://")):
            # ES_HOST is a full URL
            # For ES 7.x with full URL, we need to pass auth separately
            es_params = {
                "hosts": [self.config.host],
                "timeout": self.config.timeout,
                "max_retries": 3,
                "retry_on_timeout": True,
                "verify_certs": self.config.verify_certs,
            }

            # Add authentication if provided
            if self.config.user and self.config.password:
                # Use http_auth for better compatibility
                es_params["http_auth"] = (self.config.user, self.config.password)
        else:
            # ES_HOST is just a hostname, build the connection parameters
            es_params = {
                "hosts": [
                    {
                        "host": self.config.host,
                        "port": self.config.port,
                        "use_ssl": self.config.use_ssl,
                        "verify_certs": self.config.verify_certs,
                    }
                ],
                "timeout": self.config.timeout,
                "max_retries": 3,
                "retry_on_timeout": True,
            }

            # Add authentication if provided
            if self.config.user and self.config.password:
                es_params["http_auth"] = (self.config.user, self.config.password)

        client = Elasticsearch(**es_params)

        # Test the connection
        try:
            info = client.info()
            logger.info(
                f"Successfully connected to Elasticsearch {info['version']['number']}"
            )
        except ConnectionError as e:
            logger.error(f"Failed to connect to Elasticsearch: {str(e)}")
            raise  # Re-raise the original exception instead of creating a new one
        except Exception as e:
            logger.error(f"Failed to connect to Elasticsearch: {str(e)}")
            # For other exceptions, wrap them in a ConnectionError
            raise ConnectionError(
                503,
                f"Cannot connect to Elasticsearch: {str(e)}",
                {"error": {"type": "connection_error", "reason": str(e)}},
            )

        return client

    def health_check(self) -> dict:
        """Check Elasticsearch cluster health."""
        try:
            return self.client.cluster.health()
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {"status": "red", "error": str(e)}

    def close(self):
        """Close the Elasticsearch client connection."""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Elasticsearch client closed")


@lru_cache(maxsize=1)
def get_es_client() -> Elasticsearch:
    """Get the singleton Elasticsearch client instance."""
    manager = ElasticsearchClientManager()
    return manager.client


def get_es_manager() -> ElasticsearchClientManager:
    """Get the Elasticsearch manager instance."""
    return ElasticsearchClientManager()
