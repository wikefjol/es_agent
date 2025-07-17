#!/usr/bin/env python
"""Test script to verify real Elasticsearch connection and search functionality."""

import asyncio
import os
from dotenv import load_dotenv
import logging
from pprint import pprint

# Load environment variables
load_dotenv()

# Add the src directory to the path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.tools.elasticsearch import get_es_client, get_es_manager
from src.tools.elasticsearch.publications import search_publications_impl

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_connection():
    """Test the connection to the real Elasticsearch cluster."""
    print("\n=== Testing Elasticsearch Connection ===")
    print(f"Connecting to: {os.getenv('ES_HOST')}")
    
    try:
        manager = get_es_manager()
        health = manager.health_check()
        print(f"✅ Cluster status: {health.get('status', 'unknown')}")
        
        # Get cluster info
        client = get_es_client()
        info = client.info()
        print(f"✅ Elasticsearch version: {info['version']['number']}")
        print(f"✅ Cluster name: {info.get('cluster_name', 'N/A')}")
        
        # Check indices
        print("\n=== Available Research Indices ===")
        indices = client.indices.get_alias("research-*")
        for index in sorted(indices.keys()):
            try:
                count = client.count(index=index)['count']
                print(f"  - {index}: {count:,} documents")
            except Exception as e:
                print(f"  - {index}: Error getting count - {e}")
                
        return True
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


async def test_search():
    """Test search functionality."""
    print("\n=== Testing Search Functionality ===")
    
    test_queries = [
        # Simple text search
        {"query": "machine learning", "limit": 5},
        
        # Author search
        {"author_name": "Christian Fager", "limit": 5},
        
        # Year range search
        {"year_range": (2023, 2024), "limit": 5},
        
        # Combined search
        {"query": "energy", "year_range": (2020, 2024), "limit": 3}
    ]
    
    for i, query_params in enumerate(test_queries, 1):
        print(f"\n--- Test Query {i} ---")
        print(f"Parameters: {query_params}")
        
        try:
            result = await search_publications_impl(**query_params)
            
            print(f"✅ Found {result['total_results']} publications")
            print(f"✅ Returned {len(result['publications'])} results")
            
            # Show first result if any
            if result['publications']:
                first_pub = result['publications'][0]
                print(f"\nFirst result:")
                print(f"  Title: {first_pub['title']}")
                print(f"  Year: {first_pub['year']}")
                if first_pub.get('authors'):
                    authors = [a['name'] for a in first_pub['authors'][:3]]
                    print(f"  Authors: {', '.join(authors)}")
                if first_pub.get('doi'):
                    print(f"  DOI: {first_pub['doi']}")
                    
        except Exception as e:
            print(f"❌ Search error: {e}")
            logger.exception("Search failed")


async def test_specific_index():
    """Test querying a specific index directly."""
    print("\n=== Testing Direct Index Query ===")
    
    client = get_es_client()
    
    # Test a simple query directly
    try:
        response = client.search(
            index="research-publications-static",
            body={
                "query": {"match_all": {}},
                "size": 1,
                "_source": ["Title", "Year", "PublicationType"]
            }
        )
        
        total = response['hits']['total']
        if isinstance(total, dict):
            total = total['value']
            
        print(f"✅ Direct query successful")
        print(f"✅ Total documents in publications index: {total:,}")
        
        if response['hits']['hits']:
            doc = response['hits']['hits'][0]['_source']
            print(f"\nSample document:")
            print(f"  Title: {doc.get('Title', 'N/A')}")
            print(f"  Year: {doc.get('Year', 'N/A')}")
            print(f"  Type: {doc.get('PublicationType', {}).get('NameEng', 'N/A')}")
            
    except Exception as e:
        print(f"❌ Direct query error: {e}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Elasticsearch Tool Integration Test")
    print("=" * 60)
    
    # Test connection first
    if not await test_connection():
        print("\n⚠️  Cannot connect to Elasticsearch. Check your .env settings:")
        print("  - ES_HOST")
        print("  - ES_USER")
        print("  - ES_PASS")
        return
    
    # Test search functionality
    await test_search()
    
    # Test direct queries
    await test_specific_index()
    
    # Clean up
    manager = get_es_manager()
    manager.close()
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())