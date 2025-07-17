"""Tests for the LLM Factory module."""

import pytest
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List, AsyncGenerator
import asyncio
import requests

from src.utils.llm_factory import (
    LLMFactory,
    LiteLLMHelper,
    LLMManager,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMValidationError,
    safe_llm_call,
    stream_llm_response
)


class TestLLMFactory:
    """Test cases for LLMFactory class."""

    def setup_method(self):
        """Setup test environment before each test."""
        # Clear environment variables
        for key in ['LITELLM_API_KEY', 'LITELLM_BASE_URL']:
            if key in os.environ:
                del os.environ[key]

    @pytest.fixture
    def mock_env_vars(self):
        """Mock environment variables for testing."""
        return {
            'LITELLM_API_KEY': 'test-api-key',
            'LITELLM_BASE_URL': 'https://test.api.com'
        }

    @pytest.fixture
    def mock_chat_litellm(self):
        """Mock ChatLiteLLM instance."""
        mock = Mock()
        mock.apredict = AsyncMock(return_value="Mock response")
        mock.apredict_messages = AsyncMock()
        mock.apredict_messages.return_value = Mock(content="Mock response")
        mock.astream = AsyncMock()
        return mock

    @pytest.mark.unit
    def test_create_orchestrator_llm_success(self, mock_env_vars, mock_chat_litellm):
        """Test successful creation of orchestrator LLM."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('src.utils.llm_factory.ChatLiteLLM', return_value=mock_chat_litellm):
                llm = LLMFactory.create_orchestrator_llm()
                
                assert llm is not None
                assert llm == mock_chat_litellm

    @pytest.mark.unit
    def test_create_orchestrator_llm_missing_api_key(self):
        """Test orchestrator LLM creation with missing API key."""
        with patch.dict(os.environ, {'LITELLM_BASE_URL': 'https://test.api.com'}):
            with pytest.raises(LLMValidationError) as exc_info:
                LLMFactory.create_orchestrator_llm()
            
            assert "LITELLM_API_KEY environment variable is required" in str(exc_info.value)

    @pytest.mark.unit
    def test_create_orchestrator_llm_missing_base_url(self):
        """Test orchestrator LLM creation with missing base URL."""
        with patch.dict(os.environ, {'LITELLM_API_KEY': 'test-key'}):
            with pytest.raises(LLMValidationError) as exc_info:
                LLMFactory.create_orchestrator_llm()
            
            assert "LITELLM_BASE_URL environment variable is required" in str(exc_info.value)

    @pytest.mark.unit
    def test_create_planner_llm_success(self, mock_env_vars, mock_chat_litellm):
        """Test successful creation of planner LLM."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('src.utils.llm_factory.ChatLiteLLM', return_value=mock_chat_litellm):
                llm = LLMFactory.create_planner_llm()
                
                assert llm is not None
                assert llm == mock_chat_litellm

    @pytest.mark.unit
    def test_create_planner_llm_configuration(self, mock_env_vars):
        """Test planner LLM configuration parameters."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('src.utils.llm_factory.ChatLiteLLM') as mock_class:
                LLMFactory.create_planner_llm()
                
                mock_class.assert_called_once_with(
                    model="anthropic/claude-3-opus-20240229",
                    api_key="test-api-key",
                    api_base="https://test.api.com",
                    temperature=0.1,
                    max_tokens=2048,
                    timeout=45
                )

    @pytest.mark.unit
    def test_create_tool_llm_success(self, mock_env_vars, mock_chat_litellm):
        """Test successful creation of tool LLM."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('src.utils.llm_factory.ChatLiteLLM', return_value=mock_chat_litellm):
                llm = LLMFactory.create_tool_llm()
                
                assert llm is not None
                assert llm == mock_chat_litellm

    @pytest.mark.unit
    def test_create_tool_llm_configuration(self, mock_env_vars):
        """Test tool LLM configuration parameters."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('src.utils.llm_factory.ChatLiteLLM') as mock_class:
                LLMFactory.create_tool_llm()
                
                mock_class.assert_called_once_with(
                    model="anthropic/claude-3-haiku-20240307",
                    api_key="test-api-key",
                    api_base="https://test.api.com",
                    temperature=0.0,
                    max_tokens=512,
                    timeout=20
                )

    @pytest.mark.unit
    def test_create_summary_llm_success(self, mock_env_vars, mock_chat_litellm):
        """Test successful creation of summary LLM."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('src.utils.llm_factory.ChatLiteLLM', return_value=mock_chat_litellm):
                llm = LLMFactory.create_summary_llm()
                
                assert llm is not None
                assert llm == mock_chat_litellm

    @pytest.mark.unit
    def test_create_summary_llm_configuration(self, mock_env_vars):
        """Test summary LLM configuration parameters."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('src.utils.llm_factory.ChatLiteLLM') as mock_class:
                LLMFactory.create_summary_llm()
                
                mock_class.assert_called_once_with(
                    model="anthropic/claude-3-haiku-20240307",
                    api_key="test-api-key",
                    api_base="https://test.api.com",
                    temperature=0.2,
                    max_tokens=1024,
                    timeout=30
                )

    @pytest.mark.unit
    def test_all_factory_methods_validate_env_vars(self):
        """Test that all factory methods validate environment variables."""
        factory_methods = [
            LLMFactory.create_orchestrator_llm,
            LLMFactory.create_planner_llm,
            LLMFactory.create_tool_llm,
            LLMFactory.create_summary_llm
        ]
        
        for method in factory_methods:
            with pytest.raises(LLMValidationError):
                method()


class TestLiteLLMHelper:
    """Test cases for LiteLLMHelper utility class."""

    def setup_method(self):
        """Setup test environment before each test."""
        # Clear environment variables
        for key in ['LITELLM_API_KEY', 'LITELLM_BASE_URL']:
            if key in os.environ:
                del os.environ[key]

    @pytest.fixture
    def mock_env_vars(self):
        """Mock environment variables for testing."""
        return {
            'LITELLM_API_KEY': 'test-api-key',
            'LITELLM_BASE_URL': 'https://test.api.com'
        }

    @pytest.fixture
    def mock_models_response(self):
        """Mock response for models API."""
        return {
            "data": [
                {"id": "anthropic/claude-3-sonnet-20240229"},
                {"id": "anthropic/claude-3-opus-20240229"},
                {"id": "anthropic/claude-3-haiku-20240307"}
            ]
        }

    @pytest.mark.unit
    def test_get_available_models_success(self, mock_env_vars, mock_models_response):
        """Test successful retrieval of available models."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('requests.get') as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = mock_models_response
                
                models = LiteLLMHelper.get_available_models()
                
                assert models is not None
                assert len(models) == 3
                assert "anthropic/claude-3-sonnet-20240229" in models
                assert "anthropic/claude-3-opus-20240229" in models
                assert "anthropic/claude-3-haiku-20240307" in models

    @pytest.mark.unit
    def test_get_available_models_missing_env_vars(self):
        """Test get_available_models with missing environment variables."""
        models = LiteLLMHelper.get_available_models()
        assert models is None

    @pytest.mark.unit
    def test_get_available_models_api_error(self, mock_env_vars):
        """Test get_available_models with API error."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('requests.get') as mock_get:
                mock_get.return_value.status_code = 500
                
                models = LiteLLMHelper.get_available_models()
                
                assert models is None

    @pytest.mark.unit
    def test_get_available_models_request_exception(self, mock_env_vars):
        """Test get_available_models with request exception."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('requests.get', side_effect=requests.RequestException("Connection error")):
                models = LiteLLMHelper.get_available_models()
                
                assert models is None

    @pytest.mark.unit
    def test_get_available_models_timeout(self, mock_env_vars):
        """Test get_available_models with timeout."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('requests.get', side_effect=requests.Timeout("Timeout")):
                models = LiteLLMHelper.get_available_models()
                
                assert models is None

    @pytest.mark.unit
    def test_validate_model_availability_success(self, mock_env_vars, mock_models_response):
        """Test successful model availability validation."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('requests.get') as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = mock_models_response
                
                is_available = LiteLLMHelper.validate_model_availability("anthropic/claude-3-sonnet-20240229")
                
                assert is_available is True

    @pytest.mark.unit
    def test_validate_model_availability_not_found(self, mock_env_vars, mock_models_response):
        """Test model availability validation for non-existent model."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('requests.get') as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = mock_models_response
                
                is_available = LiteLLMHelper.validate_model_availability("nonexistent/model")
                
                assert is_available is False

    @pytest.mark.unit
    def test_validate_model_availability_api_error(self, mock_env_vars):
        """Test model availability validation with API error."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('requests.get', side_effect=requests.RequestException("Connection error")):
                is_available = LiteLLMHelper.validate_model_availability("anthropic/claude-3-sonnet-20240229")
                
                assert is_available is False

    @pytest.mark.unit
    def test_validate_configuration_success(self, mock_env_vars, mock_models_response):
        """Test successful configuration validation."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('requests.get') as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = mock_models_response
                
                result = LiteLLMHelper.validate_configuration()
                
                assert result["valid"] is True
                assert len(result["errors"]) == 0
                assert result["available_models"] is not None
                assert len(result["available_models"]) == 3

    @pytest.mark.unit
    def test_validate_configuration_missing_api_key(self):
        """Test configuration validation with missing API key."""
        with patch.dict(os.environ, {'LITELLM_BASE_URL': 'https://test.api.com'}):
            result = LiteLLMHelper.validate_configuration()
            
            assert result["valid"] is False
            assert "LITELLM_API_KEY environment variable is missing" in result["errors"]
            assert result["available_models"] is None

    @pytest.mark.unit
    def test_validate_configuration_missing_base_url(self):
        """Test configuration validation with missing base URL."""
        with patch.dict(os.environ, {'LITELLM_API_KEY': 'test-key'}):
            result = LiteLLMHelper.validate_configuration()
            
            assert result["valid"] is False
            assert "LITELLM_BASE_URL environment variable is missing" in result["errors"]
            assert result["available_models"] is None

    @pytest.mark.unit
    def test_validate_configuration_connection_error(self, mock_env_vars):
        """Test configuration validation with connection error."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('requests.get', side_effect=requests.RequestException("Connection error")):
                result = LiteLLMHelper.validate_configuration()
                
                assert result["valid"] is False
                assert "Unable to connect to LiteLLM proxy" in result["errors"]
                assert result["available_models"] is None

    @pytest.mark.unit
    def test_validate_configuration_api_unavailable(self, mock_env_vars):
        """Test configuration validation with API unavailable."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('requests.get') as mock_get:
                mock_get.return_value.status_code = 500
                
                result = LiteLLMHelper.validate_configuration()
                
                assert result["valid"] is False
                assert "Unable to connect to LiteLLM proxy" in result["errors"]
                assert result["available_models"] is None


class TestLLMManager:
    """Test cases for LLMManager class."""

    def setup_method(self):
        """Setup test environment before each test."""
        # Clear environment variables
        for key in ['LITELLM_API_KEY', 'LITELLM_BASE_URL']:
            if key in os.environ:
                del os.environ[key]

    @pytest.fixture
    def mock_env_vars(self):
        """Mock environment variables for testing."""
        return {
            'LITELLM_API_KEY': 'test-api-key',
            'LITELLM_BASE_URL': 'https://test.api.com'
        }

    @pytest.fixture
    def mock_chat_litellm(self):
        """Mock ChatLiteLLM instance."""
        mock = Mock()
        mock.apredict = AsyncMock(return_value="Mock response")
        mock.apredict_messages = AsyncMock()
        mock.apredict_messages.return_value = Mock(content="Mock response")
        return mock

    @pytest.mark.unit
    def test_manager_initialization(self):
        """Test LLMManager initialization."""
        manager = LLMManager()
        
        assert manager._orchestrator_llm is None
        assert manager._planner_llm is None
        assert manager._tool_llm is None
        assert manager._summary_llm is None

    @pytest.mark.unit
    def test_get_orchestrator_llm_creates_instance(self, mock_env_vars, mock_chat_litellm):
        """Test that get_orchestrator_llm creates and caches instance."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('src.utils.llm_factory.ChatLiteLLM', return_value=mock_chat_litellm):
                manager = LLMManager()
                
                # First call should create instance
                llm1 = manager.get_orchestrator_llm()
                assert llm1 is not None
                assert manager._orchestrator_llm is not None
                
                # Second call should return cached instance
                llm2 = manager.get_orchestrator_llm()
                assert llm2 is llm1

    @pytest.mark.unit
    def test_get_planner_llm_creates_instance(self, mock_env_vars, mock_chat_litellm):
        """Test that get_planner_llm creates and caches instance."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('src.utils.llm_factory.ChatLiteLLM', return_value=mock_chat_litellm):
                manager = LLMManager()
                
                # First call should create instance
                llm1 = manager.get_planner_llm()
                assert llm1 is not None
                assert manager._planner_llm is not None
                
                # Second call should return cached instance
                llm2 = manager.get_planner_llm()
                assert llm2 is llm1

    @pytest.mark.unit
    def test_get_tool_llm_creates_instance(self, mock_env_vars, mock_chat_litellm):
        """Test that get_tool_llm creates and caches instance."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('src.utils.llm_factory.ChatLiteLLM', return_value=mock_chat_litellm):
                manager = LLMManager()
                
                # First call should create instance
                llm1 = manager.get_tool_llm()
                assert llm1 is not None
                assert manager._tool_llm is not None
                
                # Second call should return cached instance
                llm2 = manager.get_tool_llm()
                assert llm2 is llm1

    @pytest.mark.unit
    def test_get_summary_llm_creates_instance(self, mock_env_vars, mock_chat_litellm):
        """Test that get_summary_llm creates and caches instance."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('src.utils.llm_factory.ChatLiteLLM', return_value=mock_chat_litellm):
                manager = LLMManager()
                
                # First call should create instance
                llm1 = manager.get_summary_llm()
                assert llm1 is not None
                assert manager._summary_llm is not None
                
                # Second call should return cached instance
                llm2 = manager.get_summary_llm()
                assert llm2 is llm1

    @pytest.mark.unit
    def test_reset_connections(self, mock_env_vars, mock_chat_litellm):
        """Test that reset_connections clears all cached instances."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('src.utils.llm_factory.ChatLiteLLM', return_value=mock_chat_litellm):
                manager = LLMManager()
                
                # Create all instances
                manager.get_orchestrator_llm()
                manager.get_planner_llm()
                manager.get_tool_llm()
                manager.get_summary_llm()
                
                # Verify instances exist
                assert manager._orchestrator_llm is not None
                assert manager._planner_llm is not None
                assert manager._tool_llm is not None
                assert manager._summary_llm is not None
                
                # Reset connections
                manager.reset_connections()
                
                # Verify all instances are cleared
                assert manager._orchestrator_llm is None
                assert manager._planner_llm is None
                assert manager._tool_llm is None
                assert manager._summary_llm is None

    @pytest.mark.unit
    def test_manager_handles_llm_creation_errors(self, mock_env_vars):
        """Test that manager properly handles LLM creation errors."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('src.utils.llm_factory.ChatLiteLLM', side_effect=Exception("LLM creation failed")):
                manager = LLMManager()
                
                with pytest.raises(Exception, match="LLM creation failed"):
                    manager.get_orchestrator_llm()


class TestErrorHandling:
    """Test cases for error handling functionality."""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM instance for testing."""
        mock = Mock()
        mock.apredict_messages = AsyncMock()
        mock.astream = AsyncMock()
        return mock

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_safe_llm_call_success(self, mock_llm):
        """Test successful LLM call with safe_llm_call."""
        mock_response = Mock()
        mock_response.content = "Test response"
        mock_llm.apredict_messages.return_value = mock_response
        
        messages = [{"role": "user", "content": "Test message"}]
        result = await safe_llm_call(mock_llm, messages)
        
        assert result == "Test response"
        mock_llm.apredict_messages.assert_called_once_with(messages)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_safe_llm_call_rate_limit_error(self, mock_llm):
        """Test safe_llm_call with rate limit error."""
        mock_llm.apredict_messages.side_effect = Exception("rate_limit exceeded")
        
        messages = [{"role": "user", "content": "Test message"}]
        
        with pytest.raises(LLMRateLimitError) as exc_info:
            await safe_llm_call(mock_llm, messages)
        
        assert "Rate limit hit" in str(exc_info.value)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_safe_llm_call_timeout_error(self, mock_llm):
        """Test safe_llm_call with timeout error."""
        mock_llm.apredict_messages.side_effect = Exception("Request timeout")
        
        messages = [{"role": "user", "content": "Test message"}]
        
        with pytest.raises(LLMTimeoutError) as exc_info:
            await safe_llm_call(mock_llm, messages)
        
        assert "LLM call timed out" in str(exc_info.value)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_safe_llm_call_429_error(self, mock_llm):
        """Test safe_llm_call with 429 status code."""
        mock_llm.apredict_messages.side_effect = Exception("429 Too Many Requests")
        
        messages = [{"role": "user", "content": "Test message"}]
        
        with pytest.raises(LLMRateLimitError) as exc_info:
            await safe_llm_call(mock_llm, messages)
        
        assert "Rate limit hit" in str(exc_info.value)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_safe_llm_call_504_error(self, mock_llm):
        """Test safe_llm_call with 504 status code."""
        mock_llm.apredict_messages.side_effect = Exception("504 Gateway Timeout")
        
        messages = [{"role": "user", "content": "Test message"}]
        
        with pytest.raises(LLMTimeoutError) as exc_info:
            await safe_llm_call(mock_llm, messages)
        
        assert "LLM call timed out" in str(exc_info.value)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_safe_llm_call_generic_error(self, mock_llm):
        """Test safe_llm_call with generic error."""
        mock_llm.apredict_messages.side_effect = Exception("Generic error")
        
        messages = [{"role": "user", "content": "Test message"}]
        
        with pytest.raises(LLMError) as exc_info:
            await safe_llm_call(mock_llm, messages)
        
        assert "LLM call failed" in str(exc_info.value)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_safe_llm_call_retry_mechanism(self, mock_llm):
        """Test safe_llm_call retry mechanism."""
        # Mock to fail twice, then succeed
        mock_response = Mock()
        mock_response.content = "Success after retry"
        mock_llm.apredict_messages.side_effect = [
            Exception("Temporary error"),
            Exception("Another temporary error"),
            mock_response
        ]
        
        messages = [{"role": "user", "content": "Test message"}]
        result = await safe_llm_call(mock_llm, messages)
        
        assert result == "Success after retry"
        assert mock_llm.apredict_messages.call_count == 3


class TestStreamingFunctionality:
    """Test cases for streaming functionality."""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM instance for testing."""
        mock = Mock()
        mock.astream = AsyncMock()
        return mock

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stream_llm_response_success(self, mock_llm):
        """Test successful streaming response."""
        # Mock async generator
        async def mock_stream():
            chunks = [
                Mock(content="Hello "),
                Mock(content="world!"),
                Mock(content=" How are you?")
            ]
            for chunk in chunks:
                yield chunk
        
        # Create mock that returns an async iterator
        mock_llm.astream = Mock(return_value=mock_stream())
        
        messages = [{"role": "user", "content": "Test message"}]
        chunks = []
        
        async for chunk in stream_llm_response(mock_llm, messages):
            chunks.append(chunk)
        
        assert chunks == ["Hello ", "world!", " How are you?"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stream_llm_response_with_callback(self, mock_llm):
        """Test streaming response with callback handler."""
        mock_callback = Mock()
        
        async def mock_stream():
            yield Mock(content="Test chunk")
        
        mock_llm.astream = Mock(return_value=mock_stream())
        
        messages = [{"role": "user", "content": "Test message"}]
        chunks = []
        
        async for chunk in stream_llm_response(mock_llm, messages, mock_callback):
            chunks.append(chunk)
        
        assert chunks == ["Test chunk"]
        mock_llm.astream.assert_called_once_with(messages, callbacks=[mock_callback])

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stream_llm_response_empty_content(self, mock_llm):
        """Test streaming response with empty content chunks."""
        async def mock_stream():
            chunks = [
                Mock(content="Hello "),
                Mock(content=""),  # Empty content
                Mock(content=None),  # None content
                Mock(content="world!")
            ]
            for chunk in chunks:
                yield chunk
        
        mock_llm.astream = Mock(return_value=mock_stream())
        
        messages = [{"role": "user", "content": "Test message"}]
        chunks = []
        
        async for chunk in stream_llm_response(mock_llm, messages):
            chunks.append(chunk)
        
        # Should only get chunks with actual content
        assert chunks == ["Hello ", "world!"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stream_llm_response_no_content_attribute(self, mock_llm):
        """Test streaming response with chunks without content attribute."""
        async def mock_stream():
            chunks = [
                Mock(content="Hello "),
                Mock(spec=[]),  # No content attribute
                Mock(content="world!")
            ]
            for chunk in chunks:
                yield chunk
        
        mock_llm.astream = Mock(return_value=mock_stream())
        
        messages = [{"role": "user", "content": "Test message"}]
        chunks = []
        
        async for chunk in stream_llm_response(mock_llm, messages):
            chunks.append(chunk)
        
        # Should only get chunks with content attribute
        assert chunks == ["Hello ", "world!"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stream_llm_response_rate_limit_error(self, mock_llm):
        """Test streaming response with rate limit error."""
        mock_llm.astream = Mock(side_effect=Exception("rate_limit exceeded"))
        
        messages = [{"role": "user", "content": "Test message"}]
        
        with pytest.raises(LLMRateLimitError) as exc_info:
            async for chunk in stream_llm_response(mock_llm, messages):
                pass
        
        assert "Rate limit hit during streaming" in str(exc_info.value)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stream_llm_response_timeout_error(self, mock_llm):
        """Test streaming response with timeout error."""
        mock_llm.astream = Mock(side_effect=Exception("Request timeout"))
        
        messages = [{"role": "user", "content": "Test message"}]
        
        with pytest.raises(LLMTimeoutError) as exc_info:
            async for chunk in stream_llm_response(mock_llm, messages):
                pass
        
        assert "LLM streaming timed out" in str(exc_info.value)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stream_llm_response_generic_error(self, mock_llm):
        """Test streaming response with generic error."""
        mock_llm.astream = Mock(side_effect=Exception("Generic streaming error"))
        
        messages = [{"role": "user", "content": "Test message"}]
        
        with pytest.raises(LLMError) as exc_info:
            async for chunk in stream_llm_response(mock_llm, messages):
                pass
        
        assert "LLM streaming failed" in str(exc_info.value)


class TestExceptionClasses:
    """Test cases for custom exception classes."""

    @pytest.mark.unit
    def test_llm_error_inheritance(self):
        """Test that LLMError inherits from Exception."""
        error = LLMError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    @pytest.mark.unit
    def test_llm_rate_limit_error_inheritance(self):
        """Test that LLMRateLimitError inherits from LLMError."""
        error = LLMRateLimitError("Rate limit test")
        assert isinstance(error, LLMError)
        assert isinstance(error, Exception)
        assert str(error) == "Rate limit test"

    @pytest.mark.unit
    def test_llm_timeout_error_inheritance(self):
        """Test that LLMTimeoutError inherits from LLMError."""
        error = LLMTimeoutError("Timeout test")
        assert isinstance(error, LLMError)
        assert isinstance(error, Exception)
        assert str(error) == "Timeout test"

    @pytest.mark.unit
    def test_llm_validation_error_inheritance(self):
        """Test that LLMValidationError inherits from LLMError."""
        error = LLMValidationError("Validation test")
        assert isinstance(error, LLMError)
        assert isinstance(error, Exception)
        assert str(error) == "Validation test"


class TestIntegration:
    """Integration tests for LLM factory components."""

    def setup_method(self):
        """Setup test environment before each test."""
        # Clear environment variables
        for key in ['LITELLM_API_KEY', 'LITELLM_BASE_URL']:
            if key in os.environ:
                del os.environ[key]

    @pytest.fixture
    def mock_env_vars(self):
        """Mock environment variables for testing."""
        return {
            'LITELLM_API_KEY': 'test-api-key',
            'LITELLM_BASE_URL': 'https://test.api.com'
        }

    @pytest.mark.integration
    def test_factory_and_manager_integration(self, mock_env_vars):
        """Test integration between factory and manager."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('src.utils.llm_factory.ChatLiteLLM') as mock_class:
                mock_instance = Mock()
                mock_class.return_value = mock_instance
                
                manager = LLMManager()
                
                # Test that manager uses factory correctly
                orchestrator_llm = manager.get_orchestrator_llm()
                assert orchestrator_llm is mock_instance
                
                # Verify factory method was called with correct parameters
                mock_class.assert_called_with(
                    model="anthropic/claude-3-sonnet-20240229",
                    api_key="test-api-key",
                    api_base="https://test.api.com",
                    temperature=0.3,
                    max_tokens=1024,
                    timeout=30
                )

    @pytest.mark.integration
    def test_helper_and_factory_integration(self, mock_env_vars):
        """Test integration between helper and factory."""
        mock_models_response = {
            "data": [
                {"id": "anthropic/claude-3-sonnet-20240229"},
                {"id": "anthropic/claude-3-opus-20240229"}
            ]
        }
        
        with patch.dict(os.environ, mock_env_vars):
            with patch('requests.get') as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = mock_models_response
                
                # Test configuration validation
                config_result = LiteLLMHelper.validate_configuration()
                assert config_result["valid"] is True
                assert len(config_result["available_models"]) == 2
                
                # Test model availability
                is_available = LiteLLMHelper.validate_model_availability(
                    "anthropic/claude-3-sonnet-20240229"
                )
                assert is_available is True
                
                # Test factory creation with valid configuration
                with patch('src.utils.llm_factory.ChatLiteLLM') as mock_class:
                    mock_instance = Mock()
                    mock_class.return_value = mock_instance
                    
                    llm = LLMFactory.create_orchestrator_llm()
                    assert llm is mock_instance

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, mock_env_vars):
        """Test integration of error handling across components."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('src.utils.llm_factory.ChatLiteLLM') as mock_class:
                mock_instance = Mock()
                mock_instance.apredict_messages = AsyncMock(
                    side_effect=Exception("rate_limit exceeded")
                )
                mock_class.return_value = mock_instance
                
                manager = LLMManager()
                llm = manager.get_orchestrator_llm()
                
                # Test error handling in safe_llm_call
                messages = [{"role": "user", "content": "Test"}]
                
                with pytest.raises(LLMRateLimitError):
                    await safe_llm_call(llm, messages)