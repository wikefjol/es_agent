# src/tools/elasticsearch/publications.py
"""Elasticsearch tool for searching publications."""

from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field, field_validator, ConfigDict
from langchain.tools import tool
from datetime import datetime
import logging

from .base import ElasticsearchBaseTool, ElasticsearchError
from .client import get_es_client
from src.tools.base import ToolResult

logger = logging.getLogger(__name__)


class PublicationSearchInput(BaseModel):
    """Input schema for publication search."""
    
    query: Optional[str] = Field(
        None, 
        description="Free text search in title and abstract fields"
    )
    author_name: Optional[str] = Field(
        None, 
        description="Author name to search for (searches in nested Persons)"
    )
    year_range: Optional[Tuple[int, int]] = Field(
        None, 
        description="Year range as tuple (start_year, end_year)"
    )
    publication_type: Optional[str] = Field(
        None, 
        description="Type of publication (e.g., 'Journal article', 'Conference paper')"
    )
    keywords: Optional[List[str]] = Field(
        None,
        description="Keywords to search for"
    )
    organization_id: Optional[str] = Field(
        None,
        description="Filter by organization UUID"
    )
    limit: int = Field(
        10, 
        description="Number of results to return",
        ge=1,
        le=100
    )
    
    @field_validator('year_range')
    def validate_year_range(cls, v):
        """Validate year range is reasonable."""
        if v:
            start, end = v
            current_year = datetime.now().year
            if start < 1900 or end > current_year + 1:
                raise ValueError(f"Year range must be between 1900 and {current_year + 1}")
            if start > end:
                raise ValueError("Start year must be less than or equal to end year")
        return v
    
    model_config = ConfigDict(
        schema_extra = {
            "example": {
                "query": "machine learning",
                "author_name": "John Smith",
                "year_range": (2020, 2024),
                "limit": 20
            }
        }
        )

class SearchPublicationsTool(ElasticsearchBaseTool):
    """Tool for searching publications in the research database."""
    
    name = "search_publications"
    description = """Search for academic publications in the research database.
    Can search by title/abstract text, author name, year range, publication type, and keywords.
    Returns publication details including title, authors, year, abstract, and identifiers."""
    
    def _build_query(self, params: PublicationSearchInput) -> Dict[str, Any]:
        """Build Elasticsearch query from input parameters."""
        must_clauses = []
        
        # Text search in title and abstract
        if params.query:
            must_clauses.append({
                "multi_match": {
                    "query": params.query,
                    "fields": ["Title^2", "Abstract"],  # Title has higher weight
                    "type": "best_fields",
                    "operator": "or"
                }
            })
        
        # Author search (simple match on list of objects)
        if params.author_name:
            must_clauses.append({
                "match": {
                    "Persons.PersonData.DisplayName": {
                        "query": params.author_name,
                        "operator": "and"
                    }
                }
            })
        
        # Year range filter
        if params.year_range:
            start_year, end_year = params.year_range
            must_clauses.append({
                "range": {
                    "Year": {
                        "gte": start_year,
                        "lte": end_year
                    }
                }
            })
        
        # Publication type filter
        if params.publication_type:
            must_clauses.append({
                "term": {
                    "PublicationType.NameEng": params.publication_type
                }
            })
        
        # Keywords filter
        if params.keywords:
            must_clauses.append({
                "terms": {
                    "Keywords.Value": params.keywords
                }
            })
        
        # Organization filter
        if params.organization_id:
            must_clauses.append({
                "term": {
                    "AffiliatedIdsChalmers": params.organization_id
                }
            })
        
        # Build the complete query
        if must_clauses:
            query = {"bool": {"must": must_clauses}}
        else:
            query = {"match_all": {}}
        
        return {
            "query": query,
            "sort": [
                {"Year": {"order": "desc"}},
                "_score"
            ],
            "_source": {
                "includes": [
                    "Id", "Title", "Year", "Abstract", "Language",
                    "PublicationType", "Source", "Keywords",
                    "IdentifierDoi", "IdentifierScopusId",
                    "Persons.PersonData.DisplayName",
                    "Persons.PersonData.FirstName",
                    "Persons.PersonData.LastName",
                    "Persons.Role",
                    "CreatedDate", "UpdatedDate"
                ]
            }
        }
    
    def _format_publication(self, hit: Dict[str, Any]) -> Dict[str, Any]:
        """Format a publication hit into a structured response."""
        source = hit.get('_source', {})
        
        # Extract authors from nested structure
        authors = []
        persons = source.get('Persons', [])
        for person in persons:
            person_data = person.get('PersonData', {})
            if person_data:
                authors.append({
                    'name': person_data.get('DisplayName', ''),
                    'first_name': person_data.get('FirstName', ''),
                    'last_name': person_data.get('LastName', ''),
                    'role': person.get('Role', {}).get('NameEng', 'Author')
                })
        
        # Extract keywords
        keywords = [kw.get('Value', '') for kw in source.get('Keywords', [])]
        
        return {
            'id': source.get('Id'),
            'title': source.get('Title'),
            'year': source.get('Year'),
            'abstract': source.get('Abstract'),
            'publication_type': source.get('PublicationType', {}).get('NameEng'),
            'authors': authors,
            'keywords': keywords,
            'doi': source.get('IdentifierDoi', [None])[0] if source.get('IdentifierDoi') else None,
            'scopus_id': source.get('IdentifierScopusId', [None])[0] if source.get('IdentifierScopusId') else None,
            'source': source.get('Source', {}),
            'score': hit.get('_score')
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the publication search."""
        try:
            # Validate input
            params = PublicationSearchInput(**kwargs)
            
            # Build query
            query_body = self._build_query(params)
            
            # Execute search
            response = await self._execute_search(
                index="research-publications-static",
                body=query_body,
                size=params.limit
            )
            
            # Format results
            publications = []
            for hit in response.get('hits', {}).get('hits', []):
                publications.append(self._format_publication(hit))
            
            # Prepare metadata
            total_hits = response.get('hits', {}).get('total', 0)
            # Handle both ES 6.x and 7.x response formats
            if isinstance(total_hits, dict):
                total_hits = total_hits.get('value', 0)
            
            metadata = {
                'tool_name': 'search_publications',
                'total_results': total_hits,
                'returned_results': len(publications),
                'query_time_ms': response.get('took', 0),
                'max_score': response.get('hits', {}).get('max_score')
            }
            
            return ToolResult(
                success=True,
                data={
                    'publications': publications,
                    'total_results': total_hits
                },
                metadata=metadata
            )
            
        except ValueError as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Invalid input: {str(e)}"
            )
        except ElasticsearchError as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Elasticsearch error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error in search_publications: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Unexpected error: {str(e)}"
            )


# Create the tool instance for LangChain
@tool("search_publications", args_schema=PublicationSearchInput)
async def search_publications_tool(
    query: Optional[str] = None,
    author_name: Optional[str] = None,
    year_range: Optional[Tuple[int, int]] = None,
    publication_type: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    organization_id: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Search for academic publications in the research database.
    
    Args:
        query: Free text search in title and abstract
        author_name: Author name to search for
        year_range: Tuple of (start_year, end_year)
        publication_type: Type of publication
        keywords: List of keywords to search for
        organization_id: Organization UUID to filter by
        limit: Number of results (1-100)
    
    Returns:
        Dictionary with publications list and metadata
    """
    tool = SearchPublicationsTool(get_es_client())
    result = await tool.execute(
        query=query,
        author_name=author_name,
        year_range=year_range,
        publication_type=publication_type,
        keywords=keywords,
        organization_id=organization_id,
        limit=limit
    )
    
    if result.success:
        return result.data
    else:
        raise Exception(result.error)
    
async def search_publications_impl(
    query: Optional[str] = None,
    author_name: Optional[str] = None,
    year_range: Optional[Tuple[int, int]] = None,
    publication_type: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    organization_id: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """Implementation function for search_publications tool."""
    tool = SearchPublicationsTool(get_es_client())
    result = await tool.execute(
        query=query,
        author_name=author_name,
        year_range=year_range,
        publication_type=publication_type,
        keywords=keywords,
        organization_id=organization_id,
        limit=limit
    )
    
    if result.success:
        return result.data
    else:
        raise Exception(result.error)