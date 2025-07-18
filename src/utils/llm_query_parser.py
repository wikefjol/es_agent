"""LLM-based query parser with fallback to regex patterns."""

import json
from typing import Dict, List, Optional, Any
from enum import Enum
from langchain_core.messages import HumanMessage, SystemMessage
from src.utils.llm_factory import LLMFactory


class QueryIntent(Enum):
    """Types of query intents."""
    COUNT = "count"  # How many papers...
    LIST = "list"  # Show me papers...
    SEARCH = "search"  # Find publications about...
    ANALYZE = "analyze"  # What are the trends...
    AUTHOR_SEARCH = "author_search"  # Papers by specific author
    TOPIC_SEARCH = "topic_search"  # Papers about specific topic
    UNKNOWN = "unknown"


class LLMQueryParser:
    """Parse user queries using LLM with fallback to regex patterns."""
    
    def __init__(self):
        self.llm = None
        # Fallback to the original QueryParser if LLM fails
        from src.utils.query_parser import QueryParser
        self.fallback_parser = QueryParser()
        
    def _get_llm(self):
        """Get LLM instance with lazy initialization."""
        if self.llm is None:
            self.llm = self._create_parser_llm()
        return self.llm
        
    def _create_parser_llm(self):
        """Create LLM for query parsing with fallback."""
        try:
            return LLMFactory._create_litellm_parser()
        except Exception as e:
            # Silently fall back to direct Anthropic
            try:
                return LLMFactory._create_anthropic_parser()
            except Exception as e2:
                # If both fail, we'll use regex fallback
                print(f"LLM initialization failed, will use regex fallback: {e2}")
                return None
    
    async def parse(self, query: str) -> Dict[str, Any]:
        """Parse a query to extract intent and entities.
        
        Args:
            query: User query string
            
        Returns:
            Dictionary with parsed information
        """
        llm = self._get_llm()
        
        # If no LLM available, use fallback
        if llm is None:
            return self.fallback_parser.parse(query)
            
        try:
            # Create structured prompt for the LLM
            system_prompt = """You are a query parser for an academic publication search system. 
Extract the intent and entities from user queries.

Intents:
- COUNT: Counting queries (how many, total number, count of)
- LIST: Listing queries (show me, list, display)
- SEARCH: General search queries (find, search for)
- AUTHOR_SEARCH: Searching for papers by a specific author
- TOPIC_SEARCH: Searching for papers about a specific topic
- ANALYZE: Analysis queries (trends, statistics, patterns)
- UNKNOWN: Cannot determine intent

Extract these entities:
- authors: List of author names (preserve original capitalization)
- topics: List of research topics
- years: List of years mentioned (4-digit years)
- keywords: Important keywords not captured above

IMPORTANT: For author names, extract the full name exactly as written in the query, including any capitalization or spelling variations.

Respond in JSON format:
{
    "intent": "INTENT_NAME",
    "entities": {
        "authors": ["list", "of", "authors"],
        "topics": ["list", "of", "topics"],
        "years": [2023, 2024],
        "keywords": ["other", "keywords"]
    },
    "confidence": 0.95
}"""

            user_prompt = f"""Parse this query: "{query}"

Examples:
- "How many papers has Erik kristnansson published?" → intent: COUNT, authors: ["Erik kristnansson"]
- "Find publications about machine learning" → intent: TOPIC_SEARCH, topics: ["machine learning"]
- "Show me papers by John Smith from 2023" → intent: AUTHOR_SEARCH, authors: ["John Smith"], years: [2023]
- "What are the trends in quantum computing?" → intent: ANALYZE, topics: ["quantum computing"]
"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = await llm.ainvoke(messages)
            parsed_result = json.loads(response.content)
            
            # Convert intent string to enum
            intent_str = parsed_result.get("intent", "UNKNOWN")
            try:
                intent = QueryIntent[intent_str]
            except KeyError:
                intent = QueryIntent.UNKNOWN
                
            # Return structured result matching the fallback parser format
            return {
                "original_query": query,
                "intent": intent,
                "entities": parsed_result.get("entities", {
                    "authors": [],
                    "topics": [],
                    "years": [],
                    "keywords": []
                }),
                "confidence": parsed_result.get("confidence", 0.5)
            }
            
        except Exception as e:
            print(f"LLM parsing failed, using regex fallback: {e}")
            # Fall back to regex-based parser
            return self.fallback_parser.parse(query)


# Add the parser creation methods to LLMFactory
def _create_litellm_parser():
    """Create LiteLLM parser."""
    import os
    from langchain_litellm import ChatLiteLLM
    from src.utils.llm_factory import LLMValidationError
    
    api_key = os.getenv("LITELLM_API_KEY")
    api_base = os.getenv("LITELLM_BASE_URL")

    if not api_key or not api_base:
        raise LLMValidationError("LiteLLM credentials not available")

    return ChatLiteLLM(
        model="anthropic/claude-3-haiku-20240307",  # Fast model for parsing
        api_key=api_key,
        api_base=api_base,
        temperature=0.0,  # Deterministic for parsing
        max_tokens=512,
        timeout=15,
    )


def _create_anthropic_parser():
    """Create direct Anthropic parser."""
    import os
    from langchain_anthropic import ChatAnthropic
    from src.utils.llm_factory import LLMValidationError
    
    api_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
    
    if not api_key:
        raise LLMValidationError("ANTHROPIC_AUTH_TOKEN environment variable is required")

    return ChatAnthropic(
        model="claude-3-5-haiku-20241022",  # Fast model for parsing
        api_key=api_key,
        temperature=0.0,
        max_tokens=512,
        timeout=15,
    )


# Monkey patch the methods onto LLMFactory
LLMFactory._create_litellm_parser = staticmethod(_create_litellm_parser)
LLMFactory._create_anthropic_parser = staticmethod(_create_anthropic_parser)