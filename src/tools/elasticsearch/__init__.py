# src/tools/elasticsearch/__init__.py
"""Elasticsearch tools for research database queries."""

from .client import get_es_client, get_es_manager, ElasticsearchConfig
from .base import (
    ElasticsearchBaseTool,
    ElasticsearchError,
    ElasticsearchQueryError,
    ElasticsearchConnectionError
)
from .publications import (
    search_publications_tool, 
    SearchPublicationsTool,
    search_publications_impl,
    PublicationSearchInput
)

__all__ = [
    # Client utilities
    'get_es_client',
    'get_es_manager', 
    'ElasticsearchConfig',
    
    # Base classes and errors
    'ElasticsearchBaseTool',
    'ElasticsearchError',
    'ElasticsearchQueryError',
    'ElasticsearchConnectionError',
    
    # Tools
    'search_publications_tool',
    'SearchPublicationsTool',
    'search_publications_impl',
    'PublicationSearchInput',
]