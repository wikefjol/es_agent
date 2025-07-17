"""Tests for the Context Manager component."""

import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
from typing import List, Dict, Any
from src.core.context_manager import ContextManager
from src.models.schemas import CachedResult, ConversationContext


class TestContextManager:
    """Test cases for ContextManager class."""
    
    @pytest.fixture
    def context_manager(self):
        """Create a fresh ContextManager instance."""
        return ContextManager()
    
    @pytest.fixture
    def sample_result(self):
        """Create sample tool result for testing."""
        return {
            "data": {"publications": [{"title": "Test Paper", "author": "John Doe"}]},
            "metadata": {"execution_time": 1.2, "result_count": 1}
        }
    
    @pytest.fixture
    def sample_cached_result(self):
        """Create sample cached result for testing."""
        return CachedResult(
            cache_key="test_key",
            tool_name="search_publications",
            parameters={"query": "machine learning", "author": "John Doe"},
            result={"publications": [{"title": "Test Paper"}]},
            timestamp=time.time(),
            session_id="test_session",
            similarity_score=0.9,
            metadata={"result_count": 1}
        )
    
    def test_context_manager_initializes_correctly(self, context_manager):
        """Test that ContextManager initializes with correct default values."""
        assert context_manager.cache_ttl_seconds == 300
        assert context_manager.similarity_threshold == 0.85
        assert context_manager.max_conversation_length == 100
        assert len(context_manager._cache) == 0
        assert len(context_manager._sessions) == 0
    
    def test_store_result_creates_cache_entry(self, context_manager, sample_result):
        """Test that storing a result creates a cache entry."""
        cache_key = context_manager.store_result(
            session_id="test_session",
            tool_name="search_publications",
            parameters={"query": "machine learning"},
            result=sample_result,
            metadata={"test": "data"}
        )
        
        assert cache_key is not None
        assert cache_key in context_manager._cache
        cached_result = context_manager._cache[cache_key]
        assert cached_result.tool_name == "search_publications"
        assert cached_result.session_id == "test_session"
        assert cached_result.result == sample_result
        assert cached_result.metadata["test"] == "data"
    
    def test_store_result_generates_unique_cache_keys(self, context_manager, sample_result):
        """Test that different results get different cache keys."""
        key1 = context_manager.store_result(
            session_id="session1",
            tool_name="search_publications",
            parameters={"query": "AI"},
            result=sample_result,
            metadata={}
        )
        
        key2 = context_manager.store_result(
            session_id="session2",
            tool_name="search_publications",
            parameters={"query": "ML"},
            result=sample_result,
            metadata={}
        )
        
        assert key1 != key2
    
    def test_store_result_updates_session_context(self, context_manager, sample_result):
        """Test that storing a result updates session context."""
        session_id = "test_session"
        context_manager.store_result(
            session_id=session_id,
            tool_name="search_publications",
            parameters={"query": "test"},
            result=sample_result,
            metadata={}
        )
        
        assert session_id in context_manager._sessions
        session_context = context_manager._sessions[session_id]
        assert session_context.session_id == session_id
        assert len(session_context.cached_results) == 1
    
    @patch('src.core.context_manager.ContextManager._calculate_similarity')
    def test_find_relevant_results_returns_similar_results(self, mock_similarity, context_manager, sample_cached_result):
        """Test that find_relevant_results returns results above similarity threshold."""
        # Setup
        mock_similarity.return_value = 0.9
        context_manager._cache[sample_cached_result.cache_key] = sample_cached_result
        
        # Execute
        results = context_manager.find_relevant_results(
            session_id="test_session",
            query="machine learning research",
            similarity_threshold=0.85
        )
        
        # Verify
        assert len(results) == 1
        assert results[0].cache_key == sample_cached_result.cache_key
        assert results[0].similarity_score == 0.9
    
    @patch('src.core.context_manager.ContextManager._calculate_similarity')
    def test_find_relevant_results_filters_by_threshold(self, mock_similarity, context_manager, sample_cached_result):
        """Test that find_relevant_results filters results below threshold."""
        # Setup
        mock_similarity.return_value = 0.7  # Below threshold
        context_manager._cache[sample_cached_result.cache_key] = sample_cached_result
        
        # Execute
        results = context_manager.find_relevant_results(
            session_id="test_session",
            query="machine learning research",
            similarity_threshold=0.85
        )
        
        # Verify
        assert len(results) == 0
    
    def test_find_relevant_results_filters_by_session(self, context_manager, sample_cached_result):
        """Test that find_relevant_results only returns results from the same session."""
        # Setup
        context_manager._cache[sample_cached_result.cache_key] = sample_cached_result
        
        # Execute - different session
        results = context_manager.find_relevant_results(
            session_id="different_session",
            query="machine learning research",
            similarity_threshold=0.85
        )
        
        # Verify
        assert len(results) == 0
    
    def test_find_relevant_results_respects_cache_expiry(self, context_manager):
        """Test that find_relevant_results ignores expired cache entries."""
        # Create expired cached result
        expired_result = CachedResult(
            cache_key="expired_key",
            tool_name="search_publications",
            parameters={"query": "old query"},
            result={"data": "old data"},
            timestamp=time.time() - 400,  # Expired (default TTL is 300 seconds)
            session_id="test_session",
            similarity_score=0.0
        )
        
        context_manager._cache[expired_result.cache_key] = expired_result
        
        # Execute
        results = context_manager.find_relevant_results(
            session_id="test_session",
            query="machine learning research",
            similarity_threshold=0.85
        )
        
        # Verify
        assert len(results) == 0
    
    def test_get_conversation_summary_returns_summary_for_session(self, context_manager):
        """Test that get_conversation_summary returns correct summary for session."""
        session_id = "test_session"
        expected_summary = "User asked about machine learning. Found 5 relevant papers."
        
        # Setup session with summary
        context_manager._sessions[session_id] = ConversationContext(
            session_id=session_id,
            messages=[],
            cached_results={},
            summary=expected_summary,
            metadata={}
        )
        
        # Execute
        summary = context_manager.get_conversation_summary(session_id)
        
        # Verify
        assert summary == expected_summary
    
    def test_get_conversation_summary_returns_empty_for_nonexistent_session(self, context_manager):
        """Test that get_conversation_summary returns empty string for non-existent session."""
        summary = context_manager.get_conversation_summary("nonexistent_session")
        assert summary == ""
    
    def test_expire_old_cache_entries_removes_expired_entries(self, context_manager):
        """Test that expired cache entries are properly removed."""
        # Create expired entry
        expired_result = CachedResult(
            cache_key="expired_key",
            tool_name="search_publications",
            parameters={"query": "old query"},
            result={"data": "old data"},
            timestamp=time.time() - 400,  # Expired
            session_id="test_session",
            similarity_score=0.0
        )
        
        # Create fresh entry
        fresh_result = CachedResult(
            cache_key="fresh_key",
            tool_name="search_publications",
            parameters={"query": "new query"},
            result={"data": "new data"},
            timestamp=time.time(),  # Fresh
            session_id="test_session",
            similarity_score=0.0
        )
        
        context_manager._cache[expired_result.cache_key] = expired_result
        context_manager._cache[fresh_result.cache_key] = fresh_result
        
        # Execute cleanup
        context_manager._expire_old_cache_entries()
        
        # Verify
        assert "expired_key" not in context_manager._cache
        assert "fresh_key" in context_manager._cache
    
    def test_update_conversation_summary_updates_session_summary(self, context_manager):
        """Test that conversation summary gets updated correctly."""
        session_id = "test_session"
        new_summary = "Updated conversation summary"
        
        # Execute
        context_manager._update_conversation_summary(session_id, new_summary)
        
        # Verify
        assert session_id in context_manager._sessions
        assert context_manager._sessions[session_id].summary == new_summary
    
    def test_add_message_to_conversation_adds_to_session(self, context_manager):
        """Test that messages are added to conversation context."""
        session_id = "test_session"
        message = {"role": "user", "content": "Hello"}
        
        # Execute
        context_manager._add_message_to_conversation(session_id, message)
        
        # Verify
        assert session_id in context_manager._sessions
        assert len(context_manager._sessions[session_id].messages) == 1
        assert context_manager._sessions[session_id].messages[0] == message
    
    def test_add_message_to_conversation_respects_max_length(self, context_manager):
        """Test that conversation length is limited to max_conversation_length."""
        session_id = "test_session"
        context_manager.max_conversation_length = 2
        
        # Add more messages than max length
        for i in range(5):
            message = {"role": "user", "content": f"Message {i}"}
            context_manager._add_message_to_conversation(session_id, message)
        
        # Verify only the last messages are kept
        messages = context_manager._sessions[session_id].messages
        assert len(messages) == 2
        assert messages[0]["content"] == "Message 3"
        assert messages[1]["content"] == "Message 4"
    
    def test_calculate_similarity_uses_sentence_transformer(self, context_manager):
        """Test that similarity calculation uses sentence transformer."""
        # Setup mock directly on the instance
        mock_model = Mock()
        mock_model.encode.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        context_manager._similarity_model = mock_model
        
        # Execute
        similarity = context_manager._calculate_similarity("text1", "text2")
        
        # Verify
        mock_model.encode.assert_called_once_with(["text1", "text2"])
        assert isinstance(similarity, float)
        assert 0 <= similarity <= 1
    
    def test_generate_cache_key_creates_consistent_keys(self, context_manager):
        """Test that cache key generation is consistent for same inputs."""
        key1 = context_manager._generate_cache_key(
            session_id="test",
            tool_name="search",
            parameters={"query": "test"}
        )
        
        key2 = context_manager._generate_cache_key(
            session_id="test",
            tool_name="search",
            parameters={"query": "test"}
        )
        
        assert key1 == key2
    
    def test_generate_cache_key_creates_different_keys_for_different_inputs(self, context_manager):
        """Test that cache key generation creates different keys for different inputs."""
        key1 = context_manager._generate_cache_key(
            session_id="test1",
            tool_name="search",
            parameters={"query": "test"}
        )
        
        key2 = context_manager._generate_cache_key(
            session_id="test2",
            tool_name="search",
            parameters={"query": "test"}
        )
        
        assert key1 != key2
    
    def test_is_cache_entry_expired_correctly_identifies_expired_entries(self, context_manager):
        """Test that cache expiry check works correctly."""
        # Create expired entry
        expired_result = CachedResult(
            cache_key="test_key",
            tool_name="search",
            parameters={},
            result={},
            timestamp=time.time() - 400,  # Expired
            session_id="test",
            similarity_score=0.0
        )
        
        # Create fresh entry
        fresh_result = CachedResult(
            cache_key="test_key",
            tool_name="search",
            parameters={},
            result={},
            timestamp=time.time(),  # Fresh
            session_id="test",
            similarity_score=0.0
        )
        
        assert context_manager._is_cache_entry_expired(expired_result) is True
        assert context_manager._is_cache_entry_expired(fresh_result) is False