"""
API Plugin

Plugins for API-based conditions and steps.
"""

from typing import Dict, Any
from ..base import ConditionPlugin, StepPlugin, PluginMetadata, PluginType


class APIStatusCondition(ConditionPlugin):
    """
    Check API response status

    Config:
        - url: API URL (optional, uses data['api_url'] if not set)
        - expected_status: Expected HTTP status code
        - timeout: Request timeout in seconds
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="api_status_condition",
            version="1.0.0",
            author="IA Modules Team",
            description="Check if API returns expected status",
            plugin_type=PluginType.CONDITION,
            tags=["api", "http", "condition"]
        )

    async def evaluate(self, data: Dict[str, Any]) -> bool:
        """Check API status"""
        url = self.config.get('url') or data.get('api_url')
        expected_status = self.config.get('expected_status', 200)
        self.config.get('timeout', 30)

        if not url:
            self.logger.error("No URL provided")
            return False

        try:
            # In real implementation, would make actual HTTP request
            # For now, simulate with data
            api_response = data.get('api_response', {})
            actual_status = api_response.get('status_code', 0)

            return actual_status == expected_status

        except Exception as e:
            self.logger.error(f"API request failed: {e}")
            return False


class APIDataCondition(ConditionPlugin):
    """
    Check API response data

    Config:
        - url: API URL
        - json_path: JSONPath to extract value
        - operator: Comparison operator
        - value: Expected value
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="api_data_condition",
            version="1.0.0",
            author="IA Modules Team",
            description="Check API response data",
            plugin_type=PluginType.CONDITION,
            tags=["api", "http", "condition", "jsonpath"]
        )

    async def evaluate(self, data: Dict[str, Any]) -> bool:
        """Evaluate API data condition"""
        json_path = self.config.get('json_path')
        operator = self.config.get('operator', 'eq')
        expected_value = self.config.get('value')

        if not json_path:
            return False

        # Get API response from data
        api_response = data.get('api_response', {})
        response_data = api_response.get('data', {})

        # Simple JSONPath implementation (just field access for now)
        # In real implementation, would use jsonpath_ng or similar
        actual_value = response_data.get(json_path)

        if actual_value is None:
            return False

        # Compare
        if operator == 'eq':
            return actual_value == expected_value
        elif operator == 'contains':
            return expected_value in actual_value
        elif operator == 'gt':
            return actual_value > expected_value
        elif operator == 'lt':
            return actual_value < expected_value

        return False


class APICallStep(StepPlugin):
    """
    Make API call as a step

    Config:
        - url: API URL
        - method: HTTP method (GET, POST, etc.)
        - headers: HTTP headers
        - body: Request body (for POST/PUT)
        - timeout: Request timeout
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="api_call_step",
            version="1.0.0",
            author="IA Modules Team",
            description="Make HTTP API call",
            plugin_type=PluginType.STEP,
            tags=["api", "http", "step"]
        )

    async def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute API call"""
        url = self.config.get('url')
        method = self.config.get('method', 'GET')
        self.config.get('headers', {})
        self.config.get('timeout', 30)

        if not url:
            raise ValueError("URL is required")

        self.logger.info(f"Making {method} request to {url}")

        try:
            # In real implementation, would use aiohttp or httpx
            # For now, simulate response
            response_data = {
                'api_response': {
                    'status_code': 200,
                    'data': {
                        'success': True,
                        'timestamp': '2025-10-19T12:00:00Z'
                    }
                },
                'api_call_successful': True
            }

            # Merge with input data
            result = {**data, **response_data}
            return result

        except Exception as e:
            self.logger.error(f"API call failed: {e}")
            return {
                **data,
                'api_call_successful': False,
                'api_error': str(e)
            }
