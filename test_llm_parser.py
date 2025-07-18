#!/usr/bin/env python3
"""Test the LLM query parser."""

import asyncio
from src.utils.llm_query_parser import LLMQueryParser

async def test_llm_parser():
    """Test LLM parser with various queries."""
    
    parser = LLMQueryParser()
    
    test_queries = [
        "How many papers has Erik kristnansson published?",
        "What is it like to be an ant?",
        "Find publications by John Smith",
        "Tell me about machine learning",
        "Find papers about machine learning",
        "Show me research by Sarah Johnson from 2023",
    ]
    
    print("🔍 Testing LLM Query Parser")
    print("=" * 50)
    
    for query in test_queries:
        try:
            result = await parser.parse(query)
            print(f"\nQuery: '{query}'")
            print(f"Intent: {result['intent'].value}")
            print(f"Authors: {result['entities']['authors']}")
            print(f"Topics: {result['entities']['topics']}")
            print(f"Keywords: {result['entities']['keywords']}")
            print(f"Years: {result['entities']['years']}")
            print(f"Confidence: {result['confidence']}")
        except Exception as e:
            print(f"\nQuery: '{query}'")
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_llm_parser())