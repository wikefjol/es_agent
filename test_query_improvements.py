#!/usr/bin/env python3
"""Test query improvements directly."""

import asyncio
from src.core.factory import get_configured_orchestrator

async def test_queries():
    """Test our query improvements."""
    
    print("🧪 Testing Query Improvements")
    print("=" * 50)
    
    orchestrator = get_configured_orchestrator()
    
    # Test cases
    test_queries = [
        "How many papers has Erik kristnansson published?",
        "What is it like to be an ant?",
        "Find publications by John Smith",
    ]
    
    for query in test_queries:
        print(f"\n📝 Query: '{query}'")
        
        try:
            result = await orchestrator.process_query(query, session_id="test_session")
            
            print(f"Response: {result.response[:200]}...")
            if result.sources:
                print(f"Sources: {len(result.sources)} found")
            print(f"Metadata: {result.metadata}")
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_queries())