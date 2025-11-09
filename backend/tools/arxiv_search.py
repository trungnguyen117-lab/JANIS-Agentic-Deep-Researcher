"""arXiv search tool for finding academic papers.

Inspired by AgentLaboratory's ArxivSearch class with improvements:
- Query processing (truncates long queries)
- Retry logic with exponential backoff
- Better error handling
- Async implementation to avoid blocking I/O
"""

import urllib.parse
import xml.etree.ElementTree as ET
import asyncio
from typing import Dict, Any

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    # Fallback to sync if aiohttp not available
    import urllib.request
    import time


def _process_query(query: str, max_length: int = 300) -> str:
    """Process query string to fit within max_length while preserving as much information as possible.
    
    Inspired by AgentLaboratory's query processing.
    
    Args:
        query: Original query string
        max_length: Maximum query length (default: 300)
    
    Returns:
        Processed query string truncated if necessary
    """
    if len(query) <= max_length:
        return query
    
    # Split into words and add while staying under limit
    words = query.split()
    processed_query = []
    current_length = 0
    
    for word in words:
        # +1 for the space that will be added between words
        if current_length + len(word) + 1 <= max_length:
            processed_query.append(word)
            current_length += len(word) + 1
        else:
            break
    
    return ' '.join(processed_query)


async def _arxiv_search_async(
    query: str,
    max_results: int = 5,
) -> Dict[str, Any]:
    """Async implementation of arXiv search to avoid blocking I/O."""
    
    # Process query to handle long queries (arXiv has limits)
    processed_query = _process_query(query)
    
    # arXiv API base URL
    base_url = "http://export.arxiv.org/api/query"
    
    # Build query parameters
    params = {
        "search_query": processed_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending"
    }
    
    # Encode URL parameters
    encoded_params = urllib.parse.urlencode(params)
    url = f"{base_url}?{encoded_params}"
    
    # Retry logic inspired by AgentLaboratory
    max_retries = 3
    retry_count = 0
    
    async with aiohttp.ClientSession() as session:
        while retry_count < max_retries:
            try:
                # Make async request to arXiv API
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    xml_data = await response.read()
                
                # Parse XML response
                root = ET.fromstring(xml_data)
                
                # Define namespaces
                namespaces = {
                    'atom': 'http://www.w3.org/2005/Atom',
                    'opensearch': 'http://a9.com/-/spec/opensearch/1.1/',
                    'arxiv': 'http://arxiv.org/schemas/atom'
                }
                
                # Extract entries
                entries = root.findall('atom:entry', namespaces)
                
                results = []
                for entry in entries:
                    # Extract title
                    title_elem = entry.find('atom:title', namespaces)
                    title = title_elem.text.strip() if title_elem is not None and title_elem.text else "No title"
                    
                    # Extract abstract (summary)
                    summary_elem = entry.find('atom:summary', namespaces)
                    abstract = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else "No abstract"
                    
                    # Extract DOI
                    doi_elem = entry.find('arxiv:doi', namespaces)
                    doi = doi_elem.text if doi_elem is not None and doi_elem.text else None
                    
                    # Extract arXiv ID and URL
                    id_elem = entry.find('atom:id', namespaces)
                    arxiv_id = None
                    arxiv_url = None
                    if id_elem is not None and id_elem.text:
                        arxiv_url = id_elem.text
                        # Extract arXiv ID from URL (e.g., http://arxiv.org/abs/1234.5678 -> 1234.5678)
                        if '/abs/' in arxiv_url:
                            arxiv_id = arxiv_url.split('/abs/')[-1]
                    
                    # Extract authors
                    authors = []
                    for author in entry.findall('atom:author', namespaces):
                        name_elem = author.find('atom:name', namespaces)
                        if name_elem is not None and name_elem.text:
                            authors.append(name_elem.text)
                    
                    # Extract published date
                    published_elem = entry.find('atom:published', namespaces)
                    published = published_elem.text if published_elem is not None and published_elem.text else None
                    
                    # Extract categories
                    categories = []
                    for category in entry.findall('arxiv:primary_category', namespaces):
                        if category.get('term'):
                            categories.append(category.get('term'))
                    
                    # Extract PDF link
                    pdf_url = None
                    for link in entry.findall('atom:link', namespaces):
                        if link.get('type') == 'application/pdf':
                            pdf_url = link.get('href')
                            break
                    
                    # Build result dictionary
                    paper_info = {
                        "title": title,
                        "abstract": abstract,
                        "doi": doi,
                        "arxiv_id": arxiv_id,
                        "arxiv_url": arxiv_url,
                        "pdf_url": pdf_url,
                        "authors": authors,
                        "published": published,
                        "categories": categories,
                        "url": arxiv_url or pdf_url  # For compatibility
                    }
                    results.append(paper_info)
                
                # Rate limiting: be respectful to arXiv API (async sleep)
                await asyncio.sleep(2.0)
                
                # Return successful results
                return {
                    "results": results,
                    "query": processed_query,
                    "response_time": None
                }
            
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    # Exponential backoff: wait longer between retries (async sleep)
                    await asyncio.sleep(2 * retry_count)
                    continue
                else:
                    # Final attempt failed
                    return {
                        "error": f"Failed after {max_retries} attempts: {str(e)}",
                        "results": [],
                        "query": processed_query
                    }


def arxiv_search_sync(
    query: str,
    max_results: int = 5,
) -> Dict[str, Any]:
    """Synchronous fallback implementation (for when aiohttp is not available)."""
    # Process query to handle long queries (arXiv has limits)
    processed_query = _process_query(query)
    
    # arXiv API base URL
    base_url = "http://export.arxiv.org/api/query"
    
    # Build query parameters
    params = {
        "search_query": processed_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending"
    }
    
    # Encode URL parameters
    encoded_params = urllib.parse.urlencode(params)
    url = f"{base_url}?{encoded_params}"
    
    # Retry logic inspired by AgentLaboratory
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Make request to arXiv API
            with urllib.request.urlopen(url, timeout=30) as response:
                xml_data = response.read()
            
            # Parse XML response
            root = ET.fromstring(xml_data)
            
            # Define namespaces
            namespaces = {
                'atom': 'http://www.w3.org/2005/Atom',
                'opensearch': 'http://a9.com/-/spec/opensearch/1.1/',
                'arxiv': 'http://arxiv.org/schemas/atom'
            }
            
            # Extract entries
            entries = root.findall('atom:entry', namespaces)
            
            results = []
            for entry in entries:
                # Extract title
                title_elem = entry.find('atom:title', namespaces)
                title = title_elem.text.strip() if title_elem is not None and title_elem.text else "No title"
                
                # Extract abstract (summary)
                summary_elem = entry.find('atom:summary', namespaces)
                abstract = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else "No abstract"
                
                # Extract DOI
                doi_elem = entry.find('arxiv:doi', namespaces)
                doi = doi_elem.text if doi_elem is not None and doi_elem.text else None
                
                # Extract arXiv ID and URL
                id_elem = entry.find('atom:id', namespaces)
                arxiv_id = None
                arxiv_url = None
                if id_elem is not None and id_elem.text:
                    arxiv_url = id_elem.text
                    # Extract arXiv ID from URL (e.g., http://arxiv.org/abs/1234.5678 -> 1234.5678)
                    if '/abs/' in arxiv_url:
                        arxiv_id = arxiv_url.split('/abs/')[-1]
                
                # Extract authors
                authors = []
                for author in entry.findall('atom:author', namespaces):
                    name_elem = author.find('atom:name', namespaces)
                    if name_elem is not None and name_elem.text:
                        authors.append(name_elem.text)
                
                # Extract published date
                published_elem = entry.find('atom:published', namespaces)
                published = published_elem.text if published_elem is not None and published_elem.text else None
                
                # Extract categories
                categories = []
                for category in entry.findall('arxiv:primary_category', namespaces):
                    if category.get('term'):
                        categories.append(category.get('term'))
                
                # Extract PDF link
                pdf_url = None
                for link in entry.findall('atom:link', namespaces):
                    if link.get('type') == 'application/pdf':
                        pdf_url = link.get('href')
                        break
                
                # Build result dictionary
                paper_info = {
                    "title": title,
                    "abstract": abstract,
                    "doi": doi,
                    "arxiv_id": arxiv_id,
                    "arxiv_url": arxiv_url,
                    "pdf_url": pdf_url,
                    "authors": authors,
                    "published": published,
                    "categories": categories,
                    "url": arxiv_url or pdf_url  # For compatibility
                }
                results.append(paper_info)
            
            # Rate limiting: be respectful to arXiv API
            time.sleep(2.0)
            
            # Return successful results
            return {
                "results": results,
                "query": processed_query,
                "response_time": None
            }
        
        except Exception as e:
            retry_count += 1
            if retry_count < max_retries:
                # Exponential backoff: wait longer between retries
                time.sleep(2 * retry_count)
                continue
            else:
                # Final attempt failed
                return {
                    "error": f"Failed after {max_retries} attempts: {str(e)}",
                    "results": [],
                    "query": processed_query
                }


def arxiv_search(
    query: str,
    max_results: int = 5,
) -> Dict[str, Any]:
    """Search arXiv for academic papers and return results with title, DOI, abstract, authors, and links.
    
    This tool searches the arXiv preprint repository for academic papers matching the query.
    It returns structured information about each paper including title, abstract, authors,
    publication date, arXiv ID, and links to the paper.
    
    Inspired by AgentLaboratory's ArxivSearch with retry logic and query processing.
    Uses async I/O when aiohttp is available to avoid blocking the event loop.
    
    Args:
        query: Search query string. Can use arXiv search syntax:
               - "all:machine learning" - search all fields
               - "ti:neural networks" - search title only
               - "au:Einstein" - search by author
               - "cat:cs.AI" - search by category
               - "abs:transformer" - search abstract only
               - Combine with AND/OR: "ti:transformer AND cat:cs.AI"
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        Dictionary with:
        - results: List of paper dictionaries with title, abstract, doi, arxiv_id, 
                   arxiv_url, pdf_url, authors, published
        - query: The search query used (may be truncated)
        - response_time: None (not tracked)
    """
    # Use async implementation if aiohttp is available, otherwise fallback to sync
    if HAS_AIOHTTP:
        # Run async function in event loop
        try:
            # Try to get the current event loop
            try:
                loop = asyncio.get_running_loop()
                # If we're in an async context, we need to run in executor
                # This shouldn't happen for LangChain tools, but handle it just in case
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _arxiv_search_async(query, max_results))
                    return future.result()
            except RuntimeError:
                # No running loop, we can create one
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        # Loop is closed, create a new one
                        return asyncio.run(_arxiv_search_async(query, max_results))
                    else:
                        # Use existing loop
                        return loop.run_until_complete(_arxiv_search_async(query, max_results))
                except RuntimeError:
                    # No event loop at all, create one
                    return asyncio.run(_arxiv_search_async(query, max_results))
        except Exception:
            # If async fails for any reason, fallback to sync
            return arxiv_search_sync(query, max_results)
    else:
        # Fallback to sync implementation
        return arxiv_search_sync(query, max_results)

