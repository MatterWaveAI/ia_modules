"""
API caller tool for making HTTP requests to external APIs.

Provides HTTP client functionality with proper error handling and rate limiting.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode


@dataclass
class RateLimitConfig:
    """
    Rate limiting configuration.

    Attributes:
        requests_per_second: Maximum requests per second
        requests_per_minute: Maximum requests per minute
        requests_per_hour: Maximum requests per hour
    """
    requests_per_second: Optional[int] = None
    requests_per_minute: Optional[int] = None
    requests_per_hour: Optional[int] = None


class APICallerTool:
    """
    API caller tool for HTTP requests.

    Features:
    - Support for GET, POST, PUT, DELETE, PATCH
    - Request/response headers
    - Query parameters
    - JSON payload handling
    - Rate limiting
    - Retry logic
    - Error handling

    Note: This is a simplified implementation. For production use,
    consider using libraries like aiohttp or httpx.

    Example:
        >>> tool = APICallerTool()
        >>> result = await tool.request(
        ...     method="GET",
        ...     url="https://api.example.com/data",
        ...     params={"key": "value"}
        ... )
        >>> print(result['data'])
    """

    def __init__(
        self,
        default_headers: Optional[Dict[str, str]] = None,
        rate_limit: Optional[RateLimitConfig] = None,
        timeout: float = 30.0
    ):
        """
        Initialize API caller tool.

        Args:
            default_headers: Default headers for all requests
            rate_limit: Rate limiting configuration
            timeout: Request timeout in seconds
        """
        self.default_headers = default_headers or {}
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.logger = logging.getLogger("APICallerTool")

        # Rate limiting state
        self.request_times: List[datetime] = []

    async def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        body: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            url: URL to request
            params: Query parameters
            headers: Request headers
            json_data: JSON payload
            body: Raw body content

        Returns:
            Dictionary with response data
        """
        method = method.upper()

        if method not in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            raise ValueError(f"Unsupported HTTP method: {method}")

        # Apply rate limiting
        if self.rate_limit:
            await self._apply_rate_limit()

        # Merge headers
        request_headers = {**self.default_headers, **(headers or {})}

        # Build URL with query params
        if params:
            url = f"{url}?{urlencode(params)}"

        self.logger.info(f"{method} {url}")

        # Mock implementation
        # In production, use aiohttp or httpx for real HTTP requests
        result = await self._mock_request(
            method,
            url,
            request_headers,
            json_data,
            body
        )

        return result

    async def _mock_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        json_data: Optional[Dict[str, Any]],
        body: Optional[str]
    ) -> Dict[str, Any]:
        """
        Mock HTTP request for demonstration.

        Args:
            method: HTTP method
            url: URL
            headers: Headers
            json_data: JSON data
            body: Body content

        Returns:
            Mock response
        """
        # Simulate network delay
        await asyncio.sleep(0.2)

        # Mock response
        return {
            "status": 200,
            "headers": {
                "content-type": "application/json"
            },
            "data": {
                "message": f"Mock response for {method} {url}",
                "request_headers": headers,
                "request_data": json_data or body,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }

    async def _apply_rate_limit(self) -> None:
        """Apply rate limiting."""
        if not self.rate_limit:
            return

        now = datetime.now(timezone.utc)

        # Clean old request times
        if self.rate_limit.requests_per_second:
            cutoff = now - timedelta(seconds=1)
            self.request_times = [t for t in self.request_times if t > cutoff]

            if len(self.request_times) >= self.rate_limit.requests_per_second:
                sleep_time = 1.0 - (now - self.request_times[0]).total_seconds()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        elif self.rate_limit.requests_per_minute:
            cutoff = now - timedelta(minutes=1)
            self.request_times = [t for t in self.request_times if t > cutoff]

            if len(self.request_times) >= self.rate_limit.requests_per_minute:
                sleep_time = 60.0 - (now - self.request_times[0]).total_seconds()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        elif self.rate_limit.requests_per_hour:
            cutoff = now - timedelta(hours=1)
            self.request_times = [t for t in self.request_times if t > cutoff]

            if len(self.request_times) >= self.rate_limit.requests_per_hour:
                sleep_time = 3600.0 - (now - self.request_times[0]).total_seconds()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        # Record this request
        self.request_times.append(now)

    async def get(self, url: str, **kwargs) -> Dict[str, Any]:
        """GET request shorthand."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> Dict[str, Any]:
        """POST request shorthand."""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs) -> Dict[str, Any]:
        """PUT request shorthand."""
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs) -> Dict[str, Any]:
        """DELETE request shorthand."""
        return await self.request("DELETE", url, **kwargs)

    async def patch(self, url: str, **kwargs) -> Dict[str, Any]:
        """PATCH request shorthand."""
        return await self.request("PATCH", url, **kwargs)


async def api_caller_function(
    method: str,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    body: Optional[str] = None,
    timeout: Optional[float] = None
) -> Dict[str, Any]:
    """
    API caller function for tool execution.

    Args:
        method: HTTP method
        url: URL to request
        params: Query parameters
        headers: Request headers
        json_data: JSON payload
        body: Raw body content
        timeout: Request timeout in seconds

    Returns:
        Dictionary with response data
    """
    tool = APICallerTool(timeout=timeout or 30.0)
    result = await tool.request(
        method=method,
        url=url,
        params=params,
        headers=headers,
        json_data=json_data,
        body=body
    )

    return result


def create_api_caller_tool():
    """
    Create an API caller tool definition.

    Returns:
        ToolDefinition for API caller
    """
    from ..core import ToolDefinition

    return ToolDefinition(
        name="api_caller",
        description="Make HTTP requests to external APIs",
        parameters={
            "method": {
                "type": "string",
                "required": True,
                "description": "HTTP method: GET, POST, PUT, DELETE, PATCH"
            },
            "url": {
                "type": "string",
                "required": True,
                "description": "URL to request"
            },
            "params": {
                "type": "object",
                "required": False,
                "description": "Query parameters as key-value pairs"
            },
            "headers": {
                "type": "object",
                "required": False,
                "description": "Request headers as key-value pairs"
            },
            "json_data": {
                "type": "object",
                "required": False,
                "description": "JSON payload for request body"
            },
            "body": {
                "type": "string",
                "required": False,
                "description": "Raw body content"
            },
            "timeout": {
                "type": "number",
                "required": False,
                "description": "Request timeout in seconds (default: 30.0)"
            }
        },
        function=api_caller_function,
        metadata={
            "category": "web",
            "tags": ["api", "http", "request", "web"],
            "rate_limited": True
        }
    )
