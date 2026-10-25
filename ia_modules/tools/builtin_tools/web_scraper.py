"""
Web scraping tool for extracting content from websites.

Provides web scraping capabilities with text extraction, content cleaning,
and safety features for agent-based web content gathering.
"""

import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import aiohttp
from bs4 import BeautifulSoup
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ScrapedContent:
    """
    Scraped content from a web page.

    Attributes:
        url: Source URL
        title: Page title
        text_content: Extracted text content
        html_content: Raw HTML (optional)
        metadata: Additional metadata
        success: Whether scraping was successful
        error_message: Error message if scraping failed
    """
    url: str
    title: str = ""
    text_content: str = ""
    html_content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    success: bool = True
    error_message: str = ""

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class WebScraperTool:
    """
    Web scraping tool for extracting content from websites.

    Features:
    - HTML content fetching and parsing
    - Text extraction and cleaning
    - robots.txt compliance checking
    - Rate limiting and politeness delays
    - Content type detection and handling
    - Error handling and retry logic
    - Metadata extraction

    Example:
        >>> tool = WebScraperTool()
        >>> result = await tool.scrape_url("https://example.com")
        >>> print(f"Title: {result.title}")
        >>> print(f"Content length: {len(result.text_content)}")
    """

    def __init__(
        self,
        user_agent: str = "ia_modules_web_scraper/1.0",
        timeout: int = 30,
        max_content_length: int = 10 * 1024 * 1024,  # 10MB
        respect_robots_txt: bool = True,
        delay_between_requests: float = 1.0,
        max_retries: int = 3
    ):
        """
        Initialize web scraper tool.

        Args:
            user_agent: User agent string for requests
            timeout: Request timeout in seconds
            max_content_length: Maximum content length to fetch
            respect_robots_txt: Whether to check robots.txt
            delay_between_requests: Delay between requests in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_content_length = max_content_length
        self.respect_robots_txt = respect_robots_txt
        self.delay_between_requests = delay_between_requests
        self.max_retries = max_retries

        self.logger = logging.getLogger("WebScraperTool")
        self._last_request_time: float = 0.0
        self._robots_cache: Dict[str, RobotFileParser] = {}

        # Create aiohttp session
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._close_session()

    async def _ensure_session(self):
        """Ensure aiohttp session is created."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": self.user_agent},
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )

    async def _close_session(self):
        """Close aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def scrape_url(
        self,
        url: str,
        extract_text: bool = True,
        include_html: bool = False,
        follow_redirects: bool = True
    ) -> ScrapedContent:
        """
        Scrape content from a single URL.

        Args:
            url: URL to scrape
            extract_text: Whether to extract clean text content
            include_html: Whether to include raw HTML in result
            follow_redirects: Whether to follow HTTP redirects

        Returns:
            ScrapedContent object with extracted data
        """
        await self._ensure_session()

        # Rate limiting
        await self._rate_limit()

        try:
            # Check robots.txt if enabled
            if self.respect_robots_txt and not await self._can_fetch(url):
                return ScrapedContent(
                    url=url,
                    success=False,
                    error_message="Blocked by robots.txt"
                )

            # Fetch content
            assert self._session is not None
            async with self._session.get(  # type: ignore[union-attr]
                url,
                allow_redirects=follow_redirects,
                max_redirects=5 if follow_redirects else 0
            ) as response:
                response.raise_for_status()

                # Check content type
                content_type = response.headers.get('content-type', '').lower()
                if not self._is_html_content(content_type):
                    return ScrapedContent(
                        url=url,
                        success=False,
                        error_message=f"Unsupported content type: {content_type}"
                    )

                # Read content with size limit
                content = await response.read()
                if len(content) > self.max_content_length:
                    return ScrapedContent(
                        url=url,
                        success=False,
                        error_message=f"Content too large: {len(content)} bytes"
                    )

                html_content = content.decode('utf-8', errors='ignore')

                # Extract data
                title = self._extract_title(html_content)
                text_content = ""
                if extract_text:
                    text_content = self._extract_text(html_content)

                # Extract metadata
                metadata = self._extract_metadata(html_content, response.headers)

                return ScrapedContent(
                    url=str(response.url),  # Use final URL after redirects
                    title=title,
                    text_content=text_content,
                    html_content=html_content if include_html else None,
                    metadata=metadata,
                    success=True
                )

        except aiohttp.ClientError as e:
            self.logger.error(f"Request failed for {url}: {e}")
            return ScrapedContent(
                url=url,
                success=False,
                error_message=f"Request failed: {str(e)}"
            )
        except Exception as e:
            self.logger.error(f"Unexpected error scraping {url}: {e}")
            return ScrapedContent(
                url=url,
                success=False,
                error_message=f"Unexpected error: {str(e)}"
            )

    async def scrape_multiple_urls(
        self,
        urls: List[str],
        extract_text: bool = True,
        include_html: bool = False,
        max_concurrent: int = 3
    ) -> List[ScrapedContent]:
        """
        Scrape multiple URLs concurrently with rate limiting.

        Args:
            urls: List of URLs to scrape
            extract_text: Whether to extract clean text content
            include_html: Whether to include raw HTML in result
            max_concurrent: Maximum concurrent requests

        Returns:
            List of ScrapedContent objects
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def scrape_with_semaphore(url: str) -> ScrapedContent:
            async with semaphore:
                return await self.scrape_url(url, extract_text, include_html)

        # Scrape all URLs concurrently
        tasks = [scrape_with_semaphore(url) for url in urls]
        gather_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions that occurred
        processed_results: List[ScrapedContent] = []
        for i, result in enumerate(gather_results):
            if isinstance(result, BaseException):
                processed_results.append(ScrapedContent(
                    url=urls[i],
                    success=False,
                    error_message=f"Exception: {str(result)}"
                ))
            else:
                processed_results.append(result)  # type: ignore[arg-type]

        return processed_results

    async def _can_fetch(self, url: str) -> bool:
        """
        Check if we can fetch the URL according to robots.txt.

        Args:
            url: URL to check

        Returns:
            True if allowed to fetch, False otherwise
        """
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

            # Check cache first
            if robots_url not in self._robots_cache:
                rp = RobotFileParser()
                rp.set_url(robots_url)
                try:
                    rp.read()
                    self._robots_cache[robots_url] = rp
                except Exception as e:
                    self.logger.warning(f"Could not read robots.txt for {robots_url}: {e}")
                    # If we can't read robots.txt, assume we're allowed
                    return True

            rp = self._robots_cache[robots_url]
            return rp.can_fetch(self.user_agent, url)

        except Exception as e:
            self.logger.warning(f"Error checking robots.txt for {url}: {e}")
            return True  # Default to allowing if we can't check

    async def _rate_limit(self):
        """Apply rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self.delay_between_requests:
            delay = self.delay_between_requests - time_since_last
            await asyncio.sleep(delay)

        self._last_request_time = time.time()

    def _is_html_content(self, content_type: str) -> bool:
        """Check if content type indicates HTML."""
        return 'text/html' in content_type or 'application/xhtml' in content_type

    def _extract_title(self, html: str) -> str:
        """Extract page title from HTML."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            title_tag = soup.find('title')
            return title_tag.get_text().strip() if title_tag else ""
        except Exception as e:
            self.logger.warning(f"Error extracting title: {e}")
            return ""

    def _extract_text(self, html: str) -> str:
        """Extract clean text content from HTML."""
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)

            return text
        except Exception as e:
            self.logger.warning(f"Error extracting text: {e}")
            return ""

    def _extract_metadata(self, html: str, headers: Dict[str, str]) -> Dict[str, Any]:
        """Extract metadata from HTML and headers."""
        metadata = {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "content_type": headers.get('content-type', ''),
            "content_length": headers.get('content-length', ''),
        }

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Extract meta tags
            meta_tags = soup.find_all('meta')
            for tag in meta_tags:
                name = tag.get('name') or tag.get('property')
                content = tag.get('content')
                if name and content:
                    metadata[f"meta_{name}"] = content

            # Extract Open Graph tags
            og_tags = soup.find_all('meta', property=re.compile(r'^og:'))
            for tag in og_tags:
                prop = tag.get('property', '').replace('og:', 'og_')
                content = tag.get('content')
                if prop and content:
                    metadata[prop] = content

        except Exception as e:
            self.logger.warning(f"Error extracting metadata: {e}")

        return metadata


# Tool function for integration with tool system
async def web_scraper_function(
    url: str,
    extract_text: bool = True,
    include_html: bool = False,
    follow_redirects: bool = True
) -> Dict[str, Any]:
    """
    Web scraper function for tool execution.

    Args:
        url: URL to scrape
        extract_text: Whether to extract clean text content
        include_html: Whether to include raw HTML in result
        follow_redirects: Whether to follow HTTP redirects

    Returns:
        Dictionary with scraped content
    """
    async with WebScraperTool() as scraper:
        result = await scraper.scrape_url(url, extract_text, include_html, follow_redirects)

    return {
        "url": result.url,
        "title": result.title,
        "text_content": result.text_content,
        "html_content": result.html_content,
        "metadata": result.metadata,
        "success": result.success,
        "error_message": result.error_message,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


async def web_scraper_batch_function(
    urls: List[str],
    extract_text: bool = True,
    include_html: bool = False,
    max_concurrent: int = 3
) -> Dict[str, Any]:
    """
    Batch web scraper function for multiple URLs.

    Args:
        urls: List of URLs to scrape
        extract_text: Whether to extract clean text content
        include_html: Whether to include raw HTML in result
        max_concurrent: Maximum concurrent requests

    Returns:
        Dictionary with batch scraping results
    """
    async with WebScraperTool() as scraper:
        results = await scraper.scrape_multiple_urls(urls, extract_text, include_html, max_concurrent)

    return {
        "results": [
            {
                "url": r.url,
                "title": r.title,
                "text_content": r.text_content,
                "html_content": r.html_content,
                "metadata": r.metadata,
                "success": r.success,
                "error_message": r.error_message,
            }
            for r in results
        ],
        "total_urls": len(urls),
        "successful_scrapes": sum(1 for r in results if r.success),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def create_web_scraper_tool():
    """
    Create a web scraper tool definition.

    Returns:
        ToolDefinition for web scraping
    """
    from ..core import ToolDefinition

    return ToolDefinition(
        name="web_scraper",
        description="Scrape content from websites and extract text",
        parameters={
            "url": {
                "type": "string",
                "required": True,
                "description": "URL to scrape"
            },
            "extract_text": {
                "type": "boolean",
                "required": False,
                "description": "Whether to extract clean text content (default: true)"
            },
            "include_html": {
                "type": "boolean",
                "required": False,
                "description": "Whether to include raw HTML in result (default: false)"
            },
            "follow_redirects": {
                "type": "boolean",
                "required": False,
                "description": "Whether to follow HTTP redirects (default: true)"
            }
        },
        function=web_scraper_function,
        metadata={
            "category": "web",
            "tags": ["scraping", "web", "content", "extraction"],
            "requires_approval": False,  # Could be True for production safety
            "security_level": "medium"
        }
    )


def create_web_scraper_batch_tool():
    """
    Create a batch web scraper tool definition.

    Returns:
        ToolDefinition for batch web scraping
    """
    from ..core import ToolDefinition

    return ToolDefinition(
        name="web_scraper_batch",
        description="Scrape content from multiple websites concurrently",
        parameters={
            "urls": {
                "type": "array",
                "required": True,
                "description": "List of URLs to scrape",
                "items": {"type": "string"}
            },
            "extract_text": {
                "type": "boolean",
                "required": False,
                "description": "Whether to extract clean text content (default: true)"
            },
            "include_html": {
                "type": "boolean",
                "required": False,
                "description": "Whether to include raw HTML in result (default: false)"
            },
            "max_concurrent": {
                "type": "integer",
                "required": False,
                "description": "Maximum concurrent requests (default: 3)"
            }
        },
        function=web_scraper_batch_function,
        metadata={
            "category": "web",
            "tags": ["scraping", "web", "batch", "content", "extraction"],
            "requires_approval": True,  # Batch operations need approval
            "security_level": "medium"
        }
    )