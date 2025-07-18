# tests/conftest.py
"""Pytest configuration and fixtures."""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import realistic test data fixtures
from tests.fixtures.realistic_data import *

# Import Elasticsearch fixtures
from tests.fixtures.elasticsearch_fixtures import *


# Add pytest markers for test categorization
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "performance: mark test as a performance test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line(
        "markers", "error_handling: mark test as error handling test"
    )
    config.addinivalue_line(
        "markers", "realistic_data: mark test as using realistic test data"
    )
    config.addinivalue_line(
        "markers", "elasticsearch: mark test as requiring Elasticsearch"
    )
    config.addinivalue_line(
        "markers", "real_tools: mark test as using real tool integration"
    )
    config.addinivalue_line(
        "markers", "real_integration: mark test as real integration test"
    )


# Additional test configuration for async tests
import pytest
import asyncio


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
