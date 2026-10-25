"""
Time Plugin

Time-based condition plugins.
"""

from typing import Dict, Any
from datetime import datetime
from ..base import ConditionPlugin, PluginMetadata, PluginType


class BusinessHoursCondition(ConditionPlugin):
    """
    Check if current time is within business hours

    Config:
        - start_hour: Start hour (0-23)
        - end_hour: End hour (0-23)
        - timezone: Timezone (optional)
        - weekdays_only: Only weekdays (default: True)
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="business_hours",
            version="1.0.0",
            author="IA Modules Team",
            description="Check if within business hours",
            plugin_type=PluginType.CONDITION,
            tags=["time", "business-hours", "condition"]
        )

    async def evaluate(self, data: Dict[str, Any]) -> bool:
        """Check if within business hours"""
        start_hour = self.config.get('start_hour', 9)
        end_hour = self.config.get('end_hour', 17)
        weekdays_only = self.config.get('weekdays_only', True)

        # Get current time (or from data for testing)
        if 'current_time' in data:
            current_time = datetime.fromisoformat(data['current_time']) if isinstance(data['current_time'], str) else data['current_time']
        else:
            current_time = datetime.now()

        # Check weekday
        if weekdays_only and current_time.weekday() >= 5:  # Saturday=5, Sunday=6
            return False

        # Check hour
        current_hour = current_time.hour
        return start_hour <= current_hour < end_hour


class TimeRangeCondition(ConditionPlugin):
    """
    Check if time is within a specific range

    Config:
        - start_time: Start time (HH:MM format)
        - end_time: End time (HH:MM format)
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="time_range",
            version="1.0.0",
            author="IA Modules Team",
            description="Check if within time range",
            plugin_type=PluginType.CONDITION,
            tags=["time", "condition"]
        )

    async def evaluate(self, data: Dict[str, Any]) -> bool:
        """Check if within time range"""
        start_time_str = self.config.get('start_time')
        end_time_str = self.config.get('end_time')

        if not start_time_str or not end_time_str:
            return False

        # Parse times
        try:
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.strptime(end_time_str, '%H:%M').time()
        except ValueError:
            self.logger.error("Invalid time format, use HH:MM")
            return False

        # Get current time
        if 'current_time' in data:
            current_time = datetime.fromisoformat(data['current_time']) if isinstance(data['current_time'], str) else data['current_time']
            current_time = current_time.time()
        else:
            current_time = datetime.now().time()

        # Handle overnight ranges
        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:
            return current_time >= start_time or current_time <= end_time


class DayOfWeekCondition(ConditionPlugin):
    """
    Check if specific day of week

    Config:
        - days: List of days (0=Monday, 6=Sunday) or names
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="day_of_week",
            version="1.0.0",
            author="IA Modules Team",
            description="Check if specific day of week",
            plugin_type=PluginType.CONDITION,
            tags=["time", "day", "condition"]
        )

    async def evaluate(self, data: Dict[str, Any]) -> bool:
        """Check day of week"""
        days = self.config.get('days', [])

        if not days:
            return False

        # Get current day
        if 'current_time' in data:
            current_time = datetime.fromisoformat(data['current_time']) if isinstance(data['current_time'], str) else data['current_time']
        else:
            current_time = datetime.now()

        current_day = current_time.weekday()

        # Convert day names to numbers
        day_names = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }

        normalized_days = []
        for day in days:
            if isinstance(day, str):
                day_lower = day.lower()
                if day_lower in day_names:
                    normalized_days.append(day_names[day_lower])
            elif isinstance(day, int) and 0 <= day <= 6:
                normalized_days.append(day)

        return current_day in normalized_days
