"""Context Manager for conversation memory and tool result caching."""

import time
import hashlib
import json
from typing import Dict, List, Optional, Any
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from src.models.schemas import CachedResult, ConversationContext


class ContextManager:
    """Manages conversation memory and tool result caching."""

    def __init__(
        self,
        cache_ttl_seconds: int = 300,
        similarity_threshold: float = 0.85,
        max_conversation_length: int = 100,
    ):
        """Initialize the ContextManager.

        Args:
            cache_ttl_seconds: Time to live for cached results in seconds
            similarity_threshold: Minimum similarity score for relevant results
            max_conversation_length: Maximum number of messages to keep in conversation
        """
        self.cache_ttl_seconds = cache_ttl_seconds
        self.similarity_threshold = similarity_threshold
        self.max_conversation_length = max_conversation_length

        # In-memory storage (in production, would use Redis or similar)
        self._cache: Dict[str, CachedResult] = {}
        self._sessions: Dict[str, ConversationContext] = {}

        # Initialize sentence transformer for similarity calculation
        self._similarity_model = None
        self._initialize_similarity_model()

    def _initialize_similarity_model(self):
        """Initialize the sentence transformer model for similarity calculation."""
        try:
            self._similarity_model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            # Fallback to a simple model if the preferred one fails
            try:
                self._similarity_model = SentenceTransformer("paraphrase-MiniLM-L6-v2")
            except Exception:
                # If all else fails, we'll use a basic similarity measure
                self._similarity_model = None

    def store_result(
        self,
        session_id: str,
        tool_name: str,
        parameters: Dict[str, Any],
        result: Any,
        metadata: Dict[str, Any],
    ) -> str:
        """Store a tool result in the cache.

        Args:
            session_id: Session identifier
            tool_name: Name of the tool that generated the result
            parameters: Parameters used for the tool call
            result: Result data from the tool
            metadata: Additional metadata about the result

        Returns:
            Cache key for the stored result
        """
        cache_key = self._generate_cache_key(session_id, tool_name, parameters)

        cached_result = CachedResult(
            cache_key=cache_key,
            tool_name=tool_name,
            parameters=parameters,
            result=result,
            timestamp=time.time(),
            session_id=session_id,
            similarity_score=0.0,
            metadata=metadata,
        )

        self._cache[cache_key] = cached_result

        # Update session context
        self._update_session_cache(session_id, cache_key)

        # Clean up expired entries periodically
        self._expire_old_cache_entries()

        return cache_key

    def find_relevant_results(
        self, session_id: str, query: str, similarity_threshold: Optional[float] = None
    ) -> List[CachedResult]:
        """Find cached results relevant to a query.

        Args:
            session_id: Session identifier
            query: Query string to find relevant results for
            similarity_threshold: Minimum similarity score (uses default if None)

        Returns:
            List of relevant cached results, sorted by similarity score
        """
        if similarity_threshold is None:
            similarity_threshold = self.similarity_threshold

        relevant_results = []

        for cache_key, cached_result in self._cache.items():
            # Only consider results from the same session
            if cached_result.session_id != session_id:
                continue

            # Skip expired entries
            if self._is_cache_entry_expired(cached_result):
                continue

            # Calculate similarity
            similarity_score = self._calculate_similarity_for_cached_result(
                query, cached_result
            )

            if similarity_score >= similarity_threshold:
                # Create a copy with updated similarity score
                result_copy = CachedResult(
                    cache_key=cached_result.cache_key,
                    tool_name=cached_result.tool_name,
                    parameters=cached_result.parameters,
                    result=cached_result.result,
                    timestamp=cached_result.timestamp,
                    session_id=cached_result.session_id,
                    similarity_score=similarity_score,
                    metadata=cached_result.metadata,
                )
                relevant_results.append(result_copy)

        # Sort by similarity score (descending)
        relevant_results.sort(key=lambda x: x.similarity_score, reverse=True)

        return relevant_results

    def get_conversation_summary(self, session_id: str) -> str:
        """Get conversation summary for a session.

        Args:
            session_id: Session identifier

        Returns:
            Conversation summary string
        """
        if session_id not in self._sessions:
            return ""

        return self._sessions[session_id].summary

    def _update_session_cache(self, session_id: str, cache_key: str):
        """Update session context with new cache entry."""
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationContext(
                session_id=session_id,
                messages=[],
                cached_results={},
                summary="",
                metadata={},
            )

        self._sessions[session_id].cached_results[cache_key] = time.time()

    def _update_conversation_summary(self, session_id: str, summary: str):
        """Update conversation summary for a session."""
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationContext(
                session_id=session_id,
                messages=[],
                cached_results={},
                summary="",
                metadata={},
            )

        self._sessions[session_id].summary = summary

    def _add_message_to_conversation(self, session_id: str, message: Dict[str, str]):
        """Add a message to the conversation context."""
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationContext(
                session_id=session_id,
                messages=[],
                cached_results={},
                summary="",
                metadata={},
            )

        session = self._sessions[session_id]
        session.messages.append(message)

        # Limit conversation length
        if len(session.messages) > self.max_conversation_length:
            session.messages = session.messages[-self.max_conversation_length :]

    def _calculate_similarity_for_cached_result(
        self, query: str, cached_result: CachedResult
    ) -> float:
        """Calculate similarity between query and cached result."""
        # Create a text representation of the cached result
        cached_text = self._create_text_from_cached_result(cached_result)

        return self._calculate_similarity(query, cached_text)

    def _create_text_from_cached_result(self, cached_result: CachedResult) -> str:
        """Create a text representation of a cached result for similarity calculation."""
        # Combine parameters and result information
        text_parts = []

        # Add tool name
        text_parts.append(f"Tool: {cached_result.tool_name}")

        # Add parameters
        for key, value in cached_result.parameters.items():
            text_parts.append(f"{key}: {value}")

        # Add result summary if available
        if isinstance(cached_result.result, dict):
            if "data" in cached_result.result:
                data = cached_result.result["data"]
                if isinstance(data, dict):
                    for key, value in data.items():
                        if isinstance(value, str):
                            text_parts.append(f"{key}: {value}")
                        elif isinstance(value, list) and len(value) > 0:
                            text_parts.append(f"{key}: {len(value)} items")

        return " ".join(text_parts)

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings."""
        if self._similarity_model is None:
            # Fallback to simple similarity if model unavailable
            return self._simple_similarity(text1, text2)

        try:
            # Encode both texts
            embeddings = self._similarity_model.encode([text1, text2])

            # Calculate cosine similarity
            similarity_matrix = cosine_similarity([embeddings[0]], [embeddings[1]])
            similarity = similarity_matrix[0][0]

            return max(0.0, min(1.0, similarity))  # Ensure between 0 and 1
        except Exception:
            # Fallback to simple similarity if encoding fails
            return self._simple_similarity(text1, text2)

    def _simple_similarity(self, text1: str, text2: str) -> float:
        """Simple similarity calculation based on word overlap."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union)

    def _generate_cache_key(
        self, session_id: str, tool_name: str, parameters: Dict[str, Any]
    ) -> str:
        """Generate a cache key for a tool result."""
        # Create a deterministic string representation
        key_data = {
            "session_id": session_id,
            "tool_name": tool_name,
            "parameters": parameters,
        }

        # Sort keys to ensure consistent ordering
        key_string = json.dumps(key_data, sort_keys=True)

        # Generate hash
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _is_cache_entry_expired(self, cached_result: CachedResult) -> bool:
        """Check if a cache entry has expired."""
        current_time = time.time()
        age = current_time - cached_result.timestamp
        return age > self.cache_ttl_seconds

    def _expire_old_cache_entries(self):
        """Remove expired cache entries."""
        current_time = time.time()
        expired_keys = []

        for cache_key, cached_result in self._cache.items():
            if self._is_cache_entry_expired(cached_result):
                expired_keys.append(cache_key)

        for key in expired_keys:
            del self._cache[key]

        # Also clean up session cache references
        for session in self._sessions.values():
            for cache_key in list(session.cached_results.keys()):
                if cache_key not in self._cache:
                    del session.cached_results[cache_key]
