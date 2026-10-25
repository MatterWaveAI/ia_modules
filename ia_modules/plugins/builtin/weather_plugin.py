"""
Weather Plugin

Condition plugin for weather-based routing.
"""

from typing import Dict, Any
from ..base import ConditionPlugin, PluginMetadata, PluginType
from ..decorators import condition_plugin, function_plugin


@condition_plugin(
    name="weather_condition",
    version="1.0.0",
    description="Route based on weather conditions",
    tags=["weather", "external-api", "condition"],
    auto_register=False  # We'll register manually for better control
)
class WeatherCondition(ConditionPlugin):
    """
    Check weather conditions

    Config:
        - condition: Type of condition ('sunny', 'rainy', 'temperature_above', etc.)
        - threshold: Numeric threshold for temperature checks
        - location: Location to check (optional, uses data['location'] if not set)
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="weather_condition",
            version="1.0.0",
            author="IA Modules Team",
            description="Route based on weather conditions",
            plugin_type=PluginType.CONDITION,
            tags=["weather", "external-api", "condition"]
        )

    async def evaluate(self, data: Dict[str, Any]) -> bool:
        """
        Evaluate weather condition

        Args:
            data: Must contain 'weather' key with weather data

        Returns:
            True if condition met
        """
        condition_type = self.config.get('condition', 'sunny')
        threshold = self.config.get('threshold')

        # Get weather data from input
        weather = data.get('weather', {})

        if condition_type == 'sunny':
            return weather.get('condition', '').lower() == 'sunny'

        elif condition_type == 'rainy':
            return weather.get('condition', '').lower() in ['rain', 'rainy', 'drizzle']

        elif condition_type == 'temperature_above':
            if threshold is None:
                return False
            return weather.get('temperature', 0) > threshold

        elif condition_type == 'temperature_below':
            if threshold is None:
                return False
            return weather.get('temperature', 100) < threshold

        elif condition_type == 'humidity_above':
            if threshold is None:
                return False
            return weather.get('humidity', 0) > threshold

        else:
            self.logger.warning(f"Unknown weather condition type: {condition_type}")
            return False


@function_plugin(
    name="is_good_weather",
    description="Check if weather is good for outdoor activities",
    plugin_type=PluginType.CONDITION
)
async def is_good_weather(data: Dict[str, Any]) -> bool:
    """Check if weather is good"""
    weather = data.get('weather', {})

    temperature = weather.get('temperature', 0)
    condition = weather.get('condition', '').lower()

    # Good weather: 15-25°C and not rainy
    return (
        15 <= temperature <= 25 and
        condition not in ['rain', 'rainy', 'storm', 'snow']
    )
