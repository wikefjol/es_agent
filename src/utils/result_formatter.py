"""Result formatter for presenting search results using LLM."""

import json
from typing import List, Dict, Any
from langchain_core.messages import HumanMessage

from .llm_factory import LLMFactory


class ResultFormatter:
    """Formats search results into user-friendly presentations."""
    
    def __init__(self):
        self.llm = None
    
    def _get_llm(self):
        """Get or create LLM instance."""
        if self.llm is None:
            self.llm = LLMFactory.create_result_formatter_llm()
        return self.llm
    
    async def format_search_results(self, query: str, sources: List[Dict[str, Any]], execution_plan: Dict[str, Any] = None) -> str:
        """Format search results into a natural language presentation."""
        
        if not sources:
            return "I couldn't find any publications matching your search criteria."
        
        # Extract key information from sources
        publications = []
        for source in sources:
            if source.get("type") == "search_result":
                pubs_data = source.get("publications", [])
                # Handle nested structure from Elasticsearch
                if isinstance(pubs_data, dict) and "publications" in pubs_data:
                    publications.extend(pubs_data["publications"])
                elif isinstance(pubs_data, list):
                    publications.extend(pubs_data)
                else:
                    # Handle single publication case
                    publications.append(pubs_data)
        
        if not publications:
            return "I found some results, but couldn't extract publication details."
        
        # Create a prompt for formatting
        prompt = self._create_formatting_prompt(query, publications, execution_plan)
        
        try:
            llm = self._get_llm()
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            return response.content
        except Exception as e:
            print(f"LLM formatting failed, using fallback: {e}")
            return self._fallback_format(query, publications)
    
    def _create_formatting_prompt(self, query: str, publications: List[Dict[str, Any]], execution_plan: Dict[str, Any] = None) -> str:
        """Create a prompt for formatting search results."""
        
        # Limit to top 10 results for formatting
        top_publications = publications[:10]
        
        # Create formatted publication list
        pub_list = []
        for i, pub in enumerate(top_publications, 1):
            pub_info = {
                "title": pub.get("title", "Unknown Title"),
                "authors": pub.get("authors", []),
                "year": pub.get("year", "Unknown Year"),
                "abstract": pub.get("abstract", "")[:200] + "..." if pub.get("abstract", "") else "No abstract available",
                "publication_type": pub.get("publication_type", "Unknown Type"),
                "doi": pub.get("doi", ""),
                "url": pub.get("url", "")
            }
            pub_list.append(f"{i}. {json.dumps(pub_info, indent=2)}")
        
        publications_text = "\n\n".join(pub_list)
        
        total_found = len(publications)
        showing_count = len(top_publications)
        
        prompt = f"""You are presenting academic research results to a user. Your task is to format these search results into a natural, informative response.

User's Query: "{query}"

Search Results: Found {total_found} publications (showing top {showing_count})

{publications_text}

Please format these results into a natural language response that:
1. Starts with a brief summary of what was found
2. Presents each publication in a clear, readable format
3. Highlights key information like title, authors, year, and publication type
4. Includes brief abstracts when available
5. Groups or categorizes results if there are clear themes
6. Ends with a helpful note about the search

Format should be conversational and informative, not just a list. Use markdown formatting for better readability.
"""
        
        return prompt
    
    def _fallback_format(self, query: str, publications: List[Dict[str, Any]]) -> str:
        """Fallback formatting when LLM fails."""
        
        total_found = len(publications)
        showing_count = min(5, total_found)  # Show fewer in fallback
        
        result = f"I found {total_found} publications related to '{query}'. Here are the top {showing_count} results:\n\n"
        
        for i, pub in enumerate(publications[:showing_count], 1):
            title = pub.get("title", "Unknown Title")
            authors = pub.get("authors", [])
            year = pub.get("year", "Unknown Year")
            pub_type = pub.get("publication_type", "Unknown Type")
            
            # Handle authors - extract names from dict if needed
            author_names = []
            for author in authors[:3]:
                if isinstance(author, dict):
                    author_names.append(author.get("name", "Unknown Author"))
                else:
                    author_names.append(str(author))
            
            author_str = ", ".join(author_names) if author_names else "Unknown Authors"
            if len(authors) > 3:
                author_str += f" and {len(authors) - 3} others"
            
            result += f"**{i}. {title}**\n"
            result += f"   Authors: {author_str}\n"
            result += f"   Year: {year} | Type: {pub_type}\n\n"
        
        if total_found > showing_count:
            result += f"... and {total_found - showing_count} more results.\n"
        
        return result