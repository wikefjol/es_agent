#!/usr/bin/env python
"""Debug script testing different auth methods."""

import os
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()

print("=== Testing Different Auth Methods ===")
print()

es_host = os.getenv("ES_HOST")
es_user = os.getenv("ES_USER") 
es_pass = os.getenv("ES_PASS")

print(f"Host: {es_host}")
print(f"User: {es_user}")
print(f"Pass: {'*' * len(es_pass) if es_pass else 'NOT SET'}")
print()

# Test 1: http_auth (older style)
print("Test 1: Using http_auth (ES 6.x style)...")
try:
    es = Elasticsearch(
        es_host,
        http_auth=(es_user, es_pass),
        verify_certs=True,
        request_timeout=30
    )
    
    info = es.info()
    print(f"✅ SUCCESS with http_auth! ES version: {info['version']['number']}")
    es.close()
except Exception as e:
    print(f"❌ FAILED: {type(e).__name__}: {e}")

print()

# Test 2: http_auth with hosts list
print("Test 2: Using http_auth with hosts list...")
try:
    es = Elasticsearch(
        hosts=[es_host],
        http_auth=(es_user, es_pass),
        verify_certs=True,
        request_timeout=30
    )
    
    info = es.info()
    print(f"✅ SUCCESS with http_auth + hosts! ES version: {info['version']['number']}")
    es.close()
except Exception as e:
    print(f"❌ FAILED: {type(e).__name__}: {e}")

print()

# Test 3: Embedding auth in URL
print("Test 3: Embedding auth in URL...")
try:
    # Parse the URL and embed credentials
    if es_host.startswith('https://'):
        auth_url = f"https://{es_user}:{es_pass}@{es_host[8:]}"
    else:
        auth_url = f"http://{es_user}:{es_pass}@{es_host[7:]}"
    
    print(f"   URL: {auth_url[:20]}...{auth_url[-20:]}")  # Show partial URL
    
    es = Elasticsearch(
        auth_url,
        verify_certs=True,
        request_timeout=30
    )
    
    info = es.info()
    print(f"✅ SUCCESS with URL auth! ES version: {info['version']['number']}")
    es.close()
except Exception as e:
    print(f"❌ FAILED: {type(e).__name__}: {e}")

print()

# Test 4: Check ES package version
print("Test 4: Checking elasticsearch-py version...")
try:
    import elasticsearch
    print(f"   elasticsearch-py version: {elasticsearch.__version__}")
    
    # Try to detect which auth method is available
    from inspect import signature
    sig = signature(Elasticsearch.__init__)
    params = list(sig.parameters.keys())
    
    print(f"   Available auth params: ", end="")
    auth_params = [p for p in params if 'auth' in p]
    print(auth_params if auth_params else "None found")
    
except Exception as e:
    print(f"   Error checking version: {e}")

print("\n=== End Debug ===")