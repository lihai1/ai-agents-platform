"""Unit tests for web search tool"""
import pytest
import asyncio
import json
import http.server
import threading
from internal.tools.web_search import WebSearchTool


@pytest.fixture
def mock_search_server(monkeypatch):
    """Local HTTP server returning a DuckDuckGo-style search response."""

    class MockHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = {
                "Abstract": "Mock search abstract",
                "Heading": "Mock heading",
                "AbstractURL": "http://example.com/abstract",
                "RelatedTopics": [
                    {"Text": "Result 1 - mock one", "FirstURL": "http://example.com/1"},
                    {"Text": "Result 2 - mock two", "FirstURL": "http://example.com/2"},
                    {"Text": "Result 3 - mock three", "FirstURL": "http://example.com/3"},
                ],
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))

        def log_message(self, format, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), MockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/"
    monkeypatch.setenv("SEC_API_API_KEY", url)
    yield url
    server.shutdown()
    thread.join(timeout=2)


@pytest.mark.asyncio
async def test_web_search_tool_search(mock_search_server):
    """Test web search with a simple query"""
    tool = WebSearchTool()
    result = await tool.search("Python programming", max_results=3)
    
    assert result["success"] is True
    assert result["query"] == "Python programming"
    assert "results" in result
    assert isinstance(result["results"], list)
    assert len(result["results"]) <= 3


@pytest.mark.asyncio
async def test_web_search_tool_fetch_url():
    """Test fetching content from a known URL"""
    tool = WebSearchTool()
    
    # Use a known reliable URL for testing
    test_url = "https://example.com"
    result = await tool.search_url(test_url)
    
    assert result["success"] is True
    assert result["url"] == test_url
    assert "content" in result
    assert len(result["content"]) > 0
    assert "content_type" in result


@pytest.mark.asyncio
async def test_web_search_tool_fetch_invalid_url():
    """Test fetching from an invalid URL"""
    tool = WebSearchTool()
    
    # Use an invalid URL
    test_url = "https://this-url-does-not-exist-12345.com"
    result = await tool.search_url(test_url)
    
    assert result["success"] is False
    assert result["url"] == test_url
    assert "error" in result


@pytest.mark.asyncio
async def test_web_search_tool_empty_query():
    """Test web search with empty query"""
    tool = WebSearchTool()
    result = await tool.search("", max_results=5)
    
    # Empty query should still return a result structure
    assert "success" in result
    assert "query" in result
    assert result["query"] == ""


@pytest.mark.asyncio
async def test_web_search_tool_max_results(mock_search_server):
    """Test that max_results parameter works correctly"""
    tool = WebSearchTool()
    result = await tool.search("test", max_results=2)
    
    assert result["success"] is True
    assert len(result["results"]) <= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
