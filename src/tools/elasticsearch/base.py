# src/tools/elasticsearch/base.py
"""Base classes for Elasticsearch tools."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from pydantic import BaseModel
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, RequestError, TransportError
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ElasticsearchError(Exception):
    """Base exception for Elasticsearch operations."""
    pass


class ElasticsearchQueryError(ElasticsearchError):
    """Raised when query construction or execution fails."""
    pass


class ElasticsearchConnectionError(ElasticsearchError):
    """Raised when connection to Elasticsearch fails."""
    pass


class ElasticsearchBaseTool(BaseTool):
    """Base class for all Elasticsearch tools."""
    
    def __init__(self, es_client: Elasticsearch):
        self.es_client = es_client
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TransportError)),
        reraise=True
    )
    async def _execute_search(
        self, 
        index: str, 
        body: Dict[str, Any],
        size: int = 10
    ) -> Dict[str, Any]:
        """Execute search with retry logic."""
        try:
            # Add size to body if not present
            if 'size' not in body:
                body['size'] = size
                
            response = self.es_client.search(
                index=index,
                body=body
            )
            return response
            
        except RequestError as e:
            logger.error(f"Query error: {e.info}")
            raise ElasticsearchQueryError(f"Invalid query: {e.info}")
        except ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise ElasticsearchConnectionError(f"Failed to connect to Elasticsearch: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise ElasticsearchError(f"Elasticsearch operation failed: {e}")
    
    def _extract_source_fields(
        self, 
        hit: Dict[str, Any], 
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Extract source fields from search hit."""
        source = hit.get('_source', {})
        
        if fields:
            return {field: source.get(field) for field in fields if field in source}
        return source