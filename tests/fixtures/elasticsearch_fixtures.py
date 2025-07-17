# tests/fixtures/elasticsearch_fixtures.py
"""Elasticsearch-specific test fixtures."""

import pytest
from unittest.mock import Mock, AsyncMock
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import (
    ConnectionError,
    ConnectionTimeout,
    RequestError,
    NotFoundError
)

@pytest.fixture
def mock_elasticsearch_client():
    """Create a mock Elasticsearch client for testing."""
    client = Mock(spec=Elasticsearch)
    
    # Mock common methods
    client.info = Mock(return_value={
        'version': {'number': '7.13.0'},
        'cluster_name': 'test-cluster'
    })
    
    # Mock cluster object and its methods
    client.cluster = Mock()
    client.cluster.health = Mock(return_value={
        'status': 'green',
        'number_of_nodes': 3
    })
    
    client.search = Mock()
    client.count = Mock(return_value={'count': 1000})
    client.close = Mock()
    
    # Mock indices
    client.indices = Mock()
    client.indices.get_alias = Mock(return_value={
        'research-publications-static': {},
        'research-persons-static': {},
        'research-organizations-static': {},
        'research-projects-static': {},
        'research-serials-static': {}
    })
    
    return client


@pytest.fixture
def sample_es_publication_hit():
    """Sample Elasticsearch hit for a publication."""
    return {
        '_index': 'research-publications-static',
        '_type': '_doc',  # ES 7.x uses _doc
        '_id': 'test-uuid-123',
        '_score': 1.5,
        '_source': {
            'Id': 'test-uuid-123',
            'Title': 'Sample Research Paper on Machine Learning',
            'Year': 2023,
            'Abstract': 'This paper presents a novel approach to machine learning...',
            'PublicationType': {'NameEng': 'Journal article'},
            'Persons': [
                {
                    'PersonData': {
                        'Id': 'person-uuid-1',
                        'DisplayName': 'John Doe',
                        'FirstName': 'John',
                        'LastName': 'Doe'
                    },
                    'Role': {'NameEng': 'Author'},
                    'Order': 1
                }
            ],
            'Keywords': [
                {'Value': 'machine learning'},
                {'Value': 'artificial intelligence'}
            ],
            'IdentifierDoi': ['10.1234/sample.doi.2023'],
            'IdentifierScopusId': ['85123456789'],
            'Source': {
                'SourceSerial': {
                    'Title': 'Journal of Machine Learning Research'
                },
                'Volume': '24',
                'Issue': '3',
                'Pages': '123-145'
            },
            'CreatedDate': '2023-01-15T10:30:00Z',
            'UpdatedDate': '2023-01-15T10:30:00Z'
        }
    }


@pytest.fixture
def es_error_responses():
    """Common Elasticsearch error responses for testing."""
    return {
        'connection_error': ConnectionError(
            503,
            'Connection refused',
            {'error': {'type': 'connection_error', 'reason': 'Connection refused'}}
        ),
        'timeout_error': ConnectionTimeout(
            'Request timed out',
            ('127.0.0.1', 9200),
            'Request timed out'
        ),
        'query_error': RequestError(
            400, 
            "search_phase_execution_exception",
            {'error': {'type': 'query_shard_exception', 'reason': 'Failed to parse query'}}
        ),
        'not_found_error': NotFoundError(
            404,
            "index_not_found_exception",
            {'error': {'type': 'index_not_found_exception', 'reason': 'Index not found'}}
        )
    }


@pytest.fixture
def mock_es_aggregation_response():
    """Mock response for aggregation queries."""
    return {
        'took': 20,
        'hits': {
            'total': {'value': 100, 'relation': 'eq'},  # ES 7.x format
            'max_score': None,
            'hits': []
        },
        'aggregations': {
            'publication_types': {
                'buckets': [
                    {'key': 'Journal article', 'doc_count': 45},
                    {'key': 'Conference paper', 'doc_count': 30},
                    {'key': 'Book chapter', 'doc_count': 15},
                    {'key': 'Doctoral thesis', 'doc_count': 10}
                ]
            },
            'yearly_distribution': {
                'buckets': [
                    {'key_as_string': '2023', 'key': 1672531200000, 'doc_count': 25},
                    {'key_as_string': '2022', 'key': 1640995200000, 'doc_count': 35},
                    {'key_as_string': '2021', 'key': 1609459200000, 'doc_count': 40}
                ]
            }
        }
    }