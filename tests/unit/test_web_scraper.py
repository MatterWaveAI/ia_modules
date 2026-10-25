"""
Unit tests for web scraper tool.

Tests WebScraperTool functionality including content extraction,
safety features, and error handling.
"""

import pytest

pytest.importorskip("aiohttp", reason="aiohttp not installed — web_scraper pending refactor")

from unittest.mock import Mock, patch, AsyncMock
import aiohttp
from ia_modules.tools.builtin_tools.web_scraper import (
    WebScraperTool,
    ScrapedContent,
    create_web_scraper_tool,
    create_web_scraper_batch_tool
)


class TestWebScraperTool:
    """Test WebScraperTool class."""

    @pytest.fixture
    def scraper(self):
        """Create a WebScraperTool instance."""
        return WebScraperTool(
            user_agent="TestBot/1.0",
            timeout=10,
            max_content_length=100000,
            respect_robots_txt=False,  # Disable for testing
            delay_between_requests=0  # No delay for testing
        )

    @pytest.fixture
    def sample_html(self):
        """Sample HTML content for testing."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Page</title>
            <meta name="description" content="Test description">
            <meta property="og:title" content="Open Graph Title">
        </head>
        <body>
            <h1>Main Heading</h1>
            <p>This is a paragraph of text.</p>
            <script>console.log('script');</script>
            <style>body { color: red; }</style>
            <p>Another paragraph.</p>
        </body>
        </html>
        """

    def test_scraper_initialization(self):
        """Test WebScraperTool initialization."""
        scraper = WebScraperTool(
            user_agent="CustomBot/1.0",
            timeout=30,
            max_content_length=500000,
            respect_robots_txt=True,
            delay_between_requests=2.0
        )

        assert scraper.user_agent == "CustomBot/1.0"
        assert scraper.timeout == 30
        assert scraper.max_content_length == 500000
        assert scraper.respect_robots_txt is True
        assert scraper.delay_between_requests == 2.0

    @pytest.mark.asyncio
    async def test_extract_title(self, scraper, sample_html):
        """Test title extraction from HTML."""
        title = scraper._extract_title(sample_html)
        assert title == "Test Page"

    @pytest.mark.asyncio
    async def test_extract_text(self, scraper, sample_html):
        """Test text extraction from HTML."""
        text = scraper._extract_text(sample_html)

        # Should contain the text content
        assert "Main Heading" in text
        assert "This is a paragraph of text" in text
        assert "Another paragraph" in text

        # Should not contain script or style content
        assert "console.log" not in text
        assert "color: red" not in text

    @pytest.mark.asyncio
    async def test_extract_metadata(self, scraper, sample_html):
        """Test metadata extraction from HTML."""
        headers = {"content-type": "text/html", "content-length": "500"}
        metadata = scraper._extract_metadata(sample_html, headers)

        assert metadata["content_type"] == "text/html"
        assert metadata["content_length"] == "500"
        assert "meta_description" in metadata
        assert metadata["meta_description"] == "Test description"
        assert "og_title" in metadata
        assert metadata["og_title"] == "Open Graph Title"

    def test_is_html_content(self, scraper):
        """Test HTML content type detection."""
        assert scraper._is_html_content("text/html") is True
        assert scraper._is_html_content("application/xhtml+xml") is True
        assert scraper._is_html_content("text/plain") is False
        assert scraper._is_html_content("application/json") is False

    @pytest.mark.asyncio
    async def test_rate_limiting(self, scraper):
        """Test rate limiting functionality."""

        # First call should set the timestamp
        await scraper._rate_limit()
        first_time = scraper._last_request_time

        # Second call should wait if delay is set
        scraper.delay_between_requests = 0.1
        await scraper._rate_limit()
        second_time = scraper._last_request_time

        # Should have waited at least the delay amount
        assert second_time >= first_time + scraper.delay_between_requests

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_scrape_url_success(self, mock_get, scraper, sample_html):
        """Test successful URL scraping."""
        # Mock the response
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.read = AsyncMock(return_value=sample_html.encode('utf-8'))
        mock_response.url = "https://example.com"
        mock_response.headers = {"content-type": "text/html"}

        mock_get.return_value.__aenter__.return_value = mock_response
        mock_get.return_value.__aexit__.return_value = None

        result = await scraper.scrape_url("https://example.com")

        assert result.success is True
        assert result.url == "https://example.com"
        assert result.title == "Test Page"
        assert "Main Heading" in result.text_content
        assert result.html_content is None  # Not requested

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_scrape_url_with_html(self, mock_get, scraper, sample_html):
        """Test URL scraping with HTML inclusion."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.read = AsyncMock(return_value=sample_html.encode('utf-8'))
        mock_response.url = "https://example.com"
        mock_response.headers = {"content-type": "text/html"}

        mock_get.return_value.__aenter__.return_value = mock_response
        mock_get.return_value.__aexit__.return_value = None

        result = await scraper.scrape_url(
            "https://example.com",
            extract_text=True,
            include_html=True
        )

        assert result.success is True
        assert result.html_content == sample_html

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_scrape_url_non_html_content(self, mock_get, scraper):
        """Test scraping non-HTML content."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.read = AsyncMock(return_value=b'{"key": "value"}')
        mock_response.url = "https://api.example.com/data"
        mock_response.headers = {"content-type": "application/json"}

        mock_get.return_value.__aenter__.return_value = mock_response
        mock_get.return_value.__aexit__.return_value = None

        result = await scraper.scrape_url("https://api.example.com/data")

        assert result.success is False
        assert "Unsupported content type" in result.error_message

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_scrape_url_content_too_large(self, mock_get, scraper):
        """Test handling of content that's too large."""
        scraper.max_content_length = 100  # Very small limit

        large_content = "x" * 200  # Content larger than limit
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.read = AsyncMock(return_value=large_content.encode('utf-8'))
        mock_response.url = "https://example.com"
        mock_response.headers = {"content-type": "text/html"}

        mock_get.return_value.__aenter__.return_value = mock_response
        mock_get.return_value.__aexit__.return_value = None

        result = await scraper.scrape_url("https://example.com")

        assert result.success is False
        assert "Content too large" in result.error_message

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_scrape_url_request_error(self, mock_get, scraper):
        """Test handling of request errors."""
        mock_get.side_effect = aiohttp.ClientError("Connection failed")

        result = await scraper.scrape_url("https://example.com")

        assert result.success is False
        assert "Request failed" in result.error_message

    @pytest.mark.asyncio
    async def test_scrape_multiple_urls(self, scraper):
        """Test batch URL scraping."""
        urls = ["https://example.com", "https://example.org"]

        # Mock the individual scrape_url calls
        with patch.object(scraper, 'scrape_url') as mock_scrape:
            mock_scrape.side_effect = [
                ScrapedContent(url="https://example.com", title="Site 1", success=True),
                ScrapedContent(url="https://example.org", title="Site 2", success=True)
            ]

            results = await scraper.scrape_multiple_urls(urls)

            assert len(results) == 2
            assert results[0].url == "https://example.com"
            assert results[1].url == "https://example.org"
            assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_scrape_multiple_urls_with_errors(self, scraper):
        """Test batch scraping with some errors."""
        urls = ["https://example.com", "https://bad-url.com"]

        with patch.object(scraper, 'scrape_url') as mock_scrape:
            mock_scrape.side_effect = [
                ScrapedContent(url="https://example.com", title="Site 1", success=True),
                Exception("Network error")
            ]

            results = await scraper.scrape_multiple_urls(urls)

            assert len(results) == 2
            assert results[0].success is True
            assert results[1].success is False
            assert "Exception" in results[1].error_message


class TestScrapedContent:
    """Test ScrapedContent dataclass."""

    def test_scraped_content_creation(self):
        """Test ScrapedContent creation and defaults."""
        content = ScrapedContent(
            url="https://example.com",
            title="Test Title",
            text_content="Test content",
            success=True
        )

        assert content.url == "https://example.com"
        assert content.title == "Test Title"
        assert content.text_content == "Test content"
        assert content.success is True
        assert content.metadata == {}

    def test_scraped_content_defaults(self):
        """Test ScrapedContent default values."""
        content = ScrapedContent(url="https://example.com")

        assert content.title == ""
        assert content.text_content == ""
        assert content.html_content is None
        assert content.metadata == {}
        assert content.success is True
        assert content.error_message == ""


class TestWebScraperToolFunctions:
    """Test web scraper tool creation functions."""

    def test_create_web_scraper_tool(self):
        """Test single URL scraper tool creation."""
        tool = create_web_scraper_tool()

        assert tool.name == "web_scraper"
        assert tool.description == "Scrape content from websites and extract text"
        assert "url" in tool.parameters
        assert tool.parameters["url"]["required"] is True
        assert tool.metadata["category"] == "web"
        assert tool.metadata["requires_approval"] is False

    def test_create_web_scraper_batch_tool(self):
        """Test batch scraper tool creation."""
        tool = create_web_scraper_batch_tool()

        assert tool.name == "web_scraper_batch"
        assert tool.description == "Scrape content from multiple websites concurrently"
        assert "urls" in tool.parameters
        assert tool.parameters["urls"]["required"] is True
        assert tool.metadata["category"] == "web"
        assert tool.metadata["requires_approval"] is True  # Batch operations need approval

    @pytest.mark.asyncio
    async def test_web_scraper_function(self):
        """Test the web scraper function wrapper."""
        with patch('ia_modules.tools.builtin_tools.web_scraper.WebScraperTool') as mock_tool_class:
            mock_tool = AsyncMock()
            mock_tool_class.return_value.__aenter__.return_value = mock_tool
            mock_tool_class.return_value.__aexit__.return_value = None

            mock_tool.scrape_url.return_value = ScrapedContent(
                url="https://example.com",
                title="Test",
                text_content="Content",
                success=True
            )

            from ia_modules.tools.builtin_tools.web_scraper import web_scraper_function

            result = await web_scraper_function(
                url="https://example.com",
                extract_text=True
            )

            assert result["success"] is True
            assert result["title"] == "Test"
            mock_tool.scrape_url.assert_called_once_with(
                "https://example.com",
                True,
                False,
                True
            )

    @pytest.mark.asyncio
    async def test_web_scraper_batch_function(self):
        """Test the batch web scraper function wrapper."""
        with patch('ia_modules.tools.builtin_tools.web_scraper.WebScraperTool') as mock_tool_class:
            mock_tool = AsyncMock()
            mock_tool_class.return_value.__aenter__.return_value = mock_tool
            mock_tool_class.return_value.__aexit__.return_value = None

            mock_tool.scrape_multiple_urls.return_value = [
                ScrapedContent(url="https://example.com", success=True),
                ScrapedContent(url="https://example.org", success=True)
            ]

            from ia_modules.tools.builtin_tools.web_scraper import web_scraper_batch_function

            result = await web_scraper_batch_function(
                urls=["https://example.com", "https://example.org"],
                extract_text=True
            )

            assert result["total_urls"] == 2
            assert result["successful_scrapes"] == 2
            assert len(result["results"]) == 2
            mock_tool.scrape_multiple_urls.assert_called_once_with(
                ["https://example.com", "https://example.org"],
                True,
                False,
                3
            )