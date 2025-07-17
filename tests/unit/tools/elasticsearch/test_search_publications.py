# tests/unit/tools/elasticsearch/test_search_publications.py
"""Tests for the search_publications Elasticsearch tool."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, create_autospec
from datetime import datetime
from elasticsearch.exceptions import ConnectionError, RequestError

from src.tools.elasticsearch.publications import (
    SearchPublicationsTool, 
    PublicationSearchInput,
    search_publications_tool,
    search_publications_impl
)
from src.tools.elasticsearch.base import (
    ElasticsearchQueryError,
    ElasticsearchConnectionError
)
from src.tools.base import ToolResult


@pytest.mark.unit
class TestPublicationSearchInput:
    """Test the input validation for publication search."""
    
    def test_valid_input_all_fields(self):
        """Test creating input with all valid fields."""
        input_data = PublicationSearchInput(
            query="machine learning",
            author_name="John Smith",
            year_range=(2020, 2023),
            publication_type="Journal article",
            keywords=["AI", "ML"],
            organization_id="uuid-123",
            limit=20
        )
        
        assert input_data.query == "machine learning"
        assert input_data.author_name == "John Smith"
        assert input_data.year_range == (2020, 2023)
        assert input_data.limit == 20
    
    def test_valid_input_minimal(self):
        """Test creating input with minimal fields."""
        input_data = PublicationSearchInput(query="quantum computing")
        
        assert input_data.query == "quantum computing"
        assert input_data.author_name is None
        assert input_data.year_range is None
        assert input_data.limit == 10  # default
    
    @pytest.mark.error_handling
    def test_invalid_year_range_order(self):
        """Test that start year must be <= end year."""
        with pytest.raises(ValueError, match="Start year must be less than or equal to end year"):
            PublicationSearchInput(year_range=(2023, 2020))
    
    @pytest.mark.error_handling
    def test_invalid_year_range_future(self):
        """Test that years must be reasonable."""
        current_year = datetime.now().year
        with pytest.raises(ValueError, match=f"Year range must be between 1900 and {current_year + 1}"):
            PublicationSearchInput(year_range=(1800, 2020))
    
    @pytest.mark.error_handling
    def test_invalid_limit(self):
        """Test limit validation."""
        with pytest.raises(ValueError):
            PublicationSearchInput(limit=0)
        
        with pytest.raises(ValueError):
            PublicationSearchInput(limit=101)


@pytest.mark.unit
class TestSearchPublicationsTool:
    """Test the SearchPublicationsTool implementation."""
    
    @pytest.fixture
    def mock_es_client(self):
        """Create a mock Elasticsearch client."""
        client = Mock()
        client.search = Mock()
        return client
    
    @pytest.fixture
    def tool(self, mock_es_client):
        """Create a SearchPublicationsTool instance with mock client."""
        return SearchPublicationsTool(mock_es_client)
    
    @pytest.fixture
    def sample_es_response(self, realistic_publications):
        """Sample Elasticsearch response using realistic data fixture."""
        # Use the realistic_publications fixture from your existing fixtures
        # Get the first publication from the realistic data
        pub_data = list(realistic_publications.values())[0]
        
        # Convert to ES format
        es_formatted_pub = {
            'Id': 'uuid-pub-1',
            'Title': pub_data['title'],
            'Year': pub_data['year'],
            'Abstract': pub_data['abstract'],
            'PublicationType': {'NameEng': 'Journal article'},
            'Persons': [
                {
                    'PersonData': {
                        'DisplayName': author,
                        'FirstName': author.split()[0],
                        'LastName': author.split()[-1]
                    },
                    'Role': {'NameEng': 'Author'}
                }
                for author in pub_data['authors']
            ],
            'Keywords': [{'Value': kw} for kw in pub_data['keywords']],
            'IdentifierDoi': [pub_data['doi']]
        }
        
        return {
            'took': 15,
            'hits': {
                'total': {'value': 2, 'relation': 'eq'},  # ES 7.x format
                'max_score': 1.5,
                'hits': [
                    {
                        '_id': 'pub-1',
                        '_score': 1.5,
                        '_source': es_formatted_pub
                    },
                    {
                        '_id': 'pub-2',
                        '_score': 1.2,
                        '_source': {
                            'Id': 'uuid-pub-2',
                            'Title': 'Deep Learning Applications',
                            'Year': 2022,
                            'Abstract': 'A survey of deep learning...',
                            'PublicationType': {'NameEng': 'Conference paper'},
                            'Persons': [
                                {
                                    'PersonData': {
                                        'DisplayName': 'Jane Doe',
                                        'FirstName': 'Jane',
                                        'LastName': 'Doe'
                                    },
                                    'Role': {'NameEng': 'Author'}
                                }
                            ],
                            'Keywords': [{'Value': 'deep learning'}],
                            'IdentifierScopusId': ['85055428557']
                        }
                    }
                ]
            }
        }
    
    def test_build_query_text_search(self, tool):
        """Test query building with text search."""
        params = PublicationSearchInput(query="machine learning")
        query = tool._build_query(params)
        
        assert 'query' in query
        assert 'bool' in query['query']
        assert 'must' in query['query']['bool']
        
        # Check multi_match query
        must_clauses = query['query']['bool']['must']
        assert len(must_clauses) == 1
        assert 'multi_match' in must_clauses[0]
        assert must_clauses[0]['multi_match']['query'] == "machine learning"
        assert 'Title^2' in must_clauses[0]['multi_match']['fields']
    
    def test_build_query_author_search(self, tool):
        """Test query building with author search."""
        params = PublicationSearchInput(author_name="John Smith")
        query = tool._build_query(params)
        
        must_clauses = query['query']['bool']['must']
        assert len(must_clauses) == 1
        assert 'nested' in must_clauses[0]
        assert must_clauses[0]['nested']['path'] == 'Persons'
        
        nested_query = must_clauses[0]['nested']['query']
        assert 'match' in nested_query
        assert 'Persons.PersonData.DisplayName' in nested_query['match']
    
    def test_build_query_year_range(self, tool):
        """Test query building with year range."""
        params = PublicationSearchInput(year_range=(2020, 2023))
        query = tool._build_query(params)
        
        must_clauses = query['query']['bool']['must']
        assert len(must_clauses) == 1
        assert 'range' in must_clauses[0]
        assert must_clauses[0]['range']['Year']['gte'] == 2020
        assert must_clauses[0]['range']['Year']['lte'] == 2023
    
    def test_build_query_combined(self, tool):
        """Test query building with multiple parameters."""
        params = PublicationSearchInput(
            query="AI",
            author_name="Smith",
            year_range=(2020, 2023),
            publication_type="Journal article",
            keywords=["machine learning", "AI"]
        )
        query = tool._build_query(params)
        
        must_clauses = query['query']['bool']['must']
        assert len(must_clauses) == 5  # All conditions
        
        # Verify each clause type exists
        clause_types = [list(clause.keys())[0] for clause in must_clauses]
        assert 'multi_match' in clause_types
        assert 'nested' in clause_types
        assert 'range' in clause_types
        assert 'term' in clause_types
        assert 'terms' in clause_types
    
    def test_build_query_empty(self, tool):
        """Test query building with no parameters."""
        params = PublicationSearchInput()
        query = tool._build_query(params)
        
        assert 'query' in query
        assert 'match_all' in query['query']
    
    @pytest.mark.realistic_data
    def test_format_publication(self, tool, sample_es_response):
        """Test formatting publication from ES hit."""
        hit = sample_es_response['hits']['hits'][0]
        formatted = tool._format_publication(hit)
        
        assert formatted['id'] is not None
        assert formatted['title'] is not None
        assert formatted['year'] is not None
        assert formatted['score'] == 1.5
        
        # Check authors
        assert len(formatted['authors']) > 0
        assert formatted['authors'][0]['name'] is not None
        
        # Check keywords if present
        if 'keywords' in formatted:
            assert isinstance(formatted['keywords'], list)
    
    @pytest.mark.asyncio
    async def test_execute_success(self, tool, mock_es_client, sample_es_response):
        """Test successful execution of search."""
        mock_es_client.search.return_value = sample_es_response
        
        result = await tool.execute(
            query="machine learning",
            year_range=(2020, 2023),
            limit=10
        )
        
        assert result.success is True
        assert 'publications' in result.data
        assert 'total_results' in result.data
        assert len(result.data['publications']) == 2
        assert result.data['total_results'] == 2
        
        # Check metadata
        assert result.metadata['total_results'] == 2
        assert result.metadata['returned_results'] == 2
        assert result.metadata['query_time_ms'] == 15
        assert result.metadata['max_score'] == 1.5
        
        # Verify ES was called correctly
        mock_es_client.search.assert_called_once()
        call_args = mock_es_client.search.call_args
        assert call_args[1]['index'] == 'research-publications-static'
        assert 'body' in call_args[1]
    
    @pytest.mark.asyncio
    @pytest.mark.error_handling
    async def test_execute_validation_error(self, tool):
        """Test execution with invalid input."""
        result = await tool.execute(
            year_range=(2023, 2020)  # Invalid range
        )
        
        assert result.success is False
        assert result.data is None
        assert "Invalid input" in result.error
        assert "Start year must be less than" in result.error
    
    @pytest.mark.asyncio
    @pytest.mark.error_handling
    async def test_execute_connection_error(self, tool, mock_es_client):
        """Test execution with connection error."""
        # Create a proper ES 7.x ConnectionError
        mock_es_client.search.side_effect = ConnectionError(
            503, 
            'Connection refused',
            {'error': {'type': 'connection_error', 'reason': 'Connection refused'}}
        )
        
        result = await tool.execute(query="test")
        
        assert result.success is False
        assert result.data is None
        assert "Elasticsearch error" in result.error
    
    @pytest.mark.asyncio
    @pytest.mark.error_handling
    async def test_execute_query_error(self, tool, mock_es_client):
        """Test execution with query error."""
        # Create a proper ES 7.x RequestError
        mock_es_client.search.side_effect = RequestError(
            400, 
            "search_phase_execution_exception",
            {'error': {'type': 'query_shard_exception', 'reason': 'Invalid query'}}
        )
        
        result = await tool.execute(query="test")
        
        assert result.success is False
        assert result.data is None
        assert "Elasticsearch error" in result.error
        assert "Invalid query" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_empty_results(self, tool, mock_es_client):
        """Test execution with no results."""
        mock_es_client.search.return_value = {
            'took': 5,
            'hits': {
                'total': {'value': 0, 'relation': 'eq'},
                'max_score': None,
                'hits': []
            }
        }
        
        result = await tool.execute(query="nonexistent topic")
        
        assert result.success is True
        assert len(result.data['publications']) == 0
        assert result.data['total_results'] == 0
    
    @pytest.mark.asyncio
    @pytest.mark.error_handling
    async def test_execute_handles_missing_fields(self, tool, mock_es_client):
        """Test execution handles documents with missing fields gracefully."""
        mock_es_client.search.return_value = {
            'took': 10,
            'hits': {
                'total': {'value': 1, 'relation': 'eq'},
                'max_score': 1.0,
                'hits': [
                    {
                        '_id': 'pub-3',
                        '_score': 1.0,
                        '_source': {
                            'Id': 'uuid-pub-3',
                            'Title': 'Minimal Publication',
                            'Year': 2023
                            # Missing many fields
                        }
                    }
                ]
            }
        }
        
        result = await tool.execute(query="test")
        
        assert result.success is True
        assert len(result.data['publications']) == 1
        
        pub = result.data['publications'][0]
        assert pub['title'] == 'Minimal Publication'
        assert pub['abstract'] is None
        assert pub['authors'] == []
        assert pub['keywords'] == []
        assert pub['doi'] is None


@pytest.mark.unit
class TestSearchPublicationsLangChainTool:
    """Test the LangChain tool implementation."""
    
    @pytest.mark.asyncio
    async def test_search_publications_impl_success(self):
        """Test the implementation function directly."""
        with patch('src.tools.elasticsearch.publications.get_es_client') as mock_get_client:
            with patch('src.tools.elasticsearch.publications.SearchPublicationsTool') as MockTool:
                # Setup mocks
                mock_client = Mock()
                mock_get_client.return_value = mock_client
                
                mock_tool_instance = Mock()
                MockTool.return_value = mock_tool_instance
                
                mock_tool_instance.execute = AsyncMock(return_value=ToolResult(
                    success=True,
                    data={'publications': [], 'total_results': 0},
                    metadata={}
                ))
                
                # Call the implementation function directly
                result = await search_publications_impl(
                    query="test",
                    limit=5
                )
                
                assert result == {'publications': [], 'total_results': 0}
                mock_tool_instance.execute.assert_called_once_with(
                    query="test",
                    author_name=None,
                    year_range=None,
                    publication_type=None,
                    keywords=None,
                    organization_id=None,
                    limit=5
                )
    
    @pytest.mark.asyncio
    @pytest.mark.error_handling
    async def test_search_publications_impl_error(self):
        """Test the implementation function with error."""
        with patch('src.tools.elasticsearch.publications.get_es_client') as mock_get_client:
            with patch('src.tools.elasticsearch.publications.SearchPublicationsTool') as MockTool:
                # Setup mocks
                mock_client = Mock()
                mock_get_client.return_value = mock_client
                
                mock_tool_instance = Mock()
                MockTool.return_value = mock_tool_instance
                
                mock_tool_instance.execute = AsyncMock(return_value=ToolResult(
                    success=False,
                    data=None,
                    error="Connection failed"
                ))
                
                # Call the function - should raise exception
                with pytest.raises(Exception, match="Connection failed"):
                    await search_publications_impl(query="test")
    
    def test_tool_has_correct_attributes(self):
        """Test that the tool has the correct attributes for LangChain."""
        assert hasattr(search_publications_tool, 'name')
        assert search_publications_tool.name == "search_publications"
        assert hasattr(search_publications_tool, 'description')
        assert hasattr(search_publications_tool, 'args_schema')
        assert search_publications_tool.args_schema == PublicationSearchInput


@pytest.mark.integration
@pytest.mark.slow
class TestSearchPublicationsIntegration:
    """Integration tests that require a real Elasticsearch connection."""
    
    @pytest.mark.asyncio
    async def test_real_search_basic(self):
        """Test basic search against real Elasticsearch (if available)."""
        pytest.skip("Integration test - requires real Elasticsearch connection")
        
    @pytest.mark.asyncio
    async def test_real_search_complex(self):
        """Test complex search against real Elasticsearch (if available)."""
        pytest.skip("Integration test - requires real Elasticsearch connection")