#!/usr/bin/env python3
"""Comprehensive test of all improvements."""

import asyncio
from src.core.factory import get_configured_orchestrator
from src.utils.llm_query_parser import LLMQueryParser

async def test_all_improvements():
    """Test all improvements comprehensively."""
    
    print("🧪 Comprehensive Test of All Improvements")
    print("=" * 60)
    
    # Test 1: Query Parser
    print("\n1️⃣ Testing Query Parser")
    print("-" * 40)
    
    parser = LLMQueryParser()
    test_queries = [
        "How many papers has Erik kristnansson published?",
        "What is it like to be an ant?",
        "Find publications by John Smith",
        "Show me papers about machine learning from 2023",
        "How many papers has machine learning published?",  # Should not extract "machine learning" as author
    ]
    
    for query in test_queries:
        try:
            result = await parser.parse(query)
            print(f"\n📝 Query: '{query}'")
            print(f"   Intent: {result['intent'].value}")
            print(f"   Authors: {result['entities']['authors']}")
            print(f"   Topics: {result['entities']['topics']}")
            print(f"   Years: {result['entities']['years']}")
        except Exception as e:
            print(f"   Error: {e}")
    
    # Test 2: Full orchestration
    print("\n\n2️⃣ Testing Full Orchestration")
    print("-" * 40)
    
    orchestrator = get_configured_orchestrator()
    
    test_cases = [
        ("How many papers has Erik kristnansson published?", "Should find papers by Erik Kristnansson"),
        ("What is it like to be an ant?", "Should give philosophical response"),
        ("Tell me about quantum computing", "Should give conversational response"),
        ("Find papers about neural networks", "Should search for neural network papers"),
    ]
    
    for query, expected in test_cases:
        print(f"\n📝 Query: '{query}'")
        print(f"   Expected: {expected}")
        
        try:
            result = await orchestrator.process_query(query, session_id="test_session")
            
            # Check response type
            is_conversational = result.metadata.get('type') == 'conversational'
            has_sources = len(result.sources) > 0
            
            print(f"   Type: {'Conversational' if is_conversational else 'Tool-based'}")
            print(f"   Sources: {len(result.sources)} found")
            print(f"   Response preview: {result.response[:100]}...")
            
            # Verify expected behavior
            if "philosophical" in expected.lower() or "conversational" in expected.lower():
                assert is_conversational, "Should be conversational but got tool response"
                assert not has_sources, "Conversational queries shouldn't have sources"
            else:
                assert has_sources or not result.metadata.get('success'), "Tool queries should have sources or fail"
                
            print(f"   ✅ Passed")
            
        except AssertionError as e:
            print(f"   ❌ Failed: {e}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_all_improvements())