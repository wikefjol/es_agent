"""Query parser for extracting intent and entities from user queries."""

import re
from typing import Dict, List, Optional, Tuple
from enum import Enum


class QueryIntent(Enum):
    """Types of query intents."""
    COUNT = "count"  # How many papers...
    LIST = "list"  # Show me papers...
    SEARCH = "search"  # Find publications about...
    ANALYZE = "analyze"  # What are the trends...
    AUTHOR_SEARCH = "author_search"  # Papers by specific author
    TOPIC_SEARCH = "topic_search"  # Papers about specific topic
    UNKNOWN = "unknown"


class QueryParser:
    """Parse user queries to extract intent and entities."""
    
    def __init__(self):
        # Patterns for different query types
        self.count_patterns = [
            r'\b(how many|count|number of|total)\b.*\b(papers?|publications?|articles?)\b',
            r'\b(papers?|publications?|articles?)\s+(has|have)\s+.+\s+(published|written)\b',
        ]
        
        self.author_patterns = [
            r'\b(?:by|from|authored by|written by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:published|written|authored)\b',
            r'\b(?:papers?|publications?|articles?)\s+(?:by|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:has|have)\s+(?:published|written)\b',
        ]
        
        self.topic_patterns = [
            r'\b(?:about|on|regarding|concerning)\s+(.+?)(?:\s*\?|$)',
            r'\b(?:related to|in the field of|in the area of)\s+(.+?)(?:\s*\?|$)',
        ]
        
    def parse(self, query: str) -> Dict[str, any]:
        """Parse a query to extract intent and entities.
        
        Args:
            query: User query string
            
        Returns:
            Dictionary with parsed information
        """
        query_lower = query.lower()
        query_original = query
        
        result = {
            "original_query": query,
            "intent": QueryIntent.UNKNOWN,
            "entities": {
                "authors": [],
                "topics": [],
                "years": [],
                "keywords": []
            },
            "confidence": 0.0
        }
        
        # Detect intent
        intent, confidence = self._detect_intent(query_lower, query_original)
        result["intent"] = intent
        result["confidence"] = confidence
        
        # Extract entities based on intent
        if intent in [QueryIntent.COUNT, QueryIntent.AUTHOR_SEARCH]:
            authors = self._extract_authors(query_original)
            result["entities"]["authors"] = authors
            
        if intent == QueryIntent.TOPIC_SEARCH:
            topics = self._extract_topics(query_lower)
            result["entities"]["topics"] = topics
            
        # Extract years
        years = self._extract_years(query)
        result["entities"]["years"] = years
        
        # Extract general keywords if no specific entities found
        if not any([result["entities"]["authors"], result["entities"]["topics"]]):
            keywords = self._extract_keywords(query_lower)
            result["entities"]["keywords"] = keywords
            
        return result
    
    def _detect_intent(self, query_lower: str, query_original: str) -> Tuple[QueryIntent, float]:
        """Detect the intent of the query."""
        
        # Check for count queries
        for pattern in self.count_patterns:
            if re.search(pattern, query_lower):
                # If it mentions an author, it's author search with count
                if self._extract_authors(query_original):
                    return QueryIntent.COUNT, 0.9
                return QueryIntent.COUNT, 0.8
                
        # Check for author queries
        if self._extract_authors(query_original):
            return QueryIntent.AUTHOR_SEARCH, 0.85
            
        # Check for topic queries
        topic_keywords = ['about', 'regarding', 'concerning', 'related to']
        if any(keyword in query_lower for keyword in topic_keywords):
            return QueryIntent.TOPIC_SEARCH, 0.8
            
        # Check for general search queries
        search_keywords = ['find', 'search', 'show', 'get', 'list']
        if any(keyword in query_lower for keyword in search_keywords):
            return QueryIntent.SEARCH, 0.7
            
        # Default to search if it mentions publications
        if any(word in query_lower for word in ['paper', 'publication', 'article', 'research']):
            return QueryIntent.SEARCH, 0.6
            
        return QueryIntent.UNKNOWN, 0.3
    
    def _extract_authors(self, query: str) -> List[str]:
        """Extract author names from query."""
        authors = []
        
        # First, try to find names with common patterns
        for pattern in self.author_patterns:
            matches = re.findall(pattern, query)
            authors.extend(matches)
            
        # Also try case-insensitive patterns for "has published" queries
        if "published" in query.lower() or "written" in query.lower():
            # Pattern for "X has published" where X might not be capitalized
            # Look for names between "has" and "published/written"
            pattern = r'has\s+(\w+(?:\s+\w+)*?)\s+(?:published|written)'
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                # Skip if it's a common word
                if match.lower() not in ['how', 'many', 'papers', 'who', 'what', 'the', 'a', 'an']:
                    # Capitalize the name properly
                    name_parts = match.split()
                    capitalized_name = ' '.join(word.capitalize() for word in name_parts)
                    authors.append(capitalized_name)
            
        # Also look for capitalized words that could be names
        # This is a simple heuristic - names are usually capitalized
        words = query.split()
        potential_names = []
        
        for i, word in enumerate(words):
            # Skip common words
            if word.lower() in ['how', 'many', 'papers', 'has', 'published', 'written', 'by', 'from']:
                continue
                
            # Check if it's capitalized (potential name)
            if word[0].isupper() and len(word) > 2:
                # Check if next word is also capitalized (last name)
                if i + 1 < len(words) and words[i + 1][0].isupper():
                    potential_names.append(f"{word} {words[i + 1]}")
                elif i > 0 and words[i - 1][0].isupper() and words[i - 1] not in potential_names:
                    # This might be a last name, include the previous word
                    continue  # Already handled above
                    
        authors.extend(potential_names)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_authors = []
        for author in authors:
            if author not in seen:
                seen.add(author)
                unique_authors.append(author)
                
        return unique_authors
    
    def _extract_topics(self, query_lower: str) -> List[str]:
        """Extract topic keywords from query."""
        topics = []
        
        for pattern in self.topic_patterns:
            matches = re.findall(pattern, query_lower)
            topics.extend(matches)
            
        # Clean up topics
        cleaned_topics = []
        for topic in topics:
            # Remove common words at the end
            topic = re.sub(r'\s+(papers?|publications?|articles?|research)$', '', topic)
            topic = topic.strip()
            if topic and len(topic) > 2:
                cleaned_topics.append(topic)
                
        return cleaned_topics
    
    def _extract_years(self, query: str) -> List[int]:
        """Extract year references from query."""
        # Look for 4-digit years between 1900 and 2100
        year_pattern = r'\b(19\d{2}|20\d{2})\b'
        matches = re.findall(year_pattern, query)
        return [int(year) for year in matches]
    
    def _extract_keywords(self, query_lower: str) -> List[str]:
        """Extract general keywords from query."""
        # Remove common words and extract meaningful keywords
        stop_words = {
            'find', 'search', 'show', 'get', 'list', 'how', 'many', 'what', 'where', 'when',
            'papers', 'publications', 'articles', 'research', 'has', 'have', 'published',
            'written', 'by', 'from', 'about', 'the', 'a', 'an', 'and', 'or', 'in', 'on',
            'me', 'i', 'want', 'need', 'looking', 'for', 'is', 'are', 'was', 'were'
        }
        
        words = query_lower.split()
        keywords = []
        
        for word in words:
            # Remove punctuation
            word = re.sub(r'[^\w\s]', '', word)
            if word and word not in stop_words and len(word) > 2:
                keywords.append(word)
                
        return keywords