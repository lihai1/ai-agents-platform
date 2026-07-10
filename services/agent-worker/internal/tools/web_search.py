"""Web search tool for agents"""
import logging
import aiohttp
from typing import Dict, Any, List
import json
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


class WebSearchTool:
    """Tool for performing web searches using DuckDuckGo's HTTP API"""
    
    def __init__(self):
        self.base_url = "https://api.duckduckgo.com/"
    
    async def search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Perform a web search using DuckDuckGo's instant answer API
        
        Args:
            query: The search query
            max_results: Maximum number of results to return
            
        Returns:
            Dictionary with search results including:
            - success: Whether the search was successful
            - query: The original query
            - results: List of search result dictionaries
            - answer: Instant answer if available
            - error: Error message if search failed
        """
        try:
            params = {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 0,
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params, timeout=10) as response:
                    if response.status != 200:
                        return {
                            "success": False,
                            "query": query,
                            "error": f"HTTP error: {response.status}"
                        }
                    
                    data = await response.json()
                    
                    # Parse DuckDuckGo response
                    results = []
                    
                    # Add instant answer if available
                    if data.get("Abstract"):
                        results.append({
                            "title": data.get("Heading", query),
                            "url": data.get("AbstractURL", ""),
                            "snippet": data.get("Abstract", ""),
                            "source": "DuckDuckGo"
                        })
                    
                    # Add related topics as results
                    related_topics = data.get("RelatedTopics", [])
                    for topic in related_topics[:max_results]:
                        if isinstance(topic, dict) and "Text" in topic and "FirstURL" in topic:
                            results.append({
                                "title": topic.get("Text", "").split(" - ")[0],
                                "url": topic.get("FirstURL", ""),
                                "snippet": topic.get("Text", ""),
                                "source": "DuckDuckGo"
                            })
                    
                    return {
                        "success": True,
                        "query": query,
                        "results": results[:max_results],
                        "answer": data.get("Abstract", ""),
                        "total_results": len(results)
                    }
                    
        except aiohttp.ClientError as e:
            logger.error(f"Web search failed (network error): {e}")
            return {
                "success": False,
                "query": query,
                "error": f"Network error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return {
                "success": False,
                "query": query,
                "error": str(e)
            }
    
    async def search_url(self, url: str) -> Dict[str, Any]:
        """
        Fetch and parse content from a specific URL
        
        Args:
            url: The URL to fetch
            
        Returns:
            Dictionary with the URL content
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        return {
                            "success": False,
                            "url": url,
                            "error": f"HTTP error: {response.status}"
                        }
                    
                    content_type = response.headers.get("Content-Type", "")
                    
                    # Only process text-based content
                    if "text/html" in content_type or "text/plain" in content_type:
                        text = await response.text()
                        return {
                            "success": True,
                            "url": url,
                            "content": text,
                            "content_type": content_type
                        }
                    else:
                        return {
                            "success": False,
                            "url": url,
                            "error": f"Unsupported content type: {content_type}"
                        }
                    
        except aiohttp.ClientError as e:
            logger.error(f"URL fetch failed (network error): {e}")
            return {
                "success": False,
                "url": url,
                "error": f"Network error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"URL fetch failed: {e}")
            return {
                "success": False,
                "url": url,
                "error": str(e)
            }
    
    async def browse_page(self, url: str, wait_for_selector: str = None, timeout: int = 10000) -> Dict[str, Any]:
        """
        Open a headless browser, navigate to URL, and read the page content
        
        Args:
            url: The URL to browse
            wait_for_selector: Optional CSS selector to wait for before reading content
            timeout: Maximum time to wait for page load in milliseconds
            
        Returns:
            Dictionary with page content including:
            - success: Whether the browse was successful
            - url: The browsed URL
            - title: Page title
            - content: Page text content
            - html: Full HTML content
            - error: Error message if browse failed
        """
        try:
            async with async_playwright() as p:
                # Launch headless browser
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Navigate to URL
                await page.goto(url, timeout=timeout, wait_until="networkidle")
                
                # Wait for specific selector if provided
                if wait_for_selector:
                    await page.wait_for_selector(wait_for_selector, timeout=timeout)
                
                # Extract page information
                title = await page.title()
                content = await page.inner_text("body")
                html = await page.content()
                
                # Close browser
                await browser.close()
                
                return {
                    "success": True,
                    "url": url,
                    "title": title,
                    "content": content,
                    "html": html,
                    "content_length": len(content)
                }
                
        except Exception as e:
            logger.error(f"Headless browser failed: {e}")
            return {
                "success": False,
                "url": url,
                "error": str(e)
            }
