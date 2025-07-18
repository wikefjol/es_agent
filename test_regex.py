#!/usr/bin/env python3
"""Test regex pattern for author extraction."""

import re

query = "How many papers has Erik kristnansson published?"

# Test the pattern
pattern = r'(?:how\s+many\s+papers?\s+has\s+)?(\w+(?:\s+\w+)*?)\s+(?:has|have)\s+(?:published|written)\b'
matches = re.findall(pattern, query, re.IGNORECASE)
print(f"Query: {query}")
print(f"Pattern: {pattern}")
print(f"Matches: {matches}")

# Let's try a more specific pattern
pattern2 = r'papers?\s+has\s+(\w+(?:\s+\w+)*?)\s+(?:published|written)'
matches2 = re.findall(pattern2, query, re.IGNORECASE)
print(f"\nPattern2: {pattern2}")
print(f"Matches2: {matches2}")

# Even simpler - look for words between "has" and "published"
pattern3 = r'has\s+(\w+(?:\s+\w+)*?)\s+published'
matches3 = re.findall(pattern3, query, re.IGNORECASE)
print(f"\nPattern3: {pattern3}")
print(f"Matches3: {matches3}")